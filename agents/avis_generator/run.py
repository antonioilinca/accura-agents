"""Point d'entrée de l'Agent Avis Google Accura."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agents.dashboard.onboarding import load_profile

from .generator import generer_demande_avis
from .render import ecrire_exports

RACINE = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Avis Google Accura — chantier terminé -> message")
    parser.add_argument("--client", default="", help="nom ou formule client")
    parser.add_argument("--chantier", default="", help="chantier terminé")
    parser.add_argument("--output-dir", default="outputs/avis", help="dossier de sortie")
    args = parser.parse_args()

    try:
        request = generer_demande_avis(load_profile(RACINE), client=args.client, chantier=args.chantier)
        paths = ecrire_exports(request, RACINE / args.output_dir)
    except Exception as exc:
        print(f"Erreur agent avis Google : {exc}", file=sys.stderr)
        sys.exit(2)

    print(request.message)
    print("\nExports écrits :")
    for nom, chemin in paths.items():
        print(f"- {nom}: {chemin}")


if __name__ == "__main__":
    main()

