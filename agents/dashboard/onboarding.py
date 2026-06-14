"""Onboarding artisan Accura.

Un abonnement ne suffit pas : les agents doivent connaître l'entreprise, la zone,
les métiers, les prix et les règles commerciales de l'artisan.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from agents.common.fileio import ecrire_json_atomique


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
    # Clé historique "pilotage" conservée (profils déjà sauvegardés) ; le nom
    # commercial sur accuraouest.com est « Intégral ».
    "pilotage": {
        "label": "Intégral",
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
        "franchise_tva": False,
    },
    "assets": {
        "logo_path": "",
        "logo_original_name": "",
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

ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_LOGO_BYTES = 2 * 1024 * 1024


def _profile_base(root: Path, base: Path | None) -> Path:
    """Dossier de base du profil/assets d'un artisan.

    - ``base=None`` (cas historique mono-artisan) : ``root/"outputs"``.
    - ``base`` fourni (espace d'un client de l'agence) : ce dossier tel quel.

    Les chemins ``onboarding/...`` sont ensuite ancrés sur ce dossier de base, ce
    qui garde le comportement d'origine intact quand aucun client n'est ciblé.
    """
    return base if base is not None else root / "outputs"


def profile_path(root: Path, base: Path | None = None) -> Path:
    return _profile_base(root, base) / "onboarding" / "artisan_profile.json"


def onboarding_assets_dir(root: Path, base: Path | None = None) -> Path:
    return _profile_base(root, base) / "onboarding" / "assets"


def devis_config_path(root: Path) -> Path:
    return root / "config" / "devis.yaml"


def load_profile(root: Path, base: Path | None = None) -> dict[str, Any]:
    path = profile_path(root, base)
    if not path.exists():
        return with_plan_capabilities(DEFAULT_PROFILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return with_plan_capabilities(DEFAULT_PROFILE)
    return with_plan_capabilities(merge_profile(DEFAULT_PROFILE, data))


def save_profile(root: Path, profile: dict[str, Any], base: Path | None = None) -> dict[str, Any]:
    cleaned = normalize_profile(merge_profile(DEFAULT_PROFILE, profile))
    cleaned = with_plan_capabilities(cleaned)
    ecrire_json_atomique(profile_path(root, base), cleaned)
    return cleaned


def valider_profil_production(profile: dict[str, Any]) -> list[str]:
    """Contrôles bloquants avant d'activer la config devis d'un VRAI artisan.

    Le brouillon de profil reste libre ; mais aucun document client ne doit pouvoir
    sortir avec un SIRET placeholder, une TVA aberrante ou un prix négatif.
    """
    erreurs: list[str] = []
    company = profile.get("company", {}) or {}
    settings = profile.get("quote_settings", {}) or {}

    siret = re.sub(r"\s", "", str(company.get("siret", "")))
    if not re.fullmatch(r"\d{14}", siret):
        erreurs.append("SIRET invalide : 14 chiffres attendus (obligatoire sur devis et factures).")
    url = str(company.get("google_review_url") or "").strip()
    if url and not url.startswith(("http://", "https://")):
        erreurs.append("Lien d'avis Google invalide : il doit commencer par https://")

    vat = float(settings.get("vat_rate", 0) or 0)
    if bool(company.get("franchise_tva")) and vat > 0:
        erreurs.append("Franchise en base (art. 293 B) activée : le taux de TVA doit être 0.")
    if not 0 <= vat <= 0.30:
        erreurs.append("Taux de TVA hors plage raisonnable (0 à 30 %).")
    if not 0 <= float(settings.get("deposit_rate", 0) or 0) <= 1:
        erreurs.append("Taux d'acompte hors plage (0 à 100 %).")
    if float(settings.get("hourly_rate_ht", 0) or 0) <= 0:
        erreurs.append("Taux horaire HT manquant ou nul.")
    for item in profile.get("quote_items", []) or []:
        if float(item.get("unit_price_ht", 0) or 0) < 0:
            libelle = item.get("label") or item.get("code") or "?"
            erreurs.append(f"Prix négatif sur le poste « {libelle} ».")
    return erreurs


def save_logo_asset(root: Path, filename: str, content: bytes, base: Path | None = None) -> dict[str, Any]:
    if not content:
        raise ValueError("Logo vide")
    if len(content) > MAX_LOGO_BYTES:
        raise ValueError("Logo trop lourd : maximum 2 Mo")

    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        raise ValueError("Format logo non supporté : utilisez PNG, JPG ou WebP")
    if not _looks_like_logo(content, ext):
        raise ValueError("Le fichier ne ressemble pas à une image valide")

    folder = onboarding_assets_dir(root, base)
    folder.mkdir(parents=True, exist_ok=True)
    for old_logo in folder.glob("logo.*"):
        old_logo.unlink()

    target = folder / f"logo{ext}"
    target.write_bytes(content)
    return {
        "logo_path": target.relative_to(root).as_posix(),
        "logo_original_name": Path(filename).name,
        "logo_size_bytes": len(content),
    }


def client_devis_config_path(base: Path) -> Path:
    """Config devis d'un client de l'agence, rangée DANS son espace de travail.

    On ne touche pas au ``config/devis.yaml`` global (réservé au mode mono-artisan
    historique) : chaque client a sa propre config isolée, ce qui évite qu'activer
    un client n'écrase la configuration d'un autre.
    """
    return base / "devis.config.yaml"


def apply_profile_to_devis_config(root: Path, profile: dict[str, Any], base: Path | None = None) -> dict[str, str]:
    profile = save_profile(root, profile, base=base)
    erreurs = valider_profil_production(profile)
    if erreurs:
        raise ValueError(
            "Profil incomplet pour activer la configuration devis :\n- " + "\n- ".join(erreurs)
        )
    # Mono-artisan : config/devis.yaml (inchangé). Client actif : config isolée dans son espace.
    target = devis_config_path(root) if base is None else client_devis_config_path(base)
    target.parent.mkdir(parents=True, exist_ok=True)

    backup = ""
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = target.with_suffix(f".yaml.bak-{stamp}")
        shutil.copy2(target, backup_path)
        backup = str(backup_path)

    yaml_payload = build_devis_yaml(profile)
    target.write_text(yaml.safe_dump(yaml_payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"profile": str(profile_path(root, base)), "devis_config": str(target), "backup": backup}


def build_devis_yaml(profile: dict[str, Any]) -> dict[str, Any]:
    company = profile["company"]
    assets = profile.get("assets", {}) or {}
    settings = profile["quote_settings"]
    business = profile["business"]
    main_trade = business["main_trade"]
    plan = PLANS.get(profile["plan"], PLANS["fondation"])

    franchise = bool(company.get("franchise_tva", False))
    return {
        "artisan": {
            "nom": company["name"],
            "adresse": company["address"],
            "telephone": company["phone"],
            "email": company["email"],
            "siret": company["siret"],
            "assurance_decennale": company["insurance"],
            "logo_path": assets.get("logo_path", ""),
            "franchise_tva": franchise,
            "mentions": [
                settings["payment_terms"],
                "Délais et prix à confirmer après visite technique ou photos exploitables.",
                f"Configuration Accura : offre {plan['label']} ({plan['price']}).",
            ],
        },
        "pricing": {
            "taux_tva": "0" if franchise else str(settings["vat_rate"]),
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
    profile["assets"]["logo_path"] = normalize_logo_path(profile["assets"].get("logo_path"))
    profile["assets"]["logo_original_name"] = str(profile["assets"].get("logo_original_name") or "")
    profile["company"]["franchise_tva"] = _vrai_faux(profile["company"].get("franchise_tva"))
    settings = profile["quote_settings"]
    settings["vat_rate"] = _taux(settings.get("vat_rate"), 0.10)
    settings["margin_rate"] = _taux(settings.get("margin_rate"), 0.20)
    settings["deposit_rate"] = _taux(settings.get("deposit_rate"), 0.30)
    for item in profile.get("quote_items", []):
        item["keywords"] = as_list(item.get("keywords"))
    return profile


def _taux(value: Any, defaut: float) -> float:
    """Accepte 0.10, "0,10", 10 ou "10 %" : toute valeur > 1 est lue comme un pourcentage."""
    try:
        v = float(str(value).replace("%", "").replace(",", ".").strip())
    except (TypeError, ValueError):
        return defaut
    if v > 1:
        v = v / 100
    return v if v >= 0 else defaut


def _vrai_faux(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "oui", "on", "yes"}
    return bool(value)


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


def normalize_logo_path(value: Any) -> str:
    path = str(value or "").strip().replace("\\", "/")
    if not path:
        return ""
    if path.startswith("outputs/onboarding/assets/"):
        return path
    if path.startswith("/outputs/onboarding/assets/"):
        return path.removeprefix("/")
    return ""


def _looks_like_logo(content: bytes, ext: str) -> bool:
    if ext == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if ext == ".webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


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
