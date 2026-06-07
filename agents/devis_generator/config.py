"""Chargement de la configuration devis Accura."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from .models import (
    ArtisanIdentity,
    PricingConfig,
    LLMQuoteConfig,
    QuoteConfig,
    QuoteItemConfig,
    TradeConfig,
)


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None:
        value = default
    return Decimal(str(value))


def _item(data: dict[str, Any]) -> QuoteItemConfig:
    return QuoteItemConfig(
        code=str(data["code"]),
        libelle=str(data["libelle"]),
        unite=str(data.get("unite", "forfait")),
        prix_unitaire_ht=_dec(data.get("prix_unitaire_ht")),
        quantite_defaut=_dec(data.get("quantite_defaut", 1), "1"),
        quantite_depuis=data.get("quantite_depuis"),
        mots_cles=[str(x).lower() for x in data.get("mots_cles", [])],
        materiaux=[str(x) for x in data.get("materiaux", [])],
        description=str(data.get("description", "")),
    )


def charger_config(chemin_config: str | Path) -> QuoteConfig:
    chemin = Path(chemin_config).expanduser().resolve()
    if not chemin.exists():
        raise FileNotFoundError(f"Config devis introuvable : {chemin}")

    data = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    artisan_data = data.get("artisan", {}) or {}
    pricing_data = data.get("pricing", {}) or {}
    llm_data = data.get("llm", {}) or {}

    artisan = ArtisanIdentity(
        nom=str(artisan_data.get("nom", "Votre entreprise")),
        adresse=str(artisan_data.get("adresse", "")),
        telephone=str(artisan_data.get("telephone", "")),
        email=str(artisan_data.get("email", "")),
        siret=str(artisan_data.get("siret", "")),
        assurance_decennale=str(artisan_data.get("assurance_decennale", "")),
        mentions=[str(x) for x in artisan_data.get("mentions", [])],
    )
    pricing = PricingConfig(
        taux_tva=_dec(pricing_data.get("taux_tva", "0.10"), "0.10"),
        taux_marge=_dec(pricing_data.get("taux_marge", "0.20"), "0.20"),
        main_oeuvre_heure_ht=_dec(pricing_data.get("main_oeuvre_heure_ht", "55"), "55"),
        validite_jours=int(pricing_data.get("validite_jours", 30)),
        acompte_pourcentage=_dec(pricing_data.get("acompte_pourcentage", "0.30"), "0.30"),
    )
    llm = LLMQuoteConfig(
        actif=bool(llm_data.get("actif", True)),
        provider=str(llm_data.get("provider", "auto")),
        base_url=str(llm_data.get("base_url", "https://api.openai.com/v1")).rstrip("/"),
        api_key_env=str(llm_data.get("api_key_env", "OPENAI_API_KEY")),
        modele=str(llm_data.get("modele", "gpt-4o-mini")),
        modele_anthropic=str(llm_data.get("modele_anthropic", "claude-sonnet-4-6")),
        max_tokens=int(llm_data.get("max_tokens", 1600)),
        max_retry_after_seconds=int(llm_data.get("max_retry_after_seconds", 60)),
    )

    metiers: dict[str, TradeConfig] = {}
    for nom, bloc in (data.get("metiers") or {}).items():
        metiers[str(nom)] = TradeConfig(
            nom=str(nom),
            libelle=str(bloc.get("libelle", nom)),
            mots_cles=[str(x).lower() for x in bloc.get("mots_cles", [])],
            questions_requises=[str(x) for x in bloc.get("questions_requises", [])],
            conditions=[str(x) for x in bloc.get("conditions", [])],
            postes=[_item(p) for p in bloc.get("postes", [])],
        )

    if not metiers:
        raise ValueError("Aucun métier configuré dans la config devis")

    sortie = data.get("sortie", {}) or {}
    zone = data.get("zone", {}) or {}
    return QuoteConfig(
        artisan=artisan,
        pricing=pricing,
        llm=llm,
        metiers=metiers,
        villes_connues=[str(v) for v in zone.get("villes_connues", [])],
        dossier_sortie=str(sortie.get("dossier", "outputs/devis")),
    )
