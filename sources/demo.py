"""Données fictives pour essayer le dashboard sans configuration (python dashboard.py --demo)."""
import datetime as dt
import io
import time
import zipfile

COURSES = [
    ("R3.01", "R3.01 Développement web"),
    ("R3.06", "R3.06 Architecture des réseaux"),
    ("R3.05", "R3.05 Programmation système"),
    ("R3.07", "R3.07 SQL dans un langage de programmation"),
    ("R3.08", "R3.08 Probabilités"),
    ("SAÉ 3.01", "SAÉ 3.01 Développement d'une application"),
    ("R3.12", "R3.12 Anglais"),
]

PLAN = [  # (jour 0=lundi, h début, durée h, titre, salle, prof)
    (0, 8, 2, "R3.06 Réseaux CM", "Amphi Est", "M. Garnier"),
    (0, 10.25, 2, "R3.01 Dév web TD", "Salle 112", "Mme Rossi"),
    (0, 14, 3, "R3.05 Prog système TP", "Salle TP 2", "M. Lefèvre"),
    (1, 8, 1.5, "R3.08 Probabilités CM", "Amphi Ouest", "Mme Haddad"),
    (1, 9.75, 2, "R3.07 SQL TD", "Salle 104", "M. Morel"),
    (1, 13.5, 2, "R3.12 Anglais TD", "Salle 210", "Mrs Clarke"),
    (1, 15.75, 2, "SAÉ 3.01 Projet", "Salle 118", "M. Lefèvre"),
    (2, 8, 2, "R3.01 Dév web CM", "Amphi Est", "Mme Rossi"),
    (2, 10.25, 3, "R3.06 Réseaux TP", "Salle TP 1", "M. Garnier"),
    (3, 9, 2, "R3.08 Probabilités TD", "Salle 106", "Mme Haddad"),
    (3, 13.5, 3, "R3.07 SQL TP", "Salle TP 3", "M. Morel"),
    (3, 16.75, 1.5, "R3.05 Prog système CM", "Amphi Ouest", "M. Lefèvre"),
    (4, 10, 2, "SAÉ 3.01 Projet", "Salle 118", "M. Lefèvre"),
]

# Évaluations datées (jours à partir d'aujourd'hui, h début, durée h, titre, salle, prof).
# Elles couvrent les trois couleurs du bloc « DS à venir » et un faux positif (ADS n'est pas un DS).
DS_DEMO = [
    (1, 8, 2, "DS - R3.08 Probabilités", "Amphi Ouest", "Mme Haddad"),
    (5, 9, 1.5, "DS - R3.06 Architecture des réseaux", "Amphi Est", "M. Garnier"),
    (16, 14, 2, "DS - R3.01 Développement web", "Amphi Est", "Mme Rossi"),
    (30, 8, 2, "DS2 - R3.05 Programmation système", "Amphi Ouest", "M. Lefèvre"),
    (3, 14, 1, "Réunion ADS projet", "Salle 118", "M. Lefèvre"),
]


def events(start, end):
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            for (wd, h, dur, title, room, prof) in PLAN:
                if wd != d.weekday():
                    continue
                s = dt.datetime.combine(d, dt.time(int(h), int(round((h % 1) * 60)))).astimezone()
                e = s + dt.timedelta(hours=dur)
                t = title.lower()
                etype = ("Examen" if t.startswith("ds") else "TP" if " tp" in t else "TD" if " td" in t
                         else "CM" if " cm" in t else "Projet" if "saé" in t else "Autre")
                out.append({"uid": f"{d}{title}", "title": title, "type": etype, "room": room,
                            "teacher": prof, "groups": ["BUT2 Info", "Groupe 2"],
                            "start": s.isoformat(), "end": e.isoformat()})
        d += dt.timedelta(days=1)
    today = dt.date.today()
    for off, h, dur, title, room, prof in DS_DEMO:
        day = today + dt.timedelta(days=off)
        if not start <= day <= end:
            continue
        s = dt.datetime.combine(day, dt.time(int(h), int(round((h % 1) * 60)))).astimezone()
        etype = "Examen" if title.lower().startswith("ds") else "Autre"
        # ADE renvoie parfois un créneau par groupe : on en met deux pour le premier DS.
        for g in (["BUT2 Info", "Groupe 1"], ["BUT2 Info", "Groupe 2"]) if off == 5 else (["BUT2 Info"],):
            out.append({"uid": f"{day}{title}{g[-1]}", "title": title, "type": etype, "room": room, "teacher": prof,
                        "groups": g, "start": s.isoformat(), "end": (s + dt.timedelta(hours=dur)).isoformat()})
    out.sort(key=lambda e: e["start"])
    return out


def _f(name, size, days):
    return {"name": name, "size": size, "path": "/", "fileurl": "", "modified": time.time() - days * 86400}


def _item(i, name, kind, cat, days, files=None, corr=False, mod="resource"):
    return {"id": i, "name": name, "kind": kind, "mod": mod, "category": cat, "correction": corr,
            "url": "#", "external": None, "files": files or [], "modified": time.time() - days * 86400}


def resources():
    n = 1000
    out = []
    contents = {
        "R3.06": [
            ("Généralités", [("Plan du cours et modalités", "pdf", "CM", 60), ("Rappels modèle OSI", "slides", "CM", 58)]),
            ("Routage dynamique", [("CM3 – OSPF", "slides", "CM", 9), ("TD3 – Calcul de routes OSPF", "pdf", "TD", 8),
                                   ("TD3 – Correction", "pdf", "TD", 2), ("TP3 – OSPF multi-aires sur GNS3", "pdf", "TP", 7),
                                   ("Fichiers GNS3 du TP3", "archive", "TP", 7)]),
            ("VLAN et commutation", [("CM2 – VLAN, trunk 802.1Q", "slides", "CM", 23), ("TD2 – Plan d'adressage", "pdf", "TD", 22),
                                     ("TP2 – Configuration des VLAN", "pdf", "TP", 21)]),
            ("Examens", [("Annales DS 2025", "pdf", "Examen", 5), ("Annales DS 2024 + corrigé", "pdf", "Examen", 5)]),
        ],
        "R3.01": [
            ("PHP orienté objet", [("CM4 – Classes et namespaces", "slides", "CM", 4), ("TD4 – Modéliser un panier", "pdf", "TD", 3),
                                   ("TP4 – Autoloader et Composer", "pdf", "TP", 3), ("Squelette du TP4", "archive", "TP", 3)]),
            ("PDO et sécurité", [("CM3 – PDO, requêtes préparées", "slides", "CM", 16), ("TP3 – Injection SQL et XSS", "pdf", "TP", 15),
                                 ("Documentation PHP", "link", "Autre", 40)]),
            ("Examens", [("Annales DS 2025 – Développement web", "pdf", "Examen", 18)]),
        ],
        "R3.05": [
            ("Processus", [("CM1 – fork, exec, wait", "slides", "CM", 30), ("TD1 – Arbres de processus", "pdf", "TD", 29),
                           ("TP1 – Mini shell en C", "pdf", "TP", 28), ("minishell.c", "code", "TP", 28)]),
            ("Mémoire", [("CM4 – Pagination et mémoire virtuelle", "slides", "CM", 6), ("TD4 – Exercices de pagination", "pdf", "TD", 5)]),
        ],
        "R3.07": [("Requêtes avancées", [("CM – Jointures et sous-requêtes", "slides", "CM", 12),
                                         ("TD5 – Requêtes sur la base Ventes", "pdf", "TD", 11),
                                         ("Script de création de la base", "code", "TD", 11)])],
        "R3.08": [("Lois discrètes", [("Poly de cours chapitre 3", "pdf", "CM", 20), ("Feuille de TD 3", "pdf", "TD", 19),
                                      ("Feuille de TD 3 – Corrigé", "pdf", "TD", 10)]),
                  ("Examens", [("Annales DS 2025 – Probabilités", "pdf", "Examen", 12), ("Annales DS 2024 + corrigé", "pdf", "Examen", 12)])],
        "SAÉ 3.01": [("Ressources du projet", [("Sujet de la SAÉ", "pdf", "Autre", 50), ("Grille d'évaluation", "sheet", "Examen", 50),
                                               ("Dépôt Git du groupe", "link", "Autre", 45)])],
        "R3.12": [("Unit 4 – Job interviews", [("Vocabulary list", "doc", "Autre", 14), ("Mock interview questions", "pdf", "TD", 13)])],
    }
    for short, full in COURSES:
        sections = []
        for sname, items in contents.get(short, []):
            its = []
            for (name, kind, cat, days) in items:
                n += 1
                ext = {"pdf": "pdf", "slides": "pptx", "archive": "zip", "code": "c", "sheet": "xlsx", "doc": "docx"}.get(kind)
                files = [_f(f"{name}.{ext}", 240000 + n * 913, days)] if ext else []
                mod = "url" if kind == "link" else "resource"
                its.append(_item(n, name, kind, cat, days, files, "corrig" in name.lower(), mod))
            sections.append({"name": sname, "items": its})
        out.append({"id": hash(short) % 10000, "name": full, "short": short, "url": "#", "lastaccess": 0,
                    "sections": sections})
    return out


# Dépôts de démonstration : envois simulés en mémoire (rien n'est écrit sur le disque).
_DEMO_DEPOT = {
    # id : (fichiers, texte, max_fichiers, taille_max, types, remise_requise, declaration)
    0: (True, False, 3, 20 * 1048576, [".pdf", ".zip"], True, False),     # ouvert, sans dépôt
    1: (True, False, 3, 20 * 1048576, [], True, True),                    # brouillon de 2 fichiers, déclaration
    2: (True, False, 1, 10 * 1048576, [".pdf"], False, False),            # 1 seul .pdf, le dépôt vaut remise
    3: (False, True, 1, 0, [], False, False),                             # texte en ligne seulement
    4: (True, False, 1, 20 * 1048576, [], True, False),                   # fermé (date limite passée)
    5: (True, False, 1, 20 * 1048576, [".pdf"], True, False),             # déjà remis
    6: (True, False, 1, 20 * 1048576, [], True, False),
}
_STATE = {}   # id -> {"statut", "fichiers": {nom: octets}, "modifie"}
_REMIS_LE = lambda: time.time() - 3600  # noqa: E731


def _pdf(titre):
    """Un petit PDF valide d'une page."""
    txt = f"BT /F1 20 Tf 60 740 Td ({titre}) Tj ET".encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(txt) + txt + b"\nendstream", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)


def _zip(noms):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n in noms:
            z.writestr(n, f"Contenu de démonstration de {n}\n")
    return buf.getvalue()


def _demo_file(nom):
    if nom.endswith(".pdf"):
        return _pdf(nom)
    if nom.endswith(".zip"):
        return _zip(["index.php", "src/Panier.php", "src/Produit.php", "README.md"])
    return f"Fichier de démonstration : {nom}\n".encode()


def _state(i):
    if i not in _STATE:
        if i == 1:
            fich = {"panier.zip": _demo_file("panier.zip"), "rapport.pdf": _demo_file("rapport.pdf")}
            _STATE[i] = {"statut": "brouillon", "fichiers": fich, "modifie": time.time() - 5 * 3600}
        elif i in (5, 6):
            _STATE[i] = {"statut": "remis", "fichiers": {"cover-letter.pdf": _demo_file("cover-letter.pdf")},
                         "modifie": time.time() - 4 * 86400}
        else:
            _STATE[i] = {"statut": "nouveau", "fichiers": {}, "modifie": 0}
    return _STATE[i]


def _statut_liste(statut):
    return {"remis": "rendu", "brouillon": "brouillon"}.get(statut, "a_rendre")


def _depot(i, now=None):
    fichiers, texte, maxf, taille, types, remise, decl = _DEMO_DEPOT[i]
    st = _state(i)
    row = _ROWS()[i]
    cutoff = row[5] if len(row) > 5 else 0
    raison = ""
    if cutoff and (now or time.time()) > cutoff:
        raison = "La date limite de dépôt est dépassée."
    elif st["statut"] == "remis" and remise:
        raison = "Ton dépôt est remis et Moodle ne permet plus de le modifier."
    return {"fichiers": fichiers, "texte": texte, "max_fichiers": maxf, "taille_max": taille, "types": types,
            "ouvert": not raison, "raison_fermeture": raison, "remise_requise": remise, "declaration": decl,
            "texte_declaration": "Ce travail est le mien : je n'ai pas copié celui d'un autre étudiant ni d'une IA "
                                 "sans l'avoir indiqué.",
            "statut": st["statut"], "modifie": int(st["modifie"]),
            "fichiers_actuels": [{"nom": n, "taille": len(b), "url": f"demo://{i}/{n}", "modifie": int(st["modifie"])}
                                 for n, b in st["fichiers"].items()]}


def _ROWS():  # noqa: N802
    now = time.time()
    h = 3600
    return [
        ("Compte rendu TP3 OSPF", "R3.06 Architecture des réseaux", "R3.06", now + 30 * h, "a_rendre", 0),
        ("TP4 – Panier en PHP objet", "R3.01 Développement web", "R3.01", now + 3 * 24 * h, "brouillon", 0),
        ("Livrable 2 – Maquettes et MCD", "SAÉ 3.01 Développement d'une application", "SAÉ 3.01", now + 6 * 24 * h, "a_rendre", 0),
        ("Mini shell – rendu final", "R3.05 Programmation système", "R3.05", now + 12 * 24 * h, "a_rendre", 0),
        ("TD5 – Requêtes SQL", "R3.07 SQL dans un langage de programmation", "R3.07", now - 20 * h, "a_rendre", now - 2 * h),
        ("Cover letter draft", "R3.12 Anglais", "R3.12", now - 4 * 24 * h, "rendu", 0),
        ("TP2 – Configuration des VLAN", "R3.06 Architecture des réseaux", "R3.06", now - 9 * 24 * h, "rendu", 0),
    ]


def assignments():
    out = []
    for i, (n, c, s, d, _, cut) in enumerate(_ROWS()):
        out.append({"id": i, "cmid": i, "name": n, "course": c, "courseShort": s, "due": int(d), "cutoff": int(cut),
                    "opens": 0, "url": "#", "submitUrl": "#", "status": _statut_liste(_state(i)["statut"]),
                    "graded": False, "depot": _depot(i)})
    return out


def depot_state(i):
    return {"id": i, "status": _statut_liste(_state(i)["statut"]), "graded": False, "depot": _depot(i)}


def save_draft(i, fichiers, garder, upload_max=None, state=None):
    from .moodle import verifier_envoi
    depot = _depot(i)
    verifier_envoi(depot, [(n, len(d)) for n, d in fichiers], garder, upload_max)
    time.sleep(1.2)   # laisse voir « Enregistrement dans Moodle… »
    st = _state(i)
    nouveaux = dict(fichiers)
    st["fichiers"] = {**(st["fichiers"] if garder else {}), **nouveaux}
    st["statut"] = "brouillon" if depot["remise_requise"] else "remis"
    st["modifie"] = time.time()
    return depot_state(i)


def submit(i, declaration):
    from .moodle import verifier_remise
    verifier_remise(_depot(i), declaration)
    time.sleep(0.8)
    st = _state(i)
    st["statut"], st["modifie"] = "remis", time.time()
    return depot_state(i)


def delete_file(i, nom):
    from .common import SourceError
    st = _state(i)
    if nom not in st["fichiers"] or len(st["fichiers"]) < 2:
        raise SourceError("Impossible de vider le dépôt depuis le dashboard : utilise la page Moodle.")
    del st["fichiers"][nom]
    st["modifie"] = time.time()
    return depot_state(i)


def file_bytes(url):
    """Contenu d'un fichier de démo (demo://id/nom) et son type MIME."""
    i, nom = url[len("demo://"):].split("/", 1)
    data = _state(int(i))["fichiers"].get(nom) or _demo_file(nom)
    return data, ("application/pdf" if nom.endswith(".pdf") else "application/zip" if nom.endswith(".zip") else "text/plain")


def mails():
    now = time.time()
    rows = [
        ("Scolarité IUT", "Inscriptions pédagogiques du semestre 4", "Les inscriptions pédagogiques ouvrent lundi. Vous devrez choisir vos ressources optionnelles avant le", 0.4, True, False),
        ("Moodle UniCA", "Nouveau document : TD3 – Correction", "Un nouveau fichier a été ajouté au cours R3.06 Architecture des réseaux.", 2, True, False),
        ("Lefèvre Thomas", "SAÉ 3.01 – créneaux de suivi", "Bonjour à tous, je vous propose des créneaux de suivi de 15 min jeudi après-midi. Merci de vous inscrire", 5, True, False),
        ("Relations internationales", "Stage à l'étranger : pièces à fournir", "Pour finaliser votre convention de stage, merci de déposer les documents suivants avant le 5 décembre", 26, False, True),
        ("BU Sciences", "Rappel : retour de prêt", "Le document « Réseaux, 6e édition » est à rendre avant le 28 novembre.", 30, False, False),
        ("Rossi Elena", "R3.01 – précisions sur le TP4", "Pour le TP4, vous pouvez utiliser l'autoloader de Composer. Pensez à inclure le fichier README", 50, False, False),
        ("Service des sports", "Tournoi de futsal inter-IUT", "Les inscriptions pour le tournoi du 10 décembre sont ouvertes. Équipes de 5 joueurs", 75, False, False),
    ]
    msgs = [{"from": f, "fromAddr": "", "subject": s, "snippet": sn, "date": now - hrs * 3600, "unread": u,
             "attachment": a,
             "body": sn + "…\n\nCeci est un mail de démonstration : le texte complet d'un vrai mail s'afficherait ici.\n\nCordialement,\n" + f}
            for (f, s, sn, hrs, u, a) in rows]
    return {"unread": 3, "messages": msgs, "webmail": "https://outlook.office.com/mail/inbox"}


# ── Notes ───────────────────────────────────────────────────
# Même format que sources.notes.Notes.donnees() : le front ne voit pas la différence.
_SEMESTRES = [(41, 1, "2025/2026"), (120, 2, "2025/2026"), (189, 3, "2026/2027")]
_UE_TITRES = ["Réaliser", "Optimiser", "Administrer", "Gérer", "Conduire", "Collaborer"]
_UE_COULEURS = ["#B80004", "#EC7F00", "#00A3A3", "#7D3FC0", "#2E8B57", "#2367D1"]

# module : (code, titre, type, {numéro d'UE: coef}, [(évaluation, il y a N jours, note ou None, coef)])
_MODULES = {
    3: [
        ("R3.01", "Développement web", "ressource", {1: 15, 4: 10},
         [("DS PHP", 21, 15.5, .4), ("TP1 Panier", 9, 17, .3), ("TP2 Sessions", 2, 16, .3)]),
        ("R3.02", "Qualité de développement", "ressource", {1: 10, 2: 8},
         [("TP Tests unitaires", 20, 13.5, .5), ("DS Qualité", -6, None, .5)]),
        ("R3.05", "Programmation système", "ressource", {2: 15, 3: 8},
         [("TP1 Processus", 24, 14, .5), ("DS Système", 11, 11.5, .5)]),
        ("R3.06", "Architecture des réseaux", "ressource", {3: 15, 5: 10},
         [("DS Réseaux", 3, 9.5, .6), ("TP OSPF", 12, 13, .4)]),
        ("R3.07", "SQL dans un langage de programmation", "ressource", {2: 10, 4: 12},
         [("TP Jointures", 15, 15, .5), ("DS SQL", 5, 17.5, .5)]),
        ("R3.08", "Probabilités", "ressource", {5: 15},
         [("DS1", 18, 8.5, .5), ("DS2", -9, None, .5)]),
        ("R3.09", "Cryptographie et sécurité", "ressource", {3: 8, 5: 6}, []),
        ("R3.10", "Management des systèmes d'information", "ressource", {4: 10, 6: 12},
         [("Étude de cas", 14, 7, 1)]),
        ("R3.11", "Droit des contrats et du numérique", "ressource", {6: 8},
         [("QCM Droit", 16, 6.5, 1)]),
        ("R3.12", "Anglais", "ressource", {6: 15},
         [("Oral", 22, 5.5, .5), ("Compréhension écrite", 7, 8, .5)]),
        ("R3.13", "Communication professionnelle", "ressource", {6: 10},
         [("Dossier", 13, 9, 1)]),
        ("SAÉ3.01", "Développement d'une application", "sae", {1: 40, 2: 20, 4: 20},
         [("Soutenance intermédiaire", 10, 16, 1)]),
    ],
    2: [
        ("R2.01", "Développement orienté objets", "ressource", {1: 12, 4: 8}, [("TP Java", 150, 14, .5), ("DS POO", 140, 12.5, .5)]),
        ("R2.02", "Développement d'applications avec IHM", "ressource", {1: 10}, [("TP Interfaces", 145, 15.5, 1)]),
        ("R2.03", "Qualité de développement", "ressource", {2: 10, 4: 6}, [("TP Git", 160, 13, 1)]),
        ("R2.05", "Introduction aux services réseaux", "ressource", {3: 12, 5: 8}, [("DS Réseaux", 130, 10.5, 1)]),
        ("R2.06", "Exploitation d'une base de données", "ressource", {2: 12, 3: 6}, [("TP SQL", 135, 14.5, .5), ("DS SQL", 128, 12, .5)]),
        ("R2.08", "Outils numériques pour les statistiques", "ressource", {5: 10}, [("TP Stats", 125, None, 1)]),
        ("R2.11", "Droit des contrats et du numérique", "ressource", {6: 8}, [("QCM", 120, 11, 1)]),
        ("R2.12", "Anglais", "ressource", {6: 10}, [("Oral", 118, 13.5, 1)]),
        ("SAÉ2.01", "Développement d'une application", "sae", {1: 30, 2: 15, 3: 10}, [("Soutenance", 110, 15, 1)]),
    ],
    1: [
        ("R1.01", "Initiation au développement", "ressource", {1: 15, 2: 6}, [("DS Algo", 300, 13, .5), ("TP Python", 290, 15, .5)]),
        ("R1.02", "Développement d'interfaces web", "ressource", {1: 10}, [("TP HTML/CSS", 285, 16, 1)]),
        ("R1.03", "Introduction à l'architecture des ordinateurs", "ressource", {3: 12}, [("DS Archi", 280, 8.5, 1)]),
        ("R1.05", "Introduction aux systèmes d'exploitation", "ressource", {3: 10, 2: 6}, [("TP Shell", 270, 11, 1)]),
        ("R1.06", "Mathématiques discrètes", "ressource", {5: 12}, [("DS Maths", 265, 9, 1)]),
        ("R1.10", "Anglais", "ressource", {6: 10}, [("Oral", 260, 12.5, 1)]),
        ("SAÉ1.01", "Implémentation d'un besoin client", "sae", {1: 30, 4: 15}, [("Soutenance", 255, 14, 1)]),
    ],
}

# Par semestre : (options affichées, rangs semestre + UE) ; None = masqué.
_DEMO_RANGS = {
    3: {"sem": (2, 57), "ue": [(1, 57), (2, 57), (3, 57), (9, 57), (31, 57), (48, 57)]},
    2: {"sem": None, "ue": [None] * 6},
    1: {"sem": (14, 58), "ue": [(5, 58), (17, 58), (3, 58), (22, 58), (8, 58), (31, 58)]},
}
_DEMO_PROMO = {3: True, 2: False, 1: True}


def _avg(pairs):
    pairs = [(v, c) for v, c in pairs if v is not None]
    tot = sum(c for _, c in pairs)
    return round(sum(v * c for v, c in pairs) / tot, 2) if tot else None


def _promo(v, on):
    if not on or v is None:
        return {"min": None, "moy": None, "max": None}
    moy = round(0.55 * v + 4.6, 2)
    return {"min": round(max(0, moy - 6.5), 2), "moy": moy, "max": round(min(20, moy + 4.5), 2)}


def _releve_demo(num):
    today = dt.date.today()
    rangs, promo = _DEMO_RANGS[num], _DEMO_PROMO[num]
    options = {"rangs": rangs["sem"] is not None, "rangs_ue": rangs["ue"][0] is not None,
               "rangs_modules": rangs["sem"] is not None, "promo": promo}
    modules, mod_moy = [], {}
    for code, titre, typ, _, evals in _MODULES[num]:
        evs = [{"id": num * 1000 + len(modules) * 10 + i, "titre": t,
                "date": (today - dt.timedelta(days=d)).isoformat(), "type": "normale", "etat": None, "coef": c, "note": n,
                **_promo(n, promo), "poids": {f"UE{num}.{u}": 1 for u in _MODULES[num][len(modules)][3]}}
               for i, (t, d, n, c) in enumerate(evals)]
        moy = _avg([(e["note"], e["coef"]) for e in evs])
        mod_moy[code] = moy
        modules.append({"code": code, "titre": titre, "type": typ, "moyenne": moy,
                        "rang": None, "total": None, **_promo(moy, promo), "evaluations": evs})
    ues = []
    for u in range(1, 7):
        mods = [{"code": c, "titre": t, "type": ty, "coef": coefs[u], "moyenne": mod_moy[c]}
                for c, t, ty, coefs, _ in _MODULES[num] if u in coefs]
        moy = _avg([(m["moyenne"], m["coef"]) for m in mods])
        r = rangs["ue"][u - 1]
        ues.append({"code": f"UE{num}.{u}", "titre": _UE_TITRES[u - 1], "couleur": _UE_COULEURS[u - 1],
                    "moyenne": moy, "rang": r[0] if r else None, "total": r[1] if r else None,
                    **_promo(moy, promo), "bonus": 0.0, "malus": 0.0,
                    "ects_acquis": 0.0 if num == 3 else 5.0, "ects_total": 5.0, "modules": mods})
    ues[1]["bonus"] = 0.15 if num == 3 else 0.0   # un petit bonus d'UE, pour l'affichage
    bonus = 0.1 if num == 3 else None   # venue de l'UE « bonus » du semestre, ajoutée à la moyenne générale
    sem = _avg([(u["moyenne"], 1) for u in ues])
    sem = round(sem + (bonus or 0), 2) if sem is not None else None
    rs = rangs["sem"]
    return {"publie": True, "message": "", "options": options,
            "semestre": {"numero": num, "moyenne": sem, "rang": rs[0] if rs else None, "total": rs[1] if rs else None,
                         **_promo(sem, promo), "ects_acquis": 0.0 if num == 3 else 30.0, "ects_total": 30.0,
                         "bonus": bonus,
                         "absences": {"total": 3.0, "injustifiees": 1.0, "unite": "Heure(s)"} if num == 3
                         else {"total": 0.0, "injustifiees": 0.0, "unite": "Heure(s)"}},
            "ues": ues, "modules": modules}


def notes(semestre_id=None):
    semestres = [{"id": i, "nom": f"Semestre {n} ({a})", "actuel": k == len(_SEMESTRES) - 1}
                 for k, (i, n, a) in enumerate(_SEMESTRES)]
    num = next((n for i, n, _ in _SEMESTRES if i == semestre_id), _SEMESTRES[-1][1])
    return {"semestres": semestres, "releve": _releve_demo(num)}
