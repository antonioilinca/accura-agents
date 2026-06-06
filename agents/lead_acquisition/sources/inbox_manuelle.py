"""Source n°3 : demandes collées manuellement (groupes Facebook locaux, etc.).

Pourquoi pas de scraping automatique des groupes Facebook : les CGU de Meta l'interdisent,
l'API Groupes est fermée depuis 2018, et revendre des données personnelles de tiers non
informés violerait le RGPD. La voie légale : un humain (Younès/Antonio), déjà membre des
groupes, copie les demandes pertinentes dans inbox/leads_manuels.md, et l'agent les qualifie
comme les autres. Humain dans la boucle = zéro risque juridique.

Format du fichier : un bloc par demande, blocs séparés par une ligne '---'.
Lignes optionnelles 'Commune:' et 'Adresse:' reconnues ; sinon l'IA infère depuis le texte.
Les lignes commençant par '#' sont des commentaires ignorés.
"""

from __future__ import annotations

import hashlib
import logging

from ..models import RawLead
from .base import Source

log = logging.getLogger(__name__)


class InboxManuelle(Source):
    nom = "inbox_manuelle"

    def fetch(self) -> list[RawLead]:
        rel = self.opts.get("fichier", "inbox/leads_manuels.md")
        chemin = self.config.racine / rel
        if not chemin.exists():
            log.info("inbox_manuelle : aucun fichier %s, source ignorée", rel)
            return []

        texte = chemin.read_text(encoding="utf-8")
        leads: list[RawLead] = []
        for bloc in texte.split("\n---"):
            contenu = "\n".join(
                ligne for ligne in bloc.splitlines()
                if not ligne.strip().startswith("#")
            ).strip()
            if not contenu:
                continue
            empreinte = hashlib.sha1(contenu.encode("utf-8")).hexdigest()[:16]
            leads.append(
                RawLead(
                    source="inbox_manuelle",
                    external_id=empreinte,
                    commune=self._champ(contenu, "commune"),
                    adresse=self._champ(contenu, "adresse"),
                    description=contenu,
                    date_signal=None,
                )
            )
        log.info("inbox_manuelle : %d demande(s) lue(s)", len(leads))
        return leads

    @staticmethod
    def _champ(texte: str, cle: str) -> str:
        prefixe = cle.lower() + ":"
        for ligne in texte.splitlines():
            if ligne.lower().startswith(prefixe):
                return ligne.split(":", 1)[1].strip()
        return ""
