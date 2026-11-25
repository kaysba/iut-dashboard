"""Réglages de la page (.cache/settings.json), assistant de premier lancement et page Réglages.

Rien ne touche au vrai dossier .cache/ ni au vrai config.py : chaque test travaille dans un dossier temporaire.
"""
import contextlib
import datetime as dt
import http.client
import importlib.util
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sources import ade as ade_mod, common, settings  # noqa: E402
from sources.common import SourceError  # noqa: E402
from sources.defaults import DEFAULTS  # noqa: E402
from sources.moodle import Moodle  # noqa: E402
from sources.settings import ReglageInvalide, opt  # noqa: E402
from tests.aide import avec_config  # noqa: E402

LIEN_ADE = ("https://edtweb.univ-cotedazur.fr/jsp/custom/modules/plannings/anonymous_cal.jsp?"
            "data=3eeec420bb1245aef8acSECRETSECRETSECRET0aeeb620a,1")
JETON = "SECRETSECRETSECRET"
MOT_DE_PASSE = "Mot-De-Passe-Tres-Secret-42"


def load_dashboard():
    """Même chargement que tests/test_depot.py (dashboard en mode démo, partagé entre les fichiers de tests)."""
    if "dashboard" in sys.modules:
        return sys.modules["dashboard"]
    saved_argv = sys.argv
    sys.argv = saved_argv + ["--demo"]
    try:
        spec = importlib.util.spec_from_file_location("dashboard", os.path.join(ROOT, "dashboard.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["dashboard"] = mod
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved_argv
    return mod


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DossierCache(unittest.TestCase):
    """.cache/ dans un dossier temporaire, settings.json relu depuis là."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cache_dir = os.path.join(self.tmp, ".cache")
        p = mock.patch.object(common, "CACHE_DIR", self.cache_dir)
        p.start()
        self.addCleanup(p.stop)
        avec_config(self)                       # config.py vide
        settings.charger()
        self.addCleanup(settings.charger, True)  # retour à la mémoire seule (démo) après le test

    def fichier(self):
        with open(settings.chemin(), encoding="utf-8") as f:
            return json.load(f)


# ── 1. Priorité réglages > config.py > défauts ───────────────
class PrioriteTest(DossierCache):
    def test_reglage_puis_config_puis_defaut(self):
        self.assertEqual(opt("PORT"), DEFAULTS["PORT"])
        avec_config(self, PORT=9000, MAIL_ADRESSE="ancien@etu.unice.fr")
        self.assertEqual(opt("PORT"), 9000)                                 # config.py
        self.assertEqual(opt("MAIL_ADRESSE"), "ancien@etu.unice.fr")       # valeur de départ
        settings.enregistrer({"PORT": 9100, "MAIL_ADRESSE": "page@etu.unice.fr"})
        self.assertEqual(opt("PORT"), 9100)                                 # la page passe avant
        self.assertEqual(opt("MAIL_ADRESSE"), "page@etu.unice.fr")
        self.assertEqual(opt("CACHE_MOODLE"), DEFAULTS["CACHE_MOODLE"])     # défaut
        settings.enregistrer({"PORT": None})                                # None : on revient à config.py
        self.assertEqual(opt("PORT"), 9000)
        self.assertEqual(self.fichier(), {"MAIL_ADRESSE": "page@etu.unice.fr"})

    def test_relu_au_demarrage_et_copie(self):
        settings.enregistrer({"COURS_MASQUES": ["Bibliothèque"]})
        settings.oublier()
        settings.charger()
        self.assertEqual(opt("COURS_MASQUES"), ["Bibliothèque"])
        opt("COURS_MASQUES").append("x")                                    # opt renvoie une copie
        self.assertEqual(opt("COURS_MASQUES"), ["Bibliothèque"])

    def test_fichier_illisible_ou_valeur_invalide_ignores(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(settings.chemin(), "w", encoding="utf-8") as f:
            json.dump({"PORT": 80, "THEME": "dark", "INCONNU": 1}, f)
        with contextlib.redirect_stderr(io.StringIO()):
            settings.charger()
        self.assertEqual(opt("PORT"), DEFAULTS["PORT"])
        self.assertEqual(opt("THEME"), "dark")
        with open(settings.chemin(), "w", encoding="utf-8") as f:
            f.write("{pas du json")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            settings.charger()
        self.assertIn("illisible", err.getvalue())
        self.assertEqual(opt("THEME"), "system")

    def test_option_inconnue(self):
        with self.assertRaises(KeyError):
            opt("N_EXISTE_PAS")

    @unittest.skipIf(os.name == "nt", "droits Unix")
    def test_fichier_en_600(self):
        settings.enregistrer({"THEME": "dark"})
        self.assertEqual(stat.S_IMODE(os.stat(settings.chemin()).st_mode), 0o600)


# ── 2. Validation ────────────────────────────────────────────
class ValidationTest(DossierCache):
    def refus(self, changements, morceau):
        with self.assertRaises(ReglageInvalide) as cm:
            settings.enregistrer(changements)
        self.assertIn(morceau, str(cm.exception))
        self.assertFalse(os.path.exists(settings.chemin()))                # tout ou rien

    def test_couleur_invalide(self):
        m = [{"motif": "sql", "nom": "SQL", "couleur": "rouge"}]
        self.refus({"MATIERES": m}, "#RRGGBB")
        self.refus({"COULEURS_SECOURS": ["#12345"]}, "#RRGGBB")

    def test_regex_invalide(self):
        self.refus({"MATIERES": [{"motif": "sql(", "nom": "SQL", "couleur": "#112233"}]}, "invalide")
        self.refus({"THEME": "dark", "MATIERES": [{"motif": "[", "nom": "", "couleur": "#112233"}]}, "motif")

    def test_cle_inconnue(self):
        self.refus({"UNICA_PASSWORD": "x"}, "Réglage inconnu")
        self.refus({"PRENOM": "Léa"}, "Réglage inconnu")                  # lu dans Moodle, pas un réglage
        self.refus({"MOODLE_URL": "https://evil.example"}, "Réglage inconnu")

    def test_lien_ade_hors_domaine(self):
        for url in ("https://evil.example/anonymous_cal.jsp?data=1", "http://edtweb.univ-cotedazur.fr/x",
                    "https://univ-cotedazur.fr.evil.example/x", "javascript:alert(1)"):
            self.refus({"ADE_ICAL_URL": url}, "univ-cotedazur.fr")
        settings.enregistrer({"ADE_ICAL_URL": LIEN_ADE})
        self.assertEqual(opt("ADE_ICAL_URL"), LIEN_ADE)

    def test_port_et_divers(self):
        for port in (80, 1023, 65536, "8765", True):
            self.refus({"PORT": port}, "1024")
        self.refus({"THEME": "rose"}, "THEME")
        self.refus({"MAIL_ADRESSE": "pas-une-adresse"}, "invalide")
        self.refus({"CACHE_MAILS": -1}, "CACHE_MAILS")
        settings.enregistrer({"PORT": 1024, "MATIERES": [{"motif": r"\bsql\b", "nom": "SQL", "couleur": "#aabbcc"}],
                              "COURS_MASQUES": [" Bibliothèque ", ""]})
        self.assertEqual(opt("MATIERES")[0]["couleur"], "#AABBCC")
        self.assertEqual(opt("COURS_MASQUES"), ["Bibliothèque"])

    def test_masquer_lien(self):
        m = settings.masquer_lien(LIEN_ADE)
        self.assertTrue(m.startswith("…anonymous_cal.jsp?data=3eee…"), m)
        self.assertNotIn(JETON, m)
        self.assertEqual(settings.masquer_lien(""), "")


# ── 3. Routes HTTP (dashboard en démo, vrai serveur local) ───
class RoutesTest(unittest.TestCase):
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
        avec_config(self)

    def req(self, method, path, payload=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_port, timeout=10)
        body = json.dumps(payload).encode() if payload is not None else None
        c.request(method, path, body=body, headers={"Content-Type": "application/json", **(headers or {})})
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            return r.status, json.loads(raw)
        except ValueError:
            return r.status, raw

    def test_enregistre_et_renvoie_la_page(self):
        st, d = self.req("POST", "/api/settings", {"THEME": "dark", "COURS_MASQUES": ["Biblio"]})
        self.assertEqual(st, 200, d)
        self.assertEqual(d["me"]["theme"], "dark")
        self.assertEqual(d["me"]["settings"]["coursMasques"], ["Biblio"])
        self.assertEqual(d["me"]["settings"]["origine"]["COURS_MASQUES"], "page")

    def test_validation_400(self):
        cas = [({"MATIERES": [{"motif": "a", "nom": "A", "couleur": "#zzzzzz"}]}, "#RRGGBB"),
               ({"MATIERES": [{"motif": "(", "nom": "A", "couleur": "#000000"}]}, "motif"),
               ({"INCONNUE": 1}, "Réglage inconnu"),
               ({"ADE_ICAL_URL": "https://exemple.com/ade.ics"}, "univ-cotedazur.fr"),
               ({"PORT": 22}, "1024")]
        for payload, morceau in cas:
            st, d = self.req("POST", "/api/settings", payload)
            self.assertEqual(st, 400, payload)
            self.assertIn(morceau, d["error"])
        st, d = self.req("POST", "/api/settings", [1, 2])
        self.assertEqual(st, 400)

    def test_host_origin_et_session(self):
        st, _ = self.req("POST", "/api/settings", {"THEME": "dark"}, {"Origin": "https://evil.example"})
        self.assertEqual(st, 403)
        st, _ = self.req("POST", "/api/settings", {"THEME": "dark"}, {"Host": "evil.example"})
        self.assertEqual(st, 403)
        with mock.patch.object(self.d, "DEMO_SETUP", True), mock.patch.dict(self.d.SESSION, ok=False):
            for path in ("/api/settings", "/api/settings/ade", "/api/reset", "/api/mail/disconnect"):
                st, d = self.req("POST", path, {"THEME": "dark", "confirm": True})
                self.assertEqual((st, d["code"]), (401, "login_required"), path)
        self.assertEqual(opt("THEME"), "system")

    def test_lien_ade_masque_dans_api_me(self):
        settings.enregistrer({"ADE_ICAL_URL": LIEN_ADE})
        st, raw = self.req("GET", "/api/me")
        me = raw if isinstance(raw, dict) else json.loads(raw)
        self.assertNotIn(JETON, json.dumps(me))
        self.assertTrue(me["settings"]["ade"].startswith("…anonymous_cal.jsp?data=3eee…"))
        self.assertTrue(me["sources"]["ade"])

    def test_lien_ade_demo(self):
        st, d = self.req("POST", "/api/settings/ade", {"url": LIEN_ADE})
        self.assertEqual(st, 200, d)
        self.assertGreater(d["count"], 0)
        self.assertNotIn(JETON, json.dumps(d))
        st, d = self.req("POST", "/api/settings/ade", {"url": "https://edtweb.univ-cotedazur.fr/direct/index.jsp?data=x"})
        self.assertEqual(st, 400)
        self.assertIn("consulter ADE, pas à l'exporter", d["error"])


# ── 4. Mode réel (sans démo) : connexion simulée, fichiers dans un dossier temporaire ──
class ModeReelTest(DossierCache):
    def setUp(self):
        super().setUp()
        settings.utiliser_config(None)          # pas de config.py (remis par avec_config à la fin du test)
        self.d = load_dashboard()
        for nom, val in (("DEMO", False), ("DEMO_SETUP", False)):
            p = mock.patch.object(self.d, nom, val)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.d.SESSION.update, ok=False, login="", prenom="", mail="")
        m = self.d.moodle
        for nom, fn in (("token", lambda: "jeton"), ("site", lambda: {"userid": 3, "firstname": "Léa"}),
                        ("profile_mail", lambda: "")):
            p = mock.patch.object(m, nom, fn)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(self.d.notes, "login", lambda *a: None)
        p.start()
        self.addCleanup(p.stop)

    def login(self, remember=True):
        return self.d.api_login({"login": "le123456", "password": MOT_DE_PASSE, "remember": remember})

    def tous_les_fichiers(self):
        out = ""
        for racine, _, noms in os.walk(self.tmp):
            for n in noms:
                with open(os.path.join(racine, n), encoding="utf-8", errors="replace") as f:
                    out += f.read()
        return out

    def test_assistant_puis_plus_jamais(self):
        me = self.d.api_me({})
        self.assertTrue(me["setup"])                     # rien de configuré : assistant
        self.assertNotIn("settings", me)                 # pas de réglages avant la connexion
        self.login(remember=False)
        self.d.api_logout()
        self.assertFalse(self.d.api_me({})["setup"])     # l'étape 1 a été faite : écran de connexion simple
        avec_config(self, ADE_ICAL_URL=LIEN_ADE)
        settings.oublier()
        os.remove(settings.chemin())
        self.assertFalse(self.d.api_me({})["setup"])     # ancienne installation avec config.py : pas d'assistant

    def test_prenom_et_mail_lus_dans_moodle(self):
        self.login()
        me = self.d.api_me({})
        self.assertEqual(me["prenom"], "Léa")
        self.assertEqual(me["mail"], "le123456@etu.unice.fr")          # fonction refusée : identifiant@etu.unice.fr
        self.assertEqual(me["settings"]["mailSuggestion"], "le123456@etu.unice.fr")
        self.d.api_logout()
        with mock.patch.object(self.d.moodle, "profile_mail", lambda: "lea.martin@etu.unice.fr"):
            self.login()
        self.assertEqual(self.d.api_me({})["mail"], "lea.martin@etu.unice.fr")
        settings.enregistrer({"MAIL_ADRESSE": "autre@etu.unice.fr"})
        self.assertEqual(self.d.outlook.address, "autre@etu.unice.fr")  # le réglage passe avant

    def test_mot_de_passe_jamais_dans_settings_json(self):
        self.login(remember=True)
        self.d.api_settings({"THEME": "dark", "ADE_ICAL_URL": LIEN_ADE, "MAIL_ADRESSE": "lea@etu.unice.fr"})
        data = self.fichier()
        self.assertEqual(set(data), {"THEME", "ADE_ICAL_URL", "MAIL_ADRESSE"})
        self.assertNotIn(MOT_DE_PASSE, self.tous_les_fichiers())       # ni settings.json ni aucun autre fichier
        with self.assertRaises(ReglageInvalide):
            self.d.api_settings({"password": MOT_DE_PASSE})
        self.assertNotIn(MOT_DE_PASSE, self.tous_les_fichiers())

    def test_deconnexion_garde_les_reglages_tout_effacer_les_supprime(self):
        self.login(remember=True)
        self.d.api_settings({"ADE_ICAL_URL": LIEN_ADE, "THEME": "dark"})
        self.assertTrue(os.path.exists(os.path.join(self.cache_dir, "remember.json")))
        self.d.api_logout()
        self.assertFalse(os.path.exists(os.path.join(self.cache_dir, "remember.json")))
        self.assertEqual(self.fichier()["ADE_ICAL_URL"], LIEN_ADE)     # retrouvé à la prochaine connexion
        self.assertEqual(opt("THEME"), "dark")
        self.login()
        with self.assertRaises(ReglageInvalide):
            self.d.api_reset({})                                        # confirmation obligatoire
        self.assertTrue(os.path.exists(settings.chemin()))
        self.d.api_reset({"confirm": True})
        self.assertFalse(os.path.exists(self.cache_dir))
        self.assertEqual(opt("THEME"), "system")
        self.assertFalse(self.d.api_me({})["loggedIn"])
        self.assertTrue(self.d.api_me({})["setup"])                     # tout effacé : l'assistant revient
        settings.enregistrer({"THEME": "light"})                         # .cache/ est recréé au besoin
        self.assertEqual(self.fichier(), {"THEME": "light"})


# ── 5. Faux serveur ADE ──────────────────────────────────────
def ics(jours):
    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0"]
    for i, d in enumerate(jours):
        lignes += ["BEGIN:VEVENT", f"UID:{i}", f"DTSTART:{d:%Y%m%d}T080000Z", f"DTEND:{d:%Y%m%d}T100000Z",
                   f"SUMMARY:TD R3.0{i}", "END:VEVENT"]
    return "\r\n".join(lignes + ["END:VCALENDAR"]).encode()


class FakeADE(BaseHTTPRequestHandler):
    requetes = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        FakeADE.requetes.append(self.path)
        url = urllib.parse.urlsplit(self.path)
        if url.path.endswith("direct/index.jsp"):
            body, code = b"<html><body>ADE (consultation)</body></html>", 200
        elif url.path.endswith("anonymous_cal.jsp"):
            q = dict(urllib.parse.parse_qsl(url.query))
            if not q.get("data", "").startswith("bon"):
                body, code = b"<html>Erreur</html>", 200
            else:
                lundi = dt.date.fromisoformat(q["firstDate"])
                # 3 cours dans la semaine demandée, 1 hors de la semaine (ignoré)
                body, code = ics([lundi, lundi + dt.timedelta(days=1), lundi + dt.timedelta(days=4),
                                  lundi + dt.timedelta(days=9)]), 200
        else:
            body, code = b"introuvable", 404
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FauxADETest(DossierCache):
    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeADE)
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)
        self.base = f"http://127.0.0.1:{self.srv.server_port}"
        self.ade = ade_mod.ADE()

    def lien(self, data="bonJETONPERSONNEL123"):
        return f"{self.base}/jsp/custom/modules/plannings/anonymous_cal.jsp?data={data}&firstDate=2020-01-01&lastDate=2020-01-02"

    def test_lien_ical_donne_le_nombre_de_cours(self):
        self.assertEqual(self.ade.tester(self.lien(), today=dt.date(2026, 11, 26)), 3)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(FakeADE.requetes[-1]).query))
        self.assertEqual((q["firstDate"], q["lastDate"]), ("2026-11-23", "2026-11-29"))   # lundi → dimanche

    def test_lien_de_consultation(self):
        with self.assertRaises(SourceError) as cm:
            self.ade.tester(f"{self.base}/direct/index.jsp?data=abc")
        self.assertEqual(str(cm.exception), "Ce lien sert à consulter ADE, pas à l'exporter. Utilise « Exporter l'agenda ».")

    def test_lien_sans_emploi_du_temps(self):
        for url in (self.lien("mauvais"), f"{self.base}/rien"):
            with self.assertRaises(SourceError) as cm:
                self.ade.tester(url)
            self.assertEqual(str(cm.exception), "Ce lien ne renvoie pas d'emploi du temps.")

    def test_route_enregistre_et_masque(self):
        d = load_dashboard()
        accepte = lambda _n, v: v   # noqa: E731  (127.0.0.1 au lieu du domaine univ-cotedazur.fr)
        with mock.patch.object(d, "DEMO", False), mock.patch.object(d.settings, "valider_lien_ade", accepte), \
                mock.patch.dict(settings.VALIDATEURS, {"ADE_ICAL_URL": accepte}):
            r = d.api_settings_ade({"url": self.lien()})
            self.assertIn(r["count"], (2, 3))      # 3 cours sur 7 jours, sauf si la semaine déborde du fichier
            self.assertNotIn("JETONPERSONNEL", r["ade"] + json.dumps(d.api_me({})))
            self.assertEqual(opt("ADE_ICAL_URL"), self.lien())
            self.assertEqual(self.fichier()["ADE_ICAL_URL"], self.lien())
            with self.assertRaises(SourceError) as cm:
                d.api_settings_ade({"url": self.lien("mauvais")})
            self.assertEqual(cm.exception.status, 422)
        self.assertEqual(opt("ADE_ICAL_URL"), self.lien())                 # un mauvais lien ne remplace pas le bon


# ── 6. Prénom et mail dans Moodle ────────────────────────────
class ProfilMoodleTest(unittest.TestCase):
    def test_mail_du_profil_ou_rien(self):
        avec_config(self, MOODLE_URL="https://moodle.test", MOODLE_TOKEN="t")
        m = Moodle()
        m._site = {"userid": 9}

        def ok(fn, **p):
            self.assertEqual((fn, p), ("core_user_get_users_by_field", {"field": "id", "values": [9]}))
            return [{"id": 9, "email": "lea.martin@etu.unice.fr"}]

        def refuse(fn, **p):
            raise SourceError("Moodle : Access control exception")
        with mock.patch.object(m, "call", ok):
            self.assertEqual(m.profile_mail(), "lea.martin@etu.unice.fr")
        with mock.patch.object(m, "call", refuse):
            self.assertEqual(m.profile_mail(), "")


# ── 7. Lancement pour de vrai, dans un dossier sans config.py ni .cache/ ──
class LancementTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        for dossier in ("sources", "web"):
            shutil.copytree(os.path.join(ROOT, dossier), os.path.join(self.d, dossier),
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(os.path.join(ROOT, "dashboard.py"), self.d)

    def lancer(self, *args):
        port = free_port()
        proc = subprocess.Popen([sys.executable, "dashboard.py", "--no-browser", "--port", str(port), *args],
                                cwd=self.d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)
        return proc, port

    def get(self, port, path, payload=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        if payload is None:
            c.request("GET", path)
        else:
            c.request("POST", path, body=json.dumps(payload), headers={"Content-Type": "application/json"})
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, raw

    def test_demarre_sans_config_py_et_ouvre_l_assistant(self):
        proc, port = self.lancer()
        st, raw = self.get(port, "/api/me")
        self.assertEqual(st, 200)
        me = json.loads(raw)
        self.assertTrue(me["setup"])
        self.assertFalse(me["loggedIn"])
        st, page = self.get(port, "/")
        self.assertEqual(st, 200)
        self.assertIn(b"app.js", page)
        proc.kill()
        _, err = proc.communicate()
        self.assertNotIn("Traceback", err)
        self.assertNotIn("config.py", err)               # aucun message demandant de créer config.py

    def test_demo_setup(self):
        proc, port = self.lancer("--demo", "--setup")
        me = json.loads(self.get(port, "/api/me")[1])
        self.assertTrue(me["setup"])
        st, _ = self.get(port, "/api/login", {"login": "etu", "password": "x"})
        self.assertEqual(st, 200)
        me = json.loads(self.get(port, "/api/me")[1])
        self.assertEqual((me["loggedIn"], me["prenom"], me["sources"]["ade"], me["sources"]["mail"]),
                         (True, "Camille", False, False))
        st, raw = self.get(port, "/api/settings/ade", {"url": LIEN_ADE})
        self.assertEqual(st, 200, raw)
        st, raw = self.get(port, "/api/planning")
        self.assertEqual(st, 200)
        proc.kill()
        proc.communicate()
        self.assertFalse(os.path.exists(os.path.join(self.d, ".cache", "settings.json")))   # la démo n'écrit rien


if __name__ == "__main__":
    unittest.main()
