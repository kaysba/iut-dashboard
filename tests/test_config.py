"""Valeurs par défaut, avertissements de config.py et --config-diff."""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sources import configcheck  # noqa: E402
from sources.defaults import DEFAULTS, opt  # noqa: E402


def charge(path, nom):
    spec = importlib.util.spec_from_file_location(nom, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EXEMPLE = charge(os.path.join(ROOT, "config-exemple.py"), "config_exemple_test")
OPTIONS_EXEMPLE = {n: getattr(EXEMPLE, n) for n in dir(EXEMPLE) if n.isupper()}


class DefautsTest(unittest.TestCase):
    def test_memes_options_et_memes_valeurs_que_config_exemple(self):
        self.assertEqual(set(DEFAULTS), set(OPTIONS_EXEMPLE))
        for nom, valeur in OPTIONS_EXEMPLE.items():
            self.assertEqual(DEFAULTS[nom], valeur, nom)

    def test_opt(self):
        self.assertEqual(opt(SimpleNamespace(PORT=9000), "PORT"), 9000)
        self.assertEqual(opt(SimpleNamespace(), "PORT"), DEFAULTS["PORT"])
        self.assertEqual(opt(SimpleNamespace(PORT=0), "PORT"), 0)      # une valeur fausse n'est pas « absente »
        a = opt(SimpleNamespace(), "COURS_MASQUES")
        a.append("x")
        self.assertEqual(opt(SimpleNamespace(), "COURS_MASQUES"), [])  # copie : les défauts ne bougent pas

    def test_plus_de_lecture_directe_ni_getattr_dans_le_code(self):
        import re
        for rel in ("dashboard.py", "sources/moodle.py", "sources/notes.py", "sources/outlook.py", "sources/ade.py"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                src = f.read()
            self.assertIsNone(re.search(r'getattr\((config|cfg|self\.cfg), "[A-Z_]+"', src), rel)
            self.assertIsNone(re.search(r"(?<![\w.])(config|cfg|self\.cfg)\.[A-Z][A-Z_]+\b(?!\s*=[^=])", src), rel)


class DiffTest(unittest.TestCase):
    def ancien_config(self):
        return SimpleNamespace(**{n: v for n, v in OPTIONS_EXEMPLE.items() if n != "MATIERES"})

    def test_avertissement_une_ligne_par_option_absente(self):
        out = io.StringIO()
        configcheck.avertir(self.ancien_config(), out)
        self.assertEqual(out.getvalue(), "[config] Option absente de config.py : MATIERES (valeur par défaut utilisée). "
                                         "Copie-la depuis config-exemple.py.\n")
        out = io.StringIO()
        configcheck.avertir(EXEMPLE, out)
        self.assertEqual(out.getvalue(), "")

    def test_diff_donne_le_bloc_complet_avec_ses_commentaires(self):
        out = io.StringIO()
        configcheck.diff_complet(self.ancien_config(), out)
        txt = out.getvalue()
        self.assertIn("# ── Couleurs par matière", txt)
        self.assertIn("MATIERES = [", txt)
        self.assertIn('{"motif": r"\\bsae\\b"', txt)
        self.assertNotIn("COULEURS_SECOURS = ", txt)               # présente dans l'ancien config : pas redonnée
        compile(txt, "bloc", "exec")                             # le bloc se colle tel quel dans config.py
        ns = {}
        exec(txt, ns)                                            # noqa: S102
        self.assertEqual(ns["MATIERES"], OPTIONS_EXEMPLE["MATIERES"])

    def test_diff_config_a_jour(self):
        out = io.StringIO()
        configcheck.diff_complet(EXEMPLE, out)
        self.assertIn("à jour", out.getvalue())

    def test_exemple_lu_sans_etre_execute(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "ex.py")
        with open(p, "w") as f:
            f.write("# commentaire\nA = 1\nraise SystemExit('exécuté !')\n")
        self.assertEqual(list(configcheck.blocs_exemple(p)), ["A"])


class LancementTest(unittest.TestCase):
    """dashboard.py lancé pour de vrai dans un dossier temporaire."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        shutil.copytree(os.path.join(ROOT, "sources"), os.path.join(self.d, "sources"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        for f in ("dashboard.py", "config-exemple.py"):
            shutil.copy(os.path.join(ROOT, f), self.d)

    def run_dash(self, *args):
        return subprocess.run([sys.executable, "dashboard.py", *args], cwd=self.d, capture_output=True,
                              text=True, timeout=30)

    def test_sans_config_py_message_clair_sans_traceback(self):
        r = self.run_dash()
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr + r.stdout)
        self.assertIn("cp config-exemple.py config.py", r.stderr)
        self.assertIn("copy config-exemple.py config.py", r.stderr)
        r = self.run_dash("--config-diff")
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("config-exemple.py config.py", r.stderr)

    def test_config_diff_sans_matieres(self):
        with open(os.path.join(ROOT, "config-exemple.py"), encoding="utf-8") as f:
            src = f.read()
        debut = src.index("# ── Couleurs par matière")
        with open(os.path.join(self.d, "config.py"), "w", encoding="utf-8") as f:
            f.write(src[:debut])
        r = self.run_dash("--config-diff")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("MATIERES = [", r.stdout)
        self.assertIn("COULEURS_SECOURS = [", r.stdout)
        self.assertNotIn("PORT", r.stdout)
        self.assertEqual(r.stderr, "")                           # --config-diff quitte avant tout démarrage

    def test_demarrage_signale_l_option_absente_et_demarre(self):
        with open(os.path.join(ROOT, "config-exemple.py"), encoding="utf-8") as f:
            src = f.read()
        with open(os.path.join(self.d, "config.py"), "w", encoding="utf-8") as f:
            f.write(src.replace(configcheck.blocs_exemple()["MATIERES"], "") + "\nPORT = 8791\nOUVRIR_NAVIGATEUR = False\n")
        proc = subprocess.Popen([sys.executable, "dashboard.py", "--demo", "--no-browser"], cwd=self.d,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        import time
        import urllib.request
        ok = False
        for _ in range(50):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8791/api/me", timeout=1) as r:
                    ok = r.status == 200
                    break
            except OSError:
                time.sleep(0.1)
        proc.kill()
        _, err = proc.communicate()
        self.assertTrue(ok, err)
        self.assertEqual(err.count("Option absente de config.py : MATIERES (valeur par défaut utilisée)."), 1)
        self.assertEqual(err.count("[config] Option absente"), 1)


if __name__ == "__main__":
    unittest.main()
