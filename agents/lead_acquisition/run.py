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


def _verifier_cle(cfg, log) -> None:
    """Vérifie que la clé nécessaire au fournisseur choisi est présente."""
    if cfg.llm_provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log.error("ANTHROPIC_API_KEY manquante (provider=anthropic). Renseigne-la dans .env.")
            sys.exit(2)
        return
    # openai_compat : clé requise sauf serveur local (Ollama)
    base = (cfg.llm_base_url or "").lower()
    local = any(x in base for x in ("localhost", "127.0.0.1", ":11434"))
    if not local and not os.environ.get(cfg.llm_api_key_env):
        log.error(
            "%s manquante (provider=openai_compat, base_url=%s). Renseigne-la dans .env.",
            cfg.llm_api_key_env, cfg.llm_base_url,
        )
        sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent acquisition de leads — Accura Ouest")
    parser.add_argument("--config", default=None, help="chemin du config.yaml")
    args = parser.parse_args()

    load_dotenv(RACINE / ".env")
    _setup_logs()
    log = logging.getLogger("run")

    chemin = args.config or (RACINE / "config" / "config.yaml")
    try:
        cfg = charger_config(chemin)
    except (FileNotFoundError, ValueError) as e:
        log.error("%s", e)
        sys.exit(2)

    _verifier_cle(cfg, log)

    log.info(
        "Métier=%s | communes=%d | seuil=%d | provider=%s",
        cfg.metier.nom, len(cfg.communes), cfg.seuil_livraison, cfg.llm_provider,
    )

    resultat = run_pipeline(cfg)
    print("\n" + resultat["recap"])
    log.info("Terminé : %d lead(s) livré(s) -> %s", resultat["livres"], resultat["json"])


if __name__ == "__main__":
    main()
