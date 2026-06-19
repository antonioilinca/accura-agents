"""Types de données de l'agent devis.

Le devis reste volontairement explicite : extraction, questions, lignes et totaux sont
séparés pour que l'artisan puisse vérifier vite avant envoi client.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


CENT = Decimal("0.01")


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class ArtisanIdentity:
    nom: str = "Votre entreprise"
    adresse: str = ""
    telephone: str = ""
    email: str = ""
    siret: str = ""
    assurance_decennale: str = ""
    logo_path: str = ""
    # Franchise en base de TVA (micro-entreprise, art. 293 B du CGI) : aucun
    # document ne doit alors afficher de TVA. Propagé du devis vers la facture.
    franchise_tva: bool = False
    mentions: list[str] = field(default_factory=list)


@dataclass
class PricingConfig:
    taux_tva: Decimal = Decimal("0.10")
    taux_marge: Decimal = Decimal("0.20")
    main_oeuvre_heure_ht: Decimal = Decimal("55")
    validite_jours: int = 30
    acompte_pourcentage: Decimal = Decimal("0.30")


@dataclass
class LLMQuoteConfig:
    actif: bool = True
    provider: str = "auto"  # auto | openai_compat | anthropic | off
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    modele: str = "gpt-4o-mini"
    modele_anthropic: str = "claude-sonnet-4-6"
    modele_groq: str = "llama-3.3-70b-versatile"
    max_tokens: int = 1600
    max_retry_after_seconds: int = 60


@dataclass
class QuoteItemConfig:
    code: str
    libelle: str
    unite: str
    prix_unitaire_ht: Decimal
    quantite_defaut: Decimal = Decimal("1")
    quantite_depuis: str | None = None
    mots_cles: list[str] = field(default_factory=list)
    materiaux: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class TradeConfig:
    nom: str
    libelle: str
    mots_cles: list[str]
    postes: list[QuoteItemConfig]
    questions_requises: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)


@dataclass
class QuoteConfig:
    artisan: ArtisanIdentity
    pricing: PricingConfig
    llm: LLMQuoteConfig
    metiers: dict[str, TradeConfig]
    villes_connues: list[str]
    dossier_sortie: str = "outputs/devis"


@dataclass
class ProjectRequest:
    texte_source: str
    metier: str
    metier_libelle: str
    type_chantier: str
    ville: str | None = None
    adresse: str | None = None
    surface_m2: Decimal | None = None
    prestations: list[str] = field(default_factory=list)
    materiaux_probables: list[str] = field(default_factory=list)
    contraintes: list[str] = field(default_factory=list)
    urgence: str = "standard"
    infos_manquantes: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    resume_pro: str = ""


@dataclass
class QuoteLine:
    code: str
    libelle: str
    quantite: Decimal
    unite: str
    prix_unitaire_ht: Decimal
    total_ht: Decimal
    description: str = ""


@dataclass
class QuoteTotals:
    total_ht: Decimal
    tva: Decimal
    total_ttc: Decimal
    acompte_ttc: Decimal


@dataclass
class QuoteDocument:
    id_devis: str
    date_creation: str
    artisan: ArtisanIdentity
    demande: ProjectRequest
    lignes: list[QuoteLine]
    totaux: QuoteTotals
    conditions: list[str]
    message_client: str
    statut: str = "brouillon_a_valider"
    mode_generation: str = "local"
    notes_artisan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Decimal):
                return float(value)
            if isinstance(value, list):
                return [convert(v) for v in value]
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            return value

        return convert(asdict(self))
