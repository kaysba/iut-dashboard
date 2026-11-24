"""Données fictives pour essayer le dashboard sans configuration (python dashboard.py --demo)."""
import datetime as dt
import time

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
    (4, 8, 1.5, "DS R3.06 Réseaux", "Amphi Est", "M. Garnier"),
    (4, 10, 2, "SAÉ 3.01 Projet", "Salle 118", "M. Lefèvre"),
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
                                      ("Feuille de TD 3 – Corrigé", "pdf", "TD", 10)])],
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


def assignments():
    now = time.time()
    h = 3600
    rows = [
        ("Compte rendu TP3 OSPF", "R3.06 Architecture des réseaux", "R3.06", now + 30 * h, "a_rendre"),
        ("TP4 – Panier en PHP objet", "R3.01 Développement web", "R3.01", now + 3 * 24 * h, "brouillon"),
        ("Livrable 2 – Maquettes et MCD", "SAÉ 3.01 Développement d'une application", "SAÉ 3.01", now + 6 * 24 * h, "a_rendre"),
        ("Mini shell – rendu final", "R3.05 Programmation système", "R3.05", now + 12 * 24 * h, "a_rendre"),
        ("TD5 – Requêtes SQL", "R3.07 SQL dans un langage de programmation", "R3.07", now - 20 * h, "a_rendre"),
        ("Cover letter draft", "R3.12 Anglais", "R3.12", now - 4 * 24 * h, "rendu"),
        ("TP2 – Configuration des VLAN", "R3.06 Architecture des réseaux", "R3.06", now - 9 * 24 * h, "rendu"),
    ]
    return [{"id": i, "cmid": i, "name": n, "course": c, "courseShort": s, "due": int(d), "cutoff": 0, "opens": 0,
             "url": "#", "submitUrl": "#", "status": st, "graded": False} for i, (n, c, s, d, st) in enumerate(rows)]


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
