#!/usr/bin/env python3
"""Dashboard IUT — serveur local.

Lancer :  python dashboard.py          (Windows : py dashboard.py)
La connexion se fait dans la page web (identifiant, mail, mot de passe).
Essai  :  python dashboard.py --demo   (données fictives, sans configuration)
"""
import datetime as dt
import json
import mimetypes
import os
import re
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
    sys.exit("Python 3.8 ou plus récent est nécessaire.")

import config
from sources import demo
from sources.ade import ADE
from sources.common import (UA, Session, SourceError, TTLCache, delete_secret, load_secret, parse_multipart,
                            save_secret)
from sources.moodle import DENIED, Moodle, verifier_envoi, verifier_remise
from sources.notes import Notes
from sources.outlook import Outlook

DEMO = "--demo" in sys.argv


WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

sso_session = Session()   # Moodle et Notes partagent les cookies du CAS
moodle = Moodle(config, sso_session)
notes = Notes(config, sso_session)
ade = ADE(config)
outlook = Outlook(config)
cache = TTLCache()


SESSION = {"ok": False}   # connecté pendant cette exécution ?
REMEMBER_FILE = "remember.json"
SESSION_FILES = ("moodle_token.json", "outlook_token.json", REMEMBER_FILE, "assign_status.json")


def logged_in():
    return DEMO or SESSION["ok"]


def init_session():
    """Au démarrage : on ne reprend la session que si « Se souvenir de moi » avait été coché."""
    saved = load_secret(REMEMBER_FILE)
    if saved and load_secret("moodle_token.json"):
        config.UNICA_LOGIN = saved.get("login", "")
        if saved.get("mail"):
            config.MAIL_ADRESSE = outlook.address = saved["mail"]
        SESSION["ok"] = True
    else:
        for name in SESSION_FILES:
            delete_secret(name)  # reste d'une ancienne session : on repart à zéro
    config.UNICA_PASSWORD = ""
    

def forget_unless_remembered():
    if not load_secret(REMEMBER_FILE):
        for name in SESSION_FILES:
            delete_secret(name)


def api_login(payload):
    login = (payload.get("login") or "").strip()
    mail = (payload.get("mail") or "").strip()
    pw = payload.get("password") or ""
    remember = bool(payload.get("remember"))
    if not login:
        raise SourceError("Entre ton identifiant UniCA.")
    if not pw and not (config.MOODLE_TOKEN or load_secret("moodle_token.json")):
        raise SourceError("Entre ton mot de passe.")
    config.UNICA_LOGIN = login
    if mail:
        config.MAIL_ADRESSE = mail
        outlook.address = mail
    moodle.set_credentials(login, pw)
    if pw:
        delete_secret("moodle_token.json")

    def moodle_login():
        moodle.token()
        moodle.site()

    # Moodle et Notes se connectent en parallèle ; un échec de Notes ne bloque pas la connexion
    # (il apparaît comme erreur de la source « Notes » dans la barre latérale).
    pool = ThreadPoolExecutor(max_workers=1)
    notes_job = pool.submit(notes.login, login, pw) if pw and not DEMO else None
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
    config.UNICA_PASSWORD = ""
    if remember:
        save_secret(REMEMBER_FILE, {"login": login, "mail": mail or config.MAIL_ADRESSE})
    else:
        delete_secret(REMEMBER_FILE)
        delete_secret("moodle_token.json")   # le jeton reste seulement en mémoire
    SESSION["ok"] = True
    cache.clear()
    return {"ok": True}


def api_logout():
    SESSION["ok"] = False
    moodle.set_credentials("", "")
    outlook._pending = None
    notes.forget()          # mot de passe et cookies de la passerelle
    sso_session.jar.clear()
    config.UNICA_LOGIN = config.UNICA_PASSWORD = ""
    for name in SESSION_FILES:
        delete_secret(name)
    cache.clear()
    return {"ok": True}


HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
DEFAULT_SECOURS = ["#A58A73", "#7A9CB8", "#969956", "#AE67E4", "#529B85", "#CD8572"]  # si config.py n'en définit pas


def _subject_config():
    """MATIERES et COULEURS_SECOURS de config.py, validés (un ancien config.py sans ces lignes reste valide)."""
    matieres = []
    for i, m in enumerate(getattr(config, "MATIERES", []) or []):
        try:
            motif, nom, couleur = m["motif"], m.get("nom", ""), m["couleur"]
            re.compile(motif)
            if not HEX_COLOR.fullmatch(str(couleur)):
                raise ValueError(f"couleur {couleur!r} invalide (format #RRGGBB attendu)")
        except (re.error, ValueError, KeyError, TypeError, AttributeError) as e:
            print(f"[config] MATIERES[{i}] ignorée : {e}", file=sys.stderr)
            continue
        matieres.append({"motif": motif, "nom": str(nom), "couleur": couleur})
    secours = []
    for c in getattr(config, "COULEURS_SECOURS", []) or []:
        if isinstance(c, str) and HEX_COLOR.fullmatch(c):
            secours.append(c)
        else:
            print(f"[config] COULEURS_SECOURS : {c!r} ignorée (format #RRGGBB attendu)", file=sys.stderr)
    return matieres, secours or DEFAULT_SECOURS


def api_me(_q):
    name = config.PRENOM
    matieres, secours = _subject_config()
    return {
        "matieres": matieres, "couleursSecours": secours,
        "prenom": name, "demo": DEMO, "loggedIn": logged_in(), "login": config.UNICA_LOGIN, "moodleUrl": config.MOODLE_URL,
        "sources": {
            "moodle": DEMO or bool(config.MOODLE_TOKEN or (config.UNICA_LOGIN and config.UNICA_PASSWORD)),
            "ade": DEMO or bool(config.ADE_ICAL_URL),
            "mail": DEMO or outlook.connected(),
            "notes": DEMO or notes.has_password(),
        },
        "mail": outlook.address,
    }


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
    if DEMO:
        return {"events": demo.events(start, end)}
    key = f"ade:{start}:{end}"
    return {"events": cache.get(key, config.CACHE_PLANNING, lambda: ade.events(start, end), force)}


def api_resources(_q, force):
    if DEMO:
        return {"courses": demo.resources()}
    return {"courses": cache.get("res", config.CACHE_MOODLE, moodle.resources, force)}


def api_assignments(_q, force):
    if DEMO:
        return {"assignments": demo.assignments()}
    return {"assignments": cache.get("assign", config.CACHE_MOODLE, moodle.assignments, force)}


def api_mails(_q, force):
    if DEMO:
        return demo.mails()
    return cache.get("mail", config.CACHE_MAILS, outlook.messages, force)


def api_notes(q, force):
    sid = q.get("semestre", [""])[0]
    if sid and not sid.isdigit():
        raise SourceError("Semestre invalide.")
    sid = int(sid) if sid else None
    if DEMO:
        return demo.notes(sid)
    ttl = getattr(config, "CACHE_NOTES", 15 * 60)
    return cache.get(f"notes:{sid}", ttl, lambda: notes.donnees(sid), force)


def api_notes_login(payload):
    """Après une relance avec « Se souvenir de moi », il n'y a plus de mot de passe en mémoire."""
    pw = payload.get("password") or ""
    if not pw:
        raise SourceError("Entre ton mot de passe.")
    notes.login(config.UNICA_LOGIN, pw)
    cache.clear()
    return {"ok": True}


ROUTES = {
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
        if msg == "NOT_CONNECTED":
            return self._json({"error": "Outlook n'est pas connecté.", "code": "mail_not_connected"}, 401)
        if not isinstance(e, SourceError):
            traceback.print_exc()
            msg = f"Erreur inattendue : {e}"
        self._json({"error": msg}, 502)

    def do_GET(self):
        if not self._host_ok():
            return self.send_error(403)
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        force = q.get("refresh", ["0"])[0] == "1"
        depot_get = re.fullmatch(r"/api/assignments/(\d+)/depot", url.path)
        if (url.path in ROUTES or depot_get or url.path in ("/api/file", "/api/mail/auth-url", "/api/notes/pdf")) and not logged_in():
            return self._json({"error": "Connecte-toi d'abord.", "code": "login_required"}, 401)
        try:
            if url.path == "/api/me":
                return self._json(api_me(q))
            if url.path in ROUTES:
                return self._json(ROUTES[url.path](q, force))
            if url.path == "/api/mail/auth-url":
                return self._json({"url": outlook.auth_url()})
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
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            payload = {}
        try:
            if self.path == "/api/login":
                return self._json(api_login(payload))
            if self.path == "/api/logout":
                return self._json(api_logout())
            if self.path == "/api/notes/login":
                if not logged_in():
                    return self._json({"error": "Connecte-toi d'abord.", "code": "login_required"}, 401)
                return self._json(api_notes_login(payload))
            if self.path == "/api/mail/finish":
                outlook.finish_auth(payload.get("url", ""))
                cache.clear()
                return self._json({"ok": True})
            if self.path == "/api/mail/disconnect":
                outlook.disconnect()
                cache.clear()
                return self._json({"ok": True})
        except Exception as e:  # noqa: BLE001
            return self._error(e)
        self.send_error(404)

    def _read_body(self, limit):
        """Lit le corps en flux, en mémoire (jamais sur le disque), sans dépasser la limite annoncée."""
        length = int(self.headers.get("Content-Length") or 0)
        if length > limit:
            self.close_connection = True
            raise SourceError(f"Envoi trop gros ({length // 1048576} Mo) : la limite est de {max(1, limit // 1048576)} Mo.")
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
            upload_max = getattr(config, "UPLOAD_MAX", 100 * 1024 * 1024)
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
        if not full.startswith(WEB_DIR) or not os.path.isfile(full):
            return self.send_error(404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
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


def main():
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    port = config.PORT
    if not DEMO:
        import atexit
        init_session()
        atexit.register(forget_unless_remembered)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        sys.exit(f"\n  Le port {port} est déjà utilisé : le dashboard tourne sans doute déjà.\n"
                 f"  Ferme l'ancienne instance (Linux : pkill -f dashboard.py) ou change PORT dans config.py.\n")
    url = f"http://localhost:{port}/"
    print(f"\n  Dashboard IUT {'(mode démo) ' if DEMO else ''}: {url}")
    print("  Ctrl+C pour arrêter.\n")
    if config.OUVRIR_NAVIGATEUR and "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêté.")


if __name__ == "__main__":
    main()
