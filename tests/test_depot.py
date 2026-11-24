"""Tests du dépôt de fichiers : faux Moodle sur 127.0.0.1 (REST + upload.php + pluginfile), et routes du dashboard en démo."""
import http.client
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sources import common, moodle as moodle_mod  # noqa: E402
from sources.common import SourceError, encode_multipart, parse_multipart  # noqa: E402
from sources.moodle import DENIED, Moodle, verifier_envoi  # noqa: E402

NOW = int(time.time())


class FakeMoodle(BaseHTTPRequestHandler):
    S = None   # état partagé, remis à zéro par chaque test

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, raw=None):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):   # pluginfile.php : fichiers déjà déposés
        name = urllib.parse.unquote(self.path.split("?")[0].rsplit("/", 1)[1])
        self._send(None, raw=self.S["site_files"].get(name, b"?"))

    def do_POST(self):
        S = self.S
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        if self.path.startswith("/webservice/upload.php"):
            fields, files = parse_multipart(body, self.headers["Content-Type"])
            S["uploads"].append((fields.get("itemid"), [(n, d) for _, n, d in files]))
            if S.get("upload_error"):
                return self._send(S["upload_error"])
            itemid = int(fields.get("itemid") or 0) or 777
            return self._send([{"filename": files[0][1], "itemid": itemid, "filearea": "draft"}])
        form = urllib.parse.parse_qs(body.decode(), keep_blank_values=True)
        fn = form["wsfunction"][0]
        S["calls"].append((fn, {k: v[0] for k, v in form.items()}))
        if fn in S["denied"]:
            return self._send({"exception": "webservice_access_exception", "errorcode": "accessexception",
                               "message": "Access control exception"})
        if fn == "core_webservice_get_site_info":
            return self._send({"userid": 1, "usermaxuploadfilesize": 5 * 1048576})
        if fn == "core_enrol_get_users_courses":
            return self._send([{"id": 7, "fullname": "R3.01", "shortname": "R301"}])
        if fn == "mod_assign_get_assignments":
            return self._send({"courses": [{"id": 7, "assignments": [S["assign"]]}]})
        if fn == "mod_assign_get_submission_status":
            return self._send(S["status"]())
        if fn == "mod_assign_save_submission":
            if not S.get("save_warnings"):
                S["status_value"] = "draft"
            return self._send(S.get("save_warnings", []))
        if fn == "mod_assign_submit_for_grading":
            S["status_value"] = "submitted"
            return self._send([])
        raise AssertionError(fn)


def cfg(file=True, maxfiles=2, size=0, types="", extra=None):
    c = [{"plugin": "file", "name": "enabled", "value": "1" if file else "0"},
         {"plugin": "file", "name": "maxfilesubmissions", "value": str(maxfiles)},
         {"plugin": "file", "name": "maxsubmissionsizebytes", "value": str(size)},
         {"plugin": "file", "name": "filetypeslist", "value": types}]
    return c + (extra or [])


class DepotBase(unittest.TestCase):
    def setUp(self):
        self.S = {"uploads": [], "calls": [], "denied": set(), "site_files": {}, "status_value": "draft",
                  "existing": [],
                  "assign": {"id": 5, "cmid": 50, "name": "TP", "duedate": NOW + 86400, "cutoffdate": 0,
                             "allowsubmissionsfromdate": 0, "submissiondrafts": 1, "requiresubmissionstatement": 0,
                             "configs": cfg()}}
        self.S["status"] = self.status
        FakeMoodle.S = self.S
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeMoodle)
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        base = f"http://127.0.0.1:{self.srv.server_port}"
        self.base = base
        self.m = Moodle(SimpleNamespace(MOODLE_URL=base, UNICA_LOGIN="", UNICA_PASSWORD="", MOODLE_TOKEN="tok",
                                        COURS_MASQUES=[]))

    def status(self):
        files = [{"filename": n, "filesize": len(self.S["site_files"].get(n, b"")),
                  "fileurl": f"{self.base}/webservice/pluginfile.php/1/{urllib.parse.quote(n)}", "timemodified": NOW}
                 for n in self.S["existing"]]
        sub = {"status": self.S["status_value"], "timemodified": NOW,
               "plugins": [{"type": "file", "fileareas": [{"area": "submission_files", "files": files}]}]}
        return {"lastattempt": {"submission": sub, "canedit": True, "locked": False}}

    def uploaded(self):
        return [(i, [n for n, _ in fs]) for i, fs in self.S["uploads"]]

    def call_names(self):
        return [c[0] for c in self.S["calls"]]


class MultipartTest(unittest.TestCase):
    def test_noms_accentues_espaces_et_binaire(self):
        binaire = bytes(range(256)) * 40 + b"\r\n--fin--\r\n"
        body, ctype = encode_multipart({"token": "t é", "itemid": 12},
                                       [("file_1", "Rapport final – été 2025 \"v2\".pdf", binaire), ("file_2", "vide.zip", b"")])
        self.assertTrue(ctype.startswith("multipart/form-data; boundary="))
        fields, files = parse_multipart(body, ctype)
        self.assertEqual(fields, {"token": "t é", "itemid": "12"})
        self.assertEqual(files[0], ("file_1", "Rapport final – été 2025 \"v2\".pdf", binaire))
        self.assertEqual(files[1], ("file_2", "vide.zip", b""))
        self.assertIn("filename=\"Rapport final – été 2025 %22v2%22.pdf\"".encode(), body)


class RegleTest(DepotBase):
    def rules(self, **cfg_args):
        self.S["assign"]["configs"] = cfg(**cfg_args)
        return self.m.depot_state(5)["depot"]

    def test_regles_lues_dans_moodle(self):
        d = self.rules(maxfiles=1, size=2 * 1048576, types=".pdf, .ZIP")
        self.assertEqual((d["fichiers"], d["texte"], d["max_fichiers"], d["taille_max"], d["types"]),
                         (True, False, 1, 2 * 1048576, [".pdf", ".zip"]))
        self.assertTrue(d["ouvert"])
        self.assertTrue(d["remise_requise"])
        self.assertEqual(d["statut"], "brouillon")

    def test_taille_zero_veut_la_limite_du_site(self):
        self.assertEqual(self.rules(size=0)["taille_max"], 5 * 1048576)

    def test_groupes_de_types_non_verifies(self):
        self.assertEqual(self.rules(types="document .pdf")["types"], [])

    def test_texte_seulement(self):
        d = self.rules(file=False, extra=[{"plugin": "onlinetext", "name": "enabled", "value": "1"}])
        self.assertEqual((d["fichiers"], d["texte"]), (False, True))

    def test_devoir_ferme(self):
        self.S["assign"]["allowsubmissionsfromdate"] = NOW + 3600
        self.assertEqual(self.m.depot_state(5)["depot"]["raison_fermeture"], "Le dépôt n'est pas encore ouvert.")
        self.S["assign"].update(allowsubmissionsfromdate=0, cutoffdate=NOW - 60)
        d = self.m.depot_state(5)["depot"]
        self.assertFalse(d["ouvert"])
        self.assertIn("date limite", d["raison_fermeture"])
        with self.assertRaises(SourceError):
            self.m.save_draft(5, [("a.pdf", b"x")])
        self.assertEqual(self.S["uploads"], [])      # rien n'est envoyé

    def test_remis_et_verrouille(self):
        self.S["status_value"] = "submitted"
        self.S["status"] = lambda: {"lastattempt": {"submission": {"status": "submitted"}, "canedit": False, "locked": True}}
        d = self.m.depot_state(5)["depot"]
        self.assertFalse(d["ouvert"])
        self.assertIn("remis", d["raison_fermeture"])

    def test_refus_taille_nombre_extension(self):
        d = self.rules(maxfiles=1, size=1000, types=".pdf")
        with self.assertRaisesRegex(SourceError, "trop gros"):
            verifier_envoi(d, [("a.pdf", 5000)], True)
        with self.assertRaisesRegex(SourceError, "Trop de fichiers"):
            verifier_envoi(d, [("a.pdf", 10), ("b.pdf", 10)], True)
        with self.assertRaisesRegex(SourceError, r"rapport\.docx n'est pas accepté : ce devoir demande un \.pdf"):
            verifier_envoi(d, [("rapport.docx", 10)], True)
        with self.assertRaisesRegex(SourceError, "limite du dashboard"):
            verifier_envoi({**d, "taille_max": 0}, [("a.pdf", 10)], True, upload_max=5)
        verifier_envoi(d, [("a.pdf", 10)], True)     # un envoi correct passe


class EnvoiTest(DepotBase):
    def test_deux_fichiers_meme_itemid(self):
        self.S["status_value"] = "new"
        etat = self.m.save_draft(5, [("Mon rapport é.pdf", b"%PDF-1"), ("code.zip", b"PK")], garder_existants=False)
        self.assertEqual(self.uploaded(), [(None, ["Mon rapport é.pdf"]), ("777", ["code.zip"])])
        save = next(c for c in self.S["calls"] if c[0] == "mod_assign_save_submission")[1]
        self.assertEqual(save["plugindata[files_filemanager]"], "777")
        self.assertIn("mod_assign_get_submission_status", self.call_names()[-1])    # état relu
        self.assertEqual(etat["depot"]["statut"], "brouillon")

    def test_fichiers_existants_recopies_avant_les_nouveaux(self):
        self.S["existing"] = ["ancien.pdf"]
        self.S["site_files"]["ancien.pdf"] = b"ANCIEN"
        self.m.save_draft(5, [("nouveau.pdf", b"NOUVEAU")], garder_existants=True)
        self.assertEqual(self.uploaded(), [(None, ["ancien.pdf"]), ("777", ["nouveau.pdf"])])
        self.assertEqual(self.S["uploads"][0][1][0][1], b"ANCIEN")      # téléchargé avec le jeton, puis renvoyé

    def test_remplacement_sans_garder(self):
        self.S["existing"] = ["ancien.pdf"]
        self.m.save_draft(5, [("nouveau.pdf", b"N")], garder_existants=False)
        self.assertEqual(self.uploaded(), [(None, ["nouveau.pdf"])])

    def test_nombre_max_avec_existants(self):
        self.S["existing"] = ["a.pdf", "b.pdf"]
        with self.assertRaisesRegex(SourceError, "Trop de fichiers"):
            self.m.save_draft(5, [("c.pdf", b"x")], garder_existants=True)
        self.assertEqual(self.S["uploads"], [])

    def test_warnings_donnent_une_erreur(self):
        self.S["save_warnings"] = [{"item": "x", "message": "Tu ne peux pas modifier ce dépôt."}]
        with self.assertRaisesRegex(SourceError, "ne peux pas modifier"):
            self.m.save_draft(5, [("a.pdf", b"x")], garder_existants=False)

    def test_remise_avec_et_sans_declaration(self):
        self.S["assign"]["requiresubmissionstatement"] = 1
        with self.assertRaisesRegex(SourceError, "déclaration"):
            self.m.submit(5, False)
        self.assertNotIn("mod_assign_submit_for_grading", self.call_names())
        etat = self.m.submit(5, True)
        sub = next(c for c in self.S["calls"] if c[0] == "mod_assign_submit_for_grading")[1]
        self.assertEqual(sub["acceptsubmissionstatement"], "1")
        self.assertEqual(etat["depot"]["statut"], "remis")       # relu depuis Moodle

    def test_remise_sans_declaration_requise(self):
        self.m.submit(5, False)
        sub = next(c for c in self.S["calls"] if c[0] == "mod_assign_submit_for_grading")[1]
        self.assertEqual(sub["acceptsubmissionstatement"], "0")

    def test_pas_de_remise_sans_brouillon(self):
        self.S["status_value"] = "new"
        with self.assertRaisesRegex(SourceError, "pas de brouillon"):
            self.m.submit(5, False)

    def test_fonction_refusee_par_le_site(self):
        self.S["denied"] = {"mod_assign_save_submission"}
        with self.assertRaises(SourceError) as cm:
            self.m.save_draft(5, [("a.pdf", b"x")], garder_existants=False)
        self.assertEqual(str(cm.exception), DENIED)
        self.assertIn("n'autorise pas le dépôt", DENIED)
        self.S["denied"] = {"mod_assign_submit_for_grading"}
        with self.assertRaises(SourceError) as cm:
            self.m.submit(5, False)
        self.assertEqual(str(cm.exception), DENIED)

    def test_upload_refuse_par_le_site(self):
        self.S["upload_error"] = {"error": "Le service n'autorise pas l'envoi de fichiers", "errorcode": "nofileupload"}
        with self.assertRaises(SourceError) as cm:
            self.m.save_draft(5, [("a.pdf", b"x")], garder_existants=False)
        self.assertEqual(str(cm.exception), DENIED)

    def test_erreur_moodle_a_l_envoi(self):
        self.S["upload_error"] = {"error": "Le fichier est trop volumineux", "errorcode": "uploadlimit"}
        with self.assertRaisesRegex(SourceError, "trop volumineux"):
            self.m.save_draft(5, [("a.pdf", b"x")], garder_existants=False)

    def test_suppression_d_un_fichier(self):
        self.S["existing"] = ["a.pdf", "b.pdf"]
        self.S["site_files"].update({"a.pdf": b"A", "b.pdf": b"B"})
        self.m.delete_file(5, "a.pdf")
        self.assertEqual(self.uploaded(), [(None, ["b.pdf"])])
        self.S["existing"] = ["b.pdf"]
        with self.assertRaisesRegex(SourceError, "vider"):
            self.m.delete_file(5, "b.pdf")

    def test_rien_n_est_ecrit_sur_le_disque(self):
        cache_dir = common.CACHE_DIR
        avant = (sorted(os.listdir(cache_dir)), sorted(os.listdir(tempfile.gettempdir())))
        ecritures = []
        reel = open

        def espion(f, mode="r", *a, **k):
            if any(c in str(mode) for c in "wax+") and not str(f).startswith("/proc"):
                ecritures.append(str(f))
            return reel(f, mode, *a, **k)
        self.S["existing"] = ["ancien.pdf"]
        self.S["site_files"]["ancien.pdf"] = b"A"
        with mock.patch("builtins.open", espion), mock.patch("os.replace", side_effect=AssertionError):
            self.m.save_draft(5, [("n.pdf", b"N" * 10000)], garder_existants=True)
            self.m.submit(5, True)
        self.assertEqual(ecritures, [])
        self.assertEqual((sorted(os.listdir(cache_dir)), sorted(os.listdir(tempfile.gettempdir()))), avant)


# ── Routes du dashboard (mode démo, vrai serveur HTTP local) ──
def load_dashboard():
    if "dashboard" in sys.modules:
        return sys.modules["dashboard"]
    spec = importlib.util.spec_from_file_location("config", os.path.join(ROOT, "config-exemple.py"))
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)
    saved_argv = sys.argv
    sys.argv = saved_argv + ["--demo"]
    sys.modules["config"] = conf
    try:
        spec = importlib.util.spec_from_file_location("dashboard", os.path.join(ROOT, "dashboard.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["dashboard"] = mod
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved_argv
    return mod


class RouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = load_dashboard()
        if not cls.d.DEMO:
            raise unittest.SkipTest("dashboard déjà importé hors démo")
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), cls.d.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.d.demo._STATE.clear()
        p = mock.patch.object(self.d.demo.time, "sleep", lambda *_: None)
        p.start()
        self.addCleanup(p.stop)

    def req(self, method, path, body=None, ctype=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_port, timeout=10)
        h = {"Content-Type": ctype} if ctype else {}
        c.request(method, path, body=body, headers={**h, **(headers or {})})
        r = c.getresponse()
        data = r.read()
        c.close()
        try:
            return r.status, json.loads(data)
        except ValueError:
            return r.status, None

    def draft(self, aid, files, **fields):
        body, ctype = encode_multipart(fields, [("fichiers", n, d) for n, d in files])
        return self.req("POST", f"/api/assignments/{aid}/draft", body, ctype)

    def submit(self, aid, payload):
        return self.req("POST", f"/api/assignments/{aid}/submit", json.dumps(payload).encode(), "application/json")

    def test_brouillon_puis_ajout_puis_remise(self):
        st, d = self.draft(0, [("a.pdf", b"%PDF-1")], garder_existants="1")
        self.assertEqual((st, d["depot"]["statut"], len(d["depot"]["fichiers_actuels"])), (200, "brouillon", 1))
        st, d = self.draft(0, [("b.zip", b"PK")], garder_existants="1")
        self.assertEqual([f["nom"] for f in d["depot"]["fichiers_actuels"]], ["a.pdf", "b.zip"])
        st, d = self.submit(0, {"declaration": False, "verifie": True})
        self.assertEqual((st, d["depot"]["statut"]), (200, "remis"))

    def test_remise_refusee_sans_verifie(self):
        self.draft(0, [("a.pdf", b"%PDF-1")])
        for payload in ({"declaration": True}, {"declaration": True, "verifie": False}, {"declaration": True, "verifie": "oui"}):
            st, d = self.submit(0, payload)
            self.assertEqual(st, 502)
            self.assertIn("Confirmation manquante", d["error"])
        self.assertEqual(self.d.demo.depot_state(0)["depot"]["statut"], "brouillon")      # rien n'a été rendu

    def test_remise_refusee_sans_declaration(self):
        st, d = self.submit(1, {"declaration": False, "verifie": True})
        self.assertIn("déclaration", d["error"])
        st, d = self.submit(1, {"declaration": True, "verifie": True})
        self.assertEqual(d["depot"]["statut"], "remis")

    def test_depot_direct_exige_la_confirmation(self):
        st, d = self.draft(2, [("rapport.pdf", b"%PDF-1")], garder_existants="0")      # remise_requise = non
        self.assertIn("Confirmation manquante", d["error"])
        st, d = self.draft(2, [("rapport.pdf", b"%PDF-1")], garder_existants="0", verifie="1")
        self.assertEqual(d["depot"]["statut"], "remis")

    def test_refus_serveur_extension_nombre_taille_ferme(self):
        self.assertIn("n'est pas accepté", self.draft(2, [("r.docx", b"x")])[1]["error"])
        self.assertIn("Trop de fichiers", self.draft(2, [("a.pdf", b"x"), ("b.pdf", b"x")])[1]["error"])
        self.assertIn("trop gros", self.draft(2, [("a.pdf", b"x" * (10 * 1048576 + 1))])[1]["error"])
        self.assertIn("date limite", self.draft(4, [("a.pdf", b"x")])[1]["error"])
        self.assertIn("pas de fichiers", self.draft(3, [("a.pdf", b"x")])[1]["error"])
        for i in (2, 4):
            self.assertEqual(self.d.demo.depot_state(i)["depot"]["fichiers_actuels"], [])

    def test_envoi_trop_gros_refuse_avant_lecture(self):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_port, timeout=10)
        c.putrequest("POST", "/api/assignments/2/draft")
        c.putheader("Content-Type", "multipart/form-data; boundary=x")
        c.putheader("Content-Length", str(500 * 1048576))     # annoncé, jamais envoyé
        c.endheaders()
        r = c.getresponse()
        self.assertIn("trop gros", json.loads(r.read())["error"])
        c.close()

    def test_origin_et_host_verifies(self):
        body, ctype = encode_multipart({}, [("f", "a.pdf", b"x")])
        st, _ = self.req("POST", "/api/assignments/0/draft", body, ctype, {"Origin": "https://evil.example"})
        self.assertEqual(st, 403)
        st, _ = self.req("POST", "/api/assignments/0/draft", body, ctype, {"Host": "evil.example"})
        self.assertEqual(st, 403)


if __name__ == "__main__":
    unittest.main()
