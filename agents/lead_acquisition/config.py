"""Chargement et validation de la configuration métier/zone/sources/LLM (YAML + .env).

Rien n'est codé en dur : le premier artisan client n'est pas encore connu, donc tout
(métier, communes, rayon, sources, seuil, fournisseur LLM, modèles, prix) vient des
fichiers de config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _resoudre_llm(llm: dict) -> tuple[str, Any, str, str, str]:
    """Résout le fournisseur d'IA et les modèles.

    Avec ``provider: auto`` dans config.yaml : si ANTHROPIC_API_KEY est présente,
    on bascule automatiquement sur Claude (qualité maximale) ; sinon on reste sur
    le fournisseur gratuit (Groq/Llama). Ajouter la clé suffit donc à passer en
    production, sans éditer aucun fichier. Un ``provider`` explicite est respecté tel quel.
    """
    provider = str(llm.get("provider", "openai_compat"))
    base_url = llm.get("base_url")
    api_key_env = str(llm.get("api_key_env", "GROQ_API_KEY"))
    modele_tri = str(llm.get("modele_tri", "llama-3.3-70b-versatile"))
    modele_qualif = str(llm.get("modele_qualif", "llama-3.3-70b-versatile"))

    if provider == "auto":
        if os.environ.get("ANTHROPIC_API_KEY"):
            return (
                "anthropic",
                None,
                "ANTHROPIC_API_KEY",
                str(llm.get("modele_tri_anthropic", "claude-haiku-4-5-20251001")),
                str(llm.get("modele_qualif_anthropic", "claude-sonnet-4-6")),
            )
        return ("openai_compat", base_url, api_key_env, modele_tri, modele_qualif)
    return (provider, base_url, api_key_env, modele_tri, modele_qualif)


@dataclass
class SourceConfig:
    actif: bool = False
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Metier:
    nom: str
    libelle: str
    travaux_pertinents: str
    mots_cles: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)


@dataclass
class Config:
    metier: Metier
    communes: list[str]
    rayon_km: int
    sources: dict[str, SourceConfig]
    seuil_livraison: int
    taille_lot_tri: int
    objectif_hebdo_min: int
    objectif_hebdo_max: int
    # Garde-fous (coût borné, échelle artisan garantie par le code, pas le prompt)
    max_qualif_par_run: int
    surface_max_artisan: int
    # LLM
    llm_provider: str          # openai_compat | anthropic
    llm_base_url: str | None
    llm_api_key_env: str
    modele_tri: str
    modele_qualif: str
    llm_max_retry_after_seconds: int
    llm_intervalle_min_s: float
    # divers
    dossier_sortie: Path
    prix_usd_par_million: dict[str, float]
    racine: Path

    def source(self, nom: str) -> SourceConfig:
        return self.sources.get(nom, SourceConfig())


def _charger_metier(racine: Path, nom: str) -> Metier:
    chemin = racine / "config" / "metiers" / f"{nom}.yaml"
    if not chemin.exists():
        disponibles = ", ".join(
            p.stem for p in (racine / "config" / "metiers").glob("*.yaml")
        ) or "(aucune)"
        raise FileNotFoundError(
            f"Fiche métier introuvable : {chemin}\nMétiers disponibles : {disponibles}"
        )
    data = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    return Metier(
        nom=data.get("metier", nom),
        libelle=data.get("libelle", nom),
        travaux_pertinents=(data.get("travaux_pertinents") or "").strip(),
        mots_cles=list(data.get("mots_cles_positifs") or []),
        exclusions=list(data.get("exclusions") or []),
    )


def charger_config(chemin_config: str | Path) -> Config:
    chemin_config = Path(chemin_config).expanduser().resolve()
    if not chemin_config.exists():
        raise FileNotFoundError(
            f"Config introuvable : {chemin_config}\n"
            "Copie config/config.example.yaml vers config/config.yaml et adapte-le."
        )
    racine = chemin_config.parent.parent  # .../accura-agents
    data = yaml.safe_load(chemin_config.read_text(encoding="utf-8")) or {}

    if "metier" not in data:
        raise ValueError("Champ 'metier' manquant dans le config.yaml")

    metier = _charger_metier(racine, data["metier"])

    sources: dict[str, SourceConfig] = {}
    for nom, opts in (data.get("sources") or {}).items():
        opts = dict(opts or {})
        actif = bool(opts.pop("actif", False))
        sources[nom] = SourceConfig(actif=actif, options=opts)

    zone = data.get("zone") or {}
    qualif = data.get("qualification") or {}
    sortie = data.get("sortie") or {}
    llm = data.get("llm") or {}
    llm_provider, llm_base_url, llm_api_key_env, modele_tri, modele_qualif = _resoudre_llm(llm)

    return Config(
        metier=metier,
        communes=[str(c).strip() for c in (zone.get("communes") or [])],
        rayon_km=int(zone.get("rayon_km", 0) or 0),
        sources=sources,
        seuil_livraison=int(qualif.get("seuil_livraison", 60)),
        taille_lot_tri=int(qualif.get("taille_lot_tri", 25)),
        objectif_hebdo_min=int(qualif.get("objectif_hebdo_min", 2)),
        objectif_hebdo_max=int(qualif.get("objectif_hebdo_max", 3)),
        max_qualif_par_run=int(qualif.get("max_qualif_par_run", 60)),
        surface_max_artisan=int(qualif.get("surface_max_artisan", 600)),
        llm_provider=llm_provider,
        llm_base_url=llm_base_url,
        llm_api_key_env=llm_api_key_env,
        modele_tri=modele_tri,
        modele_qualif=modele_qualif,
        llm_max_retry_after_seconds=int(llm.get("max_retry_after_seconds", 120)),
        llm_intervalle_min_s=float(llm.get("intervalle_min_s", 2.5)),
        dossier_sortie=racine / (sortie.get("dossier") or "outputs"),
        prix_usd_par_million=dict(data.get("pricing_usd_par_million") or {}),
        racine=racine,
    )
