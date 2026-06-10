"""Qualification : tri grossier (par lots) puis scoring fin (par lead).

Indépendant du fournisseur LLM : passe par LLMClient (Groq/Mistral/Ollama gratuits, ou
Claude). Le coût réel est mesuré (0 sur un fournisseur gratuit). Une erreur sur un lead
n'arrête jamais le run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .config import Config
from .llm import LLMClient, Usage
from .models import QualifiedLead, RawLead, Signaux
from .prompts import OUTIL_QUALIF, OUTIL_TRI, system_qualif, system_tri

log = logging.getLogger(__name__)


class CostTracker:
    """Accumule l'usage tokens par modèle et estime le coût USD via les prix de la config
    (0 si le modèle n'a pas de prix, donc gratuit)."""

    def __init__(self, prix_usd_par_million: dict[str, float]) -> None:
        self.prix = prix_usd_par_million
        self.usage: dict[str, dict[str, int]] = {}

    def add(self, model: str, usage: Usage) -> None:
        acc = self.usage.setdefault(
            model, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        )
        acc["input"] += usage.input
        acc["output"] += usage.output
        acc["cache_read"] += usage.cache_read
        acc["cache_write"] += usage.cache_write

    def cout_usd(self) -> float:
        total = 0.0
        for model, u in self.usage.items():
            m = model.lower()
            base = "haiku" if "haiku" in m else "sonnet" if "sonnet" in m else "opus" if "opus" in m else None
            if base is None:  # modèle gratuit (Groq/Mistral/Ollama) : aucun prix
                continue
            p_in = self.prix.get(f"{base}_input", 0.0)
            p_out = self.prix.get(f"{base}_output", 0.0)
            total += (u["input"] / 1e6) * p_in + (u["output"] / 1e6) * p_out
            total += (u["cache_read"] / 1e6) * p_in * 0.10
            total += (u["cache_write"] / 1e6) * p_in * 1.25
        return round(total, 4)

    def resume(self) -> dict:
        return {"usage": self.usage, "cout_usd_estime": self.cout_usd()}


def trier(client: LLMClient, cfg: Config, leads: list[RawLead], cost: CostTracker) -> list[RawLead]:
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
            sortie, usage = client.structured(
                systeme, message, OUTIL_TRI["input_schema"], "trier_leads",
                cfg.modele_tri, max_tokens=2000, cache=False,
            )
            cost.add(cfg.modele_tri, usage)
        except Exception as e:
            log.error("tri : erreur sur un lot (%s) — lot conservé par défaut", e)
            gardes.extend(lot)
            continue

        decisions = {d.get("id"): d for d in (sortie or {}).get("decisions", [])}
        for lead in lot:
            d = decisions.get(lead.dedup_key)
            if d is None or d.get("garder", True):
                gardes.append(lead)

    log.info("tri : %d / %d opportunités gardées", len(gardes), len(leads))
    return gardes


def qualifier(client: LLMClient, cfg: Config, leads: list[RawLead], cost: CostTracker) -> list[QualifiedLead]:
    """Scoring fin, un appel par lead, sortie structurée."""
    systeme = system_qualif(cfg)
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    resultats: list[QualifiedLead] = []

    # Coût et durée bornés : au-delà du plafond, les dossiers les plus anciens sont
    # reportés (non marqués vus → ils reviennent au run suivant).
    if cfg.max_qualif_par_run > 0 and len(leads) > cfg.max_qualif_par_run:
        leads = sorted(leads, key=lambda l: l.date_signal or "", reverse=True)
        reportes = len(leads) - cfg.max_qualif_par_run
        leads = leads[: cfg.max_qualif_par_run]
        log.warning(
            "qualif : plafond %d atteint — %d dossier(s) reporté(s) au prochain run",
            cfg.max_qualif_par_run, reportes,
        )

    for lead in leads:
        try:
            data, usage = client.structured(
                systeme, _format_lead(lead), OUTIL_QUALIF["input_schema"], "qualifier_lead",
                cfg.modele_qualif, max_tokens=900, cache=True,
            )
            cost.add(cfg.modele_qualif, usage)
        except Exception as e:
            log.error("qualif : erreur sur %s — ignoré (%s)", lead.dedup_key, e)
            continue
        if not data:
            log.warning("qualif : réponse non parsable pour %s — ignoré", lead.dedup_key)
            continue

        sig = data.get("signaux") or {}
        try:
            score = int(data.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        score = max(0, min(100, score))
        justification = str(data.get("justification", ""))
        # Garde-fou déterministe (le prompt seul ne suffit pas) : une opération
        # au-delà de l'échelle artisan ne peut jamais être livrée comme lead chaud.
        if cfg.surface_max_artisan > 0 and (lead.surface_plancher or 0) > cfg.surface_max_artisan:
            score = min(score, 25)
            justification += (
                f" [Score plafonné : {lead.surface_plancher} m² dépasse l'échelle "
                f"artisan ({cfg.surface_max_artisan} m²).]"
            )
        resultats.append(
            QualifiedLead(
                raw=lead,
                metier=cfg.metier.nom,
                score=score,
                justification=justification,
                signaux=Signaux(
                    adequation_metier=str(sig.get("adequation_metier", "inconnue")),
                    ampleur_travaux=str(sig.get("ampleur_travaux", "inconnue")),
                    fraicheur=str(sig.get("fraicheur", "inconnue")),
                    signal_budget=str(sig.get("signal_budget", "inconnu")),
                    zone_ok=bool(sig.get("zone_ok", True)),
                    contactabilite=str(sig.get("contactabilite", "moyenne")),
                ),
                message_contact=str(data.get("message_contact", "")),
                qualified_at=maintenant,
                type_opportunite=str(data.get("type_opportunite", "opportunite_a_demarcher")),
                canal_recommande=str(data.get("canal_recommande", "courrier")),
                urgence_contact=str(data.get("urgence_contact", "cette_semaine")),
                valeur_potentielle=str(data.get("valeur_potentielle", "moyenne")),
                angle_approche=str(data.get("angle_approche", "")),
                prochaine_action=str(data.get("prochaine_action", "")),
                script_appel=str(data.get("script_appel", "")),
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
