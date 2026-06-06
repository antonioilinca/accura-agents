"""Connecteurs de sources de leads. Chaque source -> liste de RawLead normalisés."""

from __future__ import annotations

from .base import Source
from .inbox_manuelle import InboxManuelle
from .sitadel import Sitadel
from .urbanisme_nantes import UrbanismeNantes

REGISTRE: dict[str, type[Source]] = {
    "urbanisme_nantes": UrbanismeNantes,
    "sitadel": Sitadel,
    "inbox_manuelle": InboxManuelle,
}

__all__ = ["Source", "REGISTRE"]
