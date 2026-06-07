"""Dashboard local Accura Ouest.

    python -m agents.dashboard.run
    python -m agents.dashboard.run --port 8787
"""

from __future__ import annotations

import argparse
from email.parser import BytesParser
from email.policy import default
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv

from agents.crm_tracker.pipeline import build_pipeline, update_item
from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import ecrire_exports
from agents.facture_generator.generator import generer_facture_depuis_devis
from agents.facture_generator.render import ecrire_exports as ecrire_exports_facture
from agents.relance_generator.generator import generer_relances_depuis_devis
from agents.relance_generator.render import ecrire_exports as ecrire_exports_relance
from agents.dashboard.onboarding import PLANS, apply_profile_to_devis_config, load_profile, save_logo_asset, save_profile

RACINE = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"


def _config_devis() -> Path:
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
    dossier = RACINE / "outputs" / "devis"
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
            "html": f"/outputs/devis/{chemin.with_suffix('.html').name}",
            "json": f"/outputs/devis/{chemin.name}",
            "markdown": f"/outputs/devis/{chemin.with_suffix('.md').name}",
        })
        if len(quotes) >= limit:
            break
    return quotes


def _quote_json_path(quote_id: str) -> Path | None:
    dossier = RACINE / "outputs" / "devis"
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
    dossier = RACINE / "outputs" / "factures"
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
            "html": f"/outputs/factures/{chemin.with_suffix('.html').name}",
            "json": f"/outputs/factures/{chemin.name}",
            "markdown": f"/outputs/factures/{chemin.with_suffix('.md').name}",
        })
        if len(invoices) >= limit:
            break
    return invoices


def _recent_followups(limit: int = 8) -> list[dict]:
    dossier = RACINE / "outputs" / "relances"
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
            "json": f"/outputs/relances/{chemin.name}",
        })
        if len(plans) >= limit:
            break
    return plans


def _recent_leads(limit: int = 8) -> list[dict]:
    leads = []
    for chemin in sorted((RACINE / "outputs").glob("leads-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
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
    doc = generer_devis(text, cfg, id_devis=quote_id)
    paths = ecrire_exports(doc, RACINE / cfg.dossier_sortie)
    payload = doc.to_dict()
    payload["exports"] = {
        "json": f"/outputs/devis/{paths['json'].name}",
        "markdown": f"/outputs/devis/{paths['markdown'].name}",
        "html": f"/outputs/devis/{paths['html'].name}",
        "pdf": f"/outputs/devis/{paths['html'].name}",
    }
    return payload


def _generate_invoice(quote_id: str, invoice_type: str = "acompte") -> dict:
    chemin = _quote_json_path(quote_id)
    if not chemin:
        raise FileNotFoundError(f"Devis introuvable : {quote_id}")
    devis = json.loads(chemin.read_text(encoding="utf-8"))
    doc = generer_facture_depuis_devis(devis, type_facture=invoice_type)
    paths = ecrire_exports_facture(doc, RACINE / "outputs" / "factures")
    payload = doc.to_dict()
    payload["exports"] = {
        "json": f"/outputs/factures/{paths['json'].name}",
        "markdown": f"/outputs/factures/{paths['markdown'].name}",
        "html": f"/outputs/factures/{paths['html'].name}",
        "pdf": f"/outputs/factures/{paths['html'].name}",
    }
    return payload


def _generate_followups(quote_id: str) -> dict:
    chemin = _quote_json_path(quote_id)
    if not chemin:
        raise FileNotFoundError(f"Devis introuvable : {quote_id}")
    devis = json.loads(chemin.read_text(encoding="utf-8"))
    plan = generer_relances_depuis_devis(devis)
    paths = ecrire_exports_relance(plan, RACINE / "outputs" / "relances")
    payload = plan.to_dict()
    payload["exports"] = {"json": f"/outputs/relances/{paths['json'].name}"}
    return payload


def _crm_pipeline() -> dict:
    return build_pipeline(RACINE)


def _update_crm(quote_id: str, status: str, next_action: str = "") -> dict:
    update_item(RACINE, quote_id, status, next_action)
    return _crm_pipeline()


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

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self) -> None:  # noqa: N802
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
                "onboarding": load_profile(RACINE),
                "plans": PLANS,
            })
            return
        if self.path == "/api/onboarding":
            _json_response(self, {"profile": load_profile(RACINE), "plans": PLANS})
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
        if self.path == "/api/onboarding":
            self._handle_onboarding(apply_config=False)
            return
        if self.path == "/api/onboarding/apply":
            self._handle_onboarding(apply_config=True)
            return
        if self.path == "/api/onboarding/logo":
            self._handle_logo_upload()
            return
        self.send_error(404)

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

    def _handle_onboarding(self, apply_config: bool) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            profile = data.get("profile") or data
            saved = save_profile(RACINE, profile)
            result = {"profile": saved, "paths": {"profile": str((RACINE / "outputs" / "onboarding" / "artisan_profile.json"))}}
            if apply_config:
                result["paths"] = apply_profile_to_devis_config(RACINE, saved)
            _json_response(self, result)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=500)

    def _handle_logo_upload(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            filename, content = _extract_multipart_file(self.headers, self.rfile.read(length), "logo")
            logo = save_logo_asset(RACINE, filename, content)
            profile = load_profile(RACINE)
            profile["assets"] = {**(profile.get("assets") or {}), **logo}
            saved = save_profile(RACINE, profile)
            _json_response(self, {"profile": saved, "logo": logo})
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, status=400)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(f"[dashboard] {self.address_string()} - {format % args}")


def main() -> None:
    load_dotenv(RACINE / ".env")
    parser = argparse.ArgumentParser(description="Dashboard local Accura Ouest")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard Accura Ouest : http://{args.host}:{args.port}")
    print("Ctrl+C pour arrêter.")
    server.serve_forever()


if __name__ == "__main__":
    main()
