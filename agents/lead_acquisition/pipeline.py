"""Orchestration : Génération -> Qualification -> Livraison. Un run = une journée."""

from __future__ import annotations

import logging
from typing import Callable

from .config import Config
from .deliver import livrer
from .llm import LLMClient
from .models import RawLead
from .qualify import CostTracker, qualifier, trier
from .sources import REGISTRE

log = logging.getLogger(__name__)


def run(
    cfg: Config,
    on_step: Callable[[str], None] | None = None,
    limite_opportunites: int | None = None,
) -> dict:
    """Lance un run complet.

    ``on_step`` (optionnel) reçoit un message lisible à chaque grande étape :
    le dashboard l'utilise pour afficher l'agent en train de travailler en
    temps réel. Par défaut (None), le comportement est strictement inchangé.

    ``limite_opportunites`` (optionnel) ne qualifie qu'un échantillon des
    opportunités scannées : sert au « mode test » du cockpit pour voir l'agent
    travailler vite. Le run quotidien (cron) appelle ``run(cfg)`` sans limite et
    traite donc toutes les opportunités, comportement inchangé.
    """
    def _emit(message: str) -> None:
        if on_step is not None:
            try:
                on_step(message)
            except Exception:  # un afficheur qui plante ne doit pas casser le run
                pass

    # 1. GÉNÉRATION ----------------------------------------------------------------------
    _emit("Scan des sources d'opportunités (open data urbanisme + inbox)…")
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
    _emit(f"Génération : {scannes} opportunité(s) unique(s) dans la zone")

    cost = CostTracker(cfg.prix_usd_par_million)
    if scannes == 0:
        log.warning("aucune opportunité à qualifier")
        _emit("Aucune opportunité à qualifier aujourd'hui")
        json_path, recap, _ = livrer(cfg, [], cost.resume(), 0, 0)
        return {"json": str(json_path), "recap": recap, "livres": 0, "scannes": 0,
                "cost": cost.resume()}

    client = LLMClient(cfg)
    log.info("LLM : provider=%s | tri=%s | qualif=%s",
             cfg.llm_provider, cfg.modele_tri, cfg.modele_qualif)

    a_qualifier = bruts
    if limite_opportunites is not None and len(bruts) > limite_opportunites:
        a_qualifier = bruts[:limite_opportunites]
        _emit(f"Mode test : qualification d'un échantillon de {len(a_qualifier)} "
              f"(le run quotidien complet traite les {scannes})")

    # 2. QUALIFICATION -------------------------------------------------------------------
    _emit(f"Tri rapide par l'IA ({cfg.modele_tri})…")
    tries = trier(client, cfg, a_qualifier, cost)
    _emit(f"Tri terminé : {len(tries)} opportunité(s) retenue(s)")
    _emit(f"Qualification fine par l'IA ({cfg.modele_qualif})…")
    qualifies = qualifier(client, cfg, tries, cost)
    _emit(f"Qualification terminée : {len(qualifies)} opportunité(s) évaluée(s)")

    # 3. LIVRAISON -----------------------------------------------------------------------
    json_path, recap, nouveaux = livrer(cfg, qualifies, cost.resume(), scannes, len(tries))
    _emit(f"Livraison : {len(nouveaux)} lead(s) au-dessus du seuil de livraison")
    return {
        "json": str(json_path),
        "recap": recap,
        "livres": len(nouveaux),
        "scannes": scannes,
        "echantillon": len(a_qualifier),
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
