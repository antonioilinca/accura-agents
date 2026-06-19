#!/bin/bash
# Double-clique ce fichier pour lancer l'API de la plateforme artisan en local.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
echo "Démarrage de l'API plateforme Accura..."
echo "Elle écoutera sur http://127.0.0.1:8790/api/v1"
echo "(Laisse cette fenêtre ouverte. Ctrl+C pour arrêter.)"
echo ""
uv run python -m agents.platform.run
