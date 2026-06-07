from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.facture_generator.generator import generer_facture_depuis_devis
from agents.facture_generator.render import ecrire_exports, rendre_html


ROOT = Path(__file__).resolve().parents[1]


class FactureGeneratorTest(unittest.TestCase):
    def _devis_payload(self):
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        cfg.artisan.logo_path = "outputs/onboarding/assets/logo.png"
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-FACTURE",
            utiliser_ia=False,
        )
        return doc.to_dict()

    def test_facture_acompte_reprend_montant_du_devis(self) -> None:
        devis = self._devis_payload()

        facture = generer_facture_depuis_devis(devis, type_facture="acompte")

        self.assertEqual(facture.id_devis, "TEST-FACTURE")
        self.assertEqual(facture.type_facture, "acompte")
        self.assertEqual(facture.totaux.total_ttc, Decimal(str(devis["totaux"]["acompte_ttc"])))
        self.assertGreater(facture.totaux.total_ht, 0)

    def test_facture_solde_deduit_acompte(self) -> None:
        devis = self._devis_payload()

        facture = generer_facture_depuis_devis(devis, type_facture="solde")

        expected = round(devis["totaux"]["total_ttc"] - devis["totaux"]["acompte_ttc"], 2)
        self.assertEqual(float(facture.totaux.total_ttc), expected)
        self.assertEqual(float(facture.totaux.deja_facture_ttc), devis["totaux"]["acompte_ttc"])

    def test_facture_html_contient_logo_et_exports(self) -> None:
        facture = generer_facture_depuis_devis(self._devis_payload(), type_facture="acompte")

        html = rendre_html(facture)

        self.assertIn("class='artisan-logo'", html)
        self.assertIn("../onboarding/assets/logo.png", html)
        with tempfile.TemporaryDirectory() as tmp:
            paths = ecrire_exports(facture, Path(tmp))
            self.assertTrue(paths["json"].exists())
            self.assertTrue(paths["markdown"].exists())
            self.assertTrue(paths["html"].exists())


if __name__ == "__main__":
    unittest.main()
