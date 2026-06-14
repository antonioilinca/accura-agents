"""Pipeline CRM local basé sur les devis Accura existants."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from agents.common.fileio import ecrire_json_atomique, lire_json, verrou_fichier


STATUSES = {
    "devis_envoye": "Devis envoyé",
    "relance": "Relancé",
    "signe": "Signé",
    "perdu": "Perdu",
}

# Les statuts terminaux protègent l'historique commercial : un devis signé ou
# perdu ne se requalifie pas d'un clic (erreur de manipulation la plus fréquente).
STATUTS_TERMINAUX = {"signe", "perdu"}

DEFAULT_NEXT_ACTIONS = {
    "devis_envoye": "Relancer à J+3 si pas de retour.",
    "relance": "Relancer à J+7 ou clarifier le blocage client.",
    "signe": "Générer facture d'acompte et planifier le chantier.",
    "perdu": "Noter la raison de perte et archiver.",
}


def _workspace(root: Path, base: Path | None) -> Path:
    """Espace de travail CRM : ``base`` si fourni (client de l'agence), sinon
    ``root/"outputs"`` (mode mono-artisan historique, comportement inchangé)."""
    return base if base is not None else root / "outputs"


def _devis_url_prefix(root: Path, base: Path | None) -> str:
    """Préfixe d'URL des devis servis (/outputs/.../devis) pour les liens CRM.

    Mono-artisan : ``/outputs/devis``. Client actif : ``/outputs/clients/<slug>/devis``,
    calculé depuis le chemin du workspace relatif à la racine du projet.
    """
    if base is None:
        return "/outputs/devis"
    try:
        return "/" + (base.resolve().relative_to(root.resolve()) / "devis").as_posix()
    except ValueError:
        return "/outputs/devis"


def crm_path(root: Path, base: Path | None = None) -> Path:
    return _workspace(root, base) / "crm" / "pipeline.json"


def load_state(root: Path, base: Path | None = None) -> dict[str, dict[str, Any]]:
    return lire_json(crm_path(root, base), {})


def save_state(root: Path, state: dict[str, dict[str, Any]], base: Path | None = None) -> None:
    ecrire_json_atomique(crm_path(root, base), state)


def build_pipeline(root: Path, limit: int = 50, base: Path | None = None) -> dict[str, Any]:
    state = load_state(root, base)
    url_prefix = _devis_url_prefix(root, base)
    items = []
    for path in _quote_files(root, base):
        try:
            quote = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        item = quote_to_crm_item(quote, state.get(str(quote.get("id_devis", "")), {}), url_prefix=url_prefix)
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


def update_item(root: Path, quote_id: str, status: str, next_action: str = "", base: Path | None = None) -> dict[str, Any]:
    quote_id = str(quote_id or "").strip()
    if not quote_id:
        raise ValueError("Devis manquant")
    if status not in STATUSES:
        raise ValueError("Statut CRM invalide")
    if not _quote_exists(root, quote_id, base):
        raise ValueError(f"Devis inconnu : {quote_id} (aucun fichier correspondant dans outputs/devis)")

    # Le cycle lecture → modification → écriture est verrouillé : deux mises à jour
    # simultanées (dashboard multi-onglets, CLI en parallèle) ne se perdent plus.
    with verrou_fichier(crm_path(root, base)):
        state = load_state(root, base)
        statut_actuel = str((state.get(quote_id) or {}).get("status") or "")
        if statut_actuel in STATUTS_TERMINAUX and status != statut_actuel:
            raise ValueError(
                f"Le devis {quote_id} est déjà marqué « {STATUSES[statut_actuel]} » : "
                "statut final, modifiable uniquement à la main dans outputs/crm/pipeline.json."
            )
        state[quote_id] = {
            "status": status,
            "next_action": str(next_action or DEFAULT_NEXT_ACTIONS[status]).strip(),
            "updated_at": date.today().isoformat(),
        }
        save_state(root, state, base)
    return state[quote_id]


def _quote_exists(root: Path, quote_id: str, base: Path | None = None) -> bool:
    direct = _workspace(root, base) / "devis" / f"{_file_stem(quote_id)}.json"
    if direct.exists():
        return True
    expected = quote_id.lower()
    for path in _quote_files(root, base):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if str(data.get("id_devis", "")).lower() == expected:
            return True
    return False


def quote_to_crm_item(
    quote: dict[str, Any],
    state: dict[str, Any],
    url_prefix: str = "/outputs/devis",
) -> dict[str, Any] | None:
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
        "html": f"{url_prefix}/{_file_stem(quote_id)}.html",
        "json": f"{url_prefix}/{_file_stem(quote_id)}.json",
    }


def _quote_files(root: Path, base: Path | None = None) -> list[Path]:
    folder = _workspace(root, base) / "devis"
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

