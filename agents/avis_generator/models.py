"""Types de données du module avis Google."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ReviewRequest:
    artisan_name: str
    google_review_url: str
    client: str
    chantier: str
    message: str
    statut: str = "a_copier"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

