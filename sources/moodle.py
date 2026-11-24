"""Moodle : connexion via le CAS de l'université, puis API web services."""
import base64
import html
import random
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from .common import (Session, SourceError, delete_secret, http_post_json,
                     load_secret, parse_html, save_secret)

TOKEN_FILE = "moodle_token.json"


class Moodle:
    def __init__(self, cfg):
        self.base = cfg.MOODLE_URL.rstrip("/")
        self.login = cfg.UNICA_LOGIN
        self.password = cfg.UNICA_PASSWORD
        self.manual_token = cfg.MOODLE_TOKEN.strip()
        self.hidden = [h.lower() for h in getattr(cfg, "COURS_MASQUES", [])]
        self._token = None
        self._site = None

    def set_credentials(self, login, password):
        self.login, self.password = login, password
        self._token = None
        self._site = None

    # ── Authentification ────────────────────────────────────
    def token(self):
        if self.manual_token:
            return self.manual_token
        if self._token:
            return self._token
        saved = load_secret(TOKEN_FILE)
        if saved and saved.get("base") == self.base:
            self._token = saved["token"]
            return self._token
        if not (self.login and self.password):
            raise SourceError("SESSION_EXPIRED")
        self._token = self._token_via_sso()
        save_secret(TOKEN_FILE, {"base": self.base, "token": self._token, "date": int(time.time())})
        return self._token

    def _token_via_sso(self):
        s = Session()
        status, url, headers, body = s.request(self.base + "/login/index.php")
        password_sent = 0

        for _ in range(15):
            on_moodle = url.startswith(self.base)
            if on_moodle and "/login/" not in url:
                break  # connecté
            page = parse_html(body)

            # 1. Sur la page de login Moodle : suivre le bouton CAS / SSO
            if on_moodle:
                sso = next((l for l in page.links if re.search(
                    r"authCAS|auth/cas|auth/shibboleth|auth/oauth2/login|auth/saml2|auth/oidc", l)), None)
                if sso:
                    status, url, headers, body = s.request(urllib.parse.urljoin(url, html.unescape(sso)))
                    continue

            # 2. Formulaire avec mot de passe : on le remplit
            form = next((f for f in page.forms if any(i["type"] == "password" for i in f["inputs"])), None)
            if form:
                if password_sent >= 1:
                    raise SourceError("Connexion UniCA refusée : vérifie ton identifiant et ton mot de passe. "
                                      "Si tu as la double authentification, utilise MOODLE_TOKEN dans config.py (voir README).")
                fields = {}
                user_field = None
                for i in form["inputs"]:
                    if not i["name"]:
                        continue
                    if i["type"] == "password":
                        fields[i["name"]] = self.password
                    elif i["type"] in ("text", "email") and user_field is None:
                        user_field = i["name"]
                        fields[i["name"]] = self.login
                    elif i["type"] in ("hidden",):
                        fields[i["name"]] = i["value"]
                    elif i["type"] == "submit" and i["name"] and i["name"] not in fields:
                        fields[i["name"]] = i["value"]
                    elif i["type"] == "checkbox":
                        pass
                password_sent += 1
                status, url, headers, body = self._submit(s, url, form, fields)
                continue

            # 3. Formulaire auto-posté (SAML, relais SSO)
            auto = next((f for f in page.forms if f["inputs"] and all(
                i["type"] in ("hidden", "submit") for i in f["inputs"])), None)
            if auto:
                fields = {i["name"]: i["value"] for i in auto["inputs"] if i["name"] and i["type"] == "hidden"}
                status, url, headers, body = self._submit(s, url, auto, fields)
                continue
            break

        # Vérification + jeton mobile
        passport = str(random.randint(10**6, 10**9))
        launch = (f"{self.base}/admin/tool/mobile/launch.php?service=moodle_mobile_app"
                  f"&passport={passport}&urlscheme=moodlemobile")
        status, url, headers, body = s.request(launch, follow=False)
        location = next((v for k, v in headers.items() if k.lower() == "location"), "")
        m = re.search(r"moodlemobile://token=([A-Za-z0-9+/=]+)", location + body.decode("utf-8", "replace"))
        if not m:
            if "/login/" in location or "/login/" in url:
                raise SourceError("Connexion automatique à Moodle impossible (page de login inattendue). "
                                  "Utilise MOODLE_TOKEN dans config.py (voir README).")
            raise SourceError("Moodle n'a pas fourni de jeton : le service mobile est peut-être désactivé. "
                              "Utilise MOODLE_TOKEN dans config.py (voir README).")
        decoded = base64.b64decode(m.group(1)).decode("utf-8", "replace")
        parts = decoded.split(":::")
        if len(parts) < 2:
            raise SourceError("Jeton Moodle illisible.")
        return parts[1]

    @staticmethod
    def _submit(s, url, form, fields):
        action = urllib.parse.urljoin(url, html.unescape(form["action"])) if form["action"] else url
        if form["method"] == "post":
            return s.request(action, data=fields)
        sep = "&" if "?" in action else "?"
        return s.request(action + sep + urllib.parse.urlencode(fields))

    # ── Appels API ──────────────────────────────────────────
    def call(self, fn, _retry=True, **params):
        data = {"wstoken": self.token(), "wsfunction": fn, "moodlewsrestformat": "json"}
        data.update(_flatten(params))
        resp = http_post_json(self.base + "/webservice/rest/server.php", data)
        if isinstance(resp, dict) and resp.get("exception"):
            code = resp.get("errorcode", "")
            if code in ("invalidtoken", "accessexception") and _retry and not self.manual_token:
                self._token = None
                delete_secret(TOKEN_FILE)
                return self.call(fn, _retry=False, **params)
            if code == "invalidtoken":
                raise SourceError("Jeton Moodle invalide ou expiré.")
            raise SourceError(f"Moodle ({fn}) : {resp.get('message', code)}")
        return resp

    def site(self):
        if not self._site:
            self._site = self.call("core_webservice_get_site_info")
        return self._site

    def courses(self):
        uid = self.site()["userid"]
        raw = self.call("core_enrol_get_users_courses", userid=uid)
        out = []
        for c in raw:
            name = html.unescape(c.get("fullname", ""))
            if c.get("hidden") or any(h in name.lower() for h in self.hidden):
                continue
            out.append({
                "id": c["id"], "name": name, "short": html.unescape(c.get("shortname", "")),
                "url": f"{self.base}/course/view.php?id={c['id']}",
                "lastaccess": c.get("lastaccess") or 0,
            })
        out.sort(key=lambda c: -c["lastaccess"])
        return out

    # ── Ressources ──────────────────────────────────────────
    def resources(self):
        courses = self.courses()

        def load(c):
            try:
                sections = self.call("core_course_get_contents", courseid=c["id"])
            except SourceError as e:
                return {**c, "sections": [], "error": str(e)}
            return {**c, "sections": _shape_sections(sections, self.base)}

        with ThreadPoolExecutor(max_workers=6) as pool:
            return list(pool.map(load, courses))

    # ── Devoirs ─────────────────────────────────────────────
    def assignments(self):
        courses = {c["id"]: c for c in self.courses()}
        if not courses:
            return []
        raw = self.call("mod_assign_get_assignments", courseids=list(courses))
        now = time.time()
        items = []
        for c in raw.get("courses", []):
            if c["id"] not in courses:
                continue
            for a in c.get("assignments", []):
                due = a.get("duedate") or 0
                if due and due < now - 45 * 86400:
                    continue  # vieux devoir, on ignore
                items.append({
                    "id": a["id"], "cmid": a["cmid"], "name": html.unescape(a["name"]),
                    "course": courses[c["id"]]["name"], "courseShort": courses[c["id"]]["short"],
                    "due": due, "cutoff": a.get("cutoffdate") or 0,
                    "opens": a.get("allowsubmissionsfromdate") or 0,
                    "url": f"{self.base}/mod/assign/view.php?id={a['cmid']}",
                    "submitUrl": f"{self.base}/mod/assign/view.php?id={a['cmid']}&action=editsubmission",
                })

        def status(item):
            try:
                st = self.call("mod_assign_get_submission_status", assignid=item["id"])
            except SourceError:
                item["status"] = "inconnu"
                return item
            last = st.get("lastattempt", {}) or {}
            sub = last.get("submission") or last.get("teamsubmission") or {}
            item["status"] = {"submitted": "rendu", "draft": "brouillon"}.get(sub.get("status"), "a_rendre")
            item["graded"] = last.get("gradingstatus") == "graded"
            return item

        with ThreadPoolExecutor(max_workers=6) as pool:
            items = list(pool.map(status, items))
        items.sort(key=lambda i: (i["due"] == 0, i["due"]))
        return items

    def file_url(self, fileurl):
        """URL de téléchargement authentifiée, uniquement pour ce Moodle."""
        if not fileurl.startswith(self.base):
            raise SourceError("Fichier hors Moodle refusé.")
        sep = "&" if "?" in fileurl else "?"
        return f"{fileurl}{sep}token={self.token()}"


# ── Mise en forme ────────────────────────────────────────────
CAT_RULES = [
    ("Examen", r"\b(examens?|exam|annales?|ds|cc\d*|partiels?|contr[ôo]les?|évaluations?|eval)\b"),
    ("TP", r"\b(tp|tps|travaux pratiques|labs?)\s?\d*\b"),
    ("TD", r"\b(td|tds|travaux dirig[ée]s|exercices?)\s?\d*\b"),
    ("CM", r"\b(cm|cours|amphi|slides?|diapos?|chapitres?|magistral|poly(copié)?)\b"),
]
EXT_KIND = {
    "pdf": "pdf", "ppt": "slides", "pptx": "slides", "odp": "slides", "key": "slides",
    "doc": "doc", "docx": "doc", "odt": "doc", "txt": "doc", "md": "doc", "rtf": "doc",
    "xls": "sheet", "xlsx": "sheet", "ods": "sheet", "csv": "sheet",
    "zip": "archive", "rar": "archive", "7z": "archive", "tar": "archive", "gz": "archive",
    "py": "code", "java": "code", "c": "code", "h": "code", "cpp": "code", "js": "code",
    "php": "code", "sql": "code", "html": "code", "css": "code", "sh": "code", "ipynb": "code",
    "json": "code", "xml": "code", "kt": "code", "ts": "code",
    "png": "image", "jpg": "image", "jpeg": "image", "gif": "image", "svg": "image",
    "mp4": "video", "mkv": "video", "webm": "video", "mov": "video", "mp3": "audio",
}
MOD_KIND = {"url": "link", "folder": "folder", "page": "page", "book": "page",
            "assign": "assign", "quiz": "quiz", "forum": "forum", "lesson": "page",
            "h5pactivity": "quiz", "choice": "quiz", "feedback": "quiz", "glossary": "page",
            "wiki": "page", "workshop": "assign"}
SKIP_MODS = {"label", "subsection", "qbank"}


def _category(*texts):
    for text in texts:
        t = (text or "").lower()
        for cat, rx in CAT_RULES:
            if re.search(rx, t):
                return cat
    return "Autre"


def _ext(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _shape_sections(sections, base):
    out = []
    for s in sections:
        sname = html.unescape(s.get("name") or "")
        items = []
        for m in s.get("modules", []):
            mod = m.get("modname")
            if mod in SKIP_MODS or m.get("uservisible") is False:
                continue
            name = html.unescape(m.get("name") or "")
            files = []
            for f in m.get("contents") or []:
                if f.get("type") == "file":
                    files.append({"name": f.get("filename"), "size": f.get("filesize") or 0,
                                  "path": (f.get("filepath") or "/"),
                                  "fileurl": f.get("fileurl"), "modified": f.get("timemodified") or 0})
            if mod == "resource":
                kind = EXT_KIND.get(_ext(files[0]["name"]), "file") if files else "file"
            else:
                kind = MOD_KIND.get(mod, "other")
            ext_url = None
            if mod == "url":
                c = (m.get("contents") or [{}])[0]
                ext_url = c.get("fileurl")
            modified = max([f["modified"] for f in files] + [m.get("added") or 0])
            items.append({
                "id": m["id"], "name": name, "kind": kind, "mod": mod,
                "category": _category(name, files[0]["name"] if files else "", sname),
                "correction": bool(re.search(r"corrig|correction|solution", name.lower())),
                "url": m.get("url") or f"{base}/mod/{mod}/view.php?id={m['id']}",
                "external": ext_url, "files": files, "modified": modified,
            })
        if items:
            out.append({"name": sname or "Général", "items": items})
    return out


def _flatten(params, prefix=""):
    flat = {}
    for k, v in params.items():
        key = f"{prefix}[{k}]" if prefix else k
        if isinstance(v, dict):
            flat.update(_flatten(v, key))
        elif isinstance(v, (list, tuple)):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    flat.update(_flatten(item, f"{key}[{i}]"))
                else:
                    flat[f"{key}[{i}]"] = item
        else:
            flat[key] = v
    return flat
