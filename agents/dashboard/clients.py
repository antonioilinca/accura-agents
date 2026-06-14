"""Gestion multi-clients de l'agence Accura Ouest.

Le dashboard est historiquement MONO-artisan : un seul profil dans
``outputs/onboarding/artisan_profile.json`` et toutes les sorties (devis,
factures, relances…) directement sous ``outputs/``.

Ce module ajoute le SOCLE multi-clients sans rien casser : chaque artisan client
de l'agence reçoit un espace cloisonné sous ``outputs/clients/<slug>/`` avec son
propre profil et ses propres sous-dossiers (devis, factures, relances, avis,
crm, onboarding). Un client peut être "actif" : tant qu'aucun ne l'est, tout
fonctionne EXACTEMENT comme avant (rétrocompatibilité totale).

Règle d'or : ``active_workspace(root)`` renvoie le dossier du client actif, ou
``root/"outputs"`` si aucun n'est sélectionné. Les agents (devis, factures…) ne
connaissent que ce dossier de travail, jamais la notion de client.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.common.fileio import ecrire_json_atomique, lire_json, verrou_fichier
from agents.dashboard import onboarding


# Sous-dossiers de l'espace de travail d'un client, créés à la demande par les agents.
WORKSPACE_SUBDIRS = ("devis", "factures", "relances", "avis", "crm", "onboarding")

# Statuts commerciaux d'un client de l'agence (cycle de vie de l'abonnement).
CLIENT_STATUSES = ("prospect", "onboarding", "actif", "pause", "perdu")

# Champs libres de la fiche client (en plus du slug et des dates générées).
CLIENT_FIELDS = (
    "company_name",
    "main_trade",
    "service_area",
    "plan",
    "status",
    "contact_name",
    "phone",
    "email",
    "notes",
)


# ---- Chemins ----------------------------------------------------------------------------

def clients_root(root: Path) -> Path:
    """Dossier racine de tous les clients de l'agence."""
    return root / "outputs" / "clients"


def client_workspace(root: Path, slug: str) -> Path:
    """Espace de travail cloisonné d'un client (= outputs/clients/<slug>)."""
    return clients_root(root) / slug


def client_file(root: Path, slug: str) -> Path:
    """Fiche JSON d'un client (outputs/clients/<slug>/client.json)."""
    return client_workspace(root, slug) / "client.json"


def _active_file(root: Path) -> Path:
    """Pointeur vers le client actif (outputs/clients/_active.json)."""
    return clients_root(root) / "_active.json"


def active_workspace(root: Path) -> Path:
    """Dossier de travail courant : client actif, sinon outputs/ (rétrocompat).

    C'est LA fonction que le serveur utilise pour router toutes les sorties.
    Tant qu'aucun client n'est actif, on renvoie ``root/"outputs"`` : le
    comportement mono-artisan d'origine est conservé à l'identique.
    """
    slug = get_active(root)
    if slug:
        workspace = client_workspace(root, slug)
        if workspace.exists():
            return workspace
    return root / "outputs"


# ---- Slug -------------------------------------------------------------------------------

def slugify(name: str) -> str:
    """Transforme un nom d'entreprise en slug de dossier sûr (ascii, minuscules)."""
    text = str(name or "").strip().lower()
    # Remplacement minimal des accents français les plus courants.
    accents = {
        "à": "a", "â": "a", "ä": "a",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "î": "i", "ï": "i",
        "ô": "o", "ö": "o",
        "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
    }
    text = "".join(accents.get(char, char) for char in text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "client"


def _unique_slug(root: Path, base: str) -> str:
    """Garantit un slug unique : ajoute -2, -3… si le dossier existe déjà."""
    slug = base
    index = 2
    while client_workspace(root, slug).exists():
        slug = f"{base}-{index}"
        index += 1
    return slug


# ---- Lecture ----------------------------------------------------------------------------

def get_client(root: Path, slug: str) -> dict[str, Any] | None:
    """Renvoie la fiche d'un client, ou None s'il n'existe pas / fiche illisible."""
    slug = str(slug or "").strip()
    if not slug:
        return None
    data = lire_json(client_file(root, slug), None)
    if not isinstance(data, dict):
        return None
    return data


def list_clients(root: Path) -> list[dict[str, Any]]:
    """Liste toutes les fiches clients, triées par date de création (récent d'abord)."""
    base = clients_root(root)
    if not base.exists():
        return []
    clients: list[dict[str, Any]] = []
    for fiche in base.glob("*/client.json"):
        data = lire_json(fiche, None)
        if isinstance(data, dict) and data.get("slug"):
            clients.append(data)
    clients.sort(key=lambda c: str(c.get("created_at") or ""), reverse=True)
    return clients


def get_active(root: Path) -> str | None:
    """Slug du client actif, ou None. Le pointeur ne survit pas à la suppression du client."""
    data = lire_json(_active_file(root), {})
    slug = str((data or {}).get("slug") or "").strip()
    if not slug:
        return None
    # Pointeur orphelin (client supprimé à la main) : on ne le laisse pas casser le dashboard.
    if not client_file(root, slug).exists():
        return None
    return slug


# ---- Écriture ---------------------------------------------------------------------------

def _normalize_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Nettoie/normalise les champs d'une fiche client venue du formulaire ou de l'API."""
    company_name = str(data.get("company_name") or "").strip()
    main_trade = str(data.get("main_trade") or "plomberie").strip() or "plomberie"

    plan = str(data.get("plan") or "fondation").strip()
    if plan not in onboarding.PLANS:
        plan = "fondation"

    status = str(data.get("status") or "prospect").strip()
    if status not in CLIENT_STATUSES:
        status = "prospect"

    return {
        "company_name": company_name,
        "main_trade": main_trade,
        "service_area": _as_list(data.get("service_area")),
        "plan": plan,
        "status": status,
        "contact_name": str(data.get("contact_name") or "").strip(),
        "phone": str(data.get("phone") or "").strip(),
        "email": str(data.get("email") or "").strip(),
        "notes": str(data.get("notes") or "").strip(),
    }


def _as_list(value: Any) -> list[str]:
    """Accepte une liste ou une chaîne « Nantes, Rezé » et renvoie une liste propre."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def create_client(root: Path, data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Crée un client : génère un slug unique, le dossier, la fiche et un profil initial.

    Le statut par défaut est ``prospect``. Un profil d'onboarding est initialisé dans
    l'espace du client (DEFAULT_PROFILE adapté avec nom/métier/zone/offre) pour que les
    agents soient utilisables dès l'activation, sans config supplémentaire.
    """
    payload = _normalize_payload(data)
    if not payload["company_name"]:
        raise ValueError("Le nom de l'entreprise est obligatoire pour créer un client.")

    horodatage = (now or datetime.now()).isoformat(timespec="seconds")
    base_slug = slugify(payload["company_name"])

    # Section critique : deux créations simultanées ne doivent pas se voler le même slug.
    with verrou_fichier(clients_root(root) / "_clients"):
        slug = _unique_slug(root, base_slug)
        workspace = client_workspace(root, slug)
        workspace.mkdir(parents=True, exist_ok=True)

        fiche = {
            "slug": slug,
            **payload,
            "created_at": horodatage,
            "updated_at": horodatage,
        }
        ecrire_json_atomique(client_file(root, slug), fiche)

    # Profil d'onboarding initial dans l'espace du client (hors verrou : nouveau dossier).
    _init_client_profile(root, slug, payload)
    return fiche


def update_client(root: Path, slug: str, patch: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Mise à jour partielle d'une fiche client (ex: changer le statut).

    Seuls les champs connus sont pris en compte ; ``slug`` et ``created_at`` sont protégés.
    """
    slug = str(slug or "").strip()
    if not slug:
        raise ValueError("Client manquant")
    with verrou_fichier(client_file(root, slug)):
        fiche = get_client(root, slug)
        if fiche is None:
            raise ValueError(f"Client introuvable : {slug}")

        for key, value in (patch or {}).items():
            if key not in CLIENT_FIELDS:
                continue
            if key == "status":
                value = str(value or "").strip()
                if value not in CLIENT_STATUSES:
                    raise ValueError(f"Statut client invalide : {value!r}")
            elif key == "plan":
                value = str(value or "").strip()
                if value not in onboarding.PLANS:
                    raise ValueError(f"Offre invalide : {value!r}")
            elif key == "service_area":
                value = _as_list(value)
            else:
                value = str(value or "").strip()
            fiche[key] = value

        fiche["updated_at"] = (now or datetime.now()).isoformat(timespec="seconds")
        ecrire_json_atomique(client_file(root, slug), fiche)
    return fiche


def set_active(root: Path, slug: str | None) -> str | None:
    """Définit le client actif (ou aucun si slug=None / vide). Renvoie le slug actif final."""
    if slug is None or str(slug).strip() == "":
        ecrire_json_atomique(_active_file(root), {"slug": None})
        return None
    slug = str(slug).strip()
    if not client_file(root, slug).exists():
        raise ValueError(f"Client introuvable : {slug}")
    ecrire_json_atomique(_active_file(root), {"slug": slug})
    return slug


# ---- Profil d'onboarding par client -----------------------------------------------------

def _init_client_profile(root: Path, slug: str, payload: dict[str, Any]) -> None:
    """Initialise le profil artisan dans l'espace du client à partir du DEFAULT_PROFILE.

    On réutilise ``onboarding.save_profile`` en ciblant le workspace du client (paramètre
    ``base``). Le profil reste un brouillon (SIRET placeholder) : il devra être complété
    avant d'activer la config devis, exactement comme pour le profil mono-artisan.
    """
    workspace = client_workspace(root, slug)
    overrides = {
        "plan": payload["plan"],
        "company": {"name": payload["company_name"] or onboarding.DEFAULT_PROFILE["company"]["name"]},
        "business": {
            "main_trade": payload["main_trade"],
            "service_area": payload["service_area"] or onboarding.DEFAULT_PROFILE["business"]["service_area"],
        },
    }
    # save_profile fusionne overrides sur DEFAULT_PROFILE et écrit dans <workspace>/onboarding/.
    onboarding.save_profile(root, overrides, base=workspace)
