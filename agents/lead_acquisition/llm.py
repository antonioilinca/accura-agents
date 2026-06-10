"""Couche LLM multi-fournisseur. Un seul point d'appel renvoyant une sortie structurée (dict).

Deux modes (réglés dans config.yaml -> llm.provider) :

- openai_compat : tout fournisseur compatible OpenAI via une base_url. Couvre :
    * Groq      (Llama 3.3 70B, GRATUIT)   base_url https://api.groq.com/openai/v1
    * Mistral   (européen, RGPD, gratuit)  base_url https://api.mistral.ai/v1
    * Ollama    (local, illimité, offline) base_url http://localhost:11434/v1
    * Gemini    (compat OpenAI)            base_url https://generativelanguage.googleapis.com/v1beta/openai
  Sortie forcée en JSON (response_format json_object) puis parsée.

- anthropic : API Claude (tool use forcé). Qualité maximale, payant. À activer quand un
  client paie.

Aucune nouvelle dépendance : openai_compat passe par `requests`.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests

log = logging.getLogger(__name__)

# Cadence proactive : le free tier Groq sature vite quand les appels partent en
# rafale. Un espacement minimal évite la plupart des 429 au lieu de les subir.
_dernier_appel = 0.0


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0


class LLMClient:
    def __init__(self, cfg) -> None:
        self.provider = cfg.llm_provider
        self.base_url = (cfg.llm_base_url or "").rstrip("/")
        self.api_key = os.environ.get(cfg.llm_api_key_env, "") if cfg.llm_api_key_env else ""
        self.max_retry_after_seconds = int(getattr(cfg, "llm_max_retry_after_seconds", 120))
        self.intervalle_min_s = float(getattr(cfg, "llm_intervalle_min_s", 2.5))
        self._anthropic = None
        if self.provider == "anthropic":
            import anthropic  # import paresseux
            self._anthropic = anthropic.Anthropic()

    def _respecter_cadence(self) -> None:
        global _dernier_appel
        if self.intervalle_min_s <= 0:
            return
        attente = _dernier_appel + self.intervalle_min_s - time.monotonic()
        if attente > 0:
            time.sleep(attente)
        _dernier_appel = time.monotonic()

    # -- API publique -------------------------------------------------------------------

    def structured(
        self, system: str, user: str, schema: dict, nom_schema: str,
        model: str, max_tokens: int, cache: bool = False,
    ) -> tuple[dict | None, Usage]:
        """Renvoie (objet validé | None, usage). Lève en cas d'échec réseau/API."""
        if self.provider == "anthropic":
            return self._appel_anthropic(system, user, schema, nom_schema, model, max_tokens, cache)
        return self._appel_openai_compat(system, user, schema, model, max_tokens)

    # -- Backends -----------------------------------------------------------------------

    def _appel_anthropic(self, system, user, schema, nom, model, max_tokens, cache):
        blocs = [{"type": "text", "text": system}]
        if cache:
            blocs[0]["cache_control"] = {"type": "ephemeral"}
        tool = {"name": nom, "description": f"Renvoie le résultat structuré ({nom}).",
                "input_schema": schema}
        resp = self._anthropic.messages.create(
            model=model, max_tokens=max_tokens, system=blocs,
            tools=[tool], tool_choice={"type": "tool", "name": nom},
            messages=[{"role": "user", "content": user}],
        )
        u = resp.usage
        usage = Usage(
            getattr(u, "input_tokens", 0) or 0,
            getattr(u, "output_tokens", 0) or 0,
            getattr(u, "cache_read_input_tokens", 0) or 0,
            getattr(u, "cache_creation_input_tokens", 0) or 0,
        )
        for bloc in resp.content:
            if bloc.type == "tool_use" and bloc.name == nom:
                return bloc.input, usage
        return None, usage

    def _appel_openai_compat(self, system, user, schema, model, max_tokens):
        instruction = (
            "\n\nRéponds UNIQUEMENT par un objet JSON valide (aucun texte autour, pas de "
            "balise markdown) respectant exactement ce schéma JSON :\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system + instruction},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = self.base_url + "/chat/completions"

        derniere_erreur: Exception | None = None
        for tentative in range(4):
            self._respecter_cadence()
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=90)
            except requests.RequestException as exc:
                # Panne transitoire (SSL, timeout, connexion) : on retente, le lead
                # ne doit pas être jeté pour un hoquet réseau.
                derniere_erreur = exc
                attente = 2.0 ** tentative
                log.warning(
                    "erreur réseau (%s), nouvel essai dans %.0fs",
                    exc.__class__.__name__, attente,
                )
                time.sleep(attente)
                continue
            if r.status_code == 429:  # rate limit : on respecte Retry-After
                attente = _parse_retry_after(r.headers.get("retry-after")) + 0.5
                if attente > self.max_retry_after_seconds:
                    raise requests.HTTPError(
                        f"rate limit trop long ({attente:.1f}s > "
                        f"{self.max_retry_after_seconds}s)"
                    )
                log.info("rate limit, attente %.1fs", attente)
                time.sleep(min(attente, 30))
                continue
            if r.status_code in (500, 502, 503, 504, 529):
                derniere_erreur = requests.HTTPError(f"HTTP {r.status_code} côté fournisseur")
                attente = 2.0 ** tentative
                log.warning("erreur serveur %s, nouvel essai dans %.0fs", r.status_code, attente)
                time.sleep(attente)
                continue
            r.raise_for_status()
            break
        else:
            raise derniere_erreur or requests.HTTPError("échec persistant après 4 tentatives")

        corps = r.json()
        message = corps["choices"][0]["message"].get("content") or ""
        u = corps.get("usage") or {}
        usage = Usage(int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)))
        return _parse_json(message), usage


def _parse_retry_after(valeur: str | None) -> float:
    """Retry-After peut être un nombre de secondes OU une date HTTP (RFC 7231)."""
    if not valeur:
        return 3.0
    try:
        return max(0.0, float(valeur))
    except (TypeError, ValueError):
        pass
    try:
        dt = parsedate_to_datetime(str(valeur))
        return max(0.0, (dt - datetime.now(dt.tzinfo)).total_seconds())
    except (TypeError, ValueError):
        return 3.0


def _parse_json(texte: str) -> dict | None:
    texte = texte.strip()
    if texte.startswith("```"):
        texte = texte.strip("`")
        texte = texte[texte.find("{"):] if "{" in texte else texte
    try:
        return json.loads(texte)
    except json.JSONDecodeError:
        debut, fin = texte.find("{"), texte.rfind("}")
        if 0 <= debut < fin:
            try:
                return json.loads(texte[debut : fin + 1])
            except json.JSONDecodeError:
                return None
        return None
