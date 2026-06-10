"""Génération de relances depuis un devis Accura existant."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .models import FollowupMessage, FollowupPlan


log = logging.getLogger(__name__)

FOLLOWUP_DAYS = (3, 7, 15)


def charger_devis_json(path: str | Path) -> dict[str, Any]:
    chemin = Path(path).expanduser().resolve()
    if not chemin.exists():
        raise FileNotFoundError(f"Devis introuvable : {chemin}")
    data = json.loads(chemin.read_text(encoding="utf-8"))
    if not data.get("id_devis") or not data.get("totaux"):
        raise ValueError("Fichier devis invalide")
    return data


def generer_relances_depuis_devis(devis: dict[str, Any], date_envoi: str | None = None) -> FollowupPlan:
    """Les J+3/J+7/J+15 se comptent depuis l'envoi du devis au client.

    `date_envoi` (ISO) est à fournir si le devis n'a pas été envoyé le jour de sa
    création ; à défaut, la date de création du devis sert de référence.
    """
    id_devis = str(devis["id_devis"])
    demande = devis.get("demande", {}) or {}
    totaux = devis.get("totaux", {}) or {}
    date_devis = str(devis.get("date_creation") or date.today().isoformat())
    base_date = _parse_date(date_envoi) if date_envoi else _parse_date(date_devis)
    total_ttc = float(totaux.get("total_ttc", 0) or 0)
    if total_ttc <= 0:
        raise ValueError("Le total TTC du devis doit être supérieur à 0")

    chantier = _chantier_label(demande)
    chantier_client = _chantier_client(demande)
    client = _client_label(demande)

    return FollowupPlan(
        id_devis=id_devis,
        date_devis=date_devis,
        client=client,
        chantier=chantier,
        total_ttc=total_ttc,
        messages=[
            FollowupMessage(
                id_devis=id_devis,
                jour=3,
                date_prevue=(base_date + timedelta(days=3)).isoformat(),
                canal="sms_whatsapp",
                objet=f"Relance J+3 devis {id_devis}",
                message=(
                    f"Bonjour, avez-vous pu jeter un œil au devis pour {chantier_client} ? "
                    "Je reste disponible si une question se pose ou si vous voulez ajuster un point."
                ),
            ),
            FollowupMessage(
                id_devis=id_devis,
                jour=7,
                date_prevue=(base_date + timedelta(days=7)).isoformat(),
                canal="sms_whatsapp",
                objet=f"Relance J+7 devis {id_devis}",
                message=(
                    f"Bonjour, je reviens vers vous au sujet du devis pour {chantier_client}. "
                    "Souhaitez-vous qu'on avance ? Je peux vous proposer une date pour démarrer."
                ),
            ),
            FollowupMessage(
                id_devis=id_devis,
                jour=15,
                date_prevue=(base_date + timedelta(days=15)).isoformat(),
                canal="sms_whatsapp",
                objet=f"Relance J+15 devis {id_devis}",
                message=(
                    f"Bonjour, sans retour de votre part je vais mettre le devis pour "
                    f"{chantier_client} en attente. Recontactez-moi quand vous voulez, "
                    "le projet reste tout à fait possible."
                ),
            ),
        ],
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        log.warning("date invalide (%r) — les relances sont calées sur aujourd'hui", value)
        return date.today()


def _client_label(demande: dict[str, Any]) -> str:
    adresse = str(demande.get("adresse") or "").strip()
    ville = str(demande.get("ville") or "").strip()
    if adresse:
        return f"Client - {adresse}"
    if ville:
        return f"Client - {ville}"
    return "Client à préciser"


def _chantier_label(demande: dict[str, Any]) -> str:
    chantier = str(demande.get("type_chantier") or "travaux").strip()
    ville = str(demande.get("ville") or "").strip()
    return f"{chantier} à {ville}" if ville else chantier


# Formulations naturelles côté client : un artisan parle du chantier ("votre salle
# de bain"), jamais du type technique ni de la référence du devis.
_CHANTIER_CLIENT = {
    "rénovation salle de bain": "votre salle de bain",
    "remplacement chauffe-eau": "votre chauffe-eau",
    "rénovation électrique": "vos travaux d'électricité",
    "peinture intérieure": "vos travaux de peinture",
    "menuiserie": "vos travaux de menuiserie",
    "carrelage": "votre carrelage",
    "rénovation générale": "votre projet de rénovation",
    "travaux de rénovation": "votre projet de rénovation",
}


def _chantier_client(demande: dict[str, Any]) -> str:
    cle = str(demande.get("type_chantier") or "").strip().lower()
    return _CHANTIER_CLIENT.get(cle, "vos travaux")

