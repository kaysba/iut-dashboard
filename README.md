# Dashboard IUT

Tableau de bord local pour l'IUT Nice Côte d'Azur : emploi du temps ADE, ressources Moodle triées (CM, TD, TP, examens), devoirs à rendre avec lien direct vers le dépôt, et derniers mails Outlook.

Le serveur tourne **sur ta machine uniquement** (`127.0.0.1`). Rien n'est envoyé ailleurs que vers Moodle, ADE, la passerelle de notes (`iut-notes.unice.fr`) et Microsoft.

Aucune bibliothèque à installer : seulement **Python 3.8 ou plus récent**.

---

## 1. Essayer tout de suite (mode démo)

```bash
python dashboard.py --demo        # Linux
py dashboard.py --demo            # Windows
```

Le navigateur s'ouvre sur `http://localhost:8765` avec des données fictives.

## 2. Configurer `config.py`

### Connexion (identifiant, mail, mot de passe)

Rien à écrire dans `config.py` : **à chaque lancement, la page web affiche un écran de connexion** (identifiant UniCA, adresse mail, mot de passe en points).

- **Sans « Se souvenir de moi »** : tout reste en mémoire et s'efface à l'arrêt. Au prochain lancement, il faudra te reconnecter (et reconnecter Outlook).
- **Avec « Se souvenir de moi »** : une session Moodle et Outlook est gardée dans `.cache/` pour ne pas te reconnecter au prochain lancement. **Ton mot de passe n'est jamais enregistré**, seulement des jetons d'accès.
- **Se déconnecter** (en bas à gauche) efface tout : session, jetons Moodle et Outlook.

Au premier lancement, le dashboard se connecte au CAS de l'université, récupère un **jeton Moodle** (le même que l'app mobile Moodle) et le garde dans `.cache/`. Ensuite, il n'utilise plus que ce jeton.

#### Jeton Moodle manuel (si la connexion automatique échoue)

Ça peut arriver si l'université ajoute une double authentification ou change sa page de connexion.

1. Installe l'app **Moodle** sur ton téléphone et connecte-toi une fois à `https://lms.univ-cotedazur.fr/2026`.
2. Sur le Moodle web : ton avatar → **Préférences** → **Clés de sécurité**.
3. Copie la clé de la ligne **Moodle mobile web service** dans `MOODLE_TOKEN`.

### Emploi du temps (lien ADE)

Le lien `direct/index.jsp?...` que tu utilises pour consulter ADE ne sert qu'à l'affichage. Il faut le **lien d'export iCal** :

1. Ouvre ton emploi du temps ADE.
2. Clique sur l'icône **Exporter l'agenda** (calendrier avec une flèche, en bas à gauche ou dans la barre d'outils).
3. Choisis une période quelconque, puis **Générer URL**.
4. Copie l'adresse (elle contient `anonymous_cal.jsp`) dans `ADE_ICAL_URL`.

Les dates du lien n'ont pas d'importance : le dashboard les remplace par la semaine affichée.

### Mails Outlook

Ta messagerie `@etu.unice.fr` est sur Microsoft 365, qui **refuse le mot de passe** pour lire les mails depuis un programme. La connexion se fait donc une seule fois :

1. Page **Mails** → **Ouvrir la connexion Microsoft**, connecte-toi dans le nouvel onglet.
2. À la fin, l'onglet affiche « La connexion a échoué » (adresse `https://localhost/?code=…`). C'est normal : la connexion a réussi.
3. Dans cet onglet : barre d'adresse, **Ctrl+A**, **Ctrl+C**. Reviens sur le dashboard et colle (**Ctrl+V**) : la validation est automatique.

Le jeton se renouvelle ensuite tout seul (environ 90 jours sans utilisation avant expiration). Microsoft n'autorise pas de retour automatique vers le dashboard pour cette application, d'où le collage.

### Notes (Passerelle ScoDoc)

Les notes viennent de la passerelle de l'IUT (`https://iut-notes.unice.fr`). Aucun réglage n'est obligatoire : `config-exemple.py` contient `NOTES_URL` et `CACHE_NOTES` (durée du cache, 15 minutes par défaut).

- À la connexion, le dashboard ouvre aussi la session des notes avec le même compte UniCA (même cookie CAS que Moodle, le mot de passe n'est envoyé qu'une fois).
- **Rien n'est écrit sur le disque** : ni notes, ni mot de passe. Le mot de passe reste en mémoire tant que le serveur tourne (pour rouvrir la session quand elle expire) et s'efface à la déconnexion.
- Après une relance avec « Se souvenir de moi », il n'y a plus de mot de passe : la carte Notes demande « Mot de passe pour afficher tes notes ».
- Le dashboard respecte les options de ton département : si la promo ou les rangs sont masqués dans le relevé officiel, ils le sont aussi ici.
- Un échec de connexion aux notes ne bloque pas Moodle : il s'affiche comme erreur de la source « Notes » dans la barre latérale.

### Dépôt de devoirs

Depuis la page **Devoirs**, **Déposer** envoie tes fichiers à Moodle sans quitter le dashboard.

- Les règles du devoir (nombre de fichiers, taille, types, date limite, remise définitive ou non, déclaration) sont lues dans Moodle et contrôlées avant l'envoi, côté page et côté serveur.
- Un devoir « avec brouillon » : **Enregistrer le brouillon** autant de fois que tu veux, puis **Rendre définitivement**. Cette dernière étape passe toujours par un écran rouge de vérification (aperçu des fichiers, contenu des ZIP, deux cases à cocher, bouton actif après 3 secondes). Rien n'est rendu sans ça.
- Après chaque opération, le dashboard relit l'état dans Moodle et t'alerte si les fichiers ne correspondent pas à ce que tu as envoyé.
- Les fichiers restent **en mémoire** le temps de l'envoi : rien n'est écrit sur le disque. `UPLOAD_MAX` (`config.py`, 100 Mo par défaut) limite la taille d'un envoi.
- Si le Moodle de l'IUT refuse le dépôt depuis un programme externe, le dashboard le dit et ne propose plus que le lien vers la page Moodle.
- Le mode `--demo` simule tout en mémoire.

### Couleurs par matière

Les couleurs se règlent dans `config.py`, section `MATIERES` (copie-la depuis `config-exemple.py`) : une liste de `{"motif": "...", "nom": "...", "couleur": "#RRGGBB"}`.

- `motif` est une expression régulière, **sans accents ni majuscules** ; la première qui correspond gagne, donc l'ordre compte.
- Une matière sans motif correspondant prend une couleur de `COULEURS_SECOURS`, choisie d'après son code (R3.01, etc.).
- Un motif invalide ou une couleur qui n'est pas au format `#RRGGBB` est ignoré, avec un message dans la console : le dashboard démarre quand même.
- Sans ces lignes dans `config.py` (ancien fichier), tout fonctionne avec les couleurs de secours par défaut. Avec `MATIERES = []`, toutes les matières prennent ces couleurs.

### Mettre à jour son `config.py`

Quand une nouvelle version ajoute des options, ton ancien `config.py` continue de marcher (les valeurs par défaut sont dans `sources/defaults.py`), et la console signale chaque option absente au démarrage. Pour les récupérer :

```bash
python3 dashboard.py --config-diff
```

La commande affiche les blocs manquants, commentaires compris, puis quitte : copie-les à la fin de ton `config.py`. Sans `config.py`, le dashboard explique comment le créer à partir de `config-exemple.py`.

## 3. Lancer

| Système | Commande |
|---|---|
| Windows | double-clic sur `lancer.bat` |
| Linux | `./lancer.sh` (ou `python3 dashboard.py`) |

Options : `--demo`, `--no-browser`, `--verbose`, `--config-diff`.

## Ce que fait chaque page

- **Aujourd'hui** : cours en cours ou à venir, frise de la journée, devoirs les plus urgents, derniers mails.
- **Planning** : vue jour ou semaine, navigation semaine précédente / suivante.
- **Ressources** : tous les documents de tes cours, filtrables (Cours, TD, TP, Examens), groupés par section Moodle ou par type, avec recherche. Le bouton de téléchargement passe par le serveur local, donc pas besoin d'être connecté à Moodle dans le navigateur.
- **Devoirs** : en retard, cette semaine, plus tard, déjà rendus. **Déposer** ouvre un panneau de dépôt (voir plus bas) ; le lien vers la page Moodle reste toujours disponible.
- **Notes** : moyenne, rang et UE du semestre (par UE ou par matière, avec toutes les évaluations). Les nouvelles notes sont signalées.
- **Mails** : 25 derniers mails de la boîte de réception.

## Sécurité

- `config.py` contient ton lien ADE personnel (avec son jeton) et ton adresse mail : ne le partage pas, et fais attention aux captures d'écran qui le montrent.
- `config.py` et `.cache/` (jetons) sont dans `.gitignore`. Vérifie avec `git status` avant chaque push.
- Le serveur n'écoute que sur `127.0.0.1` et refuse les requêtes qui ne viennent pas de `localhost`.
- Les tests utilisent `tests/fixtures/notes_reel_anonyme.json`, une vraie réponse anonymisée : elle est ignorée par git (`.gitignore`), ne la partage pas. Lancer les tests : `python3 -m unittest discover tests`.
- Pour tout réinitialiser : supprime le dossier `.cache/`.

## Dépannage

| Problème | Solution |
|---|---|
| « Connexion UniCA refusée » | Vérifie identifiant et mot de passe, sinon utilise `MOODLE_TOKEN` dans `config.py`. |
| « Le lien ADE ne renvoie pas un calendrier » | Régénère le lien d'export dans ADE. |
| « Microsoft a refusé » / `AADSTS…` | L'université bloque peut-être l'application. Dis-le-moi avec le code d'erreur. |
| Le tri CM/TD/TP se trompe | Il se base sur les noms (« TD3 », « TP », « Annales »…). Les règles sont dans `sources/moodle.py` (`CAT_RULES`). |
| Port déjà utilisé | Change `PORT` dans `config.py`. |
