"""Point d'entrée de l'Agent Relances Accura.

    python -m agents.relance_generator.run --quote outputs/devis/acc-xxx.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .generator import charger_devis_json, generer_relances_depuis_devis
from .render import ecrire_exports

RACINE = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Relances Accura — devis -> J+3/J+7/J+15")
    parser.add_argument("--quote", required=True, help="chemin du JSON devis source")
    parser.add_argument("--output-dir", default="outputs/relances", help="dossier de sortie")
    args = parser.parse_args()

    try:
        devis = charger_devis_json(args.quote)
        plan = generer_relances_depuis_devis(devis)
        paths = ecrire_exports(plan, RACINE / args.output_dir)
    except Exception as exc:
        print(f"Erreur agent relances : {exc}", file=sys.stderr)
        sys.exit(2)

    for message in plan.messages:
        print(f"\n## J+{message.jour} — {message.date_prevue}")
        print(message.message)
    print("\nExports écrits :")
    for nom, chemin in paths.items():
        print(f"- {nom}: {chemin}")


if __name__ == "__main__":
    main()

