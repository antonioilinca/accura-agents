"""Orchestration : Génération -> Qualification -> Livraison. Un run = une journée."""

from __future__ import annotations

import logging

from .config import Config
from .deliver import livrer
from .llm import LLMClient
from .models import RawLead
from .qualify import CostTracker, qualifier, trier
from .sources import REGISTRE

log = logging.getLogger(__name__)


def run(cfg: Config) -> dict:
    # 1. GÉNÉRATION ----------------------------------------------------------------------
    bruts: list[RawLead] = []
    for nom, source_cfg in cfg.sources.items():
        if not source_cfg.actif:
            continue
        cls = REGISTRE.get(nom)
        if cls is None:
            log.warning("source inconnue ignorée : %s", nom)
            continue
        try:
            bruts.extend(cls(cfg, source_cfg).fetch())
        except Exception as e:  # une source qui plante n'arrête pas les autres
            log.error("source %s a échoué : %s", nom, e)

    bruts = _dedup(_filtre_zone(cfg, bruts))
    scannes = len(bruts)
    log.info("génération : %d opportunités uniques dans la zone", scannes)

    cost = CostTracker(cfg.prix_usd_par_million)
    if scannes == 0:
        log.warning("aucune opportunité à qualifier")
        json_path, recap, _ = livrer(cfg, [], cost.resume(), 0, 0)
        return {"json": str(json_path), "recap": recap, "livres": 0, "scannes": 0,
                "cost": cost.resume()}

    client = LLMClient(cfg)
    log.info("LLM : provider=%s | tri=%s | qualif=%s",
             cfg.llm_provider, cfg.modele_tri, cfg.modele_qualif)

    # 2. QUALIFICATION -------------------------------------------------------------------
    tries = trier(client, cfg, bruts, cost)
    qualifies = qualifier(client, cfg, tries, cost)

    # 3. LIVRAISON -----------------------------------------------------------------------
    json_path, recap, nouveaux = livrer(cfg, qualifies, cost.resume(), scannes, len(tries))
    return {
        "json": str(json_path),
        "recap": recap,
        "livres": len(nouveaux),
        "scannes": scannes,
        "cost": cost.resume(),
    }


def _filtre_zone(cfg: Config, leads: list[RawLead]) -> list[RawLead]:
    """Garde les leads dont la commune est dans la zone cible. L'inbox manuelle (commune
    souvent absente) passe toujours : la qualification jugera la zone via le texte."""
    if not cfg.communes:
        return leads
    cibles = {c.lower() for c in cfg.communes}
    return [
        l for l in leads
        if l.source == "inbox_manuelle" or not l.commune or l.commune.lower() in cibles
    ]


def _dedup(leads: list[RawLead]) -> list[RawLead]:
    uniques: dict[str, RawLead] = {}
    for l in leads:
        uniques.setdefault(l.dedup_key, l)
    return list(uniques.values())
