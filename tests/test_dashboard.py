from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from agents.dashboard.run import _examples, _generate_quote


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


if __name__ == "__main__":
    unittest.main()
