"""Source n°2 : base nationale Sitadel (data.gouv.fr) — élargissement hors Nantes Métropole.

⚠️  ÉCHAFAUDAGE NON ENCORE VALIDÉ — désactivé par défaut dans config.example.yaml.

Sitadel (SDES) publie les permis de construire et déclarations préalables de toute la
France en CSV. C'est utile UNIQUEMENT pour étendre la zone au-delà des 24 communes de
Nantes Métropole (le reste des Pays de la Loire). Tant que l'artisan test est sur Nantes
+ 20 km, la source urbanisme_nantes suffit et est plus fraîche.

À faire avant activation : brancher le bon fichier départemental (44), valider le format
CSV (séparateur, colonnes, encodage) et la fréquence de mise à jour, puis mapper en RawLead.
On ne l'active pas tant que ce n'est pas testé en réel — pas de faux leads.
"""

from __future__ import annotations

import logging

from ..models import RawLead
from .base import Source

log = logging.getLogger(__name__)


class Sitadel(Source):
    nom = "sitadel"

    def fetch(self) -> list[RawLead]:
        log.warning(
            "sitadel : connecteur non encore validé (voir le docstring et le README). "
            "Activez-le seulement après avoir testé le fichier départemental. Retour vide."
        )
        return []
