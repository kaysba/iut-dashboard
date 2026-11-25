"""Tests de la source Notes : normalisation sur une réponse réelle anonymisée, reconnexion, erreurs."""
import copy
import json
import os
import sys
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sources import settings  # noqa: E402
from sources.common import SourceError  # noqa: E402
from sources.notes import Notes, _num, _releve, normaliser_releve  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "notes_reel_anonyme.json")
BASE = "https://notes.test"


def load():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


class FakeSession:
    """Fait semblant d'être la passerelle : répond selon l'URL demandée."""

    def __init__(self, answers, logged=True):
        self.answers = answers       # {nom de requête: réponse JSON}
        self.logged = logged
        self.calls = []
        self.jar = []
        self.pdf_body = b"%PDF-1.4 fake"

    def request(self, url, data=None, **kw):
        self.calls.append(url)
        if "bulletin_PDF.php" in url:
            if not self.logged:
                return 200, url, {}, b'{"redirect": "https://cas.test/login"}'
            return 200, url, {}, self.pdf_body
        if "doAuth.php" in url:
            self.logged = True
            return 200, BASE + "/", {}, b"<html></html>"
        if "q=donn%C3%A9esAuthentification" in url:
            return 200, url, {}, b'{"statut": 10}'
        if not self.logged:
            return 200, url, {}, b'{"redirect": "https://cas.test/login"}'
        for name, resp in self.answers.items():
            if name in url:
                return 200, url, {}, json.dumps(resp).encode("utf-8")
        raise AssertionError(f"requête inattendue : {url}")

    def names(self):
        return [("auth" if "doAuth" in u else "pdf" if "bulletin_PDF" in u else u.split("q=")[1].split("&")[0])
                for u in self.calls]


_ANCIENNE_CONFIG = []


def setUpModule():
    _ANCIENNE_CONFIG.append(settings.config_actuelle())
    settings.utiliser_config(SimpleNamespace(NOTES_URL=BASE))


def tearDownModule():
    settings.utiliser_config(_ANCIENNE_CONFIG.pop())


def make_notes(answers, logged=True, password="secret"):
    n = Notes(FakeSession(answers, logged))
    n._login = "etu"
    n._password = password
    return n


@unittest.skipUnless(os.path.exists(FIXTURE), "fixture réelle absente (tests/fixtures/notes_reel_anonyme.json)")
class NormalisationTest(unittest.TestCase):
    def setUp(self):
        self.data = load()
        self.rel = normaliser_releve(_releve(self.data["dataPremiereConnexion"]))

    def test_ues_sans_bonus(self):
        codes = [u["code"] for u in self.rel["ues"]]
        self.assertEqual(len(codes), 6)
        self.assertFalse(any(c.startswith("BONS") for c in codes))
        self.assertIsNone(self.rel["semestre"]["bonus"])   # le bonus du fixture est « ~ »

    def test_promo_masquee(self):
        self.assertFalse(self.rel["options"]["promo"])
        sem = self.rel["semestre"]
        self.assertEqual((sem["min"], sem["moy"], sem["max"]), (None, None, None))
        for u in self.rel["ues"]:
            self.assertEqual((u["min"], u["moy"], u["max"]), (None, None, None))
        for m in self.rel["modules"]:
            for e in m["evaluations"]:
                self.assertEqual((e["min"], e["moy"], e["max"]), (None, None, None))
        # ... alors que la réponse brute contient bien ces valeurs
        self.assertEqual(self.data["dataPremiereConnexion"]["relevé"]["semestre"]["notes"]["max"], "17.80")

    def test_promo_affichee_si_autorisee(self):
        d = copy.deepcopy(self.data["dataPremiereConnexion"])
        d["relevé"]["options"]["show_moypromo"] = True
        rel = normaliser_releve(_releve(d))
        self.assertTrue(rel["options"]["promo"])
        self.assertEqual(rel["semestre"]["moy"], 13.75)

    def test_valeurs_et_rangs(self):
        sem = self.rel["semestre"]
        self.assertEqual((sem["numero"], sem["moyenne"], sem["rang"], sem["total"]), (3, 17.4, 2, 57))
        self.assertEqual(sem["absences"], {"total": 1.0, "injustifiees": 1.0, "unite": "Heure(s)"})
        self.assertEqual((sem["ects_acquis"], sem["ects_total"]), (0.0, 30.0))
        ue = self.rel["ues"][1]
        self.assertEqual((ue["code"], ue["titre"], ue["rang"], ue["total"]), ("UE3.2", "Optimiser", 1, 57))

    def test_tilde_donne_none(self):
        ue = self.rel["ues"][0]
        self.assertIn("~", json.dumps(self.data["dataPremiereConnexion"]["relevé"]["ues"]["UE3.1"]["ressources"]))
        by_code = {m["code"]: m for m in ue["modules"]}
        self.assertIsNone(by_code["R3.02"]["moyenne"])
        self.assertEqual(by_code["R3.01"]["moyenne"], 16.25)
        for v in ("~", "", None, "ABS", "abc"):
            self.assertIsNone(_num(v))
        self.assertEqual(_num("07.50"), 7.5)

    def test_rang_masque_donne_none(self):
        d = copy.deepcopy(self.data["dataPremiereConnexion"])
        d["relevé"]["options"].update(show_rangs=False, show_ue_rangs=False, show_mod_rangs=False)
        rel = normaliser_releve(_releve(d))
        self.assertEqual((rel["semestre"]["rang"], rel["semestre"]["total"]), (None, None))
        self.assertTrue(all(u["rang"] is None and u["total"] is None for u in rel["ues"]))
        self.assertTrue(all(m["rang"] is None for m in rel["modules"]))
        self.assertFalse(rel["options"]["rangs"] or rel["options"]["rangs_ue"] or rel["options"]["rangs_modules"])

    def test_rang_absent_n_est_pas_invente(self):
        d = copy.deepcopy(self.data["dataPremiereConnexion"])
        del d["relevé"]["ues"]["UE3.1"]["moyenne"]["rang"]       # rangs autorisés, mais absents
        rel = normaliser_releve(_releve(d))
        self.assertIsNone(rel["ues"][0]["rang"])

    def test_modules_et_evaluations(self):
        self.assertEqual(len(self.rel["modules"]), 14)
        self.assertEqual(self.rel["modules"][-1]["type"], "sae")
        r301 = next(m for m in self.rel["modules"] if m["code"] == "R3.01")
        self.assertEqual(r301["type"], "ressource")
        ev = r301["evaluations"][0]
        self.assertEqual((ev["note"], ev["coef"], ev["date"]), (16.25, 0.4, "2026-11-03"))
        self.assertEqual(ev["poids"]["UE3.1"], 1)

    def test_releve_non_publie(self):
        rel = normaliser_releve({"publie": False, "options": {}}, "Pas publié, désolé.")
        self.assertFalse(rel["publie"])
        self.assertEqual(rel["message"], "Pas publié, désolé.")
        self.assertEqual(rel["ues"], [])

    def test_noms_de_semestres(self):
        n = make_notes({"dataPremi": self.data["dataPremiereConnexion"]})
        d = n.donnees()
        self.assertEqual([s["nom"] for s in d["semestres"]],
                         ["Semestre 1 (2025/2026)", "Semestre 2 (2025/2026)", "Semestre 3 (2026/2027)"])
        self.assertEqual([s["actuel"] for s in d["semestres"]], [False, False, True])
        self.assertEqual(len(d["releve"]["ues"]), 6)


class ConnexionTest(unittest.TestCase):
    PREMIERE = {"semestres": [{"formsemestre_id": 7, "semestre_id": 1, "annee_scolaire": "2025/2026"}],
                "relevé": {"publie": False}, "config": {"message_non_publication_releve": "Non publié."}}

    def test_requete_encodee_en_utf8(self):
        n = make_notes({"dataPremi": self.PREMIERE})
        n.donnees()
        self.assertIn(f"{BASE}/services/data.php?q=dataPremi%C3%A8reConnexion", n.session.calls[0])

    def test_reconnexion_sur_redirect(self):
        n = make_notes({"dataPremi": self.PREMIERE}, logged=False)
        d = n.donnees()
        self.assertEqual(n.session.names(), ["dataPremi%C3%A8reConnexion", "auth", "donn%C3%A9esAuthentification",
                                             "dataPremi%C3%A8reConnexion"])
        self.assertEqual(d["releve"]["message"], "Non publié.")

    def test_reconnexion_une_seule_fois(self):
        n = make_notes({}, logged=False)
        n.session.request = lambda url, **kw: (200, url, {}, b'{"redirect": "x"}')
        n.login = lambda *a, **k: None          # la reconnexion « réussit » mais la session reste invalide
        with self.assertRaises(SourceError):
            n.donnees()

    def test_sans_mot_de_passe(self):
        n = make_notes({}, logged=False, password="")
        with self.assertRaises(SourceError) as cm:
            n.donnees()
        self.assertEqual(str(cm.exception), "NOTES_LOGIN_REQUIRED")

    def test_passerelle_injoignable(self):
        n = make_notes({})

        def down(url, **kw):
            raise OSError("pas de réseau")
        n.session.request = down
        with self.assertRaises(SourceError) as cm:
            n.donnees()
        self.assertIn("injoignable", str(cm.exception))

    def test_erreur_de_la_passerelle(self):
        n = make_notes({"dataPremi": {"erreur": "Semestre inconnu"}})
        with self.assertRaises(SourceError) as cm:
            n.donnees()
        self.assertEqual(str(cm.exception), "Semestre inconnu")

    def test_semestre_choisi(self):
        n = make_notes({"dataPremi": self.PREMIERE, "relev%C3%A9Etudiant": {"relevé": {"publie": False}}})
        n.donnees(7)
        self.assertTrue(any("q=relev%C3%A9Etudiant&semestre=7" in u for u in n.session.calls))

    def test_pdf(self):
        n = make_notes({})
        self.assertTrue(n.pdf(189).startswith(b"%PDF"))
        self.assertIn("/services/bulletin_PDF.php?sem_id=189&type=short", n.session.calls[0])

    def test_pdf_reconnexion(self):
        n = make_notes({}, logged=False)
        self.assertTrue(n.pdf(189).startswith(b"%PDF"))
        self.assertEqual(n.session.names(), ["pdf", "auth", "donn%C3%A9esAuthentification", "pdf"])

    def test_pdf_refuse(self):
        n = make_notes({})
        n.session.pdf_body = "Relevé PDF non disponible pour ton département".encode()
        with self.assertRaises(SourceError) as cm:
            n.pdf(189)
        self.assertIn("non disponible", str(cm.exception))

    def test_oubli_efface_tout(self):
        n = make_notes({"dataPremi": self.PREMIERE})
        n.donnees()
        n.forget()
        self.assertFalse(n.has_password())
        self.assertIsNone(n._semestres)


if __name__ == "__main__":
    unittest.main()
