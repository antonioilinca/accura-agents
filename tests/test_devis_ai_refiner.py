from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from agents.devis_generator.ai_refiner import ameliorer_devis_avec_ia, creer_client_llm_si_disponible
from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis


ROOT = Path(__file__).resolve().parents[1]


class FakeLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def structured(self, *args, **kwargs):
        return self.payload, object()


class DevisAIRefinerTest(unittest.TestCase):
    def test_finition_ia_ameliore_message_sans_changer_totaux(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-IA-OK",
            utiliser_ia=False,
        )
        total_avant = doc.totaux.total_ttc
        lignes_avant = [(l.libelle, l.total_ht) for l in doc.lignes]

        ameliorer_devis_avec_ia(
            doc,
            cfg,
            client=FakeLLM({
                "resume_pro": "Rénovation complète d'une salle de bain de 6 m² à Nantes.",
                "questions": [],
                "message_client": (
                    "Bonjour, voici une première estimation pour la rénovation de votre "
                    "salle de bain à Nantes : 3909.84 € TTC. Nous pourrons finaliser le "
                    "devis après validation des derniers détails techniques."
                ),
                "notes_artisan": ["Vérifier l'état du support avant validation définitive."],
            }),
            modele="fake",
        )

        self.assertEqual(doc.totaux.total_ttc, total_avant)
        self.assertEqual([(l.libelle, l.total_ht) for l in doc.lignes], lignes_avant)
        self.assertEqual(doc.mode_generation, "ia_assistee")
        self.assertIn("Rénovation complète", doc.demande.resume_pro)
        self.assertIn("3909.84", doc.message_client)
        self.assertTrue(doc.notes_artisan)

    def test_finition_ia_refuse_message_avec_mauvais_montant(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-IA-REFUS",
            utiliser_ia=False,
        )
        message_avant = doc.message_client

        ameliorer_devis_avec_ia(
            doc,
            cfg,
            client=FakeLLM({
                "resume_pro": "Rénovation salle de bain.",
                "questions": [],
                "message_client": "Bonjour, votre devis est de 999 € TTC.",
                "notes_artisan": [],
            }),
            modele="fake",
        )

        self.assertEqual(doc.message_client, message_avant)
        self.assertEqual(str(doc.totaux.total_ttc), "3909.84")

    def test_client_ia_auto_se_prepare_quand_cle_openai_presente(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "GROQ_API_KEY": ""}):
            client, modele = creer_client_llm_si_disponible(cfg)
            self.assertIsNone(client)
            self.assertIsNone(modele)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": "", "GROQ_API_KEY": ""}):
            client, modele = creer_client_llm_si_disponible(cfg)
            self.assertIsNotNone(client)
            self.assertEqual(getattr(client, "provider"), "openai_compat")
            self.assertEqual(modele, cfg.llm.modele)

        # Fallback gratuit : Groq seul suffit à activer la finition IA (démo Fondation
        # soignée sans clé payante). OpenAI/Anthropic restent prioritaires s'ils existent.
        with patch.dict("os.environ", {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "GROQ_API_KEY": "gsk-test"}):
            client, modele = creer_client_llm_si_disponible(cfg)
            self.assertIsNotNone(client)
            self.assertEqual(getattr(client, "provider"), "openai_compat")
            self.assertEqual(modele, cfg.llm.modele_groq)


if __name__ == "__main__":
    unittest.main()
