"""Génération de factures à partir d'un devis Accura existant.

Le module ne recalcule pas le chantier : il transforme les montants verrouillés du devis
en facture d'acompte ou de solde.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from agents.common.fileio import ecrire_json_atomique, lire_json, verrou_fichier

from .models import InvoiceDocument, InvoiceLine, InvoiceParty, InvoiceTotals, money


INVOICE_TYPES = {"acompte", "solde"}

# Une facture française doit porter un numéro chronologique continu, sans trou ni
# doublon (art. 242 nonies A ann. II CGI). Le compteur est persistant et verrouillé.
SEQUENCE_FILE = "_sequence.json"


def prochain_numero_facture(dossier: Path, jour: date | None = None) -> str:
    """Attribue le prochain numéro séquentiel FAC-AAAA-NNNN, à l'épreuve des accès concurrents."""
    jour = jour or date.today()
    dossier.mkdir(parents=True, exist_ok=True)
    registre = dossier / SEQUENCE_FILE
    with verrou_fichier(registre):
        etat = lire_json(registre, {"annee": jour.year, "compteur": 0})
        annee = int(etat.get("annee", jour.year))
        compteur = int(etat.get("compteur", 0))
        if annee != jour.year:
            annee, compteur = jour.year, 0
        compteur += 1
        ecrire_json_atomique(registre, {"annee": annee, "compteur": compteur})
    return f"FAC-{annee}-{compteur:04d}"


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
    dossier: Path | None = None,
    echeance_jours: int = 30,
) -> InvoiceDocument:
    """Transforme un devis validé en facture d'acompte ou de solde.

    Avec `dossier`, le numéro est attribué par le compteur séquentiel persistant
    (recommandé en production). Sans `dossier` ni `id_facture`, un identifiant
    dérivé du devis est utilisé (tests et usages ponctuels uniquement).
    """
    if type_facture not in INVOICE_TYPES:
        raise ValueError("type_facture doit être 'acompte' ou 'solde'")

    totaux_devis = devis.get("totaux", {}) or {}
    total_ht_devis = money(totaux_devis.get("total_ht", 0))
    tva_devis = money(totaux_devis.get("tva", 0))
    total_ttc_devis = money(totaux_devis.get("total_ttc", 0))
    acompte_ttc = money(totaux_devis.get("acompte_ttc", 0))
    if total_ttc_devis <= 0:
        raise ValueError("Le total TTC du devis doit être supérieur à 0")

    artisan_source = devis.get("artisan", {}) or {}
    franchise_tva = bool(artisan_source.get("franchise_tva", False))
    if franchise_tva and tva_devis > 0:
        raise ValueError(
            "Le devis source comporte de la TVA alors que l'artisan est en franchise "
            "en base (art. 293 B) — régénérer le devis avec la config à jour."
        )

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

    demande = devis.get("demande", {}) or {}
    if id_facture:
        facture_id = id_facture
    elif dossier is not None:
        facture_id = prochain_numero_facture(dossier)
    else:
        suffix = "ACOMPTE" if type_facture == "acompte" else "SOLDE"
        facture_id = f"FAC-{devis['id_devis']}-{suffix}"

    emission = date.today()
    echeance = emission + timedelta(days=max(0, int(echeance_jours)))

    return InvoiceDocument(
        id_facture=facture_id,
        id_devis=str(devis["id_devis"]),
        type_facture=type_facture,
        date_creation=emission.isoformat(),
        date_echeance=echeance.isoformat(),
        franchise_tva=franchise_tva,
        mentions_legales=_mentions_legales(franchise_tva),
        artisan=InvoiceParty(
            nom=str(artisan_source.get("nom", "Votre entreprise")),
            adresse=str(artisan_source.get("adresse", "")),
            telephone=str(artisan_source.get("telephone", "")),
            email=str(artisan_source.get("email", "")),
            siret=str(artisan_source.get("siret", "")),
            assurance_decennale=str(artisan_source.get("assurance_decennale", "")),
            logo_path=str(artisan_source.get("logo_path", "")),
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


def _mentions_legales(franchise_tva: bool) -> list[str]:
    mentions = [
        "Tout retard de paiement entraîne des pénalités de retard au taux légal en vigueur ; "
        "pour les clients professionnels, s'y ajoute l'indemnité forfaitaire de recouvrement "
        "de 40 € (art. L441-10 et D441-5 du Code de commerce).",
        "Pas d'escompte pour paiement anticipé.",
    ]
    if franchise_tva:
        mentions.insert(0, "TVA non applicable, art. 293 B du CGI.")
    return mentions


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

