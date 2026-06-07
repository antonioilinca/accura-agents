"""Types de données du module relances Accura."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FollowupMessage:
    id_devis: str
    jour: int
    date_prevue: str
    canal: str
    objet: str
    message: str
    statut: str = "a_copier"


@dataclass
class FollowupPlan:
    id_devis: str
    date_devis: str
    client: str
    chantier: str
    total_ttc: float
    messages: list[FollowupMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

