"""Moodle : connexion via le CAS de l'université, puis API web services."""
import base64
import html
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from .common import (Session, SourceError, delete_secret, http_get, http_post_json,
                     http_post_multipart, load_secret, save_secret)
from .sso import cas_login
from .defaults import opt

TOKEN_FILE = "moodle_token.json"
STATUS_FILE = "assign_status.json"
EVENTS_PAGE = 50
DENIED = ("Le Moodle de l'IUT n'autorise pas le dépôt depuis l'extérieur. "
          "Utilise le lien vers la page Moodle.")
# Codes d'erreur Moodle qui signifient « ce service n'est pas autorisé pour l'app mobile ».
DENIED_CODES = {"accessexception", "webservice_access_exception", "nofileupload", "servicenotavailable",
                "invalidrecord", "functionnotfound", "unknownfunction", "disabled"}


class Moodle:
    def __init__(self, cfg, session=None):
        self.session = session or Session()
        self.base = opt(cfg, "MOODLE_URL").rstrip("/")
        self.login = opt(cfg, "UNICA_LOGIN")
        self.password = opt(cfg, "UNICA_PASSWORD")
        self.manual_token = opt(cfg, "MOODLE_TOKEN").strip()
        self.hidden = [h.lower() for h in opt(cfg, "COURS_MASQUES")]
        self._token = None
        self._site = None
        self._calendar_ok = None

    def set_credentials(self, login, password):
        self.login, self.password = login, password
        self._token = None
        self._site = None
        self._calendar_ok = None

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
        s = self.session

        def on_site(url):
            return url.startswith(self.base) and "/login/" not in url

        def sso_link(url, page):
            if url.startswith(self.base):
                return next((l for l in page.links if re.search(
                    r"authCAS|auth/cas|auth/shibboleth|auth/oauth2/login|auth/saml2|auth/oidc", l)), None)

        cas_login(s, self.base + "/login/index.php", self.login, self.password, on_site, follow_link=sso_link,
                  refused="Connexion UniCA refusée : vérifie ton identifiant et ton mot de passe. "
                          "Si tu as la double authentification, utilise MOODLE_TOKEN dans config.py (voir README).")

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

    # ── Appels API ──────────────────────────────────────────
    def call(self, fn, _retry=True, **params):
        data = {"wstoken": self.token(), "wsfunction": fn, "moodlewsrestformat": "json"}
        data.update(_flatten(params))
        resp = http_post_json(self.base + "/webservice/rest/server.php", data)
        if isinstance(resp, dict) and resp.get("exception"):
            code = resp.get("errorcode", "")
            if code == "invalidtoken" and not self.manual_token:
                # Le jeton est vraiment mort : on le jette. Réessayer n'a de sens que si un nouveau est possible.
                self._token = None
                delete_secret(TOKEN_FILE)
                if not (self.login and self.password):
                    raise SourceError("SESSION_EXPIRED")
                if _retry:
                    return self.call(fn, _retry=False, **params)
            err = SourceError("Jeton Moodle invalide ou expiré." if code == "invalidtoken"
                              else f"Moodle ({fn}) : {resp.get('message', code)}")
            err.code = code
            raise err
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
        raws, details = {}, {}
        for c in raw.get("courses", []):
            if c["id"] not in courses:
                continue
            for a in c.get("assignments", []):
                due = a.get("duedate") or 0
                if due and due < now - 45 * 86400:
                    continue  # vieux devoir, on ignore
                raws[a["id"]] = a
                items.append({
                    "id": a["id"], "cmid": a["cmid"], "name": html.unescape(a["name"]),
                    "course": courses[c["id"]]["name"], "courseShort": courses[c["id"]]["short"],
                    "due": due, "cutoff": a.get("cutoffdate") or 0,
                    "opens": a.get("allowsubmissionsfromdate") or 0,
                    "url": f"{self.base}/mod/assign/view.php?id={a['cmid']}",
                    "submitUrl": f"{self.base}/mod/assign/view.php?id={a['cmid']}&action=editsubmission",
                })

        events = self._actionable_assignments(now)
        cached = load_secret(STATUS_FILE) or {}
        new_cache = {}

        def fetch(item):
            """Statut réel via mod_assign_get_submission_status."""
            try:
                st = self.call("mod_assign_get_submission_status", assignid=item["id"])
            except SourceError:
                item["status"] = "inconnu"
                item["graded"] = False
                return
            details[item["id"]] = st
            item["status"], item["graded"] = _status_of(st)

        def resolve(item):
            key = str(item["id"])
            if events is not None and item["id"] in events:
                # Encore à rendre (ou brouillon) : on ne vérifie que si l'échéance est proche.
                item["status"], item["graded"] = "a_rendre", False
                if item["due"] and item["due"] <= now + 7 * 86400:
                    fetch(item)
                return
            if key in cached:
                item["status"], item["graded"] = "rendu", bool(cached[key].get("graded"))
                return
            fetch(item)
            if item["status"] == "rendu":
                new_cache[key] = {"graded": item["graded"]}

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(resolve, items))
        if new_cache:
            save_secret(STATUS_FILE, {**cached, **new_cache})
        site_limit = self._site_upload_limit()
        for item in items:
            item["depot"] = _depot(raws[item["id"]], item["status"], details.get(item["id"]), now, site_limit, self.base)
        items.sort(key=lambda i: (i["due"] == 0, i["due"]))
        return items

    def _actionable_assignments(self, now):
        """Ids des devoirs encore à rendre d'après la Chronologie de Moodle.
        Renvoie None si le service mobile refuse cette fonction (repli sur l'ancienne méthode)."""
        if self._calendar_ok is False:
            return None
        ids, after = set(), None
        try:
            for _ in range(20):
                params = {"timesortfrom": int(now - 45 * 86400), "limitnum": EVENTS_PAGE}
                if after:
                    params["aftereventid"] = after
                resp = self.call("core_calendar_get_action_events_by_timesort", **params)
                events = resp.get("events", []) if isinstance(resp, dict) else []
                for e in events:
                    if e.get("modulename") == "assign" and (e.get("action") or {}).get("actionable"):
                        ids.add(e.get("instance"))
                after = resp.get("lastid") or (events[-1]["id"] if events else None)
                if len(events) < EVENTS_PAGE or not after:
                    break
        except SourceError as e:
            if str(e) == "SESSION_EXPIRED":
                raise
            print(f"[moodle] Avertissement : calendrier indisponible ({e}). "
                  "Retour à un appel par devoir.", file=sys.stderr)
            self._calendar_ok = False
            return None
        self._calendar_ok = True
        return ids

    # ── Dépôt de fichiers ───────────────────────────────────
    def _site_upload_limit(self):
        try:
            return int(self.site().get("usermaxuploadfilesize") or 0)
        except (SourceError, ValueError, TypeError):
            return 0

    def _assignment(self, assign_id):
        ids = [c["id"] for c in self.courses()]
        raw = self.call("mod_assign_get_assignments", courseids=ids) if ids else {}
        for c in raw.get("courses", []):
            for a in c.get("assignments", []):
                if a["id"] == assign_id:
                    return a
        raise SourceError("Devoir introuvable.")

    def depot_state(self, assign_id):
        """État actuel du dépôt, relu depuis Moodle (ne suppose jamais qu'une opération a réussi)."""
        a = self._assignment(assign_id)
        st = self.call("mod_assign_get_submission_status", assignid=assign_id)
        status, graded = _status_of(st)
        return {"id": assign_id, "status": status, "graded": graded,
                "depot": _depot(a, status, st, time.time(), self._site_upload_limit(), self.base)}

    def _refuse(self, e):
        """Transforme un refus du site (fonction ou envoi non autorisés) en message clair."""
        text = str(e)
        if getattr(e, "code", "") in DENIED_CODES or text.startswith(("HTTP 403", "HTTP 404")):
            return SourceError(DENIED)
        return e

    def upload_draft(self, fichiers, itemid=None):
        """Envoie des fichiers [(nom, octets)] dans une zone de brouillon. Le premier envoi crée la zone
        (itemid renvoyé par Moodle), les suivants la réutilisent."""
        for nom, data in fichiers:
            fields = {"token": self.token(), "filearea": "draft"}
            if itemid:
                fields["itemid"] = itemid
            try:
                resp = http_post_multipart(f"{self.base}/webservice/upload.php", fields, [("file_1", nom, data)])
            except SourceError as e:
                raise self._refuse(e)
            if isinstance(resp, dict) and (resp.get("error") or resp.get("exception")):
                err = SourceError(str(resp.get("error") or resp.get("message") or resp.get("exception")))
                err.code = resp.get("errorcode", "")
                raise self._refuse(err)
            if not (isinstance(resp, list) and resp and resp[0].get("itemid")):
                raise SourceError("Moodle n'a pas confirmé la réception du fichier.")
            itemid = resp[0]["itemid"]
        return itemid

    def _check_warnings(self, warnings):
        if warnings:
            msgs = [w.get("message", "") for w in warnings if isinstance(w, dict)] if isinstance(warnings, list) else []
            raise SourceError("Moodle a refusé l'opération : " + (" ".join(m for m in msgs if m) or str(warnings)))

    def save_submission(self, assign_id, itemid, texte=None):
        plugindata = {}
        if itemid is not None:
            plugindata["files_filemanager"] = itemid
        if texte is not None:
            plugindata["onlinetext_editor"] = {"text": texte, "format": 1, "itemid": 0}
        try:
            warnings = self.call("mod_assign_save_submission", _retry=False, assignmentid=assign_id, plugindata=plugindata)
        except SourceError as e:
            raise self._refuse(e)
        self._check_warnings(warnings)

    def submit_for_grading(self, assign_id, declaration_acceptee):
        try:
            warnings = self.call("mod_assign_submit_for_grading", _retry=False, assignmentid=assign_id,
                                 acceptsubmissionstatement=1 if declaration_acceptee else 0)
        except SourceError as e:
            raise self._refuse(e)
        self._check_warnings(warnings)

    def _download(self, fileurl):
        try:
            return http_get(self.file_url(fileurl), timeout=120)
        except OSError as e:
            raise SourceError(f"Impossible de relire un fichier déjà déposé : {e}")

    def save_draft(self, assign_id, fichiers, garder_existants=True, upload_max=None, state=None):
        """fichiers : [(nom, octets)]. Remplace le brouillon Moodle : si garder_existants, les fichiers
        déjà déposés sont d'abord recopiés dans la même zone de brouillon."""
        state = state or self.depot_state(assign_id)
        depot = state["depot"]
        verifier_envoi(depot, [(n, len(d)) for n, d in fichiers], garder_existants, upload_max)
        nouveaux = {n for n, _ in fichiers}
        itemid = None
        if garder_existants:
            for f in depot["fichiers_actuels"]:
                if f["nom"] not in nouveaux:
                    itemid = self.upload_draft([(f["nom"], self._download(f["url"]))], itemid)
        itemid = self.upload_draft(fichiers, itemid)
        self.save_submission(assign_id, itemid)
        return self.depot_state(assign_id)

    def delete_file(self, assign_id, nom):
        state = self.depot_state(assign_id)
        depot = state["depot"]
        if not depot["ouvert"]:
            raise SourceError(depot["raison_fermeture"] or "Dépôt fermé.")
        reste = [f for f in depot["fichiers_actuels"] if f["nom"] != nom]
        if len(reste) == len(depot["fichiers_actuels"]):
            raise SourceError("Ce fichier n'est pas dans ton dépôt.")
        if not reste:
            raise SourceError("Impossible de vider le dépôt depuis le dashboard : utilise la page Moodle.")
        itemid = None
        for f in reste:
            itemid = self.upload_draft([(f["nom"], self._download(f["url"]))], itemid)
        self.save_submission(assign_id, itemid)
        return self.depot_state(assign_id)

    def submit(self, assign_id, declaration_acceptee):
        depot = self.depot_state(assign_id)["depot"]
        verifier_remise(depot, declaration_acceptee)
        self.submit_for_grading(assign_id, declaration_acceptee)
        return self.depot_state(assign_id)

    def file_url(self, fileurl):
        """URL de téléchargement authentifiée, uniquement pour ce Moodle."""
        if not fileurl.startswith(self.base):
            raise SourceError("Fichier hors Moodle refusé.")
        sep = "&" if "?" in fileurl else "?"
        return f"{fileurl}{sep}token={self.token()}"


# ── Règles de dépôt ──────────────────────────────────────────
def _status_of(st):
    last = (st or {}).get("lastattempt", {}) or {}
    sub = last.get("submission") or last.get("teamsubmission") or {}
    return ({"submitted": "rendu", "draft": "brouillon"}.get(sub.get("status"), "a_rendre"),
            last.get("gradingstatus") == "graded")


def _clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _depot(a, status, st, now, site_limit, base):
    """Règles de dépôt d'un devoir (mod_assign_get_assignments) + état (mod_assign_get_submission_status)."""
    cfg = {(c.get("plugin"), c.get("name")): c.get("value") for c in a.get("configs") or []}
    fichiers = cfg.get(("file", "enabled")) == "1"
    texte = cfg.get(("onlinetext", "enabled")) == "1"
    taille = int(cfg.get(("file", "maxsubmissionsizebytes")) or a.get("maxsubmissionsizebytes") or 0) or site_limit
    entries = [e.strip().lower() for e in re.split(r"[,;\s]+", cfg.get(("file", "filetypeslist")) or "") if e.strip()]
    # Des groupes (« document », « image ») ou des types MIME ne se vérifient pas ici : Moodle tranchera.
    types = [e for e in entries if e.startswith(".")] if all(e.startswith(".") for e in entries) else []
    remise_requise = bool(a.get("submissiondrafts"))
    declaration = bool(a.get("requiresubmissionstatement"))
    texte_decl = _clean(a.get("submissionstatement")) or (
        "Ce devoir est mon propre travail, à l'exception des parties où j'ai indiqué l'origine "
        "du travail d'autres personnes.")

    last = (st or {}).get("lastattempt", {}) or {}
    sub = last.get("submission") or last.get("teamsubmission") or {}
    statut = {"submitted": "remis", "draft": "brouillon"}.get(sub.get("status"), "nouveau")
    if st is None:   # liste : état déduit du statut du devoir
        statut = {"rendu": "remis", "brouillon": "brouillon"}.get(status, "nouveau")
    actuels = []
    for plugin in sub.get("plugins") or []:
        if plugin.get("type") == "file":
            for area in plugin.get("fileareas") or []:
                for f in area.get("files") or []:
                    actuels.append({"nom": f.get("filename", ""), "taille": f.get("filesize") or 0,
                                    "url": f.get("fileurl", ""), "modifie": f.get("timemodified") or 0})

    raison = ""
    opens, cutoff = a.get("allowsubmissionsfromdate") or 0, a.get("cutoffdate") or 0
    if opens and now < opens:
        raison = "Le dépôt n'est pas encore ouvert."
    elif cutoff and now > cutoff:
        raison = "La date limite de dépôt est dépassée."
    elif st is not None and (last.get("locked") or last.get("canedit") is False):
        raison = ("Ton dépôt est remis et Moodle ne permet plus de le modifier." if statut == "remis"
                  else "Moodle ne t'autorise pas à modifier ce dépôt.")
    elif st is None and statut == "remis" and remise_requise:
        raison = "Ton dépôt est déjà remis."
    return {"fichiers": fichiers, "texte": texte,
            "max_fichiers": int(cfg.get(("file", "maxfilesubmissions")) or 1),
            "taille_max": taille, "types": types, "ouvert": not raison, "raison_fermeture": raison,
            "remise_requise": remise_requise, "declaration": declaration, "texte_declaration": texte_decl,
            "statut": statut, "fichiers_actuels": actuels, "modifie": sub.get("timemodified") or 0}


def _taille(n):
    return f"{n / 1048576:.0f} Mo".replace(".0", "") if n >= 1048576 else f"{max(1, round(n / 1024))} Ko"


def verifier_envoi(depot, fichiers, garder_existants, upload_max=None):
    """Contrôles côté serveur d'un envoi : fichiers = [(nom, taille)]. Lève SourceError avec la raison."""
    if not depot["ouvert"]:
        raise SourceError(depot["raison_fermeture"] or "Le dépôt est fermé.")
    if not depot["fichiers"]:
        raise SourceError("Ce devoir n'accepte pas de fichiers : utilise la page Moodle.")
    if not fichiers:
        raise SourceError("Aucun fichier à envoyer.")
    noms = [n for n, _ in fichiers]
    if len(set(noms)) != len(noms):
        raise SourceError("Deux fichiers portent le même nom.")
    gardes = [f for f in depot["fichiers_actuels"] if f["nom"] not in noms] if garder_existants else []
    if len(noms) + len(gardes) > depot["max_fichiers"]:
        raise SourceError(f"Trop de fichiers : ce devoir en accepte {depot['max_fichiers']} au maximum "
                          f"(tu en as {len(noms) + len(gardes)}).")
    for nom, taille in fichiers:
        if not nom or "/" in nom or "\\" in nom:
            raise SourceError("Nom de fichier invalide.")
        limite = depot["taille_max"]
        if limite and taille > limite:
            raise SourceError(f"{nom} est trop gros ({_taille(taille)}) : ce devoir accepte {_taille(limite)} au maximum.")
        if upload_max and taille > upload_max:
            raise SourceError(f"{nom} dépasse la limite du dashboard ({_taille(upload_max)}).")
        if depot["types"] and not any(nom.lower().endswith(t) for t in depot["types"]):
            ok = " ou ".join(depot["types"])
            raise SourceError(f"{nom} n'est pas accepté : ce devoir demande un {ok}.")


def verifier_remise(depot, declaration_acceptee):
    if not depot["ouvert"]:
        raise SourceError(depot["raison_fermeture"] or "Le dépôt est fermé.")
    if not depot["remise_requise"]:
        raise SourceError("Ce devoir n'a pas d'étape de remise : l'enregistrement du dépôt suffit.")
    if depot["statut"] != "brouillon":
        raise SourceError("Il n'y a pas de brouillon à rendre : enregistre d'abord ton dépôt.")
    if depot["declaration"] and not declaration_acceptee:
        raise SourceError("Tu dois accepter la déclaration du devoir pour le rendre.")


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
