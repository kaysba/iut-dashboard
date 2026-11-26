#!/usr/bin/env python3
"""Dashboard IUT — serveur local.

Lancer :  double-clic sur lancer.bat (Windows), lancer.command (macOS) ou lancer.sh (Linux),
          ou  python3 dashboard.py
Tout se règle dans la page web : un assistant s'ouvre au premier lancement.
Essai  :  python3 dashboard.py --demo           (données fictives)
          python3 dashboard.py --demo --setup   (l'assistant de premier lancement, en démo)
"""
import datetime as dt
import json
import mimetypes
import os
import re
import shutil
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.version_info < (3, 8):
    sys.exit("Python 3.8 ou plus récent est nécessaire : https://www.python.org/downloads/")

from sources import common, demo, settings  # noqa: E402
from sources.ade import ADE, MSG_CONSULTATION, MSG_PAS_EDT, NOT_SET as ADE_NOT_SET  # noqa: E402
from sources.common import (UA, Session, SourceError, TTLCache, delete_secret, load_secret,  # noqa: E402
                            parse_multipart, save_secret)
from sources.defaults import DEFAULTS  # noqa: E402
from sources.moodle import DENIED, Moodle, verifier_envoi, verifier_remise  # noqa: E402
from sources.notes import Notes  # noqa: E402
from sources.outlook import Outlook  # noqa: E402
from sources.settings import opt  # noqa: E402

DEMO = "--demo" in sys.argv
DEMO_SETUP = DEMO and "--setup" in sys.argv   # démo de l'assistant de premier lancement

# La démo n'utilise ni config.py ni settings.json, et n'écrit rien : captures sans donnée personnelle.
settings.utiliser_config(None if DEMO else settings.charger_config())
settings.charger(memoire_seule=DEMO)

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
STATIC_TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2", ".svg": "image/svg+xml"}

# login, prénom (lu dans Moodle) et adresse mail proposée (profil Moodle, sinon identifiant@etu.unice.fr)
SESSION = {"ok": False, "login": "", "prenom": "", "mail": ""}
DEMO_STATE = {"mail": not DEMO_SETUP}         # Outlook « connecté » en démo


def mail_address():
    """Adresse utilisée pour Outlook : celle des réglages, sinon celle trouvée à la connexion."""
    return opt("MAIL_ADRESSE") or SESSION["mail"]


sso_session = Session()   # Moodle et Notes partagent les cookies du CAS
moodle = Moodle(sso_session)
notes = Notes(sso_session)
ade = ADE()
outlook = Outlook(mail_address)
cache = TTLCache()


REMEMBER_FILE = "remember.json"
SESSION_FILES = ("moodle_token.json", "outlook_token.json", REMEMBER_FILE, "assign_status.json")


def logged_in():
    return (DEMO and not DEMO_SETUP) or SESSION["ok"]


def init_session():
    """Au démarrage : on ne reprend la session que si « Se souvenir de moi » avait été coché."""
    saved = load_secret(REMEMBER_FILE)
    if saved and (load_secret("moodle_token.json") or opt("MOODLE_TOKEN")):
        SESSION.update(ok=True, login=saved.get("login", ""), prenom=saved.get("prenom", ""),
                       mail=saved.get("mail", ""))
        moodle.set_credentials(SESSION["login"], "")
    else:
        for name in SESSION_FILES:
            delete_secret(name)  # reste d'une ancienne session : on repart à zéro


def forget_unless_remembered():
    if not load_secret(REMEMBER_FILE):
        for name in SESSION_FILES:
            delete_secret(name)


def api_login(payload):
    login = (payload.get("login") or "").strip()
    pw = payload.get("password") or ""
    remember = bool(payload.get("remember"))
    if not login:
        raise SourceError("Entre ton identifiant UniCA.")
    if DEMO:
        if not pw:
            raise SourceError("Entre ton mot de passe.")
        SESSION.update(ok=True, login=login, prenom="Camille", mail="camille.martin@etu.unice.fr")
        settings.marquer()
        return {"ok": True}
    if not pw and not (opt("MOODLE_TOKEN") or load_secret("moodle_token.json")):
        raise SourceError("Entre ton mot de passe.")
    moodle.set_credentials(login, pw)
    if pw:
        delete_secret("moodle_token.json")
    found = {}

    def moodle_login():
        moodle.token()
        site = moodle.site()
        found["prenom"] = str(site.get("firstname") or "").strip()
        found["mail"] = moodle.profile_mail()

    # Moodle et Notes se connectent en parallèle ; un échec de Notes ne bloque pas la connexion
    # (il apparaît comme erreur de la source « Notes » dans la barre latérale).
    pool = ThreadPoolExecutor(max_workers=1)
    notes_job = pool.submit(notes.login, login, pw) if pw else None
    ok = False
    try:
        moodle_login()
        ok = True
    except OSError as e:
        moodle.set_credentials("", "")
        raise SourceError(f"Moodle injoignable : {e}")
    except SourceError:
        moodle.set_credentials("", "")
        raise
    finally:
        if notes_job:
            try:
                notes_job.result()
            except Exception as e:  # noqa: BLE001
                print(f"[notes] connexion impossible : {e}", file=sys.stderr)
        pool.shutdown()
        if not ok:
            notes.forget()
            sso_session.jar.clear()
    moodle.password = ""          # plus nécessaire en mémoire une fois le jeton obtenu
    SESSION.update(ok=True, login=login, prenom=found["prenom"] or opt("PRENOM"),
                   mail=found["mail"] or f"{login}@etu.unice.fr")
    if remember:
        save_secret(REMEMBER_FILE, {"login": login, "prenom": SESSION["prenom"], "mail": SESSION["mail"]})
    else:
        delete_secret(REMEMBER_FILE)
        delete_secret("moodle_token.json")   # le jeton reste seulement en mémoire
    settings.marquer()            # l'étape 1 de l'assistant est faite : il ne reviendra plus
    cache.clear()
    return {"ok": True}


def api_logout():
    """Ferme la session. Les réglages (settings.json : lien ADE, couleurs…) restent."""
    SESSION.update(ok=False, login="", prenom="", mail="")
    moodle.set_credentials("", "")
    outlook._pending = None
    notes.forget()          # mot de passe et cookies de la passerelle
    sso_session.jar.clear()
    DEMO_STATE["mail"] = not DEMO_SETUP
    for name in SESSION_FILES:
        delete_secret(name)
    cache.clear()
    return {"ok": True}


def api_reset(payload):
    """« Tout effacer de cet ordinateur » : session, jetons et réglages (tout le dossier .cache/)."""
    if payload.get("confirm") is not True:
        raise settings.ReglageInvalide("Confirmation manquante.")
    api_logout()
    if not DEMO:
        shutil.rmtree(common.CACHE_DIR, ignore_errors=True)
    settings.oublier()
    return {"ok": True}


# Quel cache vider quand un réglage change.
CACHE_OF = {"ADE_ICAL_URL": ("ade:",), "CACHE_PLANNING": ("ade:",), "COURS_MASQUES": ("res", "assign"),
            "CACHE_MOODLE": ("res", "assign"), "MAIL_ADRESSE": ("mail",), "CACHE_MAILS": ("mail",),
            "CACHE_NOTES": ("notes:",)}


def api_settings(payload):
    noms = settings.enregistrer(payload)
    prefixes = tuple(p for n in noms for p in CACHE_OF.get(n, ()))
    if prefixes:
        cache.clear(*prefixes)
    return {"ok": True, "me": api_me({})}


def api_settings_ade(payload):
    """Vérifie un lien ADE collé dans la page (téléchargement d'une semaine) puis l'enregistre."""
    url = str(payload.get("url") or "").strip()
    if not url:
        raise settings.ReglageInvalide("Colle le lien d'export ADE.")
    if "direct/index.jsp" in url:
        raise settings.ReglageInvalide(MSG_CONSULTATION)
    url = settings.valider_lien_ade("ADE_ICAL_URL", url)
    try:
        if DEMO:
            if "anonymous_cal" not in url:
                raise SourceError(MSG_PAS_EDT)
            lundi = dt.date.today() - dt.timedelta(days=dt.date.today().weekday())
            count = len(demo.events(lundi, lundi + dt.timedelta(days=6)))
        else:
            count = ade.tester(url)
    except SourceError as e:
        e.status = 422
        raise
    settings.enregistrer({"ADE_ICAL_URL": url})
    cache.clear("ade:")
    return {"ok": True, "count": count, "ade": settings.masquer_lien(url)}


HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")


def _subject_config():
    """MATIERES et COULEURS_SECOURS validés (un motif ou une couleur invalide de config.py est ignoré)."""
    matieres = []
    for i, m in enumerate(opt("MATIERES") or []):
        try:
            motif, nom, couleur = m["motif"], m.get("nom", ""), m["couleur"]
            re.compile(motif)
            if not HEX_COLOR.fullmatch(str(couleur)):
                raise ValueError(f"couleur {couleur!r} invalide (format #RRGGBB attendu)")
        except (re.error, ValueError, KeyError, TypeError, AttributeError) as e:
            print(f"[config] MATIERES[{i}] ignorée : {e}", file=sys.stderr)
            continue
        matieres.append({"motif": motif, "nom": str(nom), "couleur": couleur.upper()})
    secours = []
    for c in opt("COULEURS_SECOURS") or []:
        if isinstance(c, str) and HEX_COLOR.fullmatch(c):
            secours.append(c)
        else:
            print(f"[config] COULEURS_SECOURS : {c!r} ignorée (format #RRGGBB attendu)", file=sys.stderr)
    return matieres, secours or list(DEFAULTS["COULEURS_SECOURS"])


def _prenom():
    if SESSION["prenom"]:
        return SESSION["prenom"]
    site = moodle._site   # déjà chargé : pas d'appel réseau ici
    return (site or {}).get("firstname") or opt("PRENOM") or ("Camille" if DEMO and not DEMO_SETUP else "")


def _origine(nom):
    if nom in settings.tout():
        return "page"
    cfg = settings.config_actuelle()
    return "config" if cfg is not None and hasattr(cfg, nom) else "defaut"


def _settings_publics():
    """Réglages affichés dans la page. Le lien ADE n'y est jamais en entier (il contient un jeton)."""
    login = SESSION["login"]
    return {
        "ade": settings.masquer_lien(opt("ADE_ICAL_URL")),
        "mail": opt("MAIL_ADRESSE"),
        "mailSuggestion": SESSION["mail"] or (f"{login}@etu.unice.fr" if login else ""),
        "outlook": DEMO_STATE["mail"] if DEMO else outlook.connected(),
        "coursMasques": opt("COURS_MASQUES"),
        "theme": opt("THEME"),
        "cache": {n: opt(n) for n in ("CACHE_PLANNING", "CACHE_MOODLE", "CACHE_MAILS", "CACHE_NOTES")},
        "port": opt("PORT"),
        "portActuel": PORT_ACTUEL[0],
        "origine": {n: _origine(n) for n in ("ADE_ICAL_URL", "MAIL_ADRESSE", "MATIERES", "COURS_MASQUES", "PORT")},
        "configPy": settings.config_actuelle() is not None,
    }


PORT_ACTUEL = [None]


def api_me(_q):
    matieres, secours = _subject_config()
    me = {
        "matieres": matieres, "couleursSecours": secours, "theme": opt("THEME"),
        "prenom": _prenom(), "demo": DEMO, "loggedIn": logged_in(),
        # Assistant de premier lancement : rien n'est configuré (ni réglages de la page, ni config.py).
        "setup": not logged_in() and not settings.existe() and (DEMO or settings.config_actuelle() is None),
        "login": SESSION["login"] or opt("UNICA_LOGIN"), "moodleUrl": opt("MOODLE_URL"),
        "sources": {
            "moodle": logged_in(),
            "ade": (DEMO and not DEMO_SETUP) or bool(opt("ADE_ICAL_URL")),
            "mail": DEMO_STATE["mail"] if DEMO else outlook.connected(),
            "notes": DEMO or notes.has_password(),
        },
        "mail": mail_address(),
    }
    if logged_in():
        me["settings"] = _settings_publics()
    return me


def _date(q, key, default):
    try:
        return dt.date.fromisoformat(q.get(key, [""])[0])
    except ValueError:
        return default


def api_planning(q, force):
    today = dt.date.today()
    start = _date(q, "start", today)
    end = _date(q, "end", start + dt.timedelta(days=6))
    if (end - start).days > 62:
        raise SourceError("Période trop longue (2 mois maximum).")
    if DEMO_SETUP and not opt("ADE_ICAL_URL"):
        raise SourceError(ADE_NOT_SET)
    if DEMO:
        return {"events": demo.events(start, end)}
    key = f"ade:{start}:{end}"
    return {"events": cache.get(key, opt("CACHE_PLANNING"), lambda: ade.events(start, end), force)}


def api_resources(_q, force):
    if DEMO:
        return {"courses": demo.resources()}
    return {"courses": cache.get("res", opt("CACHE_MOODLE"), moodle.resources, force)}


def api_assignments(_q, force):
    if DEMO:
        return {"assignments": demo.assignments()}
    return {"assignments": cache.get("assign", opt("CACHE_MOODLE"), moodle.assignments, force)}


def api_mails(_q, force):
    if DEMO:
        if not DEMO_STATE["mail"]:
            raise SourceError("NOT_CONNECTED")
        return demo.mails()
    return cache.get("mail", opt("CACHE_MAILS"), outlook.messages, force)


def api_notes(q, force):
    sid = q.get("semestre", [""])[0]
    if sid and not sid.isdigit():
        raise SourceError("Semestre invalide.")
    sid = int(sid) if sid else None
    if DEMO:
        return demo.notes(sid)
    ttl = opt("CACHE_NOTES")
    return cache.get(f"notes:{sid}", ttl, lambda: notes.donnees(sid), force)


def api_notes_login(payload):
    """Après une relance avec « Se souvenir de moi », il n'y a plus de mot de passe en mémoire."""
    pw = payload.get("password") or ""
    if not pw:
        raise SourceError("Entre ton mot de passe.")
    notes.login(SESSION["login"], pw)
    cache.clear()
    return {"ok": True}


def api_mail_auth_url(_q, _force):
    return {"url": outlook.auth_url()}


def api_mail_finish(payload):
    url = str(payload.get("url") or "")
    if DEMO:
        if "code=" not in url:
            raise SourceError("Adresse collée incorrecte : copie toute l'adresse de l'onglet (https://localhost/?code=…)")
        DEMO_STATE["mail"] = True
    else:
        outlook.finish_auth(url)
    cache.clear("mail")
    return {"ok": True}


def api_mail_disconnect(_payload):
    if DEMO:
        DEMO_STATE["mail"] = False
    else:
        outlook.disconnect()
    cache.clear("mail")
    return {"ok": True}


# POST qui exigent une session connectée (en plus des contrôles Host et Origin).
POST_ROUTES = {
    "/api/notes/login": lambda p: api_notes_login(p),
    "/api/mail/finish": api_mail_finish,
    "/api/mail/disconnect": api_mail_disconnect,
    "/api/settings": api_settings,
    "/api/settings/ade": api_settings_ade,
    "/api/reset": api_reset,
}

ROUTES = {
    "/api/mail/auth-url": api_mail_auth_url,
    "/api/notes": api_notes,
    "/api/planning": api_planning,
    "/api/resources": api_resources,
    "/api/assignments": api_assignments,
    "/api/mails": api_mails,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "IUTDashboard"

    def log_message(self, fmt, *args):
        if "--verbose" in sys.argv:
            super().log_message(fmt, *args)

    # Le serveur n'accepte que les requêtes venant de ta machine.
    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, e):
        msg = str(e)
        if msg == "SESSION_EXPIRED":
            SESSION["ok"] = False
            return self._json({"error": "Ta session a expiré. Reconnecte-toi.", "code": "login_required"}, 401)
        if msg == DENIED:
            return self._json({"error": msg, "code": "depot_refuse"}, 403)
        if msg == "NOTES_LOGIN_REQUIRED":
            return self._json({"error": "Entre ton mot de passe pour afficher tes notes.", "code": "notes_login_required"}, 401)
        if msg == ADE_NOT_SET:
            return self._json({"error": "Emploi du temps pas encore configuré.", "code": "ade_not_set"}, 409)
        if msg == "NOT_CONNECTED":
            return self._json({"error": "Outlook n'est pas connecté.", "code": "mail_not_connected"}, 401)
        if not isinstance(e, SourceError):
            traceback.print_exc()
            msg = f"Erreur inattendue : {e}"
        self._json({"error": msg}, getattr(e, "status", 502))

    def do_GET(self):
        if not self._host_ok():
            return self.send_error(403)
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        force = q.get("refresh", ["0"])[0] == "1"
        depot_get = re.fullmatch(r"/api/assignments/(\d+)/depot", url.path)
        if (url.path in ROUTES or depot_get or url.path in ("/api/file", "/api/notes/pdf")) and not logged_in():
            return self._json({"error": "Connecte-toi d'abord.", "code": "login_required"}, 401)
        try:
            if url.path == "/api/me":
                return self._json(api_me(q))
            if url.path in ROUTES:
                return self._json(ROUTES[url.path](q, force))
            if depot_get:
                aid = int(depot_get.group(1))
                return self._json(demo.depot_state(aid) if DEMO else moodle.depot_state(aid))
            if url.path == "/api/file":
                return self._file(q.get("u", [""])[0])
            if url.path == "/api/notes/pdf":
                return self._notes_pdf(q.get("semestre", [""])[0])
        except Exception as e:  # noqa: BLE001
            return self._error(e)
        return self._static(url.path)

    def do_POST(self):
        if not self._host_ok():
            return self.send_error(403)
        origin = self.headers.get("Origin", "")
        if origin and urllib.parse.urlsplit(origin).hostname not in ("127.0.0.1", "localhost"):
            return self.send_error(403)
        depot_post = re.fullmatch(r"/api/assignments/(\d+)/(draft|submit|delete-file)", self.path)
        if depot_post:
            return self._depot_post(int(depot_post.group(1)), depot_post.group(2))
        try:
            try:
                payload = json.loads(self._read_body(1048576) or b"{}")
            except ValueError:
                raise settings.ReglageInvalide("JSON illisible.")
            if not isinstance(payload, dict):
                raise settings.ReglageInvalide("Objet JSON attendu.")
            if self.path == "/api/login":
                return self._json(api_login(payload))
            if self.path == "/api/logout":
                return self._json(api_logout())
            if self.path not in POST_ROUTES:
                return self.send_error(404)
            if not logged_in():
                return self._json({"error": "Connecte-toi d'abord.", "code": "login_required"}, 401)
            return self._json(POST_ROUTES[self.path](payload))
        except Exception as e:  # noqa: BLE001
            return self._error(e)

    def _read_body(self, limit):
        """Lit le corps en flux, en mémoire (jamais sur le disque), sans dépasser la limite annoncée."""
        length = int(self.headers.get("Content-Length") or 0)
        if length > limit:
            # Vide le corps reçu (sans le garder) pour que le navigateur lise la réponse au lieu d'une coupure.
            cap = opt("UPLOAD_MAX") + 1048576
            if length <= cap:
                left = length
                while left > 0:
                    chunk = self.rfile.read(min(65536, left))
                    if not chunk:
                        break
                    left -= len(chunk)
            else:
                self.close_connection = True
            err = SourceError(f"Envoi trop gros ({length // 1048576} Mo) : la limite est de {max(1, limit // 1048576)} Mo.")
            err.status = 413
            raise err
        chunks, left = [], length
        while left > 0:
            chunk = self.rfile.read(min(65536, left))
            if not chunk:
                break
            chunks.append(chunk)
            left -= len(chunk)
            if DEMO:
                time.sleep(0.01)   # démo : laisse voir la barre de progression
        return b"".join(chunks)

    def _depot_post(self, aid, action):
        try:
            if not logged_in():
                return self._json({"error": "Connecte-toi d'abord.", "code": "login_required"}, 401)
            upload_max = opt("UPLOAD_MAX")
            if action == "draft":
                state = demo.depot_state(aid) if DEMO else moodle.depot_state(aid)
                depot = state["depot"]
                limit = upload_max
                if depot["taille_max"]:
                    limit = min(limit, depot["taille_max"] * max(1, depot["max_fichiers"]) + 65536)
                fields, files = parse_multipart(self._read_body(limit), self.headers.get("Content-Type", ""))
                fichiers = [(nom, data) for _, nom, data in files]
                garder = fields.get("garder_existants", "1") != "0"
                verifier_envoi(depot, [(n, len(d)) for n, d in fichiers], garder, upload_max)
                if not depot["remise_requise"]:   # le dépôt vaut remise : même exigences que « submit »
                    if fields.get("verifie") != "1":
                        raise SourceError("Confirmation manquante : coche « J'ai vérifié les fichiers que je rends ».")
                    if depot["declaration"] and fields.get("declaration") != "1":
                        raise SourceError("Tu dois accepter la déclaration du devoir pour le rendre.")
                if DEMO:
                    result = demo.save_draft(aid, fichiers, garder, upload_max, state)
                else:
                    result = moodle.save_draft(aid, fichiers, garder, upload_max, state)
            else:
                payload = json.loads(self._read_body(65536) or b"{}")
                if action == "submit":
                    if payload.get("verifie") is not True:
                        raise SourceError("Confirmation manquante : coche « J'ai vérifié les fichiers que je rends ».")
                    decl = payload.get("declaration") is True
                    result = demo.submit(aid, decl) if DEMO else moodle.submit(aid, decl)
                else:
                    nom = str(payload.get("nom") or "")
                    result = demo.delete_file(aid, nom) if DEMO else moodle.delete_file(aid, nom)
            cache.clear()
            return self._json(result)
        except Exception as e:  # noqa: BLE001
            return self._error(e)

    def _notes_pdf(self, sid):
        if DEMO:
            raise SourceError("Le relevé PDF officiel n'est pas disponible en mode démo.")
        if not sid.isdigit():
            raise SourceError("Semestre invalide.")
        body = notes.pdf(int(sid))
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'attachment; filename="releve-notes-{sid}.pdf"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, fileurl):
        if DEMO and fileurl.startswith("demo://"):
            body, ctype = demo.file_bytes(fileurl)
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        url = moodle.file_url(fileurl)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            self.send_response(200)
            for h in ("Content-Type", "Content-Length", "Content-Disposition"):
                if r.headers.get(h):
                    self.send_header(h, r.headers[h])
            self.end_headers()
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        full = os.path.normpath(os.path.join(WEB_DIR, path.lstrip("/")))
        if os.path.commonpath([full, WEB_DIR]) != WEB_DIR or not os.path.isfile(full):
            return self.send_error(404)
        # Types fixés ici : le registre de Windows associe parfois .js à text/plain, et un navigateur
        # refuse alors de charger les modules ES (web/js/**).
        ext = os.path.splitext(full)[1].lower()
        ctype = STATIC_TYPES.get(ext) or mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def _port_argument():
    """--port 9000 (ou --port=9000) : passe avant le réglage, pour ce lancement seulement."""
    for i, a in enumerate(sys.argv):
        v = a.split("=", 1)[1] if a.startswith("--port=") else sys.argv[i + 1] if a == "--port" and i + 1 < len(sys.argv) else None
        if v is not None:
            if not v.isdigit() or not 1024 <= int(v) <= 65535:
                sys.exit("--port : nombre entre 1024 et 65535 attendu.")
            return int(v)
    return None


def main():
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("font/woff2", ".woff2")
    if settings.config_actuelle() is not None:
        print("[config] config.py lu : ses options servent quand la page ne les règle pas.", file=sys.stderr)
    port = _port_argument() or opt("PORT")
    if not DEMO:
        import atexit
        init_session()
        atexit.register(forget_unless_remembered)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        sys.exit(f"\n  Le port {port} est déjà utilisé : le dashboard tourne sans doute déjà.\n"
                 f"  Ouvre http://localhost:{port}/ dans ton navigateur, ou ferme l'ancienne fenêtre du dashboard.\n"
                 f"  (Si c'est un autre programme : change le port dans Réglages > Avancé.)\n")
    PORT_ACTUEL[0] = port
    url = f"http://localhost:{port}/"
    print(f"\n  Dashboard IUT {'(mode démo) ' if DEMO else ''}: {url}")
    print("  Laisse cette fenêtre ouverte pendant que tu utilises le dashboard. Ctrl+C pour arrêter.\n")
    if opt("OUVRIR_NAVIGATEUR") and "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêté.")


if __name__ == "__main__":
    main()
