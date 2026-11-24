"""Notes : Passerelle ScoDoc de l'IUT (connexion CAS, puis services/data.php).

Rien n'est écrit sur le disque : ni notes, ni mot de passe. Le mot de passe reste en mémoire
pour reconnecter la passerelle quand sa session expire."""
import json
import urllib.parse

from .common import Session, SourceError
from .sso import cas_login

LOGIN_REQUIRED = "NOTES_LOGIN_REQUIRED"
NOT_PUBLISHED = "Le relevé de notes de ce semestre n'est pas publié."


class Notes:
    def __init__(self, cfg, session=None):
        self.cfg = cfg
        self.base = getattr(cfg, "NOTES_URL", "https://iut-notes.unice.fr").rstrip("/")
        self.session = session or Session()
        self._password = ""
        self._semestres = None      # [{id, nom, actuel}], en mémoire seulement
        self._message = ""          # message « relevé non publié » de la passerelle

    # ── Connexion ───────────────────────────────────────────
    def has_password(self):
        return bool(self._password)

    def _has_cookie(self):
        host = self._host()
        return any(host.endswith(c.domain.lstrip(".")) for c in self.session.jar)

    def _host(self):
        return urllib.parse.urlsplit(self.base).hostname or ""

    def login(self, login=None, password=None):
        login = login or self.cfg.UNICA_LOGIN
        if password:
            self._password = password
        if not (login and self._password):
            raise SourceError(LOGIN_REQUIRED)
        host = self._host()
        start = f"{self.base}/services/doAuth.php?href={urllib.parse.quote(self.base + '/')}"
        try:
            url, _ = cas_login(self.session, start, login, self._password,
                               lambda u: (urllib.parse.urlsplit(u).hostname or "") == host,
                               refused="Connexion UniCA refusée : vérifie ton identifiant et ton mot de passe.")
        except OSError as e:
            raise SourceError(f"Passerelle de notes injoignable : {e}")
        if (urllib.parse.urlsplit(url).hostname or "") != host:
            raise SourceError("Connexion à la passerelle de notes impossible (page inattendue).")
        # Comme le fait la page officielle : on vérifie que la passerelle nous reconnaît.
        auth = self._fetch(self._query("donnéesAuthentification"))
        if auth is None or "redirect" in auth:
            raise SourceError("La passerelle de notes n'a pas ouvert de session.")
        if "erreur" in auth:
            raise SourceError(str(auth["erreur"]))

    def forget(self):
        self._password = ""
        self._semestres = None
        self._message = ""
        self.session.jar.clear()

    # ── Requêtes ────────────────────────────────────────────
    @staticmethod
    def _query(q, **params):
        return urllib.parse.urlencode({"q": q, **params}, quote_via=urllib.parse.quote)

    def _fetch(self, query):
        """Une requête, sans reconnexion. Renvoie le JSON, ou None si la réponse n'en est pas."""
        try:
            status, url, headers, body = self.session.request(f"{self.base}/services/data.php?{query}")
        except OSError as e:
            raise SourceError(f"Passerelle de notes injoignable : {e}")
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def _get(self, query, _retry=True):
        if not (self._password or self._has_cookie()):
            raise SourceError(LOGIN_REQUIRED)         # rien à tenter : on demandera le mot de passe
        data = self._fetch(query)
        if data is None or "redirect" in data:        # session expirée
            if not _retry:
                raise SourceError("La session de la passerelle de notes a expiré et la reconnexion a échoué.")
            self.login()                              # LOGIN_REQUIRED s'il n'y a plus de mot de passe
            return self._get(query, _retry=False)
        if "erreur" in data:
            raise SourceError(str(data["erreur"]))
        return data

    # ── Données ─────────────────────────────────────────────
    def donnees(self, semestre_id=None):
        if semestre_id is None:
            raw = self._get(self._query("dataPremièreConnexion"))
            self._remember(raw)
        else:
            if self._semestres is None:
                self._remember(self._get(self._query("dataPremièreConnexion")))
            raw = self._get(self._query("relevéEtudiant", semestre=semestre_id))
        return {"semestres": self._semestres, "releve": normaliser_releve(_releve(raw), self._message)}

    def _remember(self, raw):
        self._semestres = normaliser_semestres(raw.get("semestres") or [])
        self._message = str((raw.get("config") or {}).get("message_non_publication_releve") or "")


# ── Normalisation ───────────────────────────────────────────
def _releve(raw):
    """Le relevé est sous la clé « relevé » (parfois imbriqué une seconde fois)."""
    rel = raw.get("relevé") or raw.get("releve") or {}
    while isinstance(rel, dict) and isinstance(rel.get("relevé"), dict):
        rel = rel["relevé"]
    return rel if isinstance(rel, dict) else {}


def _num(v):
    """'16.25' -> 16.25 ; '~', '', None, 'ABS'... -> None."""
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None else None


def normaliser_semestres(liste):
    out = []
    for s in liste:
        num = s.get("semestre_id")
        annee = s.get("annee_scolaire") or ""
        out.append({"id": s.get("formsemestre_id"),
                    "nom": f"Semestre {num} ({annee})" if annee else f"Semestre {num}",
                    "actuel": False})
    if out:
        out[-1]["actuel"] = True   # du plus ancien au plus récent : le dernier est en cours
    return out


def _stats(d, promo):
    d = d if isinstance(d, dict) else {}
    return {"min": _num(d.get("min")) if promo else None,
            "moy": _num(d.get("moy")) if promo else None,
            "max": _num(d.get("max")) if promo else None}


def _rang(d, visible, key="rang"):
    """Le rang d'une UE ou d'un module est dans « rang » ; celui du semestre est dans « value »."""
    d = d if isinstance(d, dict) else {}
    r, t = (_int(d.get(key)), _int(d.get("total"))) if visible else (None, None)
    return (r, t) if r is not None and t else (None, None)


def _is_bonus(code, ue):
    return (str(code).upper().startswith("BONS") or ue.get("type") not in (0, None)
            or not isinstance(ue.get("moyenne"), dict))


def normaliser_releve(rel, message=""):
    opts = rel.get("options") or {}
    promo = bool(opts.get("show_minmax") or opts.get("show_moypromo"))
    options = {"rangs": bool(opts.get("show_rangs")), "rangs_ue": bool(opts.get("show_ue_rangs")),
               "rangs_modules": bool(opts.get("show_mod_rangs")), "promo": promo}
    out = {"publie": bool(rel.get("publie", True)), "message": "", "options": options,
           "semestre": None, "ues": [], "modules": []}
    if not out["publie"] or not rel.get("semestre"):
        out["publie"] = False
        out["message"] = str(rel.get("message") or message or NOT_PUBLISHED)
        return out

    sem = rel["semestre"]
    notes = sem.get("notes") or {}
    show_avg = opts.get("show_moyenne_generale_but", True) and not opts.get("block_moyenne_generale")
    rang, total = _rang(sem.get("rang"), options["rangs"], key="value")
    ects = sem.get("ECTS") or {}
    ab = sem.get("absences") or {}
    semestre = {
        "numero": sem.get("numero"),
        "moyenne": _num(notes.get("value")) if show_avg else None,
        "rang": rang, "total": total, **_stats(notes, promo),
        "ects_acquis": _num(ects.get("acquis")) if opts.get("show_ects", True) else None,
        "ects_total": _num(ects.get("total")) if opts.get("show_ects", True) else None,
        "bonus": None,
        "absences": ({"total": _num(ab.get("total")) or 0, "injustifiees": _num(ab.get("injustifie")) or 0,
                      "unite": ab.get("metrique") or "Heure(s)"} if opts.get("show_abs", True) and ab else None),
    }

    ressources, saes = rel.get("ressources") or {}, rel.get("saes") or {}
    titres = {c: (m.get("titre") or c) for c, m in {**ressources, **saes}.items()}
    types = {**{c: "ressource" for c in ressources}, **{c: "sae" for c in saes}}
    moyennes = {}   # moyenne d'un module d'après les UE (le relevé n'en donne pas toujours)

    ues = []
    bonus = 0.0
    for code, ue in (rel.get("ues") or {}).items():
        if _is_bonus(code, ue):
            bonus += _num(ue.get("bonus")) or 0
            continue
        mods = []
        for kind in ("ressources", "saes"):
            for mcode, m in (ue.get(kind) or {}).items():
                coef = _num(m.get("coef"))
                moy = _num(m.get("moyenne"))
                if moy is not None:
                    moyennes.setdefault(mcode, moy)
                if coef:
                    mods.append({"code": mcode, "titre": titres.get(mcode, mcode),
                                 "type": types.get(mcode, "ressource" if kind == "ressources" else "sae"),
                                 "coef": coef, "moyenne": moy})
        m = ue.get("moyenne") or {}
        r, t = _rang(m, options["rangs_ue"])
        e = ue.get("ECTS") or {}
        titre = str(ue.get("titre") or code)
        if titre.startswith(str(code)):
            titre = titre[len(str(code)):].strip(" -–:") or titre
        ues.append({"code": code, "titre": titre, "couleur": ue.get("color") or "#888888",
                    "moyenne": _num(m.get("value")), "rang": r, "total": t, **_stats(m, promo),
                    "bonus": _num(ue.get("bonus")) or 0.0, "malus": _num(ue.get("malus")) or 0.0,
                    "ects_acquis": _num(e.get("acquis")), "ects_total": _num(e.get("total")), "modules": mods})
    semestre["bonus"] = bonus or None
    ues.sort(key=lambda u: u["code"])

    modules = []
    for code, m in {**ressources, **saes}.items():
        mm = m.get("moyenne") if isinstance(m.get("moyenne"), dict) else {}
        r, t = _rang(mm, options["rangs_modules"])
        stats = _stats(mm, promo and opts.get("show_minmax_mod", True))
        evals = []
        for ev in m.get("evaluations") or []:
            n = ev.get("note")
            n = n if isinstance(n, dict) else {"value": n}
            s = _stats(n, promo and opts.get("show_minmax_eval", True))
            evals.append({"id": ev.get("id"), "titre": ev.get("description") or "Évaluation",
                          "date": (ev.get("date_debut") or ev.get("date") or "")[:10] or None,
                          "coef": _num(ev.get("coef")), "note": _num(n.get("value")), **s,
                          "poids": {k: _num(v) or 0 for k, v in (ev.get("poids") or {}).items()}})
        evals.sort(key=lambda x: (x["date"] or "", x["id"] or 0))
        modules.append({"code": code, "titre": titres.get(code, code), "type": types[code],
                        "moyenne": _num(mm.get("value")) if _num(mm.get("value")) is not None else moyennes.get(code),
                        "rang": r, "total": t, **stats, "evaluations": evals})
    modules.sort(key=lambda m: (m["type"] == "sae", m["code"]))

    out.update(semestre=semestre, ues=ues, modules=modules)
    return out
