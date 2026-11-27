"""Simulateur de notes : la formule de web/js/features/notes/simulate.js, refaite en Python, redonne le relevé.

Sans aucune valeur simulée, le recalcul doit retrouver les moyennes du relevé (UE, générale, modules) à 0,05 près,
sur la démo et sur la fixture réelle (ignorée si absente). Si Node est installé, simulate.js lui-même est exécuté
sur les mêmes relevés et doit donner les mêmes nombres que la version Python.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sources import demo  # noqa: E402
from sources.notes import _releve, normaliser_releve  # noqa: E402

SIMULATE = os.path.join(ROOT, "web", "js", "features", "notes", "simulate.js")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "notes_reel_anonyme.json")
ECART = 0.05


# ── Même logique que simulate.js ─────────────────────────────────────────────
def note_of(e, sim):
    return sim[e["id"]] if sim and e["id"] in sim else e["note"]


def type_of(e):
    return e.get("type") or "normale"


def module_fige(m):
    return any(e.get("etat") or type_of(e) not in ("normale", "bonus") for e in m["evaluations"])


def poids(e, ue):
    if ue is None or not e.get("poids"):
        return 1
    return e["poids"].get(ue) or 0


def moyenne_module(m, sim=None, ue=None):
    num = den = bonus = 0.0
    for e in m["evaluations"]:
        n = note_of(e, sim)
        if n is None or not poids(e, ue):
            continue
        if type_of(e) == "bonus":
            bonus += n
            continue
        c = (e["coef"] or 0) * poids(e, ue)
        if not c:
            continue
        num += n * c
        den += c
    return min(20, num / den + bonus) if den else None


def moyenne_module_dans_ue(um, ue, modules, sim):
    m = modules.get(um["code"])
    if not m or module_fige(m):
        return um["moyenne"]
    return moyenne_module(m, sim, ue["code"])


def moyenne_ue(ue, modules, sim=None):
    num = den = 0.0
    for um in ue["modules"]:
        v = moyenne_module_dans_ue(um, ue, modules, sim)
        if v is None or not um["coef"]:
            continue
        num += v * um["coef"]
        den += um["coef"]
    return num / den if den else None


def moyenne_generale(r, sim=None):
    modules = {m["code"]: m for m in r["modules"]}
    ects = [u["ects_total"] for u in r["ues"]]
    par_ects = all(x is not None and x > 0 for x in ects) and len(set(ects)) > 1
    num = den = 0.0
    for u in r["ues"]:
        v = moyenne_ue(u, modules, sim)
        if v is None:
            continue
        w = u["ects_total"] if par_ects else 1
        num += v * w
        den += w
    return num / den + (r["semestre"]["bonus"] or 0) if den else None


def restantes(ue, r, sim=None):
    modules = {m["code"]: m for m in r["modules"]}
    out = []
    for um in ue["modules"]:
        m = modules.get(um["code"])
        if not m or not um["coef"] or module_fige(m):
            continue
        out += [e for e in m["evaluations"] if e["note"] is None and not (sim and e["id"] in sim) and not e.get("etat") and type_of(e) == "normale"
                and (e["coef"] or 0) * poids(e, ue["code"]) > 0]
    return out


def note_minimale(ue, r, sim=None, cible=10):
    modules = {m["code"]: m for m in r["modules"]}
    reste = restantes(ue, r, sim)
    if not reste:
        return {"statut": "aucune", "note": None, "n": 0}

    def ok(x):
        s = dict(sim or {})
        s.update({e["id"]: x for e in reste})
        return moyenne_ue(ue, modules, s) >= cible - 1e-9

    if ok(0):
        return {"statut": "acquise", "note": 0, "n": len(reste)}
    if not ok(20):
        return {"statut": "impossible", "note": None, "n": len(reste)}
    lo, hi = 0.0, 20.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    import math
    return {"statut": "note", "note": math.ceil(hi * 100 - 1e-6) / 100, "n": len(reste)}


def coef_par_defaut(m):
    c = [e["coef"] for e in m["evaluations"] if type_of(e) == "normale" and (e["coef"] or 0) > 0]
    return round(sum(c) / len(c), 2) if c else 1


def avec_ajouts(r, ajouts):
    """ajouts : {code du module: [{"id": négatif, "coef": c}]} ; poids 1 dans chaque UE où le module a un coefficient."""
    if not ajouts:
        return r
    ues = {}
    for u in r["ues"]:
        for um in u["modules"]:
            if um["coef"]:
                ues.setdefault(um["code"], {})[u["code"]] = 1
    mods = []
    for m in r["modules"]:
        if ajouts.get(m["code"]) and not module_fige(m):
            m = {**m, "evaluations": m["evaluations"] + [
                {"id": a["id"], "titre": "Note ajoutée", "type": "normale", "etat": None, "coef": a["coef"], "note": None,
                 "poids": dict(ues.get(m["code"], {}))} for a in ajouts[m["code"]]]}
        mods.append(m)
    return {**r, "modules": mods}


# ── Relevés à vérifier ───────────────────────────────────────────────────────
def releves():
    out = {f"démo S{n}": demo.notes(sid)["releve"] for sid, n, _ in demo._SEMESTRES}
    if os.path.exists(FIXTURE):
        with open(FIXTURE, encoding="utf-8") as f:
            raw = json.load(f)
        for k in ("dataPremiereConnexion", "releveAutreSemestre"):
            if k in raw:
                r = normaliser_releve(_releve(raw[k]))
                if r["publie"]:
                    out[f"réel {k}"] = r
    return out


class SourceTest(unittest.TestCase):
    """simulate.js : fonctions pures attendues, sans import (ni DOM, ni réseau)."""

    def setUp(self):
        with open(SIMULATE, encoding="utf-8") as f:
            self.src = f.read()

    def test_fonctions_exportees(self):
        for nom in ("moyenneModule", "moyenneUE", "moyenneGenerale", "noteMinimale", "verifier", "recalculer"):
            self.assertRegex(self.src, rf"export function {nom}\(", nom)

    def test_pure(self):
        self.assertNotRegex(self.src, r"(?m)^import ")
        for mot in ("document", "fetch(", "localStorage", "window"):
            self.assertNotIn(mot, self.src)

    def test_meme_tolerance(self):
        self.assertRegex(self.src, r"ECART_MAX = 0\.05;")


class FormuleTest(unittest.TestCase):
    def verifier(self, nom, r):
        modules = {m["code"]: m for m in r["modules"]}
        for u in r["ues"]:
            if u["moyenne"] is not None:
                with self.subTest(releve=nom, ue=u["code"]):
                    self.assertAlmostEqual(moyenne_ue(u, modules), u["moyenne"], delta=ECART)
        if r["semestre"]["moyenne"] is not None:
            with self.subTest(releve=nom, moyenne="générale"):
                self.assertAlmostEqual(moyenne_generale(r), r["semestre"]["moyenne"], delta=ECART)
        for m in r["modules"]:
            if m["moyenne"] is not None and not module_fige(m):
                with self.subTest(releve=nom, module=m["code"]):
                    self.assertAlmostEqual(moyenne_module(m), m["moyenne"], delta=ECART)

    def test_demo(self):
        for nom, r in releves().items():
            if nom.startswith("démo"):
                self.verifier(nom, r)

    @unittest.skipUnless(os.path.exists(FIXTURE), "fixture réelle absente (tests/fixtures/notes_reel_anonyme.json)")
    def test_fixture_reelle(self):
        reels = {n: r for n, r in releves().items() if n.startswith("réel")}
        self.assertTrue(reels)
        for nom, r in reels.items():
            self.verifier(nom, r)

    @unittest.skipUnless(os.path.exists(FIXTURE), "fixture réelle absente")
    def test_evaluation_bonus_de_la_fixture(self):
        r = next(r for n, r in releves().items() if n.startswith("réel"))
        bonus = [(m, e) for m in r["modules"] for e in m["evaluations"] if e["type"] == "bonus"]
        self.assertTrue(bonus)
        for m, e in bonus:
            self.assertIsNone(e["coef"])
            self.assertAlmostEqual(moyenne_module(m), m["moyenne"], delta=ECART)   # 17 + 3 de bonus = 20


class SimulationTest(unittest.TestCase):
    def setUp(self):
        self.r = demo.notes(189)["releve"]     # S3 de la démo : évaluations sans note dans UE3.1, 3.2 et 3.5
        self.modules = {m["code"]: m for m in self.r["modules"]}

    def ue(self, code):
        return next(u for u in self.r["ues"] if u["code"] == code)

    def test_valeur_simulee_change_module_ue_et_generale(self):
        m = self.modules["R3.08"]
        manque = next(e for e in m["evaluations"] if e["note"] is None)
        sim = {manque["id"]: 20}
        self.assertAlmostEqual(moyenne_module(m, sim), (8.5 * .5 + 20 * .5) / 1)
        self.assertGreater(moyenne_ue(self.ue("UE3.5"), self.modules, sim), self.ue("UE3.5")["moyenne"])
        self.assertGreater(moyenne_generale(self.r, sim), self.r["semestre"]["moyenne"])

    def test_et_si_sur_une_note_existante(self):
        m = self.modules["R3.10"]
        e = m["evaluations"][0]
        self.assertAlmostEqual(moyenne_module(m, {e["id"]: 15}), 15)

    def test_note_minimale(self):
        res = note_minimale(self.ue("UE3.5"), self.r, cible=10)
        self.assertEqual((res["statut"], res["n"]), ("note", 1))
        s = {e["id"]: res["note"] for e in restantes(self.ue("UE3.5"), self.r)}
        self.assertGreaterEqual(moyenne_ue(self.ue("UE3.5"), self.modules, s), 10 - 1e-9)
        s = {k: res["note"] - 0.01 for k in s}
        self.assertLess(moyenne_ue(self.ue("UE3.5"), self.modules, s), 10)
        self.assertEqual(note_minimale(self.ue("UE3.1"), self.r)["statut"], "acquise")
        self.assertEqual(note_minimale(self.ue("UE3.3"), self.r)["statut"], "aucune")
        self.assertEqual(note_minimale(self.ue("UE3.5"), self.r, cible=20)["statut"], "impossible")
        self.assertLess(note_minimale(self.ue("UE3.5"), self.r, cible=8)["note"], res["note"])

    def test_modules_figes(self):
        m = {"code": "X", "moyenne": 12.0, "evaluations": [
            {"id": 1, "type": "normale", "etat": None, "coef": 1, "note": 10, "poids": {}},
            {"id": 2, "type": "rattrapage", "etat": None, "coef": 1, "note": 14, "poids": {}}]}
        self.assertTrue(module_fige(m))
        ue = {"code": "U", "modules": [{"code": "X", "coef": 1, "moyenne": 12.0}]}
        self.assertEqual(moyenne_ue(ue, {"X": m}), 12.0)   # moyenne officielle gardée, pas de règle inventée
        m["evaluations"][1].update(type="normale", etat="ABS", note=None)
        self.assertTrue(module_fige(m))

    def test_ponderation_ects_seulement_si_elles_different(self):
        r = json.loads(json.dumps(self.r))
        base = moyenne_generale(r)
        for u in r["ues"]:
            u["ects_total"] = 3.0
        self.assertAlmostEqual(moyenne_generale(r), base)
        r["ues"][0]["ects_total"] = 30.0
        self.assertNotAlmostEqual(moyenne_generale(r), base, places=2)


class AjoutTest(unittest.TestCase):
    """« Et si j'avais eu 14 en prog système » : une note ajoutée à un module."""

    def setUp(self):
        self.r = demo.notes(189)["releve"]

    def test_quatorze_en_prog_systeme(self):
        m = next(m for m in self.r["modules"] if m["code"] == "R3.05")   # dans UE3.2 et UE3.3
        coef = coef_par_defaut(m)
        ra = avec_ajouts(self.r, {"R3.05": [{"id": -1, "coef": coef}]})
        mods = {x["code"]: x for x in ra["modules"]}
        self.assertEqual(len(self.r["modules"][2]["evaluations"]), 2)          # relevé d'origine intact
        attendu = (sum(e["note"] * e["coef"] for e in m["evaluations"]) + 14 * coef) / (sum(e["coef"] for e in m["evaluations"]) + coef)
        self.assertAlmostEqual(moyenne_module(mods["R3.05"], {-1: 14}), attendu)
        for code in ("UE3.2", "UE3.3"):
            ue = next(u for u in ra["ues"] if u["code"] == code)
            self.assertNotAlmostEqual(moyenne_ue(ue, mods, {-1: 14}), moyenne_ue(ue, mods), places=3)
        ue1 = next(u for u in ra["ues"] if u["code"] == "UE3.1")
        self.assertAlmostEqual(moyenne_ue(ue1, mods, {-1: 14}), moyenne_ue(ue1, mods))
        # sans note saisie, l'ajout ne change rien
        self.assertAlmostEqual(moyenne_generale(ra), moyenne_generale(self.r))

    def test_module_encore_vide(self):
        ra = avec_ajouts(self.r, {"R3.09": [{"id": -1, "coef": 1}]})
        ue = next(u for u in ra["ues"] if u["code"] == "UE3.3")
        mods = {x["code"]: x for x in ra["modules"]}
        self.assertEqual(note_minimale(ue, self.r)["statut"], "aucune")
        res = note_minimale(ue, ra)
        self.assertEqual(res["n"], 1)
        self.assertEqual(note_minimale(ue, ra, {-1: 12})["statut"], "aucune")   # déjà saisie : gardée telle quelle
        self.assertGreaterEqual(moyenne_ue(ue, mods, {-1: 18}), moyenne_ue(ue, mods))


class NormalisationTest(unittest.TestCase):
    """Le relevé transmet le type d'évaluation et les notes non numériques, sans les convertir."""

    def test_type_et_etat(self):
        ev = lambda i, t, v: {"id": i, "coef": "1", "evaluation_type": t, "note": {"value": v}, "poids": {"UE1.1": 1}}  # noqa: E731
        rel = {"semestre": {"notes": {"value": "12"}}, "ues": {}, "ressources": {"R1.01": {"titre": "x", "evaluations": [
            ev(1, 0, "12.50"), ev(2, 1, "14"), ev(3, 2, "9"), ev(4, 3, "1.5"), ev(5, 0, "ABS"), ev(6, 0, "~"), ev(7, None, "")]}}}
        evs = {e["id"]: e for e in normaliser_releve(rel)["modules"][0]["evaluations"]}
        self.assertEqual([evs[i]["type"] for i in range(1, 8)],
                         ["normale", "rattrapage", "session2", "bonus", "normale", "normale", "normale"])
        self.assertEqual((evs[5]["note"], evs[5]["etat"]), (None, "ABS"))
        self.assertEqual((evs[6]["note"], evs[6]["etat"]), (None, None))     # « ~ » : pas encore de note
        self.assertEqual((evs[7]["note"], evs[7]["etat"]), (None, None))
        self.assertEqual((evs[1]["note"], evs[1]["etat"]), (12.5, None))


@unittest.skipUnless(shutil.which("node"), "Node absent : simulate.js n'est pas exécuté")
class NodeTest(unittest.TestCase):
    """Exécute le vrai simulate.js et compare avec la version Python."""

    def test_js_et_python_donnent_les_memes_nombres(self):
        data = releves()
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(SIMULATE, os.path.join(d, "simulate.mjs"))
            with open(os.path.join(d, "releves.json"), "w", encoding="utf-8") as f:
                json.dump(data, f)
            script = """
import * as S from "./simulate.mjs";
import { readFileSync } from "node:fs";
const all = JSON.parse(readFileSync(new URL("./releves.json", import.meta.url)));
const out = {};
for (const [k, r] of Object.entries(all)) {
  const v = S.verifier(r);
  out[k] = { ues: v.base.ues, generale: v.base.generale, ecarts: v.ecarts.length + (v.generale ? 1 : 0),
    min: Object.fromEntries(r.ues.map((u) => [u.code, [S.noteMinimale(u, r, null, 10), S.noteMinimale(u, r, null, 8)]])) };
}
console.log(JSON.stringify(out));
"""
            script += """
const r = all["démo S3"];
const ajouts = new Map([["R3.05", [{ id: -1, coef: S.coefParDefaut(r.modules.find((m) => m.code === "R3.05")) }]], ["R3.09", [{ id: -2, coef: 1 }]]]);
const ra = S.avecAjouts(r, ajouts);
const c = S.recalculer(ra, new Map([[-1, 14], [-2, 9]]));
console.error(JSON.stringify({ ues: c.ues, generale: c.generale, ajout: r.modules.find((m) => m.code === "R3.05").evaluations.length }));
"""
            with open(os.path.join(d, "t.mjs"), "w", encoding="utf-8") as f:
                f.write(script)
            res = subprocess.run(["node", "t.mjs"], cwd=d, capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        js = json.loads(res.stdout)
        aj = json.loads(res.stderr)
        r = data["démo S3"]
        self.assertEqual(aj["ajout"], 2)    # avecAjouts ne modifie pas le relevé
        m305 = next(m for m in r["modules"] if m["code"] == "R3.05")
        ra = avec_ajouts(r, {"R3.05": [{"id": -1, "coef": coef_par_defaut(m305)}], "R3.09": [{"id": -2, "coef": 1}]})
        mods = {m["code"]: m for m in ra["modules"]}
        sim = {-1: 14, -2: 9}
        self.assertAlmostEqual(aj["generale"], moyenne_generale(ra, sim), places=9)
        for u in ra["ues"]:
            self.assertAlmostEqual(aj["ues"][u["code"]], moyenne_ue(u, mods, sim), places=9)
        for nom, r in data.items():
            modules = {m["code"]: m for m in r["modules"]}
            with self.subTest(releve=nom):
                self.assertEqual(js[nom]["ecarts"], 0, "verifier() signale un écart avec le relevé")
                self.assertAlmostEqual(js[nom]["generale"], moyenne_generale(r), places=9)
                for u in r["ues"]:
                    py = moyenne_ue(u, modules)
                    if py is None:
                        self.assertIsNone(js[nom]["ues"][u["code"]])
                    else:
                        self.assertAlmostEqual(js[nom]["ues"][u["code"]], py, places=9)
                    for got, cible in zip(js[nom]["min"][u["code"]], (10, 8)):
                        self.assertEqual(got, note_minimale(u, r, cible=cible))


if __name__ == "__main__":
    unittest.main()
