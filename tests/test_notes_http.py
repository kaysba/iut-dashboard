"""Test de bout en bout de Notes contre un faux CAS + une fausse passerelle (HTTP local, vraie Session)."""
import json
import os
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sources.common import Session, SourceError  # noqa: E402
from sources.notes import Notes  # noqa: E402
from tests.aide import avec_config  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "notes_reel_anonyme.json")


class Fake(BaseHTTPRequestHandler):
    state = None   # rempli par le test : {"gateway_ok": bool, "cas_posts": int, "data": {...}}

    def log_message(self, *a):
        pass

    def _send(self, code=200, body=b"", headers=()):
        self.send_response(code)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cookies(self):
        return dict(c.strip().split("=", 1) for c in (self.headers.get("Cookie") or "").split(";") if "=" in c)

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(u.query)
        port = self.server.server_port
        notes, cas = f"http://127.0.0.1:{port}", f"http://localhost:{port}"
        st = Fake.state
        if u.path == "/services/doAuth.php":
            if "ticket" in q:
                st["gateway_ok"] = True
                return self._send(302, headers=[("Location", q["href"][0]), ("Set-Cookie", "notes_sess=1; Path=/")])
            if self._cookies().get("notes_sess") and st["gateway_ok"]:
                return self._send(302, headers=[("Location", q["href"][0])])
            service = urllib.parse.quote(f"{notes}/services/doAuth.php?href={urllib.parse.quote(q['href'][0])}", safe="")
            return self._send(302, headers=[("Location", f"{cas}/cas/login?service={service}")])
        if u.path == "/cas/login":
            service = q["service"][0]
            if self._cookies().get("TGC"):    # déjà connecté au CAS : retour direct avec un ticket
                sep = "&" if "?" in service else "?"
                return self._send(302, headers=[("Location", f"{service}{sep}ticket=ST-1")])
            form = (f'<form method="post" action="/cas/login?service={urllib.parse.quote(service, safe="")}">'
                    '<input name="username" type="text"><input name="password" type="password">'
                    '<input name="execution" type="hidden" value="e1"></form>')
            return self._send(200, form.encode(), [("Content-Type", "text/html")])
        if u.path == "/services/data.php":
            if not (self._cookies().get("notes_sess") and st["gateway_ok"]):
                return self._send(200, b'{"redirect": "/cas"}')
            name = q["q"][0]
            if name == "donnéesAuthentification":
                return self._send(200, b'{"statut": 10}')
            body = st["data"].get(name)
            return self._send(200, json.dumps(body or {"erreur": "inconnu"}).encode())
        return self._send(200, b"<html>accueil</html>", [("Content-Type", "text/html")])

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        Fake.state["cas_posts"] += 1
        service = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)["service"][0]
        if form.get("password") != ["pw"]:
            return self._send(200, b'<form action="/cas/login" method="post"><input name="password" type="password"></form>')
        sep = "&" if "?" in service else "?"
        self._send(302, headers=[("Location", f"{service}{sep}ticket=ST-1"), ("Set-Cookie", "TGC=1; Path=/")])


@unittest.skipUnless(os.path.exists(FIXTURE), "fixture réelle absente")
class HttpTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            d = json.load(f)
        Fake.state = {"gateway_ok": False, "cas_posts": 0,
                      "data": {"dataPremièreConnexion": d["dataPremiereConnexion"],
                               "relevéEtudiant": d["releveAutreSemestre"]}}
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        avec_config(self, NOTES_URL=f"http://127.0.0.1:{self.srv.server_port}")
        self.notes = Notes(Session())

    def test_connexion_puis_donnees(self):
        self.notes.login("etu", "pw")
        d = self.notes.donnees()
        self.assertEqual(len(d["releve"]["ues"]), 6)
        self.assertEqual(Fake.state["cas_posts"], 1)
        d2 = self.notes.donnees(120)
        self.assertEqual(d2["semestres"], d["semestres"])

    def test_session_expiree_reconnexion_sans_ressaisir_le_mot_de_passe(self):
        self.notes.login("etu", "pw")
        Fake.state["gateway_ok"] = False                 # la passerelle oublie la session
        self.assertEqual(len(self.notes.donnees()["releve"]["ues"]), 6)
        self.assertEqual(Fake.state["cas_posts"], 1)     # le cookie du CAS a suffi

    def test_mot_de_passe_refuse(self):
        with self.assertRaises(SourceError) as cm:
            self.notes.login("etu", "mauvais")
        self.assertIn("refusée", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
