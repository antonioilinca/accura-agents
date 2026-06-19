"""API REST de la plateforme artisan Accura — le back que le site de Younès appellera.

    python -m agents.platform.run            # local : http://127.0.0.1:8790
    python -m agents.platform.run --port 9000

Deux niveaux d'accès :
- **Clé de service** (en-tête `X-Accura-Service-Key`) : pour créer un compte après un
  paiement. À garder CÔTÉ SERVEUR du site (jamais dans le navigateur).
- **Jeton de session** (en-tête `Authorization: Bearer <jeton>`) : pour toutes les
  actions de l'artisan connecté. Obtenu via `POST /api/v1/auth/login`.

Tout est en bibliothèque standard (http.server). Sortie JSON. CORS configurable via
`ACCURA_PLATFORM_ALLOWED_ORIGIN` si le site appelle l'API depuis le navigateur.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

from agents.common.native_libs import assurer_libs_pdf
from . import api, auth

RACINE = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"

_DOC_RE = re.compile(r"^/api/v1/documents/([a-z]+)/([A-Za-z0-9._-]+)$")


class PlatformHandler(BaseHTTPRequestHandler):
    server_version = "AccuraPlatform/1.0"

    # -- utilitaires réponse ------------------------------------------------------------
    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self) -> None:
        origine = (os.environ.get("ACCURA_PLATFORM_ALLOWED_ORIGIN") or "").strip()
        if origine:
            self.send_header("Access-Control-Allow-Origin", origine)
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Accura-Service-Key")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
            self.send_header("Vary", "Origin")

    def _error(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status=status)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise api.PlatformError("Corps JSON invalide.")
        return data if isinstance(data, dict) else {}

    def _slug_from_bearer(self) -> str:
        header = self.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else ""
        slug = auth.verify_token(RACINE, token) if token else None
        if not slug:
            raise api.AuthError("Jeton de session manquant ou invalide.")
        return slug

    def _require_service_key(self) -> None:
        if not auth.verify_service_key(RACINE, self.headers.get("X-Accura-Service-Key")):
            raise api.AuthError("Clé de service invalide.")

    # -- routage ------------------------------------------------------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802 (préflight CORS)
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        try:
            path = self.path.split("?", 1)[0]
            if path == "/api/v1/health" or path == "/healthz":
                self._send_json({"ok": True, "service": "accura-platform"})
                return

            # Page de démonstration de l'espace artisan (publique ; les données restent
            # protégées par jeton derrière l'API). Sert de modèle d'UI à relier au site.
            if path in ("/", "/espace", "/espace/"):
                page = (STATIC / "espace.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self._cors()
                self.end_headers()
                self.wfile.write(page)
                return

            doc = _DOC_RE.match(path)
            if doc:
                slug = self._slug_from_bearer()
                chemin = api.document_path(RACINE, slug, doc.group(1), doc.group(2))
                self._send_file(chemin)
                return

            slug = self._slug_from_bearer()
            if path == "/api/v1/me":
                self._send_json(api.account_overview(RACINE, slug)); return
            if path == "/api/v1/profile":
                self._send_json(api.get_profile(RACINE, slug)); return
            if path == "/api/v1/devis":
                self._send_json(api.list_quotes(RACINE, slug)); return
            if path == "/api/v1/factures":
                self._send_json(api.list_invoices(RACINE, slug)); return
            if path == "/api/v1/crm":
                self._send_json(api.crm_pipeline(RACINE, slug)); return
            if path == "/api/v1/leads":
                self._send_json(api.list_leads(RACINE, slug)); return
            self._error("Route inconnue.", 404)
        except api.PlatformError as exc:
            self._error(str(exc), exc.status)
        except Exception as exc:  # ne jamais tuer le serveur sur une requête
            self._error(f"Erreur interne : {exc}", 500)

    def do_PUT(self) -> None:  # noqa: N802
        try:
            slug = self._slug_from_bearer()
            if self.path.split("?", 1)[0] == "/api/v1/profile":
                self._send_json(api.update_profile(RACINE, slug, self._body())); return
            self._error("Route inconnue.", 404)
        except api.PlatformError as exc:
            self._error(str(exc), exc.status)
        except Exception as exc:
            self._error(f"Erreur interne : {exc}", 500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = self.path.split("?", 1)[0]

            # Provisioning : réservé au site (clé de service), pas de jeton.
            if path == "/api/v1/accounts":
                self._require_service_key()
                self._send_json(api.provision_account(RACINE, self._body()), status=201)
                return

            # Connexion : public (identifiant + mot de passe).
            if path == "/api/v1/auth/login":
                data = self._body()
                token = api.authenticate(RACINE, data.get("login", ""), data.get("password", ""))
                self._send_json({"token": token, "account": api.account_overview(
                    RACINE, auth.verify_token(RACINE, token))})
                return

            # Le reste exige un jeton d'artisan.
            slug = self._slug_from_bearer()
            data = self._body()
            if path == "/api/v1/devis":
                self._send_json(api.create_quote(RACINE, slug, data.get("text", ""),
                                                 quote_id=data.get("id")), status=201); return
            if path == "/api/v1/factures":
                self._send_json(api.create_invoice(RACINE, slug, data.get("quote_id", ""),
                                                   data.get("type", "acompte")), status=201); return
            if path == "/api/v1/relances":
                self._send_json(api.create_followups(RACINE, slug, data.get("quote_id", "")), status=201); return
            if path == "/api/v1/avis":
                self._send_json(api.create_review(RACINE, slug, data.get("client", ""),
                                                  data.get("chantier", "")), status=201); return
            if path == "/api/v1/crm":
                self._send_json(api.crm_update(RACINE, slug, data.get("quote_id", ""),
                                               data.get("status", ""), data.get("next_action", ""))); return
            if path == "/api/v1/account/password":
                api.set_password(RACINE, slug, data.get("password", ""))
                self._send_json({"ok": True}); return
            self._error("Route inconnue.", 404)
        except api.PlatformError as exc:
            self._error(str(exc), exc.status)
        except Exception as exc:
            self._error(f"Erreur interne : {exc}", 500)

    def _send_file(self, chemin: Path) -> None:
        import mimetypes
        data = chemin.read_bytes()
        ctype = mimetypes.guess_type(str(chemin))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'inline; filename="{chemin.name}"')
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(f"[platform] {self.address_string()} - {format % args}")


def main() -> None:
    assurer_libs_pdf()  # PDF natif en local ; no-op en prod Docker
    load_dotenv(RACINE / ".env")
    parser = argparse.ArgumentParser(description="API plateforme artisan Accura Ouest")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()

    port = int(os.environ.get("PORT") or args.port)
    host = os.environ.get("HOST") or ("0.0.0.0" if os.environ.get("PORT") else args.host)

    # Force la création des secrets au démarrage (et les affiche une fois en local).
    auth.session_secret(RACINE)
    cle = auth.service_api_key(RACINE)

    try:
        server = ThreadingHTTPServer((host, port), PlatformHandler)
    except OSError:
        print(f"Le port {port} est déjà utilisé. Relancez avec --port {port + 1}.")
        raise SystemExit(1)
    print(f"API plateforme Accura : http://{host}:{port}/api/v1")
    print(f"Clé de service (pour le site, à garder secrète) : {cle}")
    print("Ctrl+C pour arrêter.")
    server.serve_forever()


if __name__ == "__main__":
    main()
