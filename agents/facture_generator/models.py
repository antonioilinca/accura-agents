"""Types de données du module factures Accura."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


CENT = Decimal("0.01")


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class InvoiceParty:
    nom: str
    adresse: str = ""
    telephone: str = ""
    email: str = ""
    siret: str = ""
    assurance_decennale: str = ""
    logo_path: str = ""


@dataclass
class InvoiceLine:
    libelle: str
    quantite: Decimal
    unite: str
    prix_unitaire_ht: Decimal
    total_ht: Decimal
    description: str = ""


@dataclass
class InvoiceTotals:
    total_ht: Decimal
    tva: Decimal
    total_ttc: Decimal
    deja_facture_ttc: Decimal = Decimal("0")
    reste_a_payer_ttc: Decimal = Decimal("0")


@dataclass
class InvoiceDocument:
    id_facture: str
    id_devis: str
    type_facture: str
    date_creation: str
    artisan: InvoiceParty
    client_nom: str
    chantier: str
    lignes: list[InvoiceLine]
    totaux: InvoiceTotals
    conditions: list[str] = field(default_factory=list)
    statut: str = "a_regler"

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Decimal):
                return float(value)
            if isinstance(value, list):
                return [convert(v) for v in value]
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            return value

        return convert(asdict(self))

