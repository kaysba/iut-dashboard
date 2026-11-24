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
