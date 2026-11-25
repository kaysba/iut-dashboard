#!/bin/sh
# macOS : double-clic pour lancer le dashboard (fait la même chose que lancer.sh).
cd "$(dirname "$0")" || exit 1
sh ./lancer.sh "$@"
status=$?
if [ $status -ne 0 ]; then
    printf "\n  Appuie sur Entrée pour fermer cette fenêtre."
    read -r _
fi
exit $status
