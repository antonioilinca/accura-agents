"""Génération de factures à partir d'un devis Accura existant.

Le module ne recalcule pas le chantier : il transforme les montants verrouillés du devis
en facture d'acompte ou de solde.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import InvoiceDocument, InvoiceLine, InvoiceParty, InvoiceTotals, money


INVOICE_TYPES = {"acompte", "solde"}


def charger_devis_json(path: str | Path) -> dict[str, Any]:
    chemin = Path(path).expanduser().resolve()
    if not chemin.exists():
        raise FileNotFoundError(f"Devis introuvable : {chemin}")
    data = json.loads(chemin.read_text(encoding="utf-8"))
    if not data.get("id_devis") or not data.get("totaux"):
        raise ValueError("Fichier devis invalide")
    return data


def generer_facture_depuis_devis(
    devis: dict[str, Any],
    type_facture: str = "acompte",
    id_facture: str | None = None,
) -> InvoiceDocument:
    if type_facture not in INVOICE_TYPES:
        raise ValueError("type_facture doit être 'acompte' ou 'solde'")

    totaux_devis = devis.get("totaux", {}) or {}
    total_ht_devis = money(totaux_devis.get("total_ht", 0))
    tva_devis = money(totaux_devis.get("tva", 0))
    total_ttc_devis = money(totaux_devis.get("total_ttc", 0))
    acompte_ttc = money(totaux_devis.get("acompte_ttc", 0))
    if total_ttc_devis <= 0:
        raise ValueError("Le total TTC du devis doit être supérieur à 0")

    acompte_ht = _part_ht(total_ht_devis, acompte_ttc, total_ttc_devis)
    acompte_tva = money(acompte_ttc - acompte_ht)
    if type_facture == "acompte":
        total_ht = acompte_ht
        tva = acompte_tva
        total_ttc = acompte_ttc
        deja_facture = Decimal("0")
        reste_a_payer = money(total_ttc_devis - acompte_ttc)
        libelle = f"Acompte sur devis {devis['id_devis']}"
        description = "Acompte à régler avant démarrage ou réservation du chantier."
    else:
        total_ht = money(total_ht_devis - acompte_ht)
        tva = money(tva_devis - acompte_tva)
        total_ttc = money(total_ttc_devis - acompte_ttc)
        deja_facture = acompte_ttc
        reste_a_payer = total_ttc
        libelle = f"Solde sur devis {devis['id_devis']}"
        description = "Solde à régler après réalisation ou réception des travaux."

    artisan_data = devis.get("artisan", {}) or {}
    demande = devis.get("demande", {}) or {}
    suffix = "ACOMPTE" if type_facture == "acompte" else "SOLDE"
    facture_id = id_facture or f"FAC-{devis['id_devis']}-{suffix}"

    return InvoiceDocument(
        id_facture=facture_id,
        id_devis=str(devis["id_devis"]),
        type_facture=type_facture,
        date_creation=date.today().isoformat(),
        artisan=InvoiceParty(
            nom=str(artisan_data.get("nom", "Votre entreprise")),
            adresse=str(artisan_data.get("adresse", "")),
            telephone=str(artisan_data.get("telephone", "")),
            email=str(artisan_data.get("email", "")),
            siret=str(artisan_data.get("siret", "")),
            assurance_decennale=str(artisan_data.get("assurance_decennale", "")),
            logo_path=str(artisan_data.get("logo_path", "")),
        ),
        client_nom=_client_label(demande),
        chantier=_chantier_label(demande),
        lignes=[
            InvoiceLine(
                libelle=libelle,
                quantite=Decimal("1"),
                unite="forfait",
                prix_unitaire_ht=total_ht,
                total_ht=total_ht,
                description=description,
            )
        ],
        totaux=InvoiceTotals(
            total_ht=total_ht,
            tva=tva,
            total_ttc=total_ttc,
            deja_facture_ttc=deja_facture,
            reste_a_payer_ttc=reste_a_payer,
        ),
        conditions=[
            "Montants issus du devis validé, sans modification par IA.",
            "Paiement par virement, chèque ou moyen convenu avec l'entreprise.",
        ],
    )


def _part_ht(total_ht: Decimal, part_ttc: Decimal, total_ttc: Decimal) -> Decimal:
    ratio = part_ttc / total_ttc
    return money(total_ht * ratio)


def _client_label(demande: dict[str, Any]) -> str:
    adresse = str(demande.get("adresse") or "").strip()
    ville = str(demande.get("ville") or "").strip()
    if adresse:
        return f"Client - {adresse}"
    if ville:
        return f"Client - {ville}"
    return "Client à préciser"


def _chantier_label(demande: dict[str, Any]) -> str:
    chantier = str(demande.get("type_chantier") or "Travaux").strip()
    ville = str(demande.get("ville") or "").strip()
    return f"{chantier} - {ville}" if ville else chantier

