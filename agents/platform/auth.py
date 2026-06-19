"""Sécurité de la plateforme artisan : mots de passe, jetons, clé de service.

Tout est en bibliothèque standard (aucune dépendance) :

- **Mots de passe** : jamais stockés en clair. Hachage PBKDF2-HMAC-SHA256 avec sel
  aléatoire par artisan (`hash_password` / `verify_password`).
- **Jetons de session** : signés HMAC-SHA256, sans état serveur, avec expiration
  (`issue_token` / `verify_token`). Le site n'a qu'à renvoyer le jeton à chaque appel.
- **Clé de service** : secret partagé qui autorise le site (Younès) à créer des
  comptes côté serveur après un paiement (`verify_service_key`).

Les secrets (clé de signature, clé de service) viennent d'abord des variables
d'environnement (prod / Hugging Face). À défaut, ils sont générés une fois et
persistés dans `outputs/platform/` : ainsi tout marche en local sans configuration,
et les jetons restent valides entre deux redémarrages.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

_PBKDF2_ITERATIONS = 200_000
_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 jours
_MIN_PASSWORD_LEN = 8


# ---- Secrets persistants ----------------------------------------------------------------

def _secret_store(root: Path) -> Path:
    return root / "outputs" / "platform"


def _load_or_create_secret(root: Path, nom: str, env_var: str) -> str:
    """Secret stable : variable d'environnement en priorité, sinon fichier persistant.

    Génère un secret fort au premier appel si rien n'existe. Le fichier est en
    permissions restreintes et hors Git (outputs/ est ignoré).
    """
    depuis_env = os.environ.get(env_var)
    if depuis_env and depuis_env.strip():
        return depuis_env.strip()

    store = _secret_store(root)
    store.mkdir(parents=True, exist_ok=True)
    fichier = store / nom
    if fichier.exists():
        valeur = fichier.read_text(encoding="utf-8").strip()
        if valeur:
            return valeur

    valeur = secrets.token_hex(32)
    fichier.write_text(valeur, encoding="utf-8")
    try:
        fichier.chmod(0o600)
    except OSError:
        pass
    return valeur


def session_secret(root: Path) -> str:
    """Clé de signature des jetons de session (env ACCURA_PLATFORM_SECRET sinon fichier)."""
    return _load_or_create_secret(root, "session.secret", "ACCURA_PLATFORM_SECRET")


def service_api_key(root: Path) -> str:
    """Clé de service pour le provisioning depuis le site (env ACCURA_PLATFORM_API_KEY)."""
    return _load_or_create_secret(root, "service.key", "ACCURA_PLATFORM_API_KEY")


# ---- Mots de passe ----------------------------------------------------------------------

def hash_password(password: str, *, salt: bytes | None = None) -> dict:
    """Hache un mot de passe (PBKDF2-HMAC-SHA256). Renvoie un enregistrement sérialisable."""
    if not isinstance(password, str) or len(password) < _MIN_PASSWORD_LEN:
        raise ValueError(f"Mot de passe trop court ({_MIN_PASSWORD_LEN} caractères minimum).")
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return {
        "algo": "pbkdf2_sha256",
        "iterations": _PBKDF2_ITERATIONS,
        "salt": salt.hex(),
        "hash": dk.hex(),
    }


def verify_password(password: str, record: dict) -> bool:
    """Vérifie un mot de passe contre son enregistrement, en temps constant."""
    if not isinstance(record, dict) or not isinstance(password, str) or not password:
        return False
    try:
        salt = bytes.fromhex(record["salt"])
        iterations = int(record.get("iterations", _PBKDF2_ITERATIONS))
        attendu = bytes.fromhex(record["hash"])
    except (KeyError, ValueError, TypeError):
        return False
    calcule = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(calcule, attendu)


def generate_password(longueur: int = 12) -> str:
    """Mot de passe lisible (sans caractères ambigus) à transmettre à l'artisan."""
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(max(_MIN_PASSWORD_LEN, longueur)))


# ---- Jetons de session ------------------------------------------------------------------

def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def issue_token(root: Path, slug: str, *, ttl: int = _TOKEN_TTL_SECONDS, now: int | None = None) -> str:
    """Émet un jeton de session signé pour un artisan (identifié par son slug)."""
    if not slug:
        raise ValueError("slug requis pour émettre un jeton")
    instant = int(now if now is not None else time.time())
    payload = {"slug": slug, "iat": instant, "exp": instant + int(ttl)}
    corps = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(session_secret(root).encode("utf-8"), corps.encode("ascii"), hashlib.sha256).digest()
    return f"{corps}.{_b64encode(signature)}"


def verify_token(root: Path, token: str, *, now: int | None = None) -> str | None:
    """Vérifie un jeton (signature + expiration). Renvoie le slug de l'artisan, ou None."""
    if not token or not isinstance(token, str) or "." not in token:
        return None
    corps, _, signature = token.partition(".")
    attendu = hmac.new(session_secret(root).encode("utf-8"), corps.encode("ascii"), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(_b64decode(signature), attendu):
            return None
        payload = json.loads(_b64decode(corps))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    instant = int(now if now is not None else time.time())
    if int(payload.get("exp", 0)) < instant:
        return None
    slug = str(payload.get("slug") or "").strip()
    return slug or None


def verify_service_key(root: Path, fournie: str | None) -> bool:
    """Vrai si la clé de service fournie par le site correspond (comparaison constante)."""
    if not fournie:
        return False
    return hmac.compare_digest(str(fournie), service_api_key(root))
