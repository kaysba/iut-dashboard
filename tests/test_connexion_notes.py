#!/usr/bin/env python3
"""Test de connexion à la passerelle de notes (iut-notes.unice.fr).

À lancer depuis la racine du projet :
    python tests/test_connexion_notes.py

Ce script :
  1. se connecte au CAS UniCA avec ton identifiant et ton mot de passe ;
  2. vérifie que la passerelle renvoie bien tes données ;
  3. affiche un résumé (semestres, UE, moyennes, rangs) ;
  4. enregistre une copie ANONYMISÉE de la réponse dans tests/fixtures/,
     pour servir de données de test au développement.

Rien n'est envoyé ailleurs que vers le CAS et la passerelle de l'université.
Le mot de passe n'est ni affiché ni enregistré.
"""
import getpass
import html
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sources.common import Session, parse_html  # noqa: E402

BASE = os.environ.get("NOTES_BASE", "https://iut-notes.unice.fr")
FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures")

OK, KO, INFO = "  [ok] ", "  [!!] ", "       "


def q(name):
    return urllib.parse.quote(name)


def cas_login(s, start_url, login, password, back_host):
    """Suit les redirections jusqu'au CAS, remplit le formulaire, revient sur back_host."""
    status, url, headers, body = s.request(start_url)
    sent = False
    for _ in range(15):
        host = urllib.parse.urlsplit(url).hostname or ""
        if host == back_host:
            return url, body
        page = parse_html(body)
        form = next((f for f in page.forms if any(i["type"] == "password" for i in f["inputs"])), None)
        if form:
            if sent:
                raise RuntimeError("Le CAS a refusé l'identifiant ou le mot de passe "
                                   "(ou une double authentification est demandée).")
            print(f"{INFO}Formulaire de connexion trouvé sur {host}")
            print(f"{INFO}Champs : {', '.join(i['name'] for i in form['inputs'] if i['name'])}")
            fields, user_done = {}, False
            for i in form["inputs"]:
                if not i["name"]:
                    continue
                if i["type"] == "password":
                    fields[i["name"]] = password
                elif i["type"] in ("text", "email") and not user_done:
                    fields[i["name"]] = login
                    user_done = True
                elif i["type"] == "hidden":
                    fields[i["name"]] = i["value"]
                elif i["type"] == "submit" and i["name"]:
                    fields.setdefault(i["name"], i["value"])
            action = urllib.parse.urljoin(url, html.unescape(form["action"])) if form["action"] else url
            sent = True
            status, url, headers, body = s.request(action, data=fields) if form["method"] == "post" \
                else s.request(action + ("&" if "?" in action else "?") + urllib.parse.urlencode(fields))
            continue
        auto = next((f for f in page.forms if f["inputs"] and all(
            i["type"] in ("hidden", "submit") for i in f["inputs"])), None)
        if auto:
            fields = {i["name"]: i["value"] for i in auto["inputs"] if i["name"] and i["type"] == "hidden"}
            action = urllib.parse.urljoin(url, html.unescape(auto["action"]))
            status, url, headers, body = s.request(action, data=fields)
            continue
        raise RuntimeError(f"Page inattendue pendant la connexion : {url} (HTTP {status})")
    raise RuntimeError("Trop de redirections pendant la connexion.")


def get_json(s, query):
    status, url, headers, body = s.request(f"{BASE}/services/data.php?{query}")
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError:
        raise RuntimeError(f"Réponse non JSON (HTTP {status}, {url}) : {body[:200]!r}")


# ── Anonymisation ────────────────────────────────────────────
PERSONAL_KEYS = {
    "nom", "prenom", "nomprenom", "nom_usuel", "nom_disp", "civilite", "civilite_str",
    "code_nip", "code_ine", "nip", "ine", "etudid", "email", "emailperso", "mail",
    "date_naissance", "lieu_naissance", "dept_naissance", "nationalite", "boursier",
    "telephone", "telephonemobile", "fax", "domicile", "codepostaldomicile",
    "villedomicile", "paysdomicile", "photo_url", "fiche_url", "name", "session", "user",
}


def anonymize(obj, secrets):
    if isinstance(obj, dict):
        return {k: ("ANONYME" if k.lower() in PERSONAL_KEYS and obj[k] not in (None, "", [], {})
                    else anonymize(v, secrets)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [anonymize(v, secrets) for v in obj]
    if isinstance(obj, str):
        for sec in secrets:
            if sec and len(sec) >= 3:
                obj = re.sub(re.escape(sec), "ANONYME", obj, flags=re.I)
        return obj
    return obj


def describe_releve(rel):
    sem = rel.get("semestre", {}) or {}
    print(f"{INFO}Type : {rel.get('type')} | publié : {rel.get('publie')}")
    notes = sem.get("notes", {}) or {}
    rang = sem.get("rang", {}) or {}
    print(f"{INFO}Moyenne générale : {notes.get('value')} (promo : min {notes.get('min')}, "
          f"moy {notes.get('moy')}, max {notes.get('max')})")
    print(f"{INFO}Rang semestre : {rang.get('value')} / {rang.get('total')}")
    print(f"{INFO}ECTS : {sem.get('ECTS')} | absences : {sem.get('absences')}")
    opts = rel.get("options")
    if opts:
        shown = {k: v for k, v in opts.items() if "rang" in k or "moy" in k or "min" in k}
        print(f"{INFO}Options d'affichage : {shown}")
    ues = rel.get("ues", {}) or {}
    print(f"{INFO}{len(ues)} UE :")
    for code, ue in ues.items():
        m = ue.get("moyenne", {}) or {}
        print(f"{INFO}  {code:10} moyenne {m.get('value', '?'):>6}  rang {m.get('rang', '?')}/{m.get('total', '?')}"
              f"  ({len(ue.get('ressources', {}))} ressources, {len(ue.get('saes', {}))} SAÉ)")
    res = rel.get("ressources", {}) or {}
    n_eval = sum(len(r.get("evaluations", [])) for r in res.values())
    print(f"{INFO}{len(res)} ressources, {len(rel.get('saes', {}) or {})} SAÉ, {n_eval} évaluations dans les ressources")


def main():
    print("\nTest de connexion à la passerelle de notes\n")
    login = input("  Identifiant UniCA : ").strip()
    password = getpass.getpass("  Mot de passe (caché) : ")
    s = Session()

    print("\n1. Connexion CAS")
    try:
        back = cas_login(s, f"{BASE}/services/doAuth.php?href={q(BASE + '/')}", login, password,
                         urllib.parse.urlsplit(BASE).hostname)
        print(f"{OK}Retour sur la passerelle : {back[0]}")
    except Exception as e:  # noqa: BLE001
        print(f"{KO}{e}")
        return 1
    cookies = sorted({c.name for c in s.jar})
    print(f"{INFO}Cookies reçus : {', '.join(cookies)}")

    print("\n2. Authentification sur la passerelle")
    auth = get_json(s, f"q={q('donnéesAuthentification')}")
    if "redirect" in auth or "erreur" in auth:
        print(f"{KO}Réponse : {auth}")
        return 1
    print(f"{OK}Statut : {auth.get('statut')} | clés : {sorted(auth)}")
    cfg = auth.get("config", {}) or {}
    if cfg.get("multi_scodoc"):
        print(f"{KO}multi_scodoc activé : il faudra le cookie « composante ». Départements : {auth.get('departments')}")

    print("\n3. Données de première connexion")
    data = get_json(s, f"q={q('dataPremièreConnexion')}")
    if "erreur" in data:
        print(f"{KO}{data['erreur']}")
        return 1
    print(f"{OK}Clés : {sorted(data)}")
    sems = data.get("semestres") or []
    print(f"{INFO}{len(sems)} semestre(s) :")
    for sm in sems:
        print(f"{INFO}  id {sm.get('formsemestre_id')}  {sm.get('titre_num') or sm.get('titre')}  "
              f"{sm.get('annee_scolaire') or sm.get('anneescolaire') or ''}")
    rel = (data.get("relevé") or {})
    rel = rel.get("relevé", rel) if isinstance(rel, dict) else rel
    if rel:
        print("\n4. Relevé du semestre en cours")
        describe_releve(rel)
    else:
        print(f"{KO}Pas de relevé dans la réponse (pas encore publié ?)")

    extra = {}
    if len(sems) > 1:
        sid = sems[-1].get("formsemestre_id")
        print(f"\n5. Relevé d'un autre semestre (id {sid})")
        other = get_json(s, f"q={q('relevéEtudiant')}&semestre={sid}")
        if "erreur" in other:
            print(f"{KO}{other['erreur']}")
        else:
            print(f"{OK}Clés : {sorted(other)}")
            extra = other

    os.makedirs(FIXTURE_DIR, exist_ok=True)
    secrets = [login]
    ident = (rel or {}).get("etudiant", {}) if isinstance(rel, dict) else {}
    for k in ("nom", "prenom", "code_nip", "code_ine", "email", "emailperso"):
        if ident.get(k):
            secrets.append(str(ident[k]))
    out = {"donneesAuthentification": anonymize(auth, secrets),
           "dataPremiereConnexion": anonymize(data, secrets),
           "releveAutreSemestre": anonymize(extra, secrets)}
    path = os.path.join(FIXTURE_DIR, "notes_reel_anonyme.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n{OK}Copie anonymisée enregistrée : {os.path.relpath(path, ROOT)}")
    print(f"{INFO}Ouvre-la et vérifie qu'il ne reste ni ton nom ni ton numéro avant de la partager.")
    print(f"{INFO}Elle ne doit pas être poussée sur GitHub (ajoute tests/fixtures/*reel* au .gitignore).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
