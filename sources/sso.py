"""Connexion au CAS de l'université, commune à Moodle et à la passerelle de notes."""
import html
import threading
import urllib.parse

from .common import SourceError, parse_html

_guard = threading.Lock()


def _lock_for(session):
    """Un verrou par session : si Moodle et Notes se connectent en même temps, le second
    attend la fin du premier et profite du cookie du CAS au lieu de renvoyer le mot de passe."""
    with _guard:
        if not hasattr(session, "sso_lock"):
            session.sso_lock = threading.Lock()
        return session.sso_lock


def submit_form(session, url, form, fields):
    action = urllib.parse.urljoin(url, html.unescape(form["action"])) if form["action"] else url
    if form["method"] == "post":
        return session.request(action, data=fields)
    sep = "&" if "?" in action else "?"
    return session.request(action + sep + urllib.parse.urlencode(fields))


def cas_login(session, start_url, login, password, done, follow_link=None,
              refused="Connexion UniCA refusée : vérifie ton identifiant et ton mot de passe."):
    """Part de start_url, suit les redirections, remplit le formulaire contenant un mot de passe
    et soumet les formulaires auto-postés (SAML, relais SSO), jusqu'à ce que done(url) soit vrai.

    follow_link(url, page) peut renvoyer un lien à suivre (bouton CAS d'un site) ou None.
    Renvoie (url, corps) de la dernière page ; l'appelant vérifie done(url) si l'arrêt est suspect.
    Lève SourceError(refused) si le CAS redemande le mot de passe après l'avoir reçu."""
    with _lock_for(session):
        status, url, headers, body = session.request(start_url)
        password_sent = 0
        for _ in range(15):
            if done(url):
                break  # connecté
            page = parse_html(body)

            # 1. Sur le site visé : suivre le bouton CAS / SSO
            link = follow_link(url, page) if follow_link else None
            if link:
                status, url, headers, body = session.request(urllib.parse.urljoin(url, html.unescape(link)))
                continue

            # 2. Formulaire avec mot de passe : on le remplit
            form = next((f for f in page.forms if any(i["type"] == "password" for i in f["inputs"])), None)
            if form:
                if password_sent >= 1:
                    raise SourceError(refused)
                fields = {}
                user_field = None
                for i in form["inputs"]:
                    if not i["name"]:
                        continue
                    if i["type"] == "password":
                        fields[i["name"]] = password
                    elif i["type"] in ("text", "email") and user_field is None:
                        user_field = i["name"]
                        fields[i["name"]] = login
                    elif i["type"] in ("hidden",):
                        fields[i["name"]] = i["value"]
                    elif i["type"] == "submit" and i["name"] and i["name"] not in fields:
                        fields[i["name"]] = i["value"]
                password_sent += 1
                status, url, headers, body = submit_form(session, url, form, fields)
                continue

            # 3. Formulaire auto-posté (SAML, relais SSO)
            auto = next((f for f in page.forms if f["inputs"] and all(
                i["type"] in ("hidden", "submit") for i in f["inputs"])), None)
            if auto:
                fields = {i["name"]: i["value"] for i in auto["inputs"] if i["name"] and i["type"] == "hidden"}
                status, url, headers, body = submit_form(session, url, auto, fields)
                continue
            break
        return url, body
