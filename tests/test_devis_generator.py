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
    LLMQuoteConfig,
    QuoteConfig,
    QuoteLine,
    TradeConfig,
)
from agents.devis_generator.render import ecrire_exports, rendre_html


ROOT = Path(__file__).resolve().parents[1]


class DevisGeneratorTest(unittest.TestCase):
    def test_demande_complete_genere_un_devis_exportable(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        texte = (
            "Bonjour, devis pour M. Dupont, 12 rue des Lilas à Nantes. "
            "Je veux refaire ma salle de bain, environ 6m2, remplacer douche, "
            "meuble vasque, carrelage, plomberie. Gamme standard. Photos disponibles."
        )

        doc = generer_devis(texte, cfg, id_devis="TEST-001", utiliser_ia=False)

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

        doc = generer_devis(
            "Besoin de refaire une salle de bain.",
            cfg,
            id_devis="TEST-002",
            utiliser_ia=False,
        )

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
            llm=LLMQuoteConfig(actif=False, provider="off"),
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

    def test_metiers_menuiserie_et_carrelage_sont_supportes(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")

        menuiserie = generer_devis(
            "Pose d'une porte intérieure premium à Rezé, photos disponibles.",
            cfg,
            id_devis="TEST-MENUISERIE",
            utiliser_ia=False,
        )
        carrelage = generer_devis(
            "Pose carrelage standard sur sol 20m2 à Vertou, photos disponibles.",
            cfg,
            id_devis="TEST-CARRELAGE",
            utiliser_ia=False,
        )

        self.assertEqual(menuiserie.demande.metier, "menuiserie")
        self.assertTrue(any("porte" in ligne.libelle.lower() for ligne in menuiserie.lignes))
        self.assertEqual(carrelage.demande.metier, "carrelage")
        self.assertTrue(any("carrelage" in ligne.libelle.lower() for ligne in carrelage.lignes))

    def test_pas_urgent_ne_devient_pas_urgent(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")

        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche et vasque, gamme standard, photos disponibles, pas urgent.",
            cfg,
            id_devis="TEST-PAS-URGENT",
            utiliser_ia=False,
        )

        self.assertEqual(doc.demande.urgence, "standard")

    def test_html_render_without_logo_has_clean_fallback(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-SANS-LOGO",
            utiliser_ia=False,
        )

        html = rendre_html(doc)

        self.assertNotIn("<img class='artisan-logo'", html)
        self.assertNotIn("<img", html)

    def test_ids_sequentiels_sans_collision_le_meme_jour(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        texte = "Salle de bain à Nantes 6m2, douche, vasque, gamme standard, photos disponibles."
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            doc1 = generer_devis(texte, cfg, utiliser_ia=False, dossier=dossier)
            doc2 = generer_devis(texte, cfg, utiliser_ia=False, dossier=dossier)

            self.assertNotEqual(doc1.id_devis, doc2.id_devis)
            self.assertRegex(doc1.id_devis, r"^ACC-\d{8}-001$")
            self.assertRegex(doc2.id_devis, r"^ACC-\d{8}-002$")

    def test_un_devis_existant_ne_s_ecrase_pas_sans_id_explicite(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-OVERWRITE",
            utiliser_ia=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            ecrire_exports(doc, Path(tmp))
            with self.assertRaises(FileExistsError):
                ecrire_exports(doc, Path(tmp))
            # La ré-édition volontaire reste possible.
            ecrire_exports(doc, Path(tmp), ecraser=True)

    def test_demande_trop_courte_est_refusee(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        for texte in ("", "   ", "devis ?"):
            with self.assertRaises(ValueError):
                generer_devis(texte, cfg, utiliser_ia=False)

    def test_surface_aberrante_declenche_une_question_sans_chiffrage(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 999 m2, douche, carrelage, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-SURFACE",
            utiliser_ia=False,
        )

        self.assertIsNone(doc.demande.surface_m2)
        self.assertTrue(any("999" in q and "confirmer" in q.lower() for q in doc.demande.questions))
        # Aucune ligne ne doit avoir été quantifiée avec la surface aberrante.
        self.assertTrue(all(l.quantite < 999 for l in doc.lignes))

    def test_surface_negative_jamais_lue_comme_positive(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes -999 m2, douche, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-SURFACE-NEG",
            utiliser_ia=False,
        )

        self.assertIsNone(doc.demande.surface_m2)

    def test_metier_non_reconnu_declenche_une_question(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Installer une borne de recharge dans le garage à Nantes.",
            cfg,
            id_devis="TEST-METIER",
            utiliser_ia=False,
        )

        self.assertTrue(any("métier" in q.lower() for q in doc.demande.questions))

    def test_montant_en_lettres_declenche_une_question(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Refaire la salle de bain à Nantes, budget deux mille euros, gamme standard.",
            cfg,
            id_devis="TEST-LETTRES",
            utiliser_ia=False,
        )

        self.assertTrue(any("toutes lettres" in q for q in doc.demande.questions))

    def test_franchise_tva_produit_un_devis_sans_tva(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        cfg.artisan.franchise_tva = True
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-FRANCHISE",
            utiliser_ia=False,
        )

        self.assertEqual(doc.totaux.tva, Decimal("0.00"))
        self.assertEqual(doc.totaux.total_ttc, doc.totaux.total_ht)
        self.assertTrue(any("293 B" in c for c in doc.conditions))
        self.assertIn("293 B", rendre_html(doc))


if __name__ == "__main__":
    unittest.main()
