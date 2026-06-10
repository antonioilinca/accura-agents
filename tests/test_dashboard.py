from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from agents.dashboard import run as dashboard_run
from agents.dashboard.run import (
    _crm_pipeline,
    _examples,
    _generate_followups,
    _generate_invoice,
    _generate_quote,
    _generate_review_request,
    _update_crm,
)
from agents.dashboard.onboarding import DEFAULT_PROFILE, build_devis_yaml
from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import ecrire_exports


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _racine_isolee(quote_id: str | None = None):
    """Fait pointer le dashboard vers un dossier jetable, avec un devis prêt si demandé.

    Les tests n'écrivent plus dans le vrai outputs/ : le compteur de factures de
    production ne doit jamais être consommé par la suite de tests.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        if quote_id:
            cfg = charger_config(ROOT / "config" / "devis.example.yaml")
            doc = generer_devis(
                "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, "
                "gamme standard, photos disponibles.",
                cfg,
                id_devis=quote_id,
                utiliser_ia=False,
            )
            ecrire_exports(doc, root / "outputs" / "devis")
        with patch.object(dashboard_run, "RACINE", root):
            yield root


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
        with _racine_isolee("TEST-DASH-INVOICE"):
            payload = _generate_invoice("TEST-DASH-INVOICE", invoice_type="acompte")

        self.assertEqual(payload["id_devis"], "TEST-DASH-INVOICE")
        self.assertEqual(payload["type_facture"], "acompte")
        # Numérotation séquentielle légale, plus de dérivé du devis.
        self.assertRegex(payload["id_facture"], r"^FAC-\d{4}-\d{4}$")
        self.assertTrue(payload["date_echeance"])
        self.assertGreater(payload["totaux"]["total_ttc"], 0)
        self.assertIn("html", payload["exports"])
        json.dumps(payload, ensure_ascii=False)

    def test_dashboard_genere_relances_depuis_devis(self) -> None:
        with _racine_isolee("TEST-DASH-FOLLOWUP"):
            payload = _generate_followups("TEST-DASH-FOLLOWUP")

        self.assertEqual(payload["id_devis"], "TEST-DASH-FOLLOWUP")
        self.assertEqual([m["jour"] for m in payload["messages"]], [3, 7, 15])
        self.assertIn("json", payload["exports"])
        json.dumps(payload, ensure_ascii=False)

    def test_dashboard_crm_met_a_jour_statut_devis(self) -> None:
        with _racine_isolee("TEST-DASH-CRM"):
            pipeline = _update_crm("TEST-DASH-CRM", "signe", "Préparer facture acompte")
            item = next(item for item in pipeline["items"] if item["id"] == "TEST-DASH-CRM")
            stats = _crm_pipeline()["stats"]

        self.assertEqual(item["status"], "signe")
        self.assertEqual(item["next_action"], "Préparer facture acompte")
        self.assertIn("signe", stats)

    def test_dashboard_genere_message_avis_google(self) -> None:
        payload = _generate_review_request(client="Mme Dupont", chantier="la salle de bain")

        self.assertIn("message", payload)
        self.assertIn("Mme Dupont", payload["message"])
        self.assertIn("la salle de bain", payload["message"])
        self.assertIn("json", payload["exports"])


if __name__ == "__main__":
    unittest.main()
