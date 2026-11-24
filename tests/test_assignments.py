"""Tests de Moodle.assignments() avec de fausses réponses de l'API."""
import io
import os
import sys
import time
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources import moodle as moodle_mod  # noqa: E402
from sources.common import SourceError  # noqa: E402

NOW = time.time()
DAY = 86400


def assign(i, due_days):
    return {"id": i, "cmid": 100 + i, "name": f"Devoir {i}", "duedate": int(NOW + due_days * DAY),
            "cutoffdate": 0, "allowsubmissionsfromdate": int(NOW - 30 * DAY)}


# 1 : rendu, 2 : à rendre dans 3 jours (donc vérifié), 3 : à rendre dans 20 jours,
# 4 : rendu (noté), 5 : ancien devoir ignoré
ASSIGNS = {"courses": [{"id": 7, "assignments": [
    assign(1, -5), assign(2, 3), assign(3, 20), assign(4, -10), assign(5, -100)]}]}

EVENTS = {"events": [
    {"id": 11, "modulename": "assign", "instance": 2, "action": {"actionable": True}},
    {"id": 12, "modulename": "assign", "instance": 3, "action": {"actionable": True}},
    {"id": 13, "modulename": "quiz", "instance": 9, "action": {"actionable": True}},
    {"id": 14, "modulename": "assign", "instance": 1, "action": {"actionable": False}},
], "firstid": 11, "lastid": 14}

STATUS = {
    1: {"lastattempt": {"submission": {"status": "submitted"}, "gradingstatus": "notgraded"}},
    2: {"lastattempt": {"submission": {"status": "draft"}}},
    3: {"lastattempt": {"submission": {"status": "new"}}},
    4: {"lastattempt": {"submission": {"status": "submitted"}, "gradingstatus": "graded"}},
}


class Fake:
    def __init__(self, calendar="ok", assigns=None):
        self.assigns = assigns or ASSIGNS
        self.calls = []
        self.calendar = calendar

    def __call__(self, fn, _retry=True, **params):
        self.calls.append((fn, params))
        if fn == "core_webservice_get_site_info":
            return {"userid": 1}
        if fn == "core_enrol_get_users_courses":
            return [{"id": 7, "fullname": "R3.01", "shortname": "R301"}]
        if fn == "mod_assign_get_assignments":
            return self.assigns
        if fn == "core_calendar_get_action_events_by_timesort":
            if self.calendar == "refuse":
                raise SourceError("Moodle (core_calendar_get_action_events_by_timesort) : accès refusé")
            return EVENTS
        if fn == "mod_assign_get_submission_status":
            return STATUS[params["assignid"]]
        raise AssertionError(fn)

    def count(self, *names):
        return sum(1 for fn, _ in self.calls if fn in names)

    def assign_calls(self):
        return self.count("mod_assign_get_assignments", "core_calendar_get_action_events_by_timesort",
                          "mod_assign_get_submission_status")


class AssignmentsTest(unittest.TestCase):
    def setUp(self):
        self.store = {}
        cfg = SimpleNamespace(MOODLE_URL="https://moodle.test", UNICA_LOGIN="", UNICA_PASSWORD="",
                              MOODLE_TOKEN="t", COURS_MASQUES=[])
        self.m = moodle_mod.Moodle(cfg)
        for name, fn in (("load_secret", self.store.get),
                         ("save_secret", self.store.__setitem__)):
            p = mock.patch.object(moodle_mod, name, fn)
            p.start()
            self.addCleanup(p.stop)

    def run_assignments(self, fake):
        with mock.patch.object(self.m, "call", fake):
            return {i["id"]: i for i in self.m.assignments()}

    def test_calls_and_cache(self):
        f1 = Fake()
        res = self.run_assignments(f1)
        # liste + calendrier + 1 vérification brouillon (devoir 2) + 2 inconnus (1 et 4)
        self.assertEqual(f1.count("core_calendar_get_action_events_by_timesort"), 1)
        self.assertEqual(f1.count("mod_assign_get_assignments"), 1)
        self.assertEqual(sorted(p["assignid"] for fn, p in f1.calls
                                if fn == "mod_assign_get_submission_status"), [1, 2, 4])
        f2 = Fake()
        res2 = self.run_assignments(f2)
        # 2e chargement : seul le devoir 2 (échéance < 7 j) est revérifié, les rendus viennent du cache
        self.assertEqual(sorted(p["assignid"] for fn, p in f2.calls
                                if fn == "mod_assign_get_submission_status"), [2])
        self.assertEqual({k: (v["status"], v["graded"]) for k, v in res.items()},
                         {k: (v["status"], v["graded"]) for k, v in res2.items()})

    def test_two_calls_when_nothing_to_check(self):
        """Tout est rendu (en cache) ou à rendre loin dans le temps : 2 appels exactement."""
        self.store["assign_status.json"] = {"1": {"graded": False}, "4": {"graded": True}}
        assigns = {"courses": [{"id": 7, "assignments": [assign(1, -5), assign(3, 20), assign(4, -10)]}]}
        f = Fake(assigns=assigns)
        items = list(self.run_assignments(f).values())
        self.assertEqual(f.assign_calls(), 2)
        self.assertEqual({i["id"]: i["status"] for i in items}, {1: "rendu", 3: "a_rendre", 4: "rendu"})

    def test_statuses(self):
        res = self.run_assignments(Fake())
        self.assertNotIn(5, res)
        self.assertEqual(res[1]["status"], "rendu")
        self.assertEqual(res[2]["status"], "brouillon")
        self.assertEqual(res[3]["status"], "a_rendre")  # pas vérifié : échéance dans 20 jours
        self.assertEqual(res[4]["status"], "rendu")
        self.assertTrue(res[4]["graded"])
        self.assertFalse(res[1]["graded"])
        self.assertEqual(set(res[1]), {"id", "cmid", "name", "course", "courseShort", "due", "cutoff",
                                       "opens", "url", "submitUrl", "status", "graded"})

    def test_cache_only_stores_rendu(self):
        self.run_assignments(Fake())
        self.assertEqual(set(self.store["assign_status.json"]), {"1", "4"})

    def test_fallback_when_calendar_refused(self):
        f = Fake(calendar="refuse")
        err = io.StringIO()
        with redirect_stderr(err):
            res = self.run_assignments(f)
        self.assertIn("Avertissement", err.getvalue())
        self.assertEqual({k: v["status"] for k, v in res.items()},
                         {1: "rendu", 2: "brouillon", 3: "a_rendre", 4: "rendu"})
        self.assertEqual(f.count("mod_assign_get_submission_status"), 4)
        # la fonction refusée n'est plus rappelée au chargement suivant
        f2 = Fake(calendar="refuse")
        self.run_assignments(f2)
        self.assertEqual(f2.count("core_calendar_get_action_events_by_timesort"), 0)


if __name__ == "__main__":
    unittest.main()
