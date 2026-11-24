"""Outils partagés : client HTTP avec cookies, parseur de formulaires, cache."""
import http.cookiejar
import json
import os
import re
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


# ── multipart/form-data (sans dépendance) ───────────────────
def _quote_disp(value):
    """Valeur entre guillemets d'un en-tête Content-Disposition (RFC 7578 : %22, %0D, %0A)."""
    return str(value).replace('"', "%22").replace("\r", "%0D").replace("\n", "%0A")


def encode_multipart(fields, files):
    """fields : {nom: valeur} ; files : [(champ, nom_de_fichier, octets)]. Renvoie (corps, Content-Type)."""
    boundary = "----iutdash" + os.urandom(12).hex()
    out = []
    for name, value in fields.items():
        out.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{_quote_disp(name)}"\r\n\r\n'.encode("utf-8"))
        out.append(str(value).encode("utf-8") + b"\r\n")
    for field, filename, data in files:
        out.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{_quote_disp(field)}"; '
                    f'filename="{_quote_disp(filename)}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode("utf-8"))
        out.append(bytes(data) + b"\r\n")
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def parse_multipart(body, content_type):
    """Inverse d'encode_multipart. Renvoie (champs {nom: texte}, fichiers [(champ, nom, octets)])."""
    m = re.search(r'boundary="?([^";]+)"?', content_type or "")
    if not m:
        raise SourceError("Requête multipart invalide.")
    delim = b"--" + m.group(1).encode()
    fields, files = {}, []
    for part in body.split(delim)[1:]:
        if part.startswith(b"--"):
            break
        head, sep, data = part.lstrip(b"\r\n").partition(b"\r\n\r\n")
        if not sep:
            continue
        data = data[:-2] if data.endswith(b"\r\n") else data
        header = head.decode("utf-8", "replace")
        name = re.search(r'name="([^"]*)"', header)
        filename = re.search(r'filename="([^"]*)"', header)
        unq = lambda v: urllib.parse.unquote(v, errors="replace") if re.search(r"%(22|0D|0A)", v) else v  # noqa: E731
        if not name:
            continue
        if filename:
            files.append((unq(name.group(1)), unq(filename.group(1)), data))
        else:
            fields[unq(name.group(1))] = data.decode("utf-8", "replace")
    return fields, files


def http_post_multipart(url, fields, files, timeout=300):
    """Envoie un formulaire multipart et renvoie le JSON de la réponse."""
    body, ctype = encode_multipart(fields, files)
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raw = e.read() if e.fp else b""
        if not raw.lstrip().startswith((b"{", b"[")):
            raise SourceError(f"HTTP {e.code} sur {url}")
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        raise SourceError("Réponse illisible de Moodle pendant l'envoi.")


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
