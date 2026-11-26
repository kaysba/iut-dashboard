"""Front en modules ES : imports résolus, noms exportés, couches respectées, fichiers servis avec le bon type."""
import os
import re
import socket
import subprocess
import sys
import time
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
JS = os.path.join(WEB, "js")

IMPORT_RE = re.compile(r"""^\s*import\s+(?:(?P<what>[^"';]*?)\s+from\s+)?["'](?P<src>[^"']+)["']""", re.M | re.S)
EXPORT_DECL_RE = re.compile(r"^export\s+(?:async\s+)?(?:function\*?|const|let|var|class)\s+([\w$]+)", re.M)
EXPORT_LIST_RE = re.compile(r"^export\s*\{([^}]*)\}", re.M)

# Couche -> couches dont elle peut importer (en plus d'elle-même pour features/ et views/).
ALLOWED = {
    "core": {"core"},
    "components": {"core"},
    "features": {"core", "components", "features"},
    "views": {"core", "components", "features", "views"},
    "router": {"core", "components", "features", "views"},
    "main": {"core", "components", "features", "views", "router"},
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def js_files():
    out = []
    for d, _, files in os.walk(JS):
        out += [os.path.join(d, f) for f in files if f.endswith(".js")]
    return sorted(out)


def rel(path):
    return os.path.relpath(path, JS).replace(os.sep, "/")


def layer(path):
    r = rel(path)
    if r == "main.js":
        return "main"
    if r == "router.js":
        return "router"
    return r.split("/")[0]


def imports(path):
    """[(chemin absolu importé, [noms importés])] ; les commentaires sont ignorés."""
    src = re.sub(r"/\*.*?\*/", "", read(path), flags=re.S)
    src = re.sub(r"^\s*//.*$", "", src, flags=re.M)
    out = []
    for m in IMPORT_RE.finditer(src):
        names = []
        what = (m.group("what") or "").strip()
        brace = re.search(r"\{([^}]*)\}", what)
        if brace:
            names = [n.split(" as ")[0].strip() for n in brace.group(1).split(",") if n.strip()]
        if re.match(r"^[\w$]+", what) and not what.startswith("{") and not what.startswith("*"):
            names.append("default")
        target = os.path.normpath(os.path.join(os.path.dirname(path), m.group("src")))
        out.append((target, names, m.group("src")))
    return out


def exports(path):
    src = read(path)
    names = set(EXPORT_DECL_RE.findall(src))
    for group in EXPORT_LIST_RE.findall(src):
        names |= {n.split(" as ")[-1].strip() for n in group.split(",") if n.strip()}
    if re.search(r"^export\s+default\b", src, re.M):
        names.add("default")
    return names


class ModulesTest(unittest.TestCase):
    def test_plus_de_fichiers_monolithiques(self):
        self.assertFalse(os.path.exists(os.path.join(WEB, "app.js")))
        self.assertFalse(os.path.exists(os.path.join(WEB, "style.css")))

    def test_imports_resolus_et_noms_exportes(self):
        for f in js_files():
            for target, names, src in imports(f):
                with self.subTest(fichier=rel(f), import_=src):
                    self.assertTrue(src.startswith("./") or src.startswith("../"), "import relatif attendu")
                    self.assertTrue(os.path.isfile(target), f"{src} introuvable")
                    missing = set(names) - exports(target)
                    self.assertFalse(missing, f"non exporté par {src} : {sorted(missing)}")

    def test_couches(self):
        for f in js_files():
            me = layer(f)
            for target, _, src in imports(f):
                other = layer(target)
                with self.subTest(fichier=rel(f), import_=src):
                    self.assertNotEqual(other, "main", "personne n'importe main.js")
                    if other == "router":
                        self.assertEqual(me, "main", "seul main.js importe router.js")
                    self.assertIn(other, ALLOWED[me] | ({me} if me in ("features", "views") else set()),
                                  f"{me}/ ne doit pas importer depuis {other}/")

    def test_pas_d_import_circulaire(self):
        graph = {f: [t for t, _, _ in imports(f)] for f in js_files()}
        state = {}

        def visit(n, path):
            state[n] = "en cours"
            for m in graph.get(n, []):
                if state.get(m) == "en cours":
                    self.fail("import circulaire : " + " -> ".join(rel(x) for x in path + [n, m]))
                if m not in state:
                    visit(m, path + [n])
            state[n] = "fini"

        for f in graph:
            if f not in state:
                visit(f, [])

    def test_plus_de_globales_window_ni_confirm(self):
        for f in js_files():
            code = re.sub(r"/\*.*?\*/|//[^\n]*", "", read(f), flags=re.S)
            self.assertIsNone(re.search(r"window\.__\w+", code), rel(f))
            self.assertIsNone(re.search(r"(?<![\w.])confirm\(", code), rel(f))   # modale commune à la place

    def test_taille_des_fichiers(self):
        for f in js_files():
            n = read(f).count("\n")
            self.assertLessEqual(n, 330 if rel(f) == "features/depot/panel.js" else 300, rel(f))

    def test_css_sans_import_et_variables_dans_tokens(self):
        css_dir = os.path.join(WEB, "css")
        for d, _, files in os.walk(css_dir):
            for name in files:
                path = os.path.join(d, name)
                src = read(path)
                self.assertNotIn("@import", src, name)
                if name != "tokens.css":
                    self.assertNotRegex(src, r"(?m)^\s*--[\w-]+\s*:", f"variable de thème hors de tokens.css : {name}")
                    self.assertNotIn("@font-face", src, name)


class ServiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        cls.proc = subprocess.Popen([sys.executable, "dashboard.py", "--demo", "--no-browser", "--port", str(cls.port)],
                                    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("le serveur de démo n'a pas démarré")

    @classmethod
    def tearDownClass(cls):
        cls.proc.kill()
        cls.proc.wait()

    def get(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers={"Host": f"127.0.0.1:{self.port}"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.headers, r.read()

    def test_modules_servis_en_javascript(self):
        for f in js_files():
            with self.subTest(fichier=rel(f)):
                status, headers, body = self.get("/js/" + rel(f))
                self.assertEqual(status, 200)
                self.assertEqual(headers.get_content_type(), "text/javascript")
                self.assertEqual(headers["Cache-Control"], "no-cache")
                self.assertEqual(body.decode("utf-8"), read(f))

    def test_liens_d_index_html(self):
        _, _, body = self.get("/")
        html = body.decode("utf-8")
        refs = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)
        scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
        self.assertIn('<script type="module" src="/js/main.js">', html)
        self.assertGreater(len(refs), 4)
        for ref in refs + scripts:
            with self.subTest(ref=ref):
                status, headers, _ = self.get(ref)
                self.assertEqual(status, 200)
                self.assertEqual(headers.get_content_type(), "text/css" if ref.endswith(".css") else "text/javascript")
                self.assertEqual(headers["Cache-Control"], "no-cache")
        order = [r.rsplit("/", 1)[-1] for r in refs[:4]]
        self.assertEqual(order, ["tokens.css", "base.css", "layout.css", "components.css"])
        self.assertTrue(all(r.startswith("/css/views/") for r in refs[4:]))

    def test_chemins_hors_de_web_refuses(self):
        for path in ("/../dashboard.py", "/js/../../dashboard.py", "/css/..%2f..%2fdashboard.py"):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    self.get(path)
                self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
