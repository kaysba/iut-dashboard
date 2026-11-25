"""Valeurs par défaut, config-exemple.py (documentation seulement) et lecture des options par opt()."""
import importlib.util
import os
import re
import sys
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


if __name__ == "__main__":
    unittest.main()
