"""Options du dashboard : une seule fonction, opt("NOM").

Ordre de priorité pour chaque option :
  1. les réglages faits dans la page (.cache/settings.json) ;
  2. config.py, s'il existe (utilisateurs avancés, anciennes installations) ;
  3. les valeurs par défaut (sources/defaults.py).

settings.json ne contient que des réglages (lien ADE, adresse mail, couleurs, cours masqués, thème,
préférences avancées) : jamais de mot de passe ni de jeton de connexion. Chaque valeur est validée
avant d'être enregistrée ; une clé inconnue est refusée.
"""
import copy
import json
import os
import re
import sys
import threading
import urllib.parse

from . import common
from .defaults import DEFAULTS

FICHIER = "settings.json"
ADE_DOMAINE = "univ-cotedazur.fr"

_lock = threading.Lock()
_config = None          # module config.py (ou None)
_reglages = {}          # contenu de settings.json, en mémoire
_memoire_seule = False  # démo : rien n'est écrit sur le disque
_marque_memoire = [False]  # démo : l'assistant a été fait


class ReglageInvalide(common.SourceError):
    status = 400


# ── Lecture ─────────────────────────────────────────────────
def opt(nom):
    """Valeur de l'option `nom` : réglage de la page, sinon config.py, sinon valeur par défaut.
    Renvoie toujours une copie : modifier le résultat ne change pas l'option."""
    if nom not in DEFAULTS:
        raise KeyError(nom)
    with _lock:
        if nom in _reglages:
            return copy.deepcopy(_reglages[nom])
    if _config is not None and hasattr(_config, nom):
        return copy.deepcopy(getattr(_config, nom))
    return copy.deepcopy(DEFAULTS[nom])


def charger_config():
    """Importe config.py s'il existe. Sans lui, le dashboard démarre avec les valeurs par défaut."""
    try:
        import config as module  # noqa: PLC0415
    except ModuleNotFoundError as e:
        if e.name != "config":
            raise
        return None
    return module


def utiliser_config(module):
    """Choisit la source « config.py » (un module, un SimpleNamespace dans les tests, ou None)."""
    global _config
    _config = module


def config_actuelle():
    return _config


def chemin():
    return os.path.join(common.CACHE_DIR, FICHIER)


def charger(memoire_seule=False):
    """Relit settings.json. En mémoire seule (démo), on part de zéro et rien n'est écrit."""
    global _reglages, _memoire_seule
    _memoire_seule = memoire_seule
    data = {}
    if not memoire_seule:
        try:
            with open(chemin(), encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except (OSError, ValueError) as e:
            print(f"[réglages] {FICHIER} illisible, ignoré : {e}", file=sys.stderr)
            data = {}
    propres = {}
    for nom, valeur in (data.items() if isinstance(data, dict) else []):
        try:
            propres[nom] = valider(nom, valeur)
        except ReglageInvalide as e:
            print(f"[réglages] {nom} ignoré : {e}", file=sys.stderr)
    with _lock:
        _reglages = propres


def existe():
    """Vrai si la page a déjà enregistré des réglages (l'assistant a été fait au moins une fois)."""
    if _memoire_seule:
        return bool(_reglages) or _marque_memoire[0]
    return os.path.isfile(chemin())


def tout():
    with _lock:
        return copy.deepcopy(_reglages)


# ── Écriture ────────────────────────────────────────────────
def enregistrer(changements):
    """Valide puis enregistre {NOM: valeur}. None remet l'option à sa valeur de config.py ou par défaut.
    Tout ou rien : une seule valeur invalide et rien n'est enregistré. Renvoie les noms modifiés."""
    if not isinstance(changements, dict):
        raise ReglageInvalide("Réglages attendus sous forme d'objet JSON.")
    propres = {}
    for nom, valeur in changements.items():
        propres[nom] = None if valeur is None and nom in VALIDATEURS else valider(nom, valeur)
    with _lock:
        nouveau = dict(_reglages)
        for nom, valeur in propres.items():
            if valeur is None:
                nouveau.pop(nom, None)
            else:
                nouveau[nom] = valeur
        _ecrire(nouveau)
        _reglages.clear()
        _reglages.update(nouveau)
    return list(propres)


def marquer():
    """Crée settings.json (vide si besoin) : l'assistant ne réapparaîtra plus."""
    with _lock:
        if _memoire_seule:
            _marque_memoire[0] = True
        elif not os.path.isfile(chemin()):
            _ecrire(dict(_reglages))


def oublier():
    """Vide les réglages en mémoire (après « Tout effacer de cet ordinateur »)."""
    with _lock:
        _reglages.clear()
        _marque_memoire[0] = False


def _ecrire(data):
    if _memoire_seule:
        return
    common.ecrire_prive(chemin(), json.dumps(data, ensure_ascii=False, indent=1))


# ── Validation ──────────────────────────────────────────────
COULEUR = re.compile(r"#[0-9A-Fa-f]{6}")
MAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _texte(nom, v, maxi=200):
    if not isinstance(v, str):
        raise ReglageInvalide(f"{nom} : texte attendu.")
    v = v.strip()
    if len(v) > maxi or any(ord(c) < 32 for c in v):
        raise ReglageInvalide(f"{nom} : texte trop long ou caractères invalides.")
    return v


def _entier(mini, maxi, message=None):
    def f(nom, v):
        if isinstance(v, bool) or not isinstance(v, int) or not mini <= v <= maxi:
            raise ReglageInvalide(message or f"{nom} : nombre entier entre {mini} et {maxi} attendu.")
        return v
    return f


def couleur(nom, v):
    if not isinstance(v, str) or not COULEUR.fullmatch(v):
        raise ReglageInvalide(f"{nom} : couleur {v!r} invalide (format #RRGGBB attendu).")
    return v.upper()


def motif(nom, v):
    v = _texte(nom, v, 300)
    if not v:
        raise ReglageInvalide(f"{nom} : motif vide.")
    try:
        re.compile(v)
    except re.error as e:
        raise ReglageInvalide(f"{nom} : motif {v!r} invalide ({e}).")
    return v


def valider_lien_ade(nom, v):
    v = _texte(nom, v, 2000)
    if not v:
        return ""
    parts = urllib.parse.urlsplit(v)
    hote = (parts.hostname or "").lower()
    if parts.scheme != "https" or not (hote == ADE_DOMAINE or hote.endswith("." + ADE_DOMAINE)):
        raise ReglageInvalide(f"Le lien ADE doit commencer par https:// et venir de {ADE_DOMAINE}.")
    return v


def _mail(nom, v):
    v = _texte(nom, v, 254)
    if v and not MAIL.fullmatch(v):
        raise ReglageInvalide(f"Adresse mail {v!r} invalide.")
    return v


def _matieres(nom, v):
    if not isinstance(v, list) or len(v) > 100:
        raise ReglageInvalide(f"{nom} : liste de matières attendue.")
    out = []
    for i, m in enumerate(v):
        if not isinstance(m, dict) or set(m) - {"motif", "nom", "couleur"}:
            raise ReglageInvalide(f"{nom}[{i}] : clés attendues motif, nom, couleur.")
        out.append({"motif": motif(f"{nom}[{i}].motif", m.get("motif")),
                    "nom": _texte(f"{nom}[{i}].nom", m.get("nom", ""), 80),
                    "couleur": couleur(f"{nom}[{i}].couleur", m.get("couleur"))})
    return out


def _couleurs(nom, v):
    if not isinstance(v, list) or not 0 < len(v) <= 50:
        raise ReglageInvalide(f"{nom} : liste de couleurs attendue.")
    return [couleur(nom, c) for c in v]


def _mots(nom, v):
    if not isinstance(v, list) or len(v) > 200:
        raise ReglageInvalide(f"{nom} : liste de mots attendue.")
    return [m for m in (_texte(nom, x, 120) for x in v) if m]


def _theme(nom, v):
    if v not in ("system", "light", "dark"):
        raise ReglageInvalide(f"{nom} : system, light ou dark attendu.")
    return v


VALIDATEURS = {
    "ADE_ICAL_URL": valider_lien_ade,
    "MAIL_ADRESSE": _mail,
    "MATIERES": _matieres,
    "COULEURS_SECOURS": _couleurs,
    "COURS_MASQUES": _mots,
    "THEME": _theme,
    "PORT": _entier(1024, 65535, "Le port doit être un nombre entre 1024 et 65535."),
    "CACHE_PLANNING": _entier(0, 86400),
    "CACHE_MOODLE": _entier(0, 86400),
    "CACHE_MAILS": _entier(0, 86400),
    "CACHE_NOTES": _entier(0, 86400),
}


def valider(nom, valeur):
    if nom not in VALIDATEURS:
        raise ReglageInvalide(f"Réglage inconnu : {str(nom)[:60]}.")
    return VALIDATEURS[nom](nom, valeur)


# ── Affichage du lien ADE ───────────────────────────────────
def masquer_lien(url):
    """Lien ADE sans son jeton : …anonymous_cal.jsp?data=3eee…0aeeb. Le lien entier ne quitte jamais le serveur."""
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url)
    page = parts.path.rsplit("/", 1)[-1] or parts.hostname or ""
    params = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    garde = [(k, v) for k, v in params if k not in ("firstDate", "lastDate", "calType", "projectId", "nbWeeks")]
    if not garde:
        return f"…{page}"
    k, v = garde[0]
    v = v if len(v) <= 8 else f"{v[:4]}…{v[-5:]}"
    return f"…{page}?{k}={v}" + ("&…" if len(garde) > 1 else "")
