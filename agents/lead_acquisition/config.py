"""Chargement et validation de la configuration métier/zone/sources/LLM (YAML + .env).

Rien n'est codé en dur : le premier artisan client n'est pas encore connu, donc tout
(métier, communes, rayon, sources, seuil, fournisseur LLM, modèles, prix) vient des
fichiers de config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


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
    # LLM
    llm_provider: str          # openai_compat | anthropic
    llm_base_url: str | None
    llm_api_key_env: str
    modele_tri: str
    modele_qualif: str
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

    return Config(
        metier=metier,
        communes=[str(c).strip() for c in (zone.get("communes") or [])],
        rayon_km=int(zone.get("rayon_km", 0) or 0),
        sources=sources,
        seuil_livraison=int(qualif.get("seuil_livraison", 60)),
        taille_lot_tri=int(qualif.get("taille_lot_tri", 25)),
        llm_provider=str(llm.get("provider", "openai_compat")),
        llm_base_url=llm.get("base_url"),
        llm_api_key_env=str(llm.get("api_key_env", "GROQ_API_KEY")),
        modele_tri=str(llm.get("modele_tri", "llama-3.3-70b-versatile")),
        modele_qualif=str(llm.get("modele_qualif", "llama-3.3-70b-versatile")),
        dossier_sortie=racine / (sortie.get("dossier") or "outputs"),
        prix_usd_par_million=dict(data.get("pricing_usd_par_million") or {}),
        racine=racine,
    )
