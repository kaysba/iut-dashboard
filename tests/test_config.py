"""Valeurs par défaut, config-exemple.py (documentation seulement) et lecture des options par opt()."""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sources.defaults import DEFAULTS, PAGE_SEULEMENT  # noqa: E402

CODE = ("dashboard.py", "sources/moodle.py", "sources/notes.py", "sources/outlook.py", "sources/ade.py",
        "sources/settings.py", "sources/common.py", "sources/demo.py")


def charge(path, nom):
    spec = importlib.util.spec_from_file_location(nom, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EXEMPLE = charge(os.path.join(ROOT, "config-exemple.py"), "config_exemple_test")
OPTIONS_EXEMPLE = {n: getattr(EXEMPLE, n) for n in dir(EXEMPLE) if n.isupper()}


def source(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class DefautsTest(unittest.TestCase):
    def test_memes_options_et_memes_valeurs_que_config_exemple(self):
        self.assertEqual(set(DEFAULTS) - set(PAGE_SEULEMENT), set(OPTIONS_EXEMPLE))
        for nom, valeur in OPTIONS_EXEMPLE.items():
            self.assertEqual(DEFAULTS[nom], valeur, nom)

    def test_options_reglees_dans_la_page_absentes_de_l_exemple(self):
        for nom in ("PRENOM", "MAIL_ADRESSE", "ADE_ICAL_URL", "UNICA_LOGIN", "UNICA_PASSWORD"):
            self.assertNotIn(nom, OPTIONS_EXEMPLE)
        self.assertNotIn("UNICA_PASSWORD", DEFAULTS)     # le mot de passe n'est plus une option

    def test_plus_de_lecture_directe_de_config_dans_le_code(self):
        for rel in CODE:
            src = source(rel)
            self.assertIsNone(re.search(r'getattr\((config|cfg|self\.cfg), "[A-Z_]+"', src), rel)
            self.assertIsNone(re.search(r"(?<![\w.])(config|cfg|self\.cfg)\.[A-Z][A-Z_]+\b", src), rel)
            self.assertIsNone(re.search(r"\bopt\(\s*(config|cfg|self\.cfg)\s*,", src), rel)   # opt("NOM") seulement

    def test_rien_ne_lit_config_exemple(self):
        for rel in CODE:
            self.assertNotIn("config-exemple", source(rel), rel)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "sources", "configcheck.py")))
        self.assertNotIn("--config-diff", source("dashboard.py"))


class SansExempleTest(unittest.TestCase):
    """config-exemple.py n'est que de la documentation : le dashboard démarre sans lui (cas Windows signalé)."""

    def test_demarrage_sans_config_exemple(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        for dossier in ("sources", "web"):
            shutil.copytree(os.path.join(ROOT, dossier), os.path.join(d, dossier),
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(os.path.join(ROOT, "dashboard.py"), d)
        self.assertFalse(os.path.exists(os.path.join(d, "config-exemple.py")))
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        proc = subprocess.Popen([sys.executable, "dashboard.py", "--demo", "--no-browser", "--port", str(port)],
                                cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        tournait = False
        try:
            out, err = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            tournait = True                                  # toujours en marche après 2 s : démarrage réussi
            proc.kill()
            out, err = proc.communicate()
        self.assertIsNone(re.search(r"Traceback|FileNotFoundError", out + err), err)
        self.assertTrue(tournait, err)

    def test_lancer_bat(self):
        with open(os.path.join(ROOT, "lancer.bat"), "rb") as f:
            raw = f.read()
        raw.decode("ascii")                                  # pas d'accents : la console Windows les affiche mal
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"&&", raw)                         # python n'est essayé que si py n'existe pas
        self.assertIn(b"where py", raw)
        self.assertIn(b"https://www.python.org/downloads/", raw)


if __name__ == "__main__":
    unittest.main()
