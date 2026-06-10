"""Point d'entrée de l'Agent Factures Accura.

    python -m agents.facture_generator.run --quote outputs/devis/acc-xxx.json --type acompte
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .generator import charger_devis_json, generer_facture_depuis_devis
from .render import ecrire_exports, rendre_markdown

RACINE = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Factures Accura — devis validé -> facture")
    parser.add_argument("--quote", required=True, help="chemin du JSON devis source")
    parser.add_argument("--type", choices=["acompte", "solde"], default="acompte", help="type de facture")
    parser.add_argument("--id", default=None, help="identifiant de facture optionnel")
    parser.add_argument("--output-dir", default="outputs/factures", help="dossier de sortie")
    args = parser.parse_args()

    try:
        devis = charger_devis_json(args.quote)
        dossier = RACINE / args.output_dir
        doc = generer_facture_depuis_devis(
            devis, type_facture=args.type, id_facture=args.id, dossier=dossier
        )
        paths = ecrire_exports(doc, dossier)
    except Exception as exc:
        print(f"Erreur agent factures : {exc}", file=sys.stderr)
        sys.exit(2)

    print(rendre_markdown(doc))
    print("\nExports écrits :")
    for nom, chemin in paths.items():
        print(f"- {nom}: {chemin}")


if __name__ == "__main__":
    main()

