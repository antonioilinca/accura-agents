"""Finition IA optionnelle pour les devis.

La règle de sécurité est stricte : l'IA améliore la rédaction et la clarification, mais
ne modifie jamais les lignes de devis ni les totaux. Le chiffrage reste dans la config.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from decimal import Decimal
from types import SimpleNamespace
from typing import Protocol

from agents.lead_acquisition.llm import LLMClient

from .models import QuoteConfig, QuoteDocument


class StructuredClient(Protocol):
    def structured(
        self,
        system: str,
        user: str,
        schema: dict,
        nom_schema: str,
        model: str,
        max_tokens: int,
        cache: bool = False,
    ) -> tuple[dict | None, object]:
        ...


SCHEMA_FINITION_DEVIS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "resume_pro": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "message_client": {"type": "string"},
        "notes_artisan": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resume_pro", "questions", "message_client", "notes_artisan"],
}


SYSTEM_FINITION_DEVIS = """Tu aides Accura Ouest à produire des devis professionnels pour des artisans du bâtiment.

Objectif : rendre le devis naturel, clair et crédible, comme si l'artisan l'avait rédigé.

Règles non négociables :
- Ne modifie jamais les prix, quantités, TVA, totaux ou acomptes.
- N'invente jamais une prestation non présente dans les lignes.
- Ne promets jamais un délai, une disponibilité ou une garantie non fournie.
- Ne dis jamais que le devis vient d'une IA.
- N'inclus jamais le numéro ou la référence interne du devis dans le message client.
- Parle du chantier avec les mots du client ("votre salle de bain"), pas du type technique.
- Ton style doit être simple, professionnel, artisan, pas startup.
- Si des informations manquent, pose des questions courtes et utiles.
- Garde le message client court et direct : 2 à 4 phrases maximum.
- Le message client doit pouvoir être envoyé tel quel sur WhatsApp ou par email.
"""


def creer_client_llm_si_disponible(cfg: QuoteConfig) -> tuple[StructuredClient | None, str | None]:
    """Retourne un client LLM seulement si la config et les clés sont prêtes.

    Mode `auto` (par ordre de priorité) :
    1. OpenAI si `OPENAI_API_KEY` existe (qualité maximale, payant) ;
    2. sinon Anthropic si `ANTHROPIC_API_KEY` existe (qualité maximale, payant) ;
    3. sinon Groq si `GROQ_API_KEY` existe (gratuit, finition correcte — même
       fournisseur que l'agent leads, pour que la démo Fondation soit déjà soignée
       sans clé payante) ;
    4. sinon aucune clé : l'agent reste en mode local (devis généré sans IA).

    Ajouter une clé OpenAI/Anthropic suffit donc à reprendre la qualité maximale,
    sans rien éditer d'autre. Dans tous les cas, l'IA ne touche jamais aux prix,
    quantités, TVA ni totaux (garde-fous dans `_appliquer_finition_validee`).
    """
    llm = cfg.llm
    if not llm.actif or llm.provider == "off":
        return None, None

    provider = llm.provider
    base_url = llm.base_url
    api_key_env = llm.api_key_env
    modele = llm.modele

    if provider == "auto":
        if os.environ.get("OPENAI_API_KEY"):
            provider = "openai_compat"
            base_url = "https://api.openai.com/v1"
            api_key_env = "OPENAI_API_KEY"
            modele = llm.modele
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
            base_url = ""
            api_key_env = "ANTHROPIC_API_KEY"
            modele = llm.modele_anthropic
        elif os.environ.get("GROQ_API_KEY"):
            provider = "openai_compat"
            base_url = "https://api.groq.com/openai/v1"
            api_key_env = "GROQ_API_KEY"
            modele = llm.modele_groq
        else:
            return None, None
    elif api_key_env and not os.environ.get(api_key_env):
        return None, None

    runtime_cfg = SimpleNamespace(
        llm_provider=provider,
        llm_base_url=base_url,
        llm_api_key_env=api_key_env,
        llm_max_retry_after_seconds=llm.max_retry_after_seconds,
    )
    return LLMClient(runtime_cfg), modele


def ameliorer_devis_avec_ia(
    doc: QuoteDocument,
    cfg: QuoteConfig,
    client: StructuredClient | None = None,
    modele: str | None = None,
) -> QuoteDocument:
    if client is None:
        client, modele = creer_client_llm_si_disponible(cfg)
    if client is None or not modele:
        return doc

    payload = _payload_sans_risque(doc)
    result, _usage = client.structured(
        system=SYSTEM_FINITION_DEVIS,
        user=json.dumps(payload, ensure_ascii=False, indent=2),
        schema=SCHEMA_FINITION_DEVIS,
        nom_schema="finition_devis_accura",
        model=modele,
        max_tokens=cfg.llm.max_tokens,
        cache=True,
    )
    if not isinstance(result, dict):
        return doc

    _appliquer_finition_validee(doc, result)
    doc.mode_generation = "ia_assistee"
    return doc


def _payload_sans_risque(doc: QuoteDocument) -> dict:
    return {
        "id_devis": doc.id_devis,
        "artisan": {
            "nom": doc.artisan.nom,
            "ville_zone": doc.artisan.adresse,
        },
        "demande": _jsonable(asdict(doc.demande)),
        "lignes_verrouillees": [
            {
                "libelle": l.libelle,
                "quantite": str(l.quantite),
                "unite": l.unite,
                "total_ht": str(l.total_ht),
            }
            for l in doc.lignes
        ],
        "totaux_verrouilles": {
            "total_ht": str(doc.totaux.total_ht),
            "tva": str(doc.totaux.tva),
            "total_ttc": str(doc.totaux.total_ttc),
            "acompte_ttc": str(doc.totaux.acompte_ttc),
        },
        "message_client_actuel": doc.message_client,
        "conditions": doc.conditions,
    }


def _appliquer_finition_validee(doc: QuoteDocument, result: dict) -> None:
    resume = _clean_text(result.get("resume_pro", ""), max_len=700)
    if resume:
        doc.demande.resume_pro = resume

    questions = [_clean_text(q, max_len=220) for q in result.get("questions", []) if isinstance(q, str)]
    questions = [q for q in questions if q]
    if questions:
        doc.demande.questions = questions[:6]
        doc.demande.infos_manquantes = doc.demande.infos_manquantes or ["ia_clarification"]

    message = _clean_text(result.get("message_client", ""), max_len=1200)
    if message and _message_garde_totaux(doc, message):
        doc.message_client = message

    notes = [_clean_text(n, max_len=240) for n in result.get("notes_artisan", []) if isinstance(n, str)]
    doc.notes_artisan = [n for n in notes if n][:6]


def _message_garde_totaux(doc: QuoteDocument, message: str) -> bool:
    """Le message IA doit garder le total TTC exact s'il mentionne un montant."""
    contains_euro = "€" in message or "eur" in message.lower()
    if not contains_euro:
        return True
    return _digits_money(str(doc.totaux.total_ttc)) in _digits_money(message)


def _clean_text(value: str, max_len: int) -> str:
    value = " ".join(str(value).strip().split())
    return value[:max_len].strip()


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def _digits_money(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())
