"""Génération de relances depuis un devis Accura existant."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .models import FollowupMessage, FollowupPlan


FOLLOWUP_DAYS = (3, 7, 15)


def charger_devis_json(path: str | Path) -> dict[str, Any]:
    chemin = Path(path).expanduser().resolve()
    if not chemin.exists():
        raise FileNotFoundError(f"Devis introuvable : {chemin}")
    data = json.loads(chemin.read_text(encoding="utf-8"))
    if not data.get("id_devis") or not data.get("totaux"):
        raise ValueError("Fichier devis invalide")
    return data


def generer_relances_depuis_devis(devis: dict[str, Any]) -> FollowupPlan:
    id_devis = str(devis["id_devis"])
    demande = devis.get("demande", {}) or {}
    totaux = devis.get("totaux", {}) or {}
    date_devis = str(devis.get("date_creation") or date.today().isoformat())
    base_date = _parse_date(date_devis)
    total_ttc = float(totaux.get("total_ttc", 0) or 0)
    if total_ttc <= 0:
        raise ValueError("Le total TTC du devis doit être supérieur à 0")

    chantier = _chantier_label(demande)
    client = _client_label(demande)
    total = _eur(total_ttc)

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
                    f"Bonjour, je me permets de revenir vers vous concernant le devis {id_devis} "
                    f"pour {chantier}, d'un montant de {total} TTC. Avez-vous pu le regarder ? "
                    "Je reste disponible si vous avez une question ou si vous souhaitez ajuster un point."
                ),
            ),
            FollowupMessage(
                id_devis=id_devis,
                jour=7,
                date_prevue=(base_date + timedelta(days=7)).isoformat(),
                canal="sms_whatsapp",
                objet=f"Relance J+7 devis {id_devis}",
                message=(
                    f"Bonjour, je reviens vers vous pour savoir si le devis {id_devis} "
                    f"pour {chantier} vous convient. Le montant prévu est de {total} TTC. "
                    "Si vous souhaitez avancer, je peux vous confirmer les prochaines étapes."
                ),
            ),
            FollowupMessage(
                id_devis=id_devis,
                jour=15,
                date_prevue=(base_date + timedelta(days=15)).isoformat(),
                canal="sms_whatsapp",
                objet=f"Relance J+15 devis {id_devis}",
                message=(
                    f"Bonjour, je vous fais une dernière relance concernant le devis {id_devis} "
                    f"pour {chantier}. Sans retour de votre part, je le mets en attente. "
                    "Vous pouvez bien sûr me recontacter si le projet est toujours d'actualité."
                ),
            ),
        ],
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
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


def _eur(value: float) -> str:
    txt = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
    return f"{txt} €"

