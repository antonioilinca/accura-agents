"""Interface commune à toutes les sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..models import RawLead

if TYPE_CHECKING:
    from ..config import Config, SourceConfig


class Source(ABC):
    """Une source de leads. Le pipeline isole les erreurs : une source qui plante
    n'arrête pas les autres."""

    nom: str = "source"

    def __init__(self, config: "Config", source_config: "SourceConfig") -> None:
        self.config = config
        self.opts = source_config.options

    @abstractmethod
    def fetch(self) -> list[RawLead]:
        """Récupère les opportunités brutes de cette source."""
        raise NotImplementedError
