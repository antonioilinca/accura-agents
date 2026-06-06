"""Qualification : tri grossier (Haiku, par lots) puis scoring fin (Sonnet, par lead).

Économie : Haiku trie en masse (peu cher), Sonnet ne score que les survivants. Le system
prompt de scoring est mis en cache (cache_control ephemeral) car il est réutilisé à chaque
lead du run. Le coût réel est mesuré, pas supposé.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import anthropic

from .config import Config
from .models import QualifiedLead, RawLead, Signaux
from .prompts import OUTIL_QUALIF, OUTIL_TRI, system_qualif, system_tri

log = logging.getLogger(__name__)


class CostTracker:
    """Accumule l'usage tokens et estime le coût en USD à partir des prix de la config."""

    def __init__(self, prix_usd_par_million: dict[str, float]) -> None:
        self.prix = prix_usd_par_million
        self.usage: dict[str, dict[str, int]] = {}

    def add(self, model: str, u) -> None:
        acc = self.usage.setdefault(
            model, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        )
        acc["input"] += getattr(u, "input_tokens", 0) or 0
        acc["output"] += getattr(u, "output_tokens", 0) or 0
        acc["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
        acc["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0

    def cout_usd(self) -> float:
        total = 0.0
        for model, u in self.usage.items():
            base = "haiku" if "haiku" in model else "sonnet" if "sonnet" in model else "opus"
            p_in = self.prix.get(f"{base}_input", 0.0)
            p_out = self.prix.get(f"{base}_output", 0.0)
            total += (u["input"] / 1e6) * p_in + (u["output"] / 1e6) * p_out
            # cache : lecture ~10% du prix d'entrée, écriture ~125% (ordres documentés)
            total += (u["cache_read"] / 1e6) * p_in * 0.10
            total += (u["cache_write"] / 1e6) * p_in * 1.25
        return round(total, 4)

    def resume(self) -> dict:
        return {"usage": self.usage, "cout_usd_estime": self.cout_usd()}


def _appel_outil(client, model, system, outils, nom_outil, message, max_tokens, cache, cost):
    blocs_system = [{"type": "text", "text": system}]
    if cache:
        blocs_system[0]["cache_control"] = {"type": "ephemeral"}
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=blocs_system,
        tools=outils,
        tool_choice={"type": "tool", "name": nom_outil},
        messages=[{"role": "user", "content": message}],
    )
    if cost is not None:
        cost.add(model, resp.usage)
    for bloc in resp.content:
        if bloc.type == "tool_use" and bloc.name == nom_outil:
            return bloc.input
    return None


def trier(client, cfg: Config, leads: list[RawLead], cost: CostTracker) -> list[RawLead]:
    """Tri grossier par métier, par lots. Fail-open : en cas de doute, on garde."""
    if not leads:
        return []
    systeme = system_tri(cfg)
    taille = max(1, cfg.taille_lot_tri)
    gardes: list[RawLead] = []

    for debut in range(0, len(leads), taille):
        lot = leads[debut : debut + taille]
        lignes = [
            f"- id={l.dedup_key} | commune={l.commune or '?'} | type={l.type_dossier or '?'} "
            f"| surface={l.surface_plancher if l.surface_plancher is not None else '?'} m2 "
            f"| projet : {l.description or '(sans description)'}"
            for l in lot
        ]
        message = "Annonces à trier :\n" + "\n".join(lignes)
        try:
            sortie = _appel_outil(
                client, cfg.modele_tri, systeme, [OUTIL_TRI], "trier_leads",
                message, max_tokens=1500, cache=False, cost=cost,
            )
        except anthropic.APIError as e:
            log.error("tri : erreur API sur un lot (%s) — lot conservé par défaut", e)
            gardes.extend(lot)
            continue

        decisions = {d.get("id"): d for d in (sortie or {}).get("decisions", [])}
        for lead in lot:
            d = decisions.get(lead.dedup_key)
            if d is None or d.get("garder", True):
                gardes.append(lead)

    log.info("tri : %d / %d opportunités gardées", len(gardes), len(leads))
    return gardes


def qualifier(client, cfg: Config, leads: list[RawLead], cost: CostTracker) -> list[QualifiedLead]:
    """Scoring fin, un appel par lead, sortie structurée. Une erreur sur un lead n'arrête
    pas le run."""
    systeme = system_qualif(cfg)
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    resultats: list[QualifiedLead] = []

    for lead in leads:
        try:
            data = _appel_outil(
                client, cfg.modele_qualif, systeme, [OUTIL_QUALIF], "qualifier_lead",
                _format_lead(lead), max_tokens=900, cache=True, cost=cost,
            )
        except anthropic.APIError as e:
            log.error("qualif : erreur API sur %s — ignoré (%s)", lead.dedup_key, e)
            continue
        if not data:
            continue

        sig = data.get("signaux") or {}
        resultats.append(
            QualifiedLead(
                raw=lead,
                metier=cfg.metier.nom,
                score=int(data.get("score", 0)),
                justification=str(data.get("justification", "")),
                signaux=Signaux(
                    adequation_metier=sig.get("adequation_metier", "inconnue"),
                    ampleur_travaux=sig.get("ampleur_travaux", "inconnue"),
                    fraicheur=sig.get("fraicheur", "inconnue"),
                    signal_budget=sig.get("signal_budget", "inconnu"),
                    zone_ok=bool(sig.get("zone_ok", True)),
                ),
                message_contact=str(data.get("message_contact", "")),
                qualified_at=maintenant,
            )
        )

    resultats.sort(key=lambda x: x.score, reverse=True)
    log.info("qualif : %d opportunités scorées", len(resultats))
    return resultats


def _format_lead(lead: RawLead) -> str:
    surface = lead.surface_plancher if lead.surface_plancher is not None else "inconnue"
    return (
        "Opportunité à évaluer :\n"
        f"- Commune : {lead.commune or 'inconnue'}\n"
        f"- Adresse : {lead.adresse or 'inconnue'}\n"
        f"- Type de dossier : {lead.type_dossier or 'inconnu'}\n"
        f"- Surface de plancher (m2) : {surface}\n"
        f"- Date du signal : {lead.date_signal or 'inconnue'}\n"
        f"- Source : {lead.source}\n"
        f"- Description du projet : {lead.description or '(vide)'}"
    )
