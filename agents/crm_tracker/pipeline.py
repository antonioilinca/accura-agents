"""Pipeline CRM local basé sur les devis Accura existants."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


STATUSES = {
    "devis_envoye": "Devis envoyé",
    "relance": "Relancé",
    "signe": "Signé",
    "perdu": "Perdu",
}

DEFAULT_NEXT_ACTIONS = {
    "devis_envoye": "Relancer à J+3 si pas de retour.",
    "relance": "Relancer à J+7 ou clarifier le blocage client.",
    "signe": "Générer facture d'acompte et planifier le chantier.",
    "perdu": "Noter la raison de perte et archiver.",
}


def crm_path(root: Path) -> Path:
    return root / "outputs" / "crm" / "pipeline.json"


def load_state(root: Path) -> dict[str, dict[str, Any]]:
    path = crm_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_state(root: Path, state: dict[str, dict[str, Any]]) -> None:
    path = crm_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_pipeline(root: Path, limit: int = 50) -> dict[str, Any]:
    state = load_state(root)
    items = []
    for path in _quote_files(root):
        try:
            quote = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        item = quote_to_crm_item(quote, state.get(str(quote.get("id_devis", "")), {}))
        if item:
            items.append(item)
        if len(items) >= limit:
            break

    return {
        "items": items,
        "statuses": STATUSES,
        "stats": {
            key: sum(1 for item in items if item["status"] == key)
            for key in STATUSES
        },
    }


def update_item(root: Path, quote_id: str, status: str, next_action: str = "") -> dict[str, Any]:
    quote_id = str(quote_id or "").strip()
    if not quote_id:
        raise ValueError("Devis manquant")
    if status not in STATUSES:
        raise ValueError("Statut CRM invalide")

    state = load_state(root)
    state[quote_id] = {
        "status": status,
        "next_action": str(next_action or DEFAULT_NEXT_ACTIONS[status]).strip(),
        "updated_at": date.today().isoformat(),
    }
    save_state(root, state)
    return state[quote_id]


def quote_to_crm_item(quote: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    quote_id = str(quote.get("id_devis", "")).strip()
    if not quote_id:
        return None
    demande = quote.get("demande", {}) or {}
    totaux = quote.get("totaux", {}) or {}
    status = str(state.get("status") or "devis_envoye")
    if status not in STATUSES:
        status = "devis_envoye"
    return {
        "id": quote_id,
        "date": quote.get("date_creation", ""),
        "client": _client_label(demande),
        "chantier": _chantier_label(demande),
        "ville": demande.get("ville") or "à préciser",
        "total_ttc": float(totaux.get("total_ttc", 0) or 0),
        "status": status,
        "status_label": STATUSES[status],
        "next_action": str(state.get("next_action") or DEFAULT_NEXT_ACTIONS[status]),
        "updated_at": state.get("updated_at", ""),
        "html": f"/outputs/devis/{_file_stem(quote_id)}.html",
        "json": f"/outputs/devis/{_file_stem(quote_id)}.json",
    }


def _quote_files(root: Path) -> list[Path]:
    folder = root / "outputs" / "devis"
    if not folder.exists():
        return []
    return sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


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


def _file_stem(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")

