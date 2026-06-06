"""Source n°1 (socle) : autorisations d'urbanisme de Nantes Métropole.

Open data public, licence ouverte, API Opendatasoft v2.1. Expose les demandes des
3 derniers mois glissants (déclarations préalables, permis de construire/aménager/démolir).

RGPD : pour les particuliers, le champ 'demandeur' est déjà anonymisé à la source
("RGPD - Personne physique"). On ne récupère donc QUE l'opportunité (adresse + nature
des travaux + ampleur + date), sans aucune donnée personnelle nominative.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import requests

from ..models import RawLead
from .base import Source

log = logging.getLogger(__name__)

API = (
    "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/"
    "244400404_demandes-autorisations-decisions-urbanisme-nantes-metropole/records"
)
PAGE = 100          # max autorisé par l'API ODS
PLAFOND = 5000      # garde-fou anti-boucle


class UrbanismeNantes(Source):
    nom = "urbanisme_nantes"

    def fetch(self) -> list[RawLead]:
        jours = int(self.opts.get("jours_recents", 30))
        depuis = (date.today() - timedelta(days=jours)).isoformat()

        leads: list[RawLead] = []
        offset = 0
        while offset < PLAFOND:
            params = {
                "limit": PAGE,
                "offset": offset,
                "order_by": "date_de_depot DESC",
            }
            resp = requests.get(API, params=params, timeout=30)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                break

            stop = False
            for r in results:
                depot = r.get("date_de_depot") or ""
                if depot and depot < depuis:
                    # trié par date décroissante : tout le reste est plus ancien
                    stop = True
                    break
                leads.append(self._to_lead(r))
            if stop or len(results) < PAGE:
                break
            offset += PAGE

        log.info("urbanisme_nantes : %d dossiers déposés depuis %s", len(leads), depuis)
        return leads

    @staticmethod
    def _to_lead(r: dict) -> RawLead:
        surface = r.get("surface_de_plancher")
        try:
            surface = float(surface) if surface not in (None, "", "null") else None
        except (TypeError, ValueError):
            surface = None
        return RawLead(
            source="urbanisme_nantes",
            external_id=str(r.get("numero_de_dossier") or ""),
            commune=str(r.get("commune") or "").strip(),
            adresse=str(r.get("adresse_du_terrain") or "").strip(),
            description=str(r.get("details_du_projet") or "").strip(),
            date_signal=r.get("date_de_depot"),
            type_dossier=r.get("type_dossier"),
            surface_plancher=surface,
            raw=r,
        )
