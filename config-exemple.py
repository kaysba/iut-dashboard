# ─────────────────────────────────────────────────────────────
#  Options avancées du dashboard IUT (FACULTATIF)
#
#  Tu n'as PAS besoin de ce fichier : tout se règle dans la page web
#  (assistant au premier lancement, puis page Réglages).
#
#  Ce fichier documente les options avancées. Le dashboard ne le lit pas.
#  Pour en changer une, crée un fichier config.py à côté de dashboard.py
#  et recopie-y seulement les lignes voulues. Une option réglée dans la page
#  passe avant config.py ; une option absente prend sa valeur par défaut.
#  config.py est dans .gitignore : ne le pousse jamais sur Git.
# ─────────────────────────────────────────────────────────────

# ── Moodle ───────────────────────────────────────────────────
MOODLE_URL = "https://lms.univ-cotedazur.fr/2026"

# Plan B si la connexion automatique échoue (double authentification, etc.) :
# colle ici ton jeton « Moodle mobile web service ».
# Voir le README, section « Jeton Moodle manuel ».
MOODLE_TOKEN = ""

# Cours à masquer (mots présents dans le nom, insensible à la casse). Aussi dans Réglages > Affichage.
COURS_MASQUES = []        # ex : ["Espace étudiants", "Bibliothèque"]

# ── Mails (Outlook / Microsoft 365) ──────────────────────────
# L'adresse mail et le lien ADE se règlent dans la page (assistant, puis Réglages).
MAIL_NOMBRE = 25          # nombre de mails récents à afficher

# Application OAuth utilisée pour se connecter à Outlook.
# Par défaut : l'identifiant public de Thunderbird, que l'université
# documente déjà pour la messagerie. Ne change que si tu sais pourquoi.
MS_CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
MS_TENANT = "organizations"
# Adresse de retour acceptée par Microsoft pour cette application (ne pas changer).
MS_REDIRECT_URI = "https://localhost"

# ── Notes (Passerelle ScoDoc de l'IUT) ───────────────────────
NOTES_URL = "https://iut-notes.unice.fr"
# Type de relevé PDF demandé à la passerelle (paramètre « type » de services/bulletin_PDF.php).
NOTES_PDF_TYPE = "short"

# ── Serveur local ────────────────────────────────────────────
# Taille maximale (octets) d'un envoi de fichiers depuis le dashboard, quelle que soit la limite du devoir.
UPLOAD_MAX = 100 * 1024 * 1024
PORT = 8765               # aussi dans Réglages > Avancé
OUVRIR_NAVIGATEUR = True

# Durée de cache (secondes) avant de redemander les données
CACHE_PLANNING = 15 * 60
CACHE_MOODLE = 10 * 60
CACHE_MAILS = 2 * 60
CACHE_NOTES = 15 * 60

# ── Couleurs par matière (aussi dans Réglages > Couleurs des matières) ──
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
