# Dashboard IUT

Tableau de bord local pour l'IUT Nice Côte d'Azur : emploi du temps ADE, ressources Moodle triées (CM, TD, TP, examens), devoirs à rendre avec lien direct vers le dépôt, et derniers mails Outlook.

Le serveur tourne **sur ta machine uniquement** (`127.0.0.1`). Rien n'est envoyé ailleurs que vers Moodle, ADE et Microsoft.

Aucune bibliothèque à installer : seulement **Python 3.9 ou plus récent**.

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

### Couleurs par matière

Les couleurs se règlent dans `config.py`, section `MATIERES` (copie-la depuis `config-exemple.py`) : une liste de `{"motif": "...", "nom": "...", "couleur": "#RRGGBB"}`.

- `motif` est une expression régulière, **sans accents ni majuscules** ; la première qui correspond gagne, donc l'ordre compte.
- Une matière sans motif correspondant prend une couleur de `COULEURS_SECOURS`, choisie d'après son code (R3.01, etc.).
- Un motif invalide ou une couleur qui n'est pas au format `#RRGGBB` est ignoré, avec un message dans la console : le dashboard démarre quand même.
- Sans ces lignes dans `config.py` (ancien fichier), tout fonctionne avec les couleurs de secours par défaut. Avec `MATIERES = []`, toutes les matières prennent ces couleurs.

## 3. Lancer

| Système | Commande |
|---|---|
| Windows | double-clic sur `lancer.bat` |
| Linux | `./lancer.sh` (ou `python3 dashboard.py`) |

Options : `--demo`, `--no-browser`, `--verbose`.

## Ce que fait chaque page

- **Aujourd'hui** : cours en cours ou à venir, frise de la journée, devoirs les plus urgents, derniers mails.
- **Planning** : vue jour ou semaine, navigation semaine précédente / suivante.
- **Ressources** : tous les documents de tes cours, filtrables (Cours, TD, TP, Examens), groupés par section Moodle ou par type, avec recherche. Le bouton de téléchargement passe par le serveur local, donc pas besoin d'être connecté à Moodle dans le navigateur.
- **Devoirs** : en retard, cette semaine, plus tard, déjà rendus. **Déposer** ouvre directement la page de dépôt Moodle.
- **Mails** : 25 derniers mails de la boîte de réception.

## Sécurité

- `config.py` et `.cache/` (jetons) sont dans `.gitignore`. Vérifie avec `git status` avant chaque push.
- Le serveur n'écoute que sur `127.0.0.1` et refuse les requêtes qui ne viennent pas de `localhost`.
- Pour tout réinitialiser : supprime le dossier `.cache/`.

## Dépannage

| Problème | Solution |
|---|---|
| « Connexion UniCA refusée » | Vérifie identifiant et mot de passe, sinon utilise `MOODLE_TOKEN` dans `config.py`. |
| « Le lien ADE ne renvoie pas un calendrier » | Régénère le lien d'export dans ADE. |
| « Microsoft a refusé » / `AADSTS…` | L'université bloque peut-être l'application. Dis-le-moi avec le code d'erreur. |
| Le tri CM/TD/TP se trompe | Il se base sur les noms (« TD3 », « TP », « Annales »…). Les règles sont dans `sources/moodle.py` (`CAT_RULES`). |
| Port déjà utilisé | Change `PORT` dans `config.py`. |
