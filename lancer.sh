#!/bin/sh
# Dashboard IUT : lance le serveur local et ouvre le navigateur sur l'assistant.
cd "$(dirname "$0")" || exit 1

for p in python3 python; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 8))' 2>/dev/null; then
        exec "$p" dashboard.py "$@"
    fi
done

echo
echo "  Python 3.8 ou plus récent n'est pas installé sur cet ordinateur."
echo
echo "  macOS : télécharge-le sur https://www.python.org/downloads/ puis relance ce fichier."
echo "  Linux : installe le paquet python3 (ex. sudo apt install python3), puis relance."
echo
exit 1
