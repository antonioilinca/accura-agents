#!/bin/bash
# Double-clique ce fichier pour lancer l'agent et voir les leads dans le navigateur.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
echo "Recherche des leads en cours... (laisse la fenêtre ouverte, ~2-3 min)"
uv run python -m agents.lead_acquisition.run
open outputs/index.html
echo ""
echo "Termine. La page des leads s'est ouverte dans ton navigateur."
