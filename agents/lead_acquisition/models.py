"""Types de données du pipeline. Sorties structurées, jamais de dict anonyme qui circule."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class RawLead:
    """Une opportunité de chantier brute, normalisée depuis n'importe quelle source."""

    source: str
    external_id: str
    commune: str
    adresse: str
    description: str
    date_signal: Optional[str] = None        # date ISO du signal (dépôt de dossier, post...)
    type_dossier: Optional[str] = None        # ex "Déclaration préalable", "Permis de construire"
    surface_plancher: Optional[float] = None  # m², si disponible
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        """Clé stable pour ne jamais livrer deux fois la même opportunité."""
        if self.external_id:
            return f"{self.source}:{self.external_id}"
        empreinte = hashlib.sha1(
            f"{self.commune}|{self.description}".encode("utf-8")
        ).hexdigest()[:16]
        return f"{self.source}:{empreinte}"


@dataclass
class Signaux:
    """Décomposition lisible du score, pour que l'artisan comprenne le 'pourquoi'."""

    adequation_metier: str = "inconnue"  # forte | moyenne | faible
    ampleur_travaux: str = "inconnue"    # lourde | moyenne | legere
    fraicheur: str = "inconnue"          # recent | moyen | ancien
    signal_budget: str = "inconnu"       # fort | moyen | faible | inconnu
    zone_ok: bool = True
    contactabilite: str = "moyenne"      # forte | moyenne | faible


@dataclass
class QualifiedLead:
    """Une opportunité scorée, prête à être livrée à l'artisan."""

    raw: RawLead
    metier: str
    score: int                # 0-100
    justification: str
    signaux: Signaux
    message_contact: str      # brouillon de prise de contact
    qualified_at: str         # ISO datetime UTC
    type_opportunite: str = "opportunite_a_demarcher"
    canal_recommande: str = "courrier_ou_visite"
    urgence_contact: str = "cette_semaine"
    valeur_potentielle: str = "moyenne"
    angle_approche: str = ""
    prochaine_action: str = ""
    script_appel: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "metier": self.metier,
            "commune": self.raw.commune,
            "adresse": self.raw.adresse,
            "description": self.raw.description,
            "type_dossier": self.raw.type_dossier,
            "surface_plancher": self.raw.surface_plancher,
            "date_signal": self.raw.date_signal,
            "source": self.raw.source,
            "id_source": self.raw.external_id,
            "justification": self.justification,
            "signaux": asdict(self.signaux),
            "message_contact": self.message_contact,
            "qualified_at": self.qualified_at,
            "type_opportunite": self.type_opportunite,
            "canal_recommande": self.canal_recommande,
            "urgence_contact": self.urgence_contact,
            "valeur_potentielle": self.valeur_potentielle,
            "angle_approche": self.angle_approche,
            "prochaine_action": self.prochaine_action,
            "script_appel": self.script_appel,
        }
