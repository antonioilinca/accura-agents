"""Logique métier de la plateforme artisan (sans HTTP : testable directement).

Chaque action est :
- **authentifiée** : on part du slug de l'artisan (issu d'un jeton vérifié) ;
- **cloisonnée** : tout se passe dans `outputs/clients/<slug>/`, jamais ailleurs —
  un artisan ne peut pas voir les données d'un autre ;
- **filtrée par plan** : une action dont l'agent n'est pas inclus dans le plan acheté
  lève `PlanError` (ex. un Fondation qui tente d'accéder aux leads).

On réutilise les vrais générateurs des agents (devis, factures, relances, avis, CRM) :
zéro logique dupliquée, mêmes garde-fous (l'IA ne touche jamais aux prix).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from agents.common.fileio import ecrire_json_atomique, lire_json
from agents.dashboard import clients, onboarding
from agents.devis_generator.config import charger_config as charger_config_devis
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import ecrire_exports as ecrire_devis
from agents.facture_generator.generator import generer_facture_depuis_devis
from agents.facture_generator.render import ecrire_exports as ecrire_facture
from agents.relance_generator.generator import generer_relances_depuis_devis
from agents.relance_generator.render import ecrire_exports as ecrire_relance
from agents.avis_generator.generator import generer_demande_avis
from agents.avis_generator.render import ecrire_exports as ecrire_avis
from agents.crm_tracker.pipeline import build_pipeline, update_item

from . import auth


# ---- Erreurs (le serveur les transforme en codes HTTP) ----------------------------------

class PlatformError(Exception):
    """Erreur métier avec un statut HTTP associé."""

    status = 400

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        if status is not None:
            self.status = status


class AuthError(PlatformError):
    status = 401


class PlanError(PlatformError):
    status = 403


class NotFoundError(PlatformError):
    status = 404


# Action → capacité requise dans le plan (voir onboarding.PLANS).
_AGENT_PAR_ACTION = {
    "devis": "devis",
    "factures": "devis",      # la facturation fait partie du socle Fondation
    "relances": "relances",
    "avis": "avis_google",
    "crm": "crm",
    "leads": "acquisition",
}


# ---- Identifiants (stockés dans l'espace cloisonné du client) ---------------------------

def _credentials_path(root: Path, slug: str) -> Path:
    return clients.client_workspace(root, slug) / "auth.json"


def get_credentials(root: Path, slug: str) -> dict | None:
    data = lire_json(_credentials_path(root, slug), None)
    return data if isinstance(data, dict) else None


def set_credentials(root: Path, slug: str, login: str, password: str) -> None:
    """Enregistre l'identifiant + le mot de passe haché d'un artisan."""
    login = str(login or "").strip()
    if not login:
        raise PlatformError("Identifiant (email) obligatoire.")
    record = {
        "login": login,
        "login_lower": login.lower(),
        "password": auth.hash_password(password),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    ecrire_json_atomique(_credentials_path(root, slug), record)


def find_slug_by_login(root: Path, login: str) -> str | None:
    """Retrouve l'artisan par son identifiant (insensible à la casse)."""
    cible = str(login or "").strip().lower()
    if not cible:
        return None
    base = clients.clients_root(root)
    if not base.exists():
        return None
    for fichier in base.glob("*/auth.json"):
        data = lire_json(fichier, None)
        if isinstance(data, dict) and data.get("login_lower") == cible:
            return fichier.parent.name
    return None


# ---- Provisioning + authentification ----------------------------------------------------

def provision_account(
    root: Path,
    payload: dict[str, Any],
    *,
    password: str | None = None,
    login: str | None = None,
) -> dict[str, Any]:
    """Crée un compte artisan après un achat (appelé par le site, côté serveur).

    `payload` = champs entreprise (company_name obligatoire, plan, main_trade, email…).
    `login` par défaut = email. Si `password` n'est pas fourni, on en génère un et on le
    renvoie (à transmettre à l'artisan). Le client passe en statut « actif ».
    """
    login = str(login or payload.get("email") or "").strip()
    if not login:
        raise PlatformError("Email/identifiant obligatoire pour créer un compte.")
    if find_slug_by_login(root, login):
        raise PlatformError("Un compte existe déjà avec cet identifiant.", status=409)

    fiche = clients.create_client(root, payload)
    slug = fiche["slug"]

    genere = None
    if not password:
        password = auth.generate_password()
        genere = password
    set_credentials(root, slug, login, password)

    fiche = clients.update_client(root, slug, {"status": "actif"})
    return {
        "slug": slug,
        "login": login,
        "password": genere,  # non-null seulement si généré ici (à transmettre une fois)
        "client": fiche,
        "account": account_overview(root, slug),
    }


def authenticate(root: Path, login: str, password: str) -> str:
    """Vérifie identifiant + mot de passe et renvoie un jeton de session. Lève AuthError."""
    slug = find_slug_by_login(root, login)
    creds = get_credentials(root, slug) if slug else None
    if not slug or not creds or not auth.verify_password(password, creds.get("password") or {}):
        raise AuthError("Identifiant ou mot de passe incorrect.")
    return auth.issue_token(root, slug)


def set_password(root: Path, slug: str, password: str) -> None:
    """Change le mot de passe d'un artisan (garde le même identifiant)."""
    creds = get_credentials(root, slug)
    if not creds:
        raise NotFoundError("Compte introuvable.")
    set_credentials(root, slug, creds.get("login", slug), password)


# ---- Contexte d'un artisan (à partir d'un slug déjà authentifié) ------------------------

def _require_client(root: Path, slug: str) -> dict[str, Any]:
    fiche = clients.get_client(root, slug)
    if fiche is None:
        raise AuthError("Compte introuvable ou supprimé.")
    return fiche


def _workspace(root: Path, slug: str) -> Path:
    return clients.client_workspace(root, slug)


def _profile(root: Path, slug: str) -> dict[str, Any]:
    return onboarding.load_profile(root, base=_workspace(root, slug))


def _capacites(profile: dict[str, Any]) -> list[str]:
    return list((profile.get("plan_capabilities") or {}).get("agents") or [])


def _exiger_plan(profile: dict[str, Any], action: str) -> None:
    """Lève PlanError si l'agent de cette action n'est pas inclus dans le plan."""
    requis = _AGENT_PAR_ACTION.get(action)
    if requis and requis not in _capacites(profile):
        plan = (profile.get("plan_capabilities") or {}).get("label", "votre offre")
        raise PlanError(
            f"L'action « {action} » n'est pas incluse dans l'offre {plan}. "
            "Passez à une offre supérieure pour y accéder."
        )


def account_overview(root: Path, slug: str) -> dict[str, Any]:
    """Vue d'ensemble du compte : entreprise, plan, agents autorisés, compteurs."""
    fiche = _require_client(root, slug)
    profile = _profile(root, slug)
    ws = _workspace(root, slug)
    caps = profile.get("plan_capabilities") or {}
    return {
        "slug": slug,
        "company": profile.get("company", {}),
        "status": fiche.get("status"),
        "plan": {
            "key": profile.get("plan"),
            "label": caps.get("label"),
            "price": caps.get("price"),
            "agents": caps.get("agents", []),
        },
        "counts": {
            "devis": _compter(ws / "devis"),
            "factures": _compter(ws / "factures"),
            "relances": _compter(ws / "relances"),
            "leads": _compter_leads(ws),
        },
    }


def _compter(dossier: Path) -> int:
    if not dossier.exists():
        return 0
    return sum(1 for p in dossier.glob("*.json") if not p.name.startswith("_"))


def _compter_leads(ws: Path) -> int:
    total = 0
    for fichier in ws.glob("leads-*.json"):
        data = lire_json(fichier, None)
        if isinstance(data, dict):
            total += len(data.get("leads") or [])
    return total


# ---- Profil (l'artisan complète son entreprise / ses prix) ------------------------------

def get_profile(root: Path, slug: str) -> dict[str, Any]:
    _require_client(root, slug)
    return _profile(root, slug)


def update_profile(root: Path, slug: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Met à jour le profil de l'artisan (entreprise, zone, prix, postes…)."""
    _require_client(root, slug)
    ws = _workspace(root, slug)
    actuel = _profile(root, slug)
    fusion = onboarding.merge_profile(actuel, patch or {})
    # Le plan reste piloté par l'abonnement (clients/admin), pas modifiable par l'artisan.
    fusion["plan"] = actuel.get("plan", "fondation")
    return onboarding.save_profile(root, fusion, base=ws)


# ---- Devis -------------------------------------------------------------------------------

def _config_devis(root: Path, slug: str):
    """Construit la config devis de l'artisan à partir de son profil (toujours à jour).

    On régénère `devis.config.yaml` dans l'espace du client depuis son profil : les prix
    et l'identité viennent donc TOUJOURS de ce que l'artisan a renseigné, jamais d'un
    fichier figé. (Le chiffrage reste piloté par la config, pas par l'IA.)
    """
    ws = _workspace(root, slug)
    profile = _profile(root, slug)
    payload = onboarding.build_devis_yaml(profile)
    chemin = onboarding.client_devis_config_path(ws)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return charger_config_devis(chemin)


def create_quote(root: Path, slug: str, texte: str, *, quote_id: str | None = None) -> dict[str, Any]:
    profile = _profile(root, slug)
    _exiger_plan(profile, "devis")
    texte = str(texte or "").strip()
    if len(texte) < 12:
        raise PlatformError("Demande trop courte : décrivez le chantier (ville, surface, travaux).")
    ws = _workspace(root, slug)
    cfg = _config_devis(root, slug)
    doc = generer_devis(texte, cfg, id_devis=quote_id, dossier=ws / "devis")
    paths = ecrire_devis(doc, ws / "devis", ecraser=bool(quote_id))
    data = doc.to_dict()
    data["exports"] = _exports(slug, "devis", paths)
    return data


def list_quotes(root: Path, slug: str, limit: int = 50) -> list[dict[str, Any]]:
    _exiger_plan(_profile(root, slug), "devis")
    return _lister(root, slug, "devis", limit, _resume_devis)


def create_invoice(root: Path, slug: str, quote_id: str, type_facture: str = "acompte") -> dict[str, Any]:
    _exiger_plan(_profile(root, slug), "factures")
    devis = _charger_devis(root, slug, quote_id)
    ws = _workspace(root, slug)
    doc = generer_facture_depuis_devis(devis, type_facture=type_facture, dossier=ws / "factures")
    paths = ecrire_facture(doc, ws / "factures")
    data = doc.to_dict()
    data["exports"] = _exports(slug, "factures", paths)
    return data


def list_invoices(root: Path, slug: str, limit: int = 50) -> list[dict[str, Any]]:
    _exiger_plan(_profile(root, slug), "factures")
    return _lister(root, slug, "factures", limit, _resume_facture)


def create_followups(root: Path, slug: str, quote_id: str) -> dict[str, Any]:
    _exiger_plan(_profile(root, slug), "relances")
    devis = _charger_devis(root, slug, quote_id)
    ws = _workspace(root, slug)
    plan = generer_relances_depuis_devis(devis)
    paths = ecrire_relance(plan, ws / "relances")
    data = plan.to_dict()
    data["exports"] = {"json": _doc_url(slug, "relances", paths["json"].name)}
    return data


def create_review(root: Path, slug: str, client: str = "", chantier: str = "") -> dict[str, Any]:
    _exiger_plan(_profile(root, slug), "avis")
    ws = _workspace(root, slug)
    request = generer_demande_avis(_profile(root, slug), client=client, chantier=chantier)
    paths = ecrire_avis(request, ws / "avis")
    data = request.to_dict()
    data["exports"] = {"json": _doc_url(slug, "avis", paths["json"].name)}
    return data


def crm_pipeline(root: Path, slug: str) -> dict[str, Any]:
    _exiger_plan(_profile(root, slug), "crm")
    return build_pipeline(root, base=_workspace(root, slug))


def crm_update(root: Path, slug: str, quote_id: str, status: str, next_action: str = "") -> dict[str, Any]:
    _exiger_plan(_profile(root, slug), "crm")
    update_item(root, quote_id, status, next_action, base=_workspace(root, slug))
    return crm_pipeline(root, slug)


def list_leads(root: Path, slug: str, limit: int = 50) -> list[dict[str, Any]]:
    """Leads livrés à cet artisan (offres Croissance / Intégral)."""
    _exiger_plan(_profile(root, slug), "leads")
    ws = _workspace(root, slug)
    leads: list[dict[str, Any]] = []
    for fichier in sorted(ws.glob("leads-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = lire_json(fichier, None)
        if not isinstance(data, dict):
            continue
        for lead in data.get("leads") or []:
            leads.append(lead)
            if len(leads) >= limit:
                return leads
    return leads


# ---- Téléchargement de documents (cloisonné + anti-traversée) ---------------------------

def document_path(root: Path, slug: str, kind: str, name: str) -> Path:
    """Chemin sûr d'un document de l'artisan. Lève NotFoundError sinon.

    Garantit : type autorisé, pas de remontée de dossier (« .. »), fichier présent,
    et strictement dans l'espace de CE client.
    """
    if kind not in {"devis", "factures", "relances", "avis"}:
        raise NotFoundError("Type de document inconnu.")
    base = (_workspace(root, slug) / kind).resolve()
    cible = (base / name).resolve()
    if base != cible.parent or not cible.is_file():
        raise NotFoundError("Document introuvable.")
    return cible


# ---- Helpers internes -------------------------------------------------------------------

def _charger_devis(root: Path, slug: str, quote_id: str) -> dict[str, Any]:
    dossier = _workspace(root, slug) / "devis"
    attendu = str(quote_id or "").strip().lower()
    if not attendu:
        raise PlatformError("Devis source manquant.")
    if dossier.exists():
        for chemin in dossier.glob("*.json"):
            if chemin.name.startswith("_"):
                continue
            data = lire_json(chemin, None)
            if isinstance(data, dict) and (
                str(data.get("id_devis", "")).lower() == attendu or chemin.stem.lower() == attendu
            ):
                return data
    raise NotFoundError(f"Devis introuvable : {quote_id}")


def _lister(root: Path, slug: str, kind: str, limit: int, resume) -> list[dict[str, Any]]:
    dossier = _workspace(root, slug) / kind
    if not dossier.exists():
        return []
    items: list[dict[str, Any]] = []
    fichiers = sorted(
        (p for p in dossier.glob("*.json") if not p.name.startswith("_")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for chemin in fichiers[:limit]:
        data = lire_json(chemin, None)
        if isinstance(data, dict):
            items.append(resume(slug, kind, chemin, data))
    return items


def _resume_devis(slug: str, kind: str, chemin: Path, data: dict) -> dict[str, Any]:
    demande = data.get("demande", {}) or {}
    totaux = data.get("totaux", {}) or {}
    return {
        "id": data.get("id_devis", chemin.stem),
        "date": data.get("date_creation", ""),
        "chantier": demande.get("type_chantier", ""),
        "ville": demande.get("ville") or "à préciser",
        "total_ttc": totaux.get("total_ttc", 0),
        "statut": data.get("statut", ""),
        "exports": _exports_noms(slug, kind, chemin),
    }


def _resume_facture(slug: str, kind: str, chemin: Path, data: dict) -> dict[str, Any]:
    totaux = data.get("totaux", {}) or {}
    return {
        "id": data.get("id_facture", chemin.stem),
        "devis": data.get("id_devis", ""),
        "date": data.get("date_creation", ""),
        "type": data.get("type_facture", ""),
        "total_ttc": totaux.get("total_ttc", 0),
        "exports": _exports_noms(slug, kind, chemin),
    }


def _doc_url(slug: str, kind: str, name: str) -> str:
    return f"/api/v1/documents/{kind}/{name}"


def _exports(slug: str, kind: str, paths: dict) -> dict[str, str]:
    """URLs de téléchargement d'un document fraîchement généré (PDF → repli HTML)."""
    out: dict[str, str] = {}
    for cle in ("json", "markdown", "html", "pdf"):
        if paths.get(cle):
            out[cle] = _doc_url(slug, kind, paths[cle].name)
    if "pdf" not in out and "html" in out:
        out["pdf"] = out["html"]  # repli : le HTML s'imprime en PDF côté navigateur
    return out


def _exports_noms(slug: str, kind: str, chemin: Path) -> dict[str, str]:
    """URLs de téléchargement déduites du JSON (mêmes noms, autres extensions)."""
    out = {"json": _doc_url(slug, kind, chemin.name)}
    for ext in ("md", "html", "pdf"):
        frere = chemin.with_suffix("." + ext)
        if frere.exists():
            out["markdown" if ext == "md" else ext] = _doc_url(slug, kind, frere.name)
    if "pdf" not in out and "html" in out:
        out["pdf"] = out["html"]
    return out
