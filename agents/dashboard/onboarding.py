"""Onboarding artisan Accura.

Un abonnement ne suffit pas : les agents doivent connaître l'entreprise, la zone,
les métiers, les prix et les règles commerciales de l'artisan.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


PLANS = {
    "fondation": {
        "label": "Fondation",
        "price": "199 €/mois",
        "agents": ["devis", "relances", "crm", "avis_google"],
    },
    "croissance": {
        "label": "Croissance",
        "price": "349 €/mois",
        "agents": ["devis", "relances", "crm", "avis_google", "acquisition"],
    },
    "pilotage": {
        "label": "Pilotage",
        "price": "599 €/mois",
        "agents": ["devis", "relances", "crm", "avis_google", "acquisition", "reporting"],
    },
}

DEFAULT_PROFILE = {
    "plan": "fondation",
    "company": {
        "name": "Entreprise Démo Accura",
        "legal_name": "",
        "siret": "SIRET à compléter",
        "insurance": "Assurance décennale à compléter",
        "address": "Nantes et Pays de la Loire",
        "phone": "07 61 77 20 65",
        "email": "contact@accuraouest.com",
        "google_review_url": "",
    },
    "business": {
        "main_trade": "plomberie",
        "secondary_trades": ["carrelage"],
        "service_area": ["Nantes", "Saint-Herblain", "Rezé", "Vertou"],
        "ideal_jobs": ["salle de bain", "rénovation intérieure", "dépannage qualifié"],
        "excluded_jobs": ["petites interventions non rentables", "urgence de nuit"],
        "minimum_job_ttc": 350,
    },
    "quote_settings": {
        "vat_rate": 0.10,
        "margin_rate": 0.20,
        "hourly_rate_ht": 55,
        "deposit_rate": 0.30,
        "validity_days": 30,
        "default_material_range": "standard",
        "payment_terms": "Acompte conseillé avant démarrage, solde à réception des travaux.",
    },
    "quote_items": [
        {
            "code": "protection_depose",
            "label": "Protection du chantier et dépose des éléments existants",
            "unit": "forfait",
            "unit_price_ht": 320,
            "keywords": ["refaire", "remplacer", "dépose", "salle de bain"],
        },
        {
            "code": "douche",
            "label": "Fourniture et pose d'une douche standard",
            "unit": "forfait",
            "unit_price_ht": 950,
            "keywords": ["douche"],
        },
        {
            "code": "meuble_vasque",
            "label": "Fourniture et pose meuble vasque",
            "unit": "forfait",
            "unit_price_ht": 520,
            "keywords": ["vasque", "meuble"],
        },
        {
            "code": "reseaux_plomberie",
            "label": "Adaptation plomberie alimentation et évacuation",
            "unit": "forfait",
            "unit_price_ht": 680,
            "keywords": ["plomberie", "sanitaire", "douche", "vasque", "wc"],
        },
        {
            "code": "carrelage_sol_mur",
            "label": "Pose carrelage / faïence salle de bain",
            "unit": "m²",
            "unit_price_ht": 82,
            "quantity_from": "surface_m2",
            "keywords": ["carrelage", "faïence", "salle de bain"],
        },
    ],
    "followups": {
        "enabled": True,
        "days": [3, 7, 15],
        "tone": "professionnel, simple, relance courte",
    },
    "acquisition": {
        "enabled": False,
        "weekly_target_min": 2,
        "weekly_target_max": 3,
        "lead_threshold": 60,
    },
}


def profile_path(root: Path) -> Path:
    return root / "outputs" / "onboarding" / "artisan_profile.json"


def devis_config_path(root: Path) -> Path:
    return root / "config" / "devis.yaml"


def load_profile(root: Path) -> dict[str, Any]:
    path = profile_path(root)
    if not path.exists():
        return with_plan_capabilities(DEFAULT_PROFILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return with_plan_capabilities(DEFAULT_PROFILE)
    return with_plan_capabilities(merge_profile(DEFAULT_PROFILE, data))


def save_profile(root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    cleaned = normalize_profile(merge_profile(DEFAULT_PROFILE, profile))
    cleaned = with_plan_capabilities(cleaned)
    path = profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return cleaned


def apply_profile_to_devis_config(root: Path, profile: dict[str, Any]) -> dict[str, str]:
    profile = save_profile(root, profile)
    target = devis_config_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)

    backup = ""
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = target.with_suffix(f".yaml.bak-{stamp}")
        shutil.copy2(target, backup_path)
        backup = str(backup_path)

    yaml_payload = build_devis_yaml(profile)
    target.write_text(yaml.safe_dump(yaml_payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"profile": str(profile_path(root)), "devis_config": str(target), "backup": backup}


def build_devis_yaml(profile: dict[str, Any]) -> dict[str, Any]:
    company = profile["company"]
    settings = profile["quote_settings"]
    business = profile["business"]
    main_trade = business["main_trade"]
    plan = PLANS.get(profile["plan"], PLANS["fondation"])

    return {
        "artisan": {
            "nom": company["name"],
            "adresse": company["address"],
            "telephone": company["phone"],
            "email": company["email"],
            "siret": company["siret"],
            "assurance_decennale": company["insurance"],
            "mentions": [
                settings["payment_terms"],
                "Délais et prix à confirmer après visite technique ou photos exploitables.",
                f"Configuration Accura : offre {plan['label']} ({plan['price']}).",
            ],
        },
        "pricing": {
            "taux_tva": str(settings["vat_rate"]),
            "taux_marge": str(settings["margin_rate"]),
            "main_oeuvre_heure_ht": str(settings["hourly_rate_ht"]),
            "validite_jours": int(settings["validity_days"]),
            "acompte_pourcentage": str(settings["deposit_rate"]),
        },
        "llm": {
            "actif": True,
            "provider": "auto",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
            "modele": "gpt-4o-mini",
            "modele_anthropic": "claude-sonnet-4-6",
            "max_tokens": 1600,
            "max_retry_after_seconds": 60,
        },
        "zone": {"villes_connues": business["service_area"]},
        "sortie": {"dossier": "outputs/devis"},
        "metiers": {
            main_trade: {
                "libelle": trade_label(main_trade),
                "mots_cles": trade_keywords(main_trade, business),
                "questions_requises": ["ville", "surface", "prestations", "gamme_materiaux", "photos"],
                "conditions": [
                    "Chiffrage établi selon la grille tarifaire transmise par l'artisan.",
                    f"Chantier minimum cible : {business['minimum_job_ttc']} € TTC.",
                ],
                "postes": [
                    {
                        "code": item["code"],
                        "libelle": item["label"],
                        "unite": item["unit"],
                        "prix_unitaire_ht": str(item["unit_price_ht"]),
                        **({"quantite_depuis": item["quantity_from"]} if item.get("quantity_from") else {}),
                        "mots_cles": item["keywords"],
                    }
                    for item in profile["quote_items"]
                ],
            }
        },
    }


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    profile["plan"] = profile.get("plan") if profile.get("plan") in PLANS else "fondation"
    profile["acquisition"]["enabled"] = "acquisition" in PLANS[profile["plan"]]["agents"]
    profile["business"]["service_area"] = as_list(profile["business"].get("service_area"))
    profile["business"]["ideal_jobs"] = as_list(profile["business"].get("ideal_jobs"))
    profile["business"]["excluded_jobs"] = as_list(profile["business"].get("excluded_jobs"))
    for item in profile.get("quote_items", []):
        item["keywords"] = as_list(item.get("keywords"))
    return profile


def with_plan_capabilities(profile: dict[str, Any]) -> dict[str, Any]:
    plan = PLANS.get(profile.get("plan"), PLANS["fondation"])
    profile["plan_capabilities"] = {
        "label": plan["label"],
        "price": plan["price"],
        "agents": plan["agents"],
    }
    return profile


def merge_profile(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {k: merge_profile(v, override[k]) if k in override else v for k, v in base.items()}
        for key, value in override.items():
            if key not in merged:
                merged[key] = value
        return merged
    return override


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def trade_label(trade: str) -> str:
    labels = {
        "plomberie": "Plomberie / salle de bain",
        "electricite": "Électricité",
        "carrelage": "Carrelage / faïence",
        "menuiserie": "Menuiserie",
        "peinture": "Peinture / finitions",
        "renovation_generale": "Rénovation générale",
    }
    return labels.get(trade, trade.replace("_", " ").capitalize())


def trade_keywords(trade: str, business: dict[str, Any]) -> list[str]:
    defaults = {
        "plomberie": ["plomberie", "plombier", "salle de bain", "douche", "vasque", "wc", "sanitaire"],
        "electricite": ["électricité", "electricite", "électricien", "tableau", "prise", "mise aux normes"],
        "carrelage": ["carrelage", "carreleur", "faïence", "faience", "sol"],
        "menuiserie": ["menuiserie", "menuisier", "porte", "fenêtre", "placard"],
        "peinture": ["peinture", "peintre", "mur", "plafond", "enduit"],
        "renovation_generale": ["rénovation", "renovation", "travaux", "appartement", "maison"],
    }
    words = defaults.get(trade, [trade])
    return sorted(set(words + business.get("ideal_jobs", [])))

