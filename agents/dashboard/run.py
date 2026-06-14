"""Dashboard local Accura Ouest.

    python -m agents.dashboard.run
    python -m agents.dashboard.run --port 8787
"""

from __future__ import annotations

import argparse
import base64
from email.parser import BytesParser
from email.policy import default
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv

from agents.avis_generator.generator import generer_demande_avis
from agents.avis_generator.render import ecrire_exports as ecrire_exports_avis
from agents.crm_tracker.pipeline import build_pipeline, update_item
from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import ecrire_exports
from agents.facture_generator.generator import generer_facture_depuis_devis
from agents.facture_generator.render import ecrire_exports as ecrire_exports_facture
from agents.relance_generator.generator import generer_relances_depuis_devis
from agents.relance_generator.render import ecrire_exports as ecrire_exports_relance
from agents.dashboard.onboarding import PLANS, apply_profile_to_devis_config, load_profile, save_logo_asset, save_profile
from agents.dashboard import activity, clients, cockpit

RACINE = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"


def _workspace() -> Path:
    """Dossier de travail courant : espace du client actif, sinon RACINE/outputs.

    Tant qu'aucun client n'est sélectionné, ``clients.active_workspace`` renvoie
    ``RACINE/"outputs"`` : toutes les sorties retombent à l'identique sur le
    comportement mono-artisan d'origine (rétrocompatibilité garantie). RACINE est
    lue dynamiquement (les tests la patchent via patch.object).
    """
    return clients.active_workspace(RACINE)


def _profile_base() -> Path | None:
    """Base onboarding : workspace du client actif, sinon None (profil mono-artisan)."""
    return _workspace() if clients.get_active(RACINE) else None


def _active_client_payload() -> dict | None:
    """Fiche du client actif (ou None) pour le front : sert à afficher « Client actif »."""
    slug = clients.get_active(RACINE)
    if not slug:
        return None
    return clients.get_client(RACINE, slug)


def _url_for(chemin: Path) -> str:
    """Transforme un chemin de fichier sous RACINE en URL servie (/outputs/...).

    Un fichier dans ``outputs/clients/<slug>/devis/x.pdf`` devient
    ``/outputs/clients/<slug>/devis/x.pdf`` : l'URL reste sous /outputs/ et passe
    donc par ``_safe_output_path``. Si le chemin sort de RACINE (ne devrait pas
    arriver), on retombe sur l'ancien préfixe pour ne jamais casser un lien.
    """
    try:
        return "/" + chemin.resolve().relative_to(RACINE.resolve()).as_posix()
    except ValueError:
        return "/outputs/" + chemin.name


def _dashboard_password() -> str | None:
    """Mot de passe d'accès. Si absent, le dashboard reste ouvert (mode local)."""
    pw = (os.environ.get("ACCURA_DASHBOARD_PASSWORD") or "").strip()
    return pw or None


def _dashboard_user() -> str:
    return (os.environ.get("ACCURA_DASHBOARD_USER") or "accura").strip()


def _config_devis() -> Path:
    # Client actif avec sa propre config devis (générée via l'onboarding du client).
    base = _profile_base()
    if base is not None:
        client_cfg = base / "devis.config.yaml"
        if client_cfg.exists():
            return client_cfg
    # Mode mono-artisan historique : config locale puis exemple versionné.
    locale = RACINE / "config" / "devis.yaml"
    if locale.exists():
        return locale
    return RACINE / "config" / "devis.example.yaml"


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _text_response(handler: BaseHTTPRequestHandler, body: bytes, content_type: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _safe_output_path(path: str) -> Path | None:
    requested = (RACINE / unquote(path.lstrip("/"))).resolve()
    outputs = (RACINE / "outputs").resolve()
    if outputs not in requested.parents and requested != outputs:
        return None
    if not requested.exists() or not requested.is_file():
        return None
    return requested


def _examples() -> list[dict]:
    dossier = RACINE / "examples" / "devis" / "requests"
    items = []
    for chemin in sorted(dossier.glob("*.txt")):
        items.append({
            "id": chemin.stem,
            "label": chemin.stem.replace("_", " ").capitalize(),
            "text": chemin.read_text(encoding="utf-8").strip(),
        })
    return items


def _recent_quotes(limit: int = 8) -> list[dict]:
    dossier = _workspace() / "devis"
    if not dossier.exists():
        return []
    quotes = []
    for chemin in sorted(dossier.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        demande = data.get("demande", {}) or {}
        totaux = data.get("totaux", {}) or {}
        quotes.append({
            "id": data.get("id_devis", chemin.stem),
            "date": data.get("date_creation", ""),
            "metier": demande.get("metier_libelle", ""),
            "chantier": demande.get("type_chantier", ""),
            "ville": demande.get("ville") or "à préciser",
            "total_ttc": totaux.get("total_ttc", 0),
            "questions": len(demande.get("questions", []) or []),
            "html": _url_for(chemin.with_suffix(".html")),
            "json": _url_for(chemin),
            "markdown": _url_for(chemin.with_suffix(".md")),
        })
        if len(quotes) >= limit:
            break
    return quotes


def _quote_json_path(quote_id: str) -> Path | None:
    dossier = _workspace() / "devis"
    if not dossier.exists():
        return None
    expected = quote_id.lower()
    for chemin in dossier.glob("*.json"):
        try:
            data = json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if str(data.get("id_devis", "")).lower() == expected or chemin.stem.lower() == expected:
            return chemin
    return None


def _recent_invoices(limit: int = 8) -> list[dict]:
    dossier = _workspace() / "factures"
    if not dossier.exists():
        return []
    invoices = []
    for chemin in sorted(dossier.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        totaux = data.get("totaux", {}) or {}
        invoices.append({
            "id": data.get("id_facture", chemin.stem),
            "quote_id": data.get("id_devis", ""),
            "date": data.get("date_creation", ""),
            "type": data.get("type_facture", ""),
            "client": data.get("client_nom", ""),
            "total_ttc": totaux.get("total_ttc", 0),
            "html": _url_for(chemin.with_suffix(".html")),
            "json": _url_for(chemin),
            "markdown": _url_for(chemin.with_suffix(".md")),
        })
        if len(invoices) >= limit:
            break
    return invoices


def _recent_followups(limit: int = 8) -> list[dict]:
    dossier = _workspace() / "relances"
    if not dossier.exists():
        return []
    plans = []
    for chemin in sorted(dossier.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        messages = data.get("messages", []) or []
        plans.append({
            "quote_id": data.get("id_devis", ""),
            "client": data.get("client", ""),
            "chantier": data.get("chantier", ""),
            "messages_count": len(messages),
            "next_date": messages[0].get("date_prevue", "") if messages else "",
            "json": _url_for(chemin),
        })
        if len(plans) >= limit:
            break
    return plans


def _recent_leads(limit: int = 8) -> list[dict]:
    leads = []
    for chemin in sorted(_workspace().glob("leads-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for lead in data.get("leads", []) or []:
            leads.append({
                "score": lead.get("score"),
                "commune": lead.get("commune") or "commune ?",
                "metier": lead.get("metier") or "",
                "prochaine_action": lead.get("prochaine_action") or "à contacter",
                "source": lead.get("source") or "",
            })
            if len(leads) >= limit:
                return leads
    return leads


def _generate_quote(text: str, quote_id: str | None = None) -> dict:
    cfg = charger_config(_config_devis())
    # Sortie recontextualisée : espace du client actif, sinon outputs/devis (rétrocompat).
    dossier = _workspace() / "devis"
    doc = generer_devis(text, cfg, id_devis=quote_id, dossier=dossier)
    # Un id saisi par l'artisan est une ré-édition volontaire du même devis.
    paths = ecrire_exports(doc, dossier, ecraser=bool(quote_id))
    payload = doc.to_dict()
    payload["exports"] = _exports_for(paths)
    return payload


def _generate_invoice(quote_id: str, invoice_type: str = "acompte") -> dict:
    chemin = _quote_json_path(quote_id)
    if not chemin:
        raise FileNotFoundError(f"Devis introuvable : {quote_id}")
    devis = json.loads(chemin.read_text(encoding="utf-8"))
    dossier = _workspace() / "factures"
    doc = generer_facture_depuis_devis(devis, type_facture=invoice_type, dossier=dossier)
    paths = ecrire_exports_facture(doc, dossier)
    payload = doc.to_dict()
    payload["exports"] = _exports_for(paths)
    return payload


def _generate_followups(quote_id: str) -> dict:
    chemin = _quote_json_path(quote_id)
    if not chemin:
        raise FileNotFoundError(f"Devis introuvable : {quote_id}")
    devis = json.loads(chemin.read_text(encoding="utf-8"))
    plan = generer_relances_depuis_devis(devis)
    paths = ecrire_exports_relance(plan, _workspace() / "relances")
    payload = plan.to_dict()
    payload["exports"] = {"json": _url_for(paths["json"])}
    return payload


def _crm_pipeline() -> dict:
    # Le CRM ancre lui-même sur "outputs" : on lui passe RACINE + la base client
    # éventuelle (et non _workspace(), pour ne pas doubler le segment outputs).
    return build_pipeline(RACINE, base=_profile_base())


def _update_crm(quote_id: str, status: str, next_action: str = "") -> dict:
    update_item(RACINE, quote_id, status, next_action, base=_profile_base())
    return _crm_pipeline()


def _generate_review_request(client: str = "", chantier: str = "") -> dict:
    request = generer_demande_avis(load_profile(RACINE, base=_profile_base()), client=client, chantier=chantier)
    paths = ecrire_exports_avis(request, _workspace() / "avis")
    payload = request.to_dict()
    payload["exports"] = {"json": _url_for(paths["json"])}
    return payload


def _exports_for(paths: dict) -> dict:
    """Exports (URLs) d'un document généré : json, markdown, html, pdf (fallback html)."""
    return {
        "json": _url_for(paths["json"]),
        "markdown": _url_for(paths["markdown"]),
        "html": _url_for(paths["html"]),
        "pdf": _url_for(paths["pdf"]) if paths.get("pdf") else _url_for(paths["html"]),
    }


def _extract_multipart_file(headers, body: bytes, field_name: str) -> tuple[str, bytes]:
    content_type = headers.get("Content-Type", "")
    if not content_type.startswith("multipart/form-data"):
        raise ValueError("Upload invalide")

    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if name != field_name:
            continue
        filename = part.get_filename() or "logo"
        content = part.get_payload(decode=True) or b""
        return filename, content
    raise ValueError("Fichier logo manquant")


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AccuraDashboard/0.1"

    def _authorized(self) -> bool:
        """Mot de passe (Basic Auth) si ACCURA_DASHBOARD_PASSWORD est défini.

        En local sans mot de passe, l'accès reste libre. En ligne (tunnel), le mot
        de passe est obligatoire : on ne sert jamais de page ni d'API sans lui.
        """
        password = _dashboard_password()
        if not password:
            return True
        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                user, _, given = base64.b64decode(header[6:]).decode("utf-8").partition(":")
                if user == _dashboard_user() and given == password:
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Accura Ouest"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def do_HEAD(self) -> None:  # noqa: N802
        if not self._authorized():
            return
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":  # sonde de santé de l'hébergeur, sans authentification
            _text_response(self, b"ok", "text/plain; charset=utf-8")
            return
        if not self._authorized():
            return
        if self.path == "/" or self.path.startswith("/?"):
            _text_response(self, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if self.path == "/api/bootstrap":
            _json_response(self, {
                "examples": _examples(),
                "recent_quotes": _recent_quotes(),
                "recent_invoices": _recent_invoices(),
                "recent_followups": _recent_followups(),
                "recent_leads": _recent_leads(),
                "crm": _crm_pipeline(),
                "onboarding": load_profile(RACINE, base=_profile_base()),
                "plans": PLANS,
                "agents": cockpit.catalog_public(),
                "activity": {"agents": activity.agent_states(), "runs": activity.snapshot()},
                "clients": clients.list_clients(RACINE),
                "active_client": _active_client_payload(),
            })
            return
        if self.path == "/api/onboarding":
            _json_response(self, {"profile": load_profile(RACINE, base=_profile_base()), "plans": PLANS})
            return
        if self.path == "/api/clients":
            _json_response(self, {"clients": clients.list_clients(RACINE), "active": clients.get_active(RACINE)})
            return
        if self.path == "/api/agents/activity":
            _json_response(self, {"agents": activity.agent_states(), "runs": activity.snapshot()})
            return
        if self.path.startswith("/static/"):
            chemin = (STATIC / self.path.removeprefix("/static/")).resolve()
            if STATIC.resolve() in chemin.parents and chemin.exists():
                content_type = mimetypes.guess_type(str(chemin))[0] or "application/octet-stream"
                _text_response(self, chemin.read_bytes(), content_type)
                return
        if self.path.startswith("/outputs/"):
            chemin = _safe_output_path(self.path)
            if chemin:
                content_type = mimetypes.guess_type(str(chemin))[0] or "application/octet-stream"
                _text_response(self, chemin.read_bytes(), content_type)
                return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            return
        if self.path == "/api/devis":
            self._handle_devis()
            return
        if self.path == "/api/factures":
            self._handle_factures()
            return
        if self.path == "/api/relances":
            self._handle_relances()
            return
        if self.path == "/api/crm":
            self._handle_crm()
            return
        if self.path == "/api/avis-google":
            self._handle_avis_google()
            return
        if self.path == "/api/onboarding":
            self._handle_onboarding(apply_config=False)
            return
        if self.path == "/api/onboarding/apply":
            self._handle_onboarding(apply_config=True)
            return
        if self.path == "/api/onboarding/logo":
            self._handle_logo_upload()
            return
        if self.path == "/api/clients":
            self._handle_create_client()
            return
        if self.path == "/api/clients/active":
            self._handle_set_active_client()
            return
        if self.path == "/api/clients/status":
            self._handle_client_status()
            return
        if self.path == "/api/agents/run":
            self._handle_agent_run()
            return
        self.send_error(404)

    def _handle_agent_run(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            agent = str(data.get("agent", "")).strip()
            run_id = cockpit.start_run(agent)
            _json_response(self, {"run_id": run_id})
        except KeyError:
            _json_response(self, {"error": "Agent inconnu"}, status=400)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_devis(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            text = str(data.get("text", "")).strip()
            quote_id = str(data.get("id", "")).strip() or None
            if not text:
                _json_response(self, {"error": "Demande vide"}, status=400)
                return
            _json_response(self, _generate_quote(text, quote_id=quote_id))
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_factures(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            quote_id = str(data.get("quote_id", "")).strip()
            invoice_type = str(data.get("type", "acompte")).strip() or "acompte"
            if not quote_id:
                _json_response(self, {"error": "Devis source manquant"}, status=400)
                return
            _json_response(self, _generate_invoice(quote_id, invoice_type=invoice_type))
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_relances(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            quote_id = str(data.get("quote_id", "")).strip()
            if not quote_id:
                _json_response(self, {"error": "Devis source manquant"}, status=400)
                return
            _json_response(self, _generate_followups(quote_id))
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_crm(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            quote_id = str(data.get("quote_id", "")).strip()
            status = str(data.get("status", "")).strip()
            next_action = str(data.get("next_action", "")).strip()
            _json_response(self, _update_crm(quote_id, status, next_action))
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=400)

    def _handle_avis_google(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            client = str(data.get("client", "")).strip()
            chantier = str(data.get("chantier", "")).strip()
            _json_response(self, _generate_review_request(client=client, chantier=chantier))
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_onboarding(self, apply_config: bool) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            profile = data.get("profile") or data
            # Onboarding du client actif ciblé dans son espace, sinon profil mono-artisan.
            base = _profile_base()
            from agents.dashboard.onboarding import profile_path  # chemin exact (mono ou client)
            saved = save_profile(RACINE, profile, base=base)
            result = {"profile": saved, "paths": {"profile": str(profile_path(RACINE, base))}}
            if apply_config:
                result["paths"] = apply_profile_to_devis_config(RACINE, saved, base=base)
            _json_response(self, result)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_logo_upload(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            base = _profile_base()
            filename, content = _extract_multipart_file(self.headers, self.rfile.read(length), "logo")
            logo = save_logo_asset(RACINE, filename, content, base=base)
            profile = load_profile(RACINE, base=base)
            profile["assets"] = {**(profile.get("assets") or {}), **logo}
            saved = save_profile(RACINE, profile, base=base)
            _json_response(self, {"profile": saved, "logo": logo})
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=400)

    def _handle_create_client(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "Corps JSON invalide"}, status=400)
            return
        try:
            fiche = clients.create_client(RACINE, data if isinstance(data, dict) else {})
            _json_response(self, {"client": fiche}, status=201)
        except ValueError as exc:  # nom manquant, etc. → faute du client
            _json_response(self, {"error": str(exc)}, status=400)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_set_active_client(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "Corps JSON invalide"}, status=400)
            return
        try:
            slug = (data or {}).get("slug")  # {slug: null} ou absent => aucun client actif
            active = clients.set_active(RACINE, slug)
            _json_response(self, {"active": active})
        except ValueError as exc:  # client introuvable
            _json_response(self, {"error": str(exc)}, status=400)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_client_status(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "Corps JSON invalide"}, status=400)
            return
        try:
            slug = str((data or {}).get("slug") or "").strip()
            status = str((data or {}).get("status") or "").strip()
            if not slug:
                _json_response(self, {"error": "Client manquant"}, status=400)
                return
            fiche = clients.update_client(RACINE, slug, {"status": status})
            _json_response(self, {"client": fiche})
        except ValueError as exc:  # statut invalide ou client introuvable
            _json_response(self, {"error": str(exc)}, status=400)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(f"[dashboard] {self.address_string()} - {format % args}")


def main() -> None:
    load_dotenv(RACINE / ".env")
    parser = argparse.ArgumentParser(description="Dashboard local Accura Ouest")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    # En hébergement cloud (Render, etc.), la plateforme impose le port via $PORT et
    # exige une écoute sur toutes les interfaces (0.0.0.0). En local (Mac), on reste
    # sur 127.0.0.1:8787 pour ne rien exposer en dehors de la machine.
    port = int(os.environ.get("PORT") or args.port)
    host = os.environ.get("HOST") or ("0.0.0.0" if os.environ.get("PORT") else args.host)

    try:
        server = ThreadingHTTPServer((host, port), DashboardHandler)
    except OSError:
        print(
            f"Le port {port} est déjà utilisé : le dashboard tourne sans doute déjà.\n"
            f"Ouvrez http://{host}:{port} dans le navigateur, ou relancez avec "
            f"--port {port + 1}."
        )
        raise SystemExit(1)
    print(f"Dashboard Accura Ouest : http://{host}:{port}")
    print("Ctrl+C pour arrêter.")
    server.serve_forever()


if __name__ == "__main__":
    main()
