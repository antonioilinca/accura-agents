from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import calculer_totaux, generer_devis
from agents.devis_generator.models import (
    ArtisanIdentity,
    PricingConfig,
    QuoteConfig,
    QuoteLine,
    TradeConfig,
)
from agents.devis_generator.render import ecrire_exports


ROOT = Path(__file__).resolve().parents[1]


class DevisGeneratorTest(unittest.TestCase):
    def test_demande_complete_genere_un_devis_exportable(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        texte = (
            "Bonjour, devis pour M. Dupont, 12 rue des Lilas à Nantes. "
            "Je veux refaire ma salle de bain, environ 6m2, remplacer douche, "
            "meuble vasque, carrelage, plomberie. Gamme standard. Photos disponibles."
        )

        doc = generer_devis(texte, cfg, id_devis="TEST-001")

        self.assertEqual(doc.demande.metier, "plomberie")
        self.assertEqual(doc.demande.ville, "Nantes")
        self.assertEqual(doc.demande.surface_m2, Decimal("6"))
        self.assertGreaterEqual(len(doc.lignes), 4)
        self.assertEqual(doc.demande.questions, [])
        self.assertGreater(doc.totaux.total_ttc, Decimal("0"))

        with tempfile.TemporaryDirectory() as tmp:
            paths = ecrire_exports(doc, Path(tmp))
            self.assertTrue(paths["json"].exists())
            self.assertTrue(paths["markdown"].exists())
            self.assertTrue(paths["html"].exists())

    def test_demande_incomplete_genere_des_questions(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")

        doc = generer_devis("Besoin de refaire une salle de bain.", cfg, id_devis="TEST-002")

        questions = " ".join(doc.demande.questions)
        self.assertIn("ville exacte", questions)
        self.assertIn("surface", questions)
        self.assertIn("photos", questions)
        self.assertIn("Pour le finaliser", doc.message_client)

    def test_calcul_ht_tva_ttc_est_correct(self) -> None:
        cfg = QuoteConfig(
            artisan=ArtisanIdentity(),
            pricing=PricingConfig(
                taux_tva=Decimal("0.20"),
                taux_marge=Decimal("0.00"),
                main_oeuvre_heure_ht=Decimal("50"),
                validite_jours=30,
                acompte_pourcentage=Decimal("0.30"),
            ),
            metiers={
                "test": TradeConfig(
                    nom="test",
                    libelle="Test",
                    mots_cles=[],
                    postes=[],
                )
            },
            villes_connues=[],
        )
        lignes = [
            QuoteLine("a", "Poste A", Decimal("2"), "u", Decimal("100"), Decimal("200")),
            QuoteLine("b", "Poste B", Decimal("1"), "u", Decimal("50"), Decimal("50")),
        ]

        totaux = calculer_totaux(lignes, cfg)

        self.assertEqual(totaux.total_ht, Decimal("250.00"))
        self.assertEqual(totaux.tva, Decimal("50.00"))
        self.assertEqual(totaux.total_ttc, Decimal("300.00"))
        self.assertEqual(totaux.acompte_ttc, Decimal("90.00"))


if __name__ == "__main__":
    unittest.main()

