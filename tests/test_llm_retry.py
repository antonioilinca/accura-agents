from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

from agents.lead_acquisition.llm import LLMClient, _parse_retry_after


def _cfg() -> SimpleNamespace:
    return SimpleNamespace(
        llm_provider="openai_compat",
        llm_base_url="https://exemple.invalid/v1",
        llm_api_key_env="",
        llm_max_retry_after_seconds=120,
        llm_intervalle_min_s=0,
    )


class _Reponse:
    def __init__(self, status_code: int = 200, headers: dict | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> dict:
        return {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class LLMRetryTest(unittest.TestCase):
    """La promesse Croissance ne doit pas dépendre d'un hoquet réseau ou d'un 429.

    Cas réels du run du 09/06/2026 : erreur SSL transitoire et rafales de rate
    limit Groq ont fait jeter 7 dossiers. Ces tests verrouillent le correctif.
    """

    def _appel(self, client: LLMClient):
        return client.structured("sys", "user", {"type": "object"}, "test", "modele-test", 100)

    @patch("agents.lead_acquisition.llm.time.sleep")
    @patch("agents.lead_acquisition.llm.requests.post")
    def test_une_erreur_ssl_est_retentee(self, post, _sleep) -> None:
        post.side_effect = [requests.exceptions.SSLError("bad record mac"), _Reponse()]

        data, _ = self._appel(LLMClient(_cfg()))

        self.assertEqual(data, {"ok": True})
        self.assertEqual(post.call_count, 2)

    @patch("agents.lead_acquisition.llm.time.sleep")
    @patch("agents.lead_acquisition.llm.requests.post")
    def test_un_5xx_fournisseur_est_retente(self, post, _sleep) -> None:
        post.side_effect = [_Reponse(status_code=503), _Reponse()]

        data, _ = self._appel(LLMClient(_cfg()))

        self.assertEqual(data, {"ok": True})
        self.assertEqual(post.call_count, 2)

    @patch("agents.lead_acquisition.llm.time.sleep")
    @patch("agents.lead_acquisition.llm.requests.post")
    def test_retry_after_en_date_http_ne_crashe_pas(self, post, _sleep) -> None:
        # RFC 7231 : Retry-After peut être une date HTTP, pas seulement des secondes.
        entetes = {"retry-after": "Wed, 21 Oct 2020 07:28:00 GMT"}  # passée -> attente nulle
        post.side_effect = [_Reponse(status_code=429, headers=entetes), _Reponse()]

        data, _ = self._appel(LLMClient(_cfg()))

        self.assertEqual(data, {"ok": True})

    @patch("agents.lead_acquisition.llm.time.sleep")
    @patch("agents.lead_acquisition.llm.requests.post")
    def test_une_panne_persistante_finit_par_lever(self, post, _sleep) -> None:
        post.side_effect = requests.exceptions.ConnectionError("down")

        with self.assertRaises(requests.exceptions.ConnectionError):
            self._appel(LLMClient(_cfg()))
        self.assertEqual(post.call_count, 4)

    def test_parse_retry_after_couvre_les_trois_formats(self) -> None:
        self.assertEqual(_parse_retry_after("7"), 7.0)
        self.assertEqual(_parse_retry_after(None), 3.0)
        self.assertEqual(_parse_retry_after("n'importe quoi"), 3.0)
        self.assertGreaterEqual(_parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT"), 0.0)


if __name__ == "__main__":
    unittest.main()
