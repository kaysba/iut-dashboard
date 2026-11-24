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
import sys
import threading
import traceback
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.version_info < (3, 8):
    sys.exit("Python 3.8 ou plus récent est nécessaire.")

import config
from sources import demo
from sources.ade import ADE
from sources.common import UA, SourceError, TTLCache, delete_secret, load_secret, save_secret
from sources.moodle import Moodle
from sources.outlook import Outlook

DEMO = "--demo" in sys.argv


WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

moodle = Moodle(config)
ade = ADE(config)
outlook = Outlook(config)
cache = TTLCache()


SESSION = {"ok": False}   # connecté pendant cette exécution ?
REMEMBER_FILE = "remember.json"
SESSION_FILES = ("moodle_token.json", "outlook_token.json", REMEMBER_FILE)


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
    try:
        moodle.token()
        moodle.site()
    except OSError as e:
        moodle.set_credentials("", "")
        raise SourceError(f"Moodle injoignable : {e}")
    except SourceError:
        moodle.set_credentials("", "")
        raise
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
    config.UNICA_LOGIN = config.UNICA_PASSWORD = ""
    for name in SESSION_FILES:
        delete_secret(name)
    cache.clear()
    return {"ok": True}


def api_me(_q):
    name = config.PRENOM
    return {
        "prenom": name, "demo": DEMO, "loggedIn": logged_in(), "login": config.UNICA_LOGIN, "moodleUrl": config.MOODLE_URL,
        "sources": {
            "moodle": DEMO or bool(config.MOODLE_TOKEN or (config.UNICA_LOGIN and config.UNICA_PASSWORD)),
            "ade": DEMO or bool(config.ADE_ICAL_URL),
            "mail": DEMO or outlook.connected(),
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


ROUTES = {
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
        if (url.path in ROUTES or url.path in ("/api/file", "/api/mail/auth-url")) and not logged_in():
            return self._json({"error": "Connecte-toi d'abord.", "code": "login_required"}, 401)
        try:
            if url.path == "/api/me":
                return self._json(api_me(q))
            if url.path in ROUTES:
                return self._json(ROUTES[url.path](q, force))
            if url.path == "/api/mail/auth-url":
                return self._json({"url": outlook.auth_url(manual=True)})
            if url.path == "/oauth/callback":
                return self._oauth_callback()
            if url.path == "/api/file":
                return self._file(q.get("u", [""])[0])
        except Exception as e:  # noqa: BLE001
            return self._error(e)
        return self._static(url.path)

    def do_POST(self):
        if not self._host_ok():
            return self.send_error(403)
        origin = self.headers.get("Origin", "")
        if origin and urllib.parse.urlsplit(origin).hostname not in ("127.0.0.1", "localhost"):
            return self.send_error(403)
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

    def _oauth_callback(self):
        try:
            outlook.finish_auth(self.path)
            cache.clear()
        except Exception as e:  # noqa: BLE001
            import html as _h
            body = ("<meta charset=utf-8><body style='font:16px system-ui;max-width:520px;margin:12vh auto'>"
                    f"<h2>Connexion Outlook impossible</h2><p>{_h.escape(str(e))}</p>"
                    "<p><a href='/#/mails'>Retour au dashboard</a></p>").encode()
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(302)
        self.send_header("Location", "/#/mails")
        self.end_headers()

    def _file(self, fileurl):
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
