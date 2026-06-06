"""Point d'entrée. Un run complet, conçu pour être lancé par cron (1x/jour).

    python -m agents.lead_acquisition.run
    python -m agents.lead_acquisition.run --config /chemin/config.yaml
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .config import charger_config
from .pipeline import run as run_pipeline

RACINE = Path(__file__).resolve().parents[2]  # .../accura-agents


def _setup_logs() -> None:
    (RACINE / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                RACINE / "logs" / f"run-{date.today().isoformat()}.log", encoding="utf-8"
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent acquisition de leads — Accura Ouest"
    )
    parser.add_argument("--config", default=None, help="chemin du config.yaml")
    args = parser.parse_args()

    load_dotenv(RACINE / ".env")
    _setup_logs()
    log = logging.getLogger("run")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error(
            "ANTHROPIC_API_KEY manquante. Copie .env.example vers .env et renseigne la clé."
        )
        sys.exit(2)

    chemin = args.config or (RACINE / "config" / "config.yaml")
    try:
        cfg = charger_config(chemin)
    except (FileNotFoundError, ValueError) as e:
        log.error("%s", e)
        sys.exit(2)

    log.info(
        "Métier=%s | communes=%d | seuil=%d | tri=%s | qualif=%s",
        cfg.metier.nom, len(cfg.communes), cfg.seuil_livraison,
        cfg.modele_tri, cfg.modele_qualif,
    )

    resultat = run_pipeline(cfg)
    print("\n" + resultat["recap"])
    log.info("Terminé : %d lead(s) livré(s) -> %s", resultat["livres"], resultat["json"])


if __name__ == "__main__":
    main()
