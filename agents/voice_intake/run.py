"""Agent Vocal Accura : transcrit un vocal d'artisan, puis devis brouillon optionnel.

    python -m agents.voice_intake.run --audio memo.m4a
    python -m agents.voice_intake.run --audio memo.m4a --devis

Le texte transcrit est affiché pour RELECTURE. Avec --devis, un devis brouillon est
généré (à vérifier, rien n'est envoyé). Les prix viennent toujours de la config artisan,
jamais de la voix ni de l'IA.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from .transcriber import transcrire

RACINE = Path(__file__).resolve().parents[2]


def _config_devis() -> Path:
    locale = RACINE / "config" / "devis.yaml"
    return locale if locale.exists() else RACINE / "config" / "devis.example.yaml"


def main() -> None:
    load_dotenv(RACINE / ".env")
    parser = argparse.ArgumentParser(description="Agent Vocal Accura — vocal -> texte (-> devis)")
    parser.add_argument("--audio", required=True, help="fichier audio (m4a, mp3, wav, aiff...)")
    parser.add_argument("--provider", default=None, help="local (défaut) | openai")
    parser.add_argument("--model", default=None, help="modèle whisper local (défaut: small)")
    parser.add_argument("--devis", action="store_true", help="génère aussi un devis brouillon à relire")
    parser.add_argument("--id", default=None, help="identifiant de devis optionnel")
    args = parser.parse_args()

    if not Path(args.audio).exists():
        parser.error(f"Fichier audio introuvable : {args.audio}")

    try:
        texte = transcrire(args.audio, provider=args.provider, model=args.model)
    except Exception as exc:
        print(f"Erreur transcription : {exc}", file=sys.stderr)
        sys.exit(2)

    print("=== Transcription (à relire et corriger avant d'envoyer quoi que ce soit) ===")
    print(texte or "(aucun texte détecté)")

    if not args.devis:
        return

    try:
        from agents.devis_generator.config import charger_config
        from agents.devis_generator.generator import generer_devis
        from agents.devis_generator.render import ecrire_exports

        cfg = charger_config(_config_devis())
        doc = generer_devis(texte, cfg, id_devis=args.id)
        paths = ecrire_exports(doc, RACINE / cfg.dossier_sortie)
    except Exception as exc:
        print(f"Erreur génération devis : {exc}", file=sys.stderr)
        sys.exit(2)

    data = doc.to_dict()
    demande = data.get("demande", {})
    totaux = data.get("totaux", {})
    questions = demande.get("questions", []) or []
    print("\n=== Devis BROUILLON (à vérifier — rien n'est envoyé automatiquement) ===")
    print(f"  Métier  : {demande.get('metier_libelle', '-')}")
    print(f"  Ville   : {demande.get('ville', 'à préciser')}")
    print(f"  Total TTC : {totaux.get('total_ttc', 0)}")
    if questions:
        print(f"  À confirmer avec le client : {' | '.join(questions)}")
    print("  Documents :")
    for nom, chemin in paths.items():
        print(f"    - {nom}: {chemin}")


if __name__ == "__main__":
    main()
