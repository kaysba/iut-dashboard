"""Valeurs par défaut de toutes les options.

Ordre de priorité (voir sources/settings.py) : réglages faits dans la page (.cache/settings.json),
puis config.py s'il existe, puis ces valeurs. Dans le code, lire une option avec opt("NOM").
Les options de config-exemple.py ont ici la même valeur : tests/test_config.py le vérifie.
"""

DEFAULTS = {
    # Réglées dans la page (ou lues dans Moodle) : plus dans config-exemple.py. Un ancien config.py
    # qui les définit encore sert de valeur de départ.
    "PRENOM": "",
    "UNICA_LOGIN": "",
    "ADE_ICAL_URL": "",
    "MAIL_ADRESSE": "",
    "THEME": "system",
    # Options avancées (config-exemple.py)
    "MOODLE_URL": "https://lms.univ-cotedazur.fr/2026",
    "MOODLE_TOKEN": "",
    "COURS_MASQUES": [],
    "MAIL_NOMBRE": 25,
    "MS_CLIENT_ID": "9e5f94bc-e8a4-4e73-b8be-63364c29d753",
    "MS_TENANT": "organizations",
    "MS_REDIRECT_URI": "https://localhost",
    "NOTES_URL": "https://iut-notes.unice.fr",
    "NOTES_PDF_TYPE": "short",
    "UPLOAD_MAX": 100 * 1024 * 1024,
    "PORT": 8765,
    "OUVRIR_NAVIGATEUR": True,
    "CACHE_PLANNING": 15 * 60,
    "CACHE_MOODLE": 10 * 60,
    "CACHE_MAILS": 2 * 60,
    "CACHE_NOTES": 15 * 60,
    "MATIERES": [
        {"motif": r"\bsae\b", "nom": "SAÉ", "couleur": "#8E959F"},
        {"motif": r"\bsql\b|base.? de donnee|\bbdd\b", "nom": "SQL", "couleur": "#D57676"},
        {"motif": r"qualite", "nom": "Qualité de dev", "couleur": "#CC3D8A"},
        {"motif": r"efficace", "nom": "Dev efficace", "couleur": "#3ABB60"},
        {"motif": r"systeme", "nom": "Prog système", "couleur": "#D2893E"},
        {"motif": r"\bweb\b", "nom": "Dev web", "couleur": "#CEAE24"},
        {"motif": r"communication", "nom": "Communication pro", "couleur": "#839650"},
        {"motif": r"\bdroit\b", "nom": "Droit", "couleur": "#4A76C5"},
        {"motif": r"proba|statist", "nom": "Probabilités", "couleur": "#91C488"},
        {"motif": r"manag|gestion", "nom": "Management", "couleur": "#8D63C2"},
        {"motif": r"anglais|english", "nom": "Anglais", "couleur": "#D873A0"},
        {"motif": r"reseau", "nom": "Réseaux", "couleur": "#30A5B6"},
        {"motif": r"math|graphe|algebre", "nom": "Maths", "couleur": "#606BC0"},
        {"motif": r"cyber|securite", "nom": "Sécurité", "couleur": "#89705C"},
        {"motif": r"donnee|\bia\b|intelligence", "nom": "Données / IA", "couleur": "#44A196"},
        {"motif": r"objet|poo|java\b", "nom": "Objet", "couleur": "#B0627E"},
        {"motif": r"portfolio|ppp|projet pers|stage", "nom": "Projet pro", "couleur": "#707A85"},
    ],
    "COULEURS_SECOURS": ["#A58A73", "#7A9CB8", "#969956", "#AE67E4", "#529B85", "#CD8572"],
}


# Options qui ne figurent pas dans config-exemple.py (réglées dans la page).
PAGE_SEULEMENT = ("PRENOM", "UNICA_LOGIN", "ADE_ICAL_URL", "MAIL_ADRESSE", "THEME")
