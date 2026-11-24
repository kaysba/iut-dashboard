"""Outils partagés : client HTTP avec cookies, parseur de formulaires, cache."""
import http.cookiejar
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class SourceError(Exception):
    """Erreur lisible, affichée telle quelle dans le dashboard."""


# ── Stockage local (jetons) ─────────────────────────────────
def load_secret(name):
    path = os.path.join(CACHE_DIR, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_secret(name, data):
    path = os.path.join(CACHE_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def delete_secret(name):
    try:
        os.remove(os.path.join(CACHE_DIR, name))
    except OSError:
        pass


# ── HTTP ─────────────────────────────────────────────────────
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Session:
    """Petit équivalent de requests.Session, sans dépendance."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        cookies = urllib.request.HTTPCookieProcessor(self.jar)
        self.opener = urllib.request.build_opener(cookies)
        self.opener_noredirect = urllib.request.build_opener(cookies, _NoRedirect())

    def request(self, url, data=None, follow=True, timeout=25, headers=None):
        if isinstance(data, dict):
            data = urllib.parse.urlencode(data, doseq=True).encode()
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        opener = self.opener if follow else self.opener_noredirect
        try:
            resp = opener.open(req, timeout=timeout)
            return resp.status, resp.geturl(), dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            # Sans suivi de redirection, un 30x arrive ici : on le renvoie normalement.
            return e.code, url, dict(e.headers or {}), e.read() if e.fp else b""


def http_get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_post_json(url, data, timeout=25):
    body = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except ValueError:
            raise SourceError(f"HTTP {e.code} sur {url}")


# ── Parseur de formulaires HTML ─────────────────────────────
class FormParser(HTMLParser):
    """Récupère les <form>, leurs <input> et les liens <a href>."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.links = []
        self._form = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._form = {"action": a.get("action") or "", "method": (a.get("method") or "get").lower(),
                          "id": a.get("id") or "", "inputs": []}
            self.forms.append(self._form)
        elif tag in ("input", "button") and self._form is not None:
            self._form["inputs"].append({
                "name": a.get("name"), "value": a.get("value") or "",
                "type": (a.get("type") or ("submit" if tag == "button" else "text")).lower(),
            })
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None


def parse_html(html_bytes):
    p = FormParser()
    p.feed(html_bytes.decode("utf-8", errors="replace"))
    return p


# ── Cache mémoire avec durée de vie ─────────────────────────
class TTLCache:
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key, ttl, producer, force=False):
        now = time.time()
        with self._lock:
            hit = self._data.get(key)
        if hit and not force and now - hit[0] < ttl:
            return hit[1]
        value = producer()
        with self._lock:
            self._data[key] = (now, value)
        return value

    def clear(self):
        with self._lock:
            self._data.clear()
