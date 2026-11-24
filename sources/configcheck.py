"""Compare config.py à config-exemple.py : options absentes, blocs à copier."""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXEMPLE = os.path.join(ROOT, "config-exemple.py")


def blocs_exemple(path=EXEMPLE):
    """{NOM: bloc de texte complet, commentaires compris} pour chaque option en majuscules du fichier
    exemple. Le fichier est lu avec ast, jamais exécuté."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lines = src.splitlines()
    out = {}
    for node in ast.parse(src).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper()):
            continue
        start = node.lineno - 1
        while start > 0 and lines[start - 1].lstrip().startswith("#"):   # commentaires collés au-dessus
            start -= 1
        out[node.targets[0].id] = "\n".join(lines[start:node.end_lineno])
    return out


def options_absentes(config, path=EXEMPLE):
    """Noms (dans l'ordre du fichier exemple) que config.py ne définit pas."""
    return [n for n in blocs_exemple(path) if not hasattr(config, n)]


def avertir(config, out, path=EXEMPLE):
    for n in options_absentes(config, path):
        print(f"[config] Option absente de config.py : {n} (valeur par défaut utilisée). "
              "Copie-la depuis config-exemple.py.", file=out)


def diff_complet(config, out, path=EXEMPLE):
    blocs = blocs_exemple(path)
    manquantes = options_absentes(config, path)
    if not manquantes:
        print("config.py est à jour : aucune option manquante.", file=out)
        return
    print("# Options absentes de ton config.py. Copie ces blocs à la fin du fichier.\n", file=out)
    for n in manquantes:
        print(blocs[n], file=out)
        print(file=out)


MESSAGE_SANS_CONFIG = """
  Il n'y a pas de config.py : copie le fichier d'exemple puis adapte-le.

    Linux / macOS :  cp config-exemple.py config.py
    Windows       :  copy config-exemple.py config.py

  (Pour essayer sans rien configurer :  python3 dashboard.py --demo)
"""
