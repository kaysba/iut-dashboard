"""Mails Outlook / Microsoft 365 en IMAP + OAuth2.

Microsoft a désactivé la connexion IMAP par mot de passe : il faut un jeton OAuth.
On se connecte une seule fois dans le navigateur ; le jeton se renouvelle ensuite tout seul.
"""
import base64
import email
import email.header
import email.utils
import hashlib
import html
import imaplib
import re
import secrets
import time
import urllib.parse

from .common import SourceError, delete_secret, http_post_json, load_secret, save_secret
from .defaults import opt

TOKEN_FILE = "outlook_token.json"
SCOPE = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"
IMAP_HOST = "outlook.office365.com"


class Outlook:
    def __init__(self, cfg):
        self.address = opt(cfg, "MAIL_ADRESSE")
        self.count = opt(cfg, "MAIL_NOMBRE")
        self.client_id = opt(cfg, "MS_CLIENT_ID")
        self.tenant = opt(cfg, "MS_TENANT")
        self.redirect_uri = opt(cfg, "MS_REDIRECT_URI")
        self._pending = None  # (state, verifier, redirect_uri)

    @property
    def authority(self):
        return f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0"

    def connected(self):
        return bool(load_secret(TOKEN_FILE))

    # ── Connexion (une fois) ────────────────────────────────
    def auth_url(self):
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        self._pending = (state, verifier, self.redirect_uri)
        q = {
            "client_id": self.client_id, "response_type": "code", "redirect_uri": self.redirect_uri,
            "response_mode": "query", "scope": SCOPE, "state": state, "login_hint": self.address,
            "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account",
        }
        return f"{self.authority}/authorize?{urllib.parse.urlencode(q)}"

    def finish_auth(self, pasted_url):
        if not self._pending:
            raise SourceError("Clique d'abord sur « Ouvrir la connexion Microsoft », puis colle l'adresse obtenue.")
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(pasted_url.strip()).query))
        if "error" in q:
            raise SourceError(f"Microsoft a refusé : {q.get('error_description', q['error'])}")
        if q.get("state") != self._pending[0] or "code" not in q:
            raise SourceError("Adresse collée incorrecte : copie toute l'adresse de l'onglet (https://localhost/?code=…)")
        tok = http_post_json(f"{self.authority}/token", {
            "client_id": self.client_id, "grant_type": "authorization_code", "code": q["code"],
            "redirect_uri": self._pending[2], "code_verifier": self._pending[1], "scope": SCOPE,
        })
        self._store(tok)
        self._pending = None

    def disconnect(self):
        delete_secret(TOKEN_FILE)

    def _store(self, tok):
        if "access_token" not in tok:
            raise SourceError(f"Connexion Outlook échouée : {tok.get('error_description', tok)}"[:400])
        old = load_secret(TOKEN_FILE) or {}
        save_secret(TOKEN_FILE, {
            "access_token": tok["access_token"],
            "refresh_token": tok.get("refresh_token") or old.get("refresh_token"),
            "expires_at": time.time() + int(tok.get("expires_in", 3600)) - 120,
        })

    def _access_token(self):
        t = load_secret(TOKEN_FILE)
        if not t:
            raise SourceError("NOT_CONNECTED")
        if time.time() < t["expires_at"]:
            return t["access_token"]
        tok = http_post_json(f"{self.authority}/token", {
            "client_id": self.client_id, "grant_type": "refresh_token",
            "refresh_token": t["refresh_token"], "scope": SCOPE,
        })
        if "access_token" not in tok:
            delete_secret(TOKEN_FILE)
            raise SourceError("NOT_CONNECTED")
        self._store(tok)
        return tok["access_token"]

    # ── Lecture des mails ───────────────────────────────────
    def messages(self):
        token = self._access_token()
        auth = f"user={self.address}\x01auth=Bearer {token}\x01\x01".encode()
        try:
            imap = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=25)
            imap.authenticate("XOAUTH2", lambda _: auth)
        except imaplib.IMAP4.error as e:
            raise SourceError(f"Outlook a refusé la connexion IMAP : {e}")
        try:
            imap.select("INBOX", readonly=True)
            _, data = imap.uid("search", None, "ALL")
            uids = data[0].split()[-self.count:]
            _, unseen = imap.uid("search", None, "UNSEEN")
            unread_total = len(unseen[0].split()) if unseen and unseen[0] else 0
            out = []
            if uids:
                _, rows = imap.uid("fetch", b",".join(uids), "(FLAGS BODY.PEEK[]<0.60000>)")
                for i in range(0, len(rows)):
                    row = rows[i]
                    if not isinstance(row, tuple):
                        continue
                    meta, raw = row
                    out.append(_shape(meta, raw))
            out.sort(key=lambda m: m["date"], reverse=True)
            return {"unread": unread_total, "messages": out,
                    "webmail": "https://outlook.office.com/mail/inbox"}
        finally:
            try:
                imap.logout()
            except Exception:
                pass


def _decode(value):
    if not value:
        return ""
    parts = []
    for text, enc in email.header.decode_header(value):
        if isinstance(text, bytes):
            parts.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts).strip()


def _snippet(msg):
    plain, htm = None, None
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and htm is None:
            htm = text
    text = plain
    if not text and htm:
        text = re.sub(r"(?is)<(style|script).*?</\1>", " ", htm)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:220]


def _body(msg):
    """Texte complet du mail (sans HTML), avec les retours à la ligne."""
    plain, htm = None, None
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and htm is None:
            htm = text
    text = plain
    if not text and htm:
        text = re.sub(r"(?is)<(style|script|head).*?</\1>", " ", htm)
        text = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", text)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = (text or "").replace("\r", "").replace("\xa0", " ")
    text = "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:20000]


def _shape(meta, raw):
    msg = email.message_from_bytes(raw)
    name, addr = email.utils.parseaddr(_decode(msg.get("From")))
    try:
        date = email.utils.parsedate_to_datetime(msg.get("Date")).timestamp()
    except Exception:
        date = 0
    has_attach = any(p.get_filename() for p in msg.walk())
    return {
        "from": name or addr, "fromAddr": addr,
        "subject": _decode(msg.get("Subject")) or "(sans objet)",
        "date": date,
        "unread": b"\\Seen" not in meta,
        "snippet": _snippet(msg),
        "body": _body(msg),
        "attachment": has_attach,
    }
