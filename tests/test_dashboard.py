from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.dashboard.run import _examples, _generate_followups, _generate_invoice, _generate_quote
from agents.dashboard.onboarding import DEFAULT_PROFILE, build_devis_yaml
from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import ecrire_exports


ROOT = Path(__file__).resolve().parents[1]


class DashboardTest(unittest.TestCase):
    def test_dashboard_charge_les_exemples(self) -> None:
        examples = _examples()

        self.assertGreaterEqual(len(examples), 5)
        self.assertIn("text", examples[0])

    def test_dashboard_genere_un_devis_api(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
            payload = _generate_quote(
                "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
                quote_id="TEST-DASHBOARD",
            )

        self.assertEqual(payload["id_devis"], "TEST-DASHBOARD")
        self.assertGreater(payload["totaux"]["total_ttc"], 0)
        self.assertIn("html", payload["exports"])
        json.dumps(payload, ensure_ascii=False)

    def test_onboarding_payload_can_generate_devis_yaml(self) -> None:
        data = build_devis_yaml(DEFAULT_PROFILE)

        self.assertIn("artisan", data)
        self.assertIn("metiers", data)
        self.assertIn(DEFAULT_PROFILE["business"]["main_trade"], data["metiers"])

    def test_dashboard_genere_facture_depuis_devis(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-DASH-INVOICE",
            utiliser_ia=False,
        )
        ecrire_exports(doc, ROOT / "outputs" / "devis")

        payload = _generate_invoice("TEST-DASH-INVOICE", invoice_type="acompte")

        self.assertEqual(payload["id_devis"], "TEST-DASH-INVOICE")
        self.assertEqual(payload["type_facture"], "acompte")
        self.assertGreater(payload["totaux"]["total_ttc"], 0)
        self.assertIn("html", payload["exports"])
        json.dumps(payload, ensure_ascii=False)

    def test_dashboard_genere_relances_depuis_devis(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-DASH-FOLLOWUP",
            utiliser_ia=False,
        )
        ecrire_exports(doc, ROOT / "outputs" / "devis")

        payload = _generate_followups("TEST-DASH-FOLLOWUP")

        self.assertEqual(payload["id_devis"], "TEST-DASH-FOLLOWUP")
        self.assertEqual([m["jour"] for m in payload["messages"]], [3, 7, 15])
        self.assertIn("json", payload["exports"])
        json.dumps(payload, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
