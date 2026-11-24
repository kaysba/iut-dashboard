# ─────────────────────────────────────────────────────────────
#  Configuration du dashboard IUT
#  Copie ce fichier en « config.py » puis adapte-le :
#      cp config-exemple.py config.py        (Windows : copy config-exemple.py config.py)
#  config.py est dans .gitignore : ne le pousse jamais sur Git.
# ─────────────────────────────────────────────────────────────

# Ton prénom, affiché en haut du dashboard
PRENOM = "Prénom"

# ── Moodle ───────────────────────────────────────────────────
MOODLE_URL = "https://lms.univ-cotedazur.fr/2026"

# Identifiants UniCA : ils sont demandés dans la page web au lancement
# et restent en mémoire. Laisse ces lignes vides.
UNICA_LOGIN = ""
UNICA_PASSWORD = ""

# Plan B si la connexion automatique échoue (double authentification, etc.) :
# colle ici ton jeton « Moodle mobile web service ».
# Voir le README, section « Jeton Moodle manuel ».
MOODLE_TOKEN = ""

# Cours à masquer (mots présents dans le nom, insensible à la casse)
COURS_MASQUES = []        # ex : ["Espace étudiants", "Bibliothèque"]

# ── Emploi du temps (ADE) ────────────────────────────────────
# Lien d'export iCal généré depuis ADE (voir README, section « Lien ADE »).
# Il ressemble à :
# https://edtweb.univ-cotedazur.fr/jsp/custom/modules/plannings/anonymous_cal.jsp?resources=XXXX&projectId=6&calType=ical&firstDate=...&lastDate=...
ADE_ICAL_URL = ""

# ── Mails (Outlook / Microsoft 365) ──────────────────────────
MAIL_ADRESSE = "prenom.nom@etu.unice.fr"
MAIL_NOMBRE = 25          # nombre de mails récents à afficher

# Application OAuth utilisée pour se connecter à Outlook.
# Par défaut : l'identifiant public de Thunderbird, que l'université
# documente déjà pour la messagerie. Ne change que si tu sais pourquoi.
MS_CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
MS_TENANT = "organizations"
# Adresse de retour acceptée par Microsoft pour cette application (ne pas changer).
MS_REDIRECT_URI = "https://localhost"

# ── Serveur local ────────────────────────────────────────────
PORT = 8765
OUVRIR_NAVIGATEUR = True

# Durée de cache (secondes) avant de redemander les données
CACHE_PLANNING = 15 * 60
CACHE_MOODLE = 10 * 60
CACHE_MAILS = 2 * 60

# ── Couleurs par matière ─────────────────────────────────────
# motif = expression régulière, sans accents ni majuscules, la première qui correspond gagne.
# Une matière sans motif correspondant prend une couleur de COULEURS_SECOURS.
MATIERES = [
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
]
COULEURS_SECOURS = ["#A58A73", "#7A9CB8", "#969956", "#AE67E4", "#529B85", "#CD8572"]
