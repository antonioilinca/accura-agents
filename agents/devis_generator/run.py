"""Point d'entrée de l'Agent Devis Accura.

    python -m agents.devis_generator.run --input "Refaire une salle de bain..."
    python -m agents.devis_generator.run --input-file demande.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from agents.common.native_libs import assurer_libs_pdf

from .config import charger_config
from .generator import generer_devis
from .render import ecrire_exports, rendre_markdown

RACINE = Path(__file__).resolve().parents[2]


def _config_par_defaut() -> Path:
    locale = RACINE / "config" / "devis.yaml"
    if locale.exists():
        return locale
    return RACINE / "config" / "devis.example.yaml"


def main() -> None:
    assurer_libs_pdf()  # PDF natif en local (macOS) ; no-op en prod Docker
    load_dotenv(RACINE / ".env")
    parser = argparse.ArgumentParser(description="Agent Devis Accura — demande brute -> devis")
    parser.add_argument("--config", default=str(_config_par_defaut()), help="chemin du devis.yaml")
    parser.add_argument("--input", default=None, help="demande client brute")
    parser.add_argument("--input-file", default=None, help="fichier texte contenant la demande")
    parser.add_argument("--id", default=None, help="identifiant de devis optionnel")
    args = parser.parse_args()

    if not args.input and not args.input_file:
        parser.error("Ajoute --input ou --input-file")

    texte = args.input
    if args.input_file:
        texte = Path(args.input_file).read_text(encoding="utf-8")

    try:
        cfg = charger_config(args.config)
        dossier = RACINE / cfg.dossier_sortie
        doc = generer_devis(str(texte), cfg, id_devis=args.id, dossier=dossier)
        # Un id fourni à la main est une ré-édition volontaire du même devis.
        paths = ecrire_exports(doc, dossier, ecraser=bool(args.id))
    except Exception as exc:
        print(f"Erreur agent devis : {exc}", file=sys.stderr)
        sys.exit(2)

    print(rendre_markdown(doc))
    print("\nExports écrits :")
    for nom, chemin in paths.items():
        print(f"- {nom}: {chemin}")


if __name__ == "__main__":
    main()
