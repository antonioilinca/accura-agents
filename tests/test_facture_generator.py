from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.facture_generator.generator import generer_facture_depuis_devis, prochain_numero_facture
from agents.facture_generator.render import ecrire_exports, rendre_html, rendre_markdown


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

    def test_numerotation_sequentielle_sans_collision(self) -> None:
        devis = self._devis_payload()
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            acompte = generer_facture_depuis_devis(devis, type_facture="acompte", dossier=dossier)
            solde = generer_facture_depuis_devis(devis, type_facture="solde", dossier=dossier)

            self.assertRegex(acompte.id_facture, r"^FAC-\d{4}-0001$")
            self.assertRegex(solde.id_facture, r"^FAC-\d{4}-0002$")
            self.assertNotEqual(acompte.id_facture, solde.id_facture)

    def test_compteur_facture_survit_aux_relances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            numeros = [prochain_numero_facture(dossier) for _ in range(3)]
            self.assertEqual([n.rsplit("-", 1)[1] for n in numeros], ["0001", "0002", "0003"])

    def test_facture_porte_echeance_et_mentions_legales(self) -> None:
        facture = generer_facture_depuis_devis(self._devis_payload(), type_facture="acompte")

        self.assertTrue(facture.date_echeance)
        self.assertGreater(facture.date_echeance, facture.date_creation)
        markdown = rendre_markdown(facture)
        html = rendre_html(facture)
        for rendu in (markdown, html):
            self.assertIn("Date d'échéance", rendu)
            self.assertIn("pénalités de retard", rendu)
            self.assertIn("40 €", rendu)

    def test_facture_franchise_tva_montre_la_mention_293b(self) -> None:
        devis = self._devis_payload()
        devis["artisan"]["franchise_tva"] = True
        devis["totaux"]["tva"] = 0.0
        # En franchise, TTC == HT (le devis source doit déjà être généré ainsi).
        devis["totaux"]["total_ttc"] = devis["totaux"]["total_ht"]
        devis["totaux"]["acompte_ttc"] = round(devis["totaux"]["total_ttc"] * 0.3, 2)

        facture = generer_facture_depuis_devis(devis, type_facture="acompte")

        self.assertTrue(facture.franchise_tva)
        self.assertIn("293 B", rendre_markdown(facture))
        self.assertIn("293 B", rendre_html(facture))

    def test_facture_refuse_devis_avec_tva_si_franchise(self) -> None:
        devis = self._devis_payload()
        devis["artisan"]["franchise_tva"] = True  # TVA du devis laissée > 0 : incohérent.

        with self.assertRaises(ValueError) as ctx:
            generer_facture_depuis_devis(devis, type_facture="acompte")
        self.assertIn("293 B", str(ctx.exception))

    def test_une_facture_emise_ne_s_ecrase_pas(self) -> None:
        facture = generer_facture_depuis_devis(self._devis_payload(), type_facture="acompte")
        with tempfile.TemporaryDirectory() as tmp:
            ecrire_exports(facture, Path(tmp))
            with self.assertRaises(FileExistsError):
                ecrire_exports(facture, Path(tmp))


if __name__ == "__main__":
    unittest.main()
