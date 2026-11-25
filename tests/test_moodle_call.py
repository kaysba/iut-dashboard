"""Moodle.call : quand jeter le jeton et réessayer, quand lever SESSION_EXPIRED."""
import json
import os
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources import moodle as moodle_mod  # noqa: E402
from sources.common import SourceError  # noqa: E402
from sources.moodle import Moodle  # noqa: E402
from tests.aide import avec_config  # noqa: E402


class Fake(BaseHTTPRequestHandler):
    S = None

    def log_message(self, *a):
        pass

    def do_POST(self):
        form = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        fn, tok = form["wsfunction"][0], form["wstoken"][0]
        self.S["calls"].append((fn, tok))
        out = self.S["handler"](fn, tok)
        body = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CallTest(unittest.TestCase):
    def setUp(self):
        self.S = {"calls": []}
        Fake.S = self.S
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.deleted = []
        for name, val in (("load_secret", None), ("save_secret", None)):
            p = mock.patch.object(moodle_mod, name, return_value=val)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(moodle_mod, "delete_secret", side_effect=lambda f: self.deleted.append(f))
        p.start()
        self.addCleanup(p.stop)
        self.base = f"http://127.0.0.1:{self.srv.server_port}"

    def moodle(self, login="", password=""):
        avec_config(self, MOODLE_URL=self.base, MOODLE_TOKEN="", COURS_MASQUES=[])
        m = Moodle(login=login, password=password)
        m._token = "vieux"
        return m

    def test_accessexception_ne_deconnecte_pas_et_repli_par_devoir(self):
        now = 1_800_000_000
        assigns = {"courses": [{"id": 7, "assignments": [
            {"id": 2, "cmid": 102, "name": "D2", "duedate": now + 3 * 86400, "cutoffdate": 0, "allowsubmissionsfromdate": 0}]}]}

        def handler(fn, tok):
            if fn == "core_calendar_get_action_events_by_timesort":
                return {"exception": "webservice_access_exception", "errorcode": "accessexception", "message": "refusé"}
            if fn == "core_webservice_get_site_info":
                return {"userid": 1}
            if fn == "core_enrol_get_users_courses":
                return [{"id": 7, "fullname": "R3.01", "shortname": "R301"}]
            if fn == "mod_assign_get_assignments":
                return assigns
            if fn == "mod_assign_get_submission_status":
                return {"lastattempt": {"submission": {"status": "new"}}}
            raise AssertionError(fn)
        self.S["handler"] = handler
        m = self.moodle()          # aucun mot de passe en mémoire
        with mock.patch.object(moodle_mod.time, "time", return_value=now), \
                mock.patch("sys.stderr"):
            items = m.assignments()
        self.assertEqual([i["id"] for i in items], [2])
        self.assertEqual(self.deleted, [])          # le jeton n'a pas été jeté
        self.assertEqual(sum(1 for f, _ in self.S["calls"] if f == "core_calendar_get_action_events_by_timesort"), 1)
        self.assertIn("mod_assign_get_submission_status", [f for f, _ in self.S["calls"]])

    def test_accessexception_donne_une_erreur_avec_code(self):
        self.S["handler"] = lambda fn, tok: {"exception": "x", "errorcode": "accessexception", "message": "non"}
        with self.assertRaises(SourceError) as cm:
            self.moodle().call("une_fonction")
        self.assertEqual(cm.exception.code, "accessexception")
        self.assertNotEqual(str(cm.exception), "SESSION_EXPIRED")
        self.assertEqual(len(self.S["calls"]), 1)

    def test_invalidtoken_sans_mot_de_passe(self):
        self.S["handler"] = lambda fn, tok: {"exception": "x", "errorcode": "invalidtoken", "message": "m"}
        with self.assertRaises(SourceError) as cm:
            self.moodle().call("une_fonction")
        self.assertEqual(str(cm.exception), "SESSION_EXPIRED")
        self.assertEqual(len(self.S["calls"]), 1)
        self.assertEqual(self.deleted, [moodle_mod.TOKEN_FILE])

    def test_invalidtoken_avec_mot_de_passe_reessaie_une_fois(self):
        self.S["handler"] = lambda fn, tok: ([] if tok == "neuf" else {"exception": "x", "errorcode": "invalidtoken", "message": "m"})
        m = self.moodle("u", "p")
        with mock.patch.object(Moodle, "_token_via_sso", return_value="neuf") as sso:
            self.assertEqual(m.call("une_fonction"), [])
        self.assertEqual(sso.call_count, 1)
        self.assertEqual(self.S["calls"], [("une_fonction", "vieux"), ("une_fonction", "neuf")])

    def test_invalidtoken_persistant_avec_mot_de_passe_une_seule_relance(self):
        self.S["handler"] = lambda fn, tok: {"exception": "x", "errorcode": "invalidtoken", "message": "m"}
        m = self.moodle("u", "p")
        with mock.patch.object(Moodle, "_token_via_sso", return_value="neuf"):
            with self.assertRaises(SourceError):
                m.call("une_fonction")
        self.assertEqual(len(self.S["calls"]), 2)


if __name__ == "__main__":
    unittest.main()
