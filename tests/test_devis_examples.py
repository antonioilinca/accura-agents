from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import ecrire_exports


ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "examples" / "devis" / "requests"


class DevisExamplesTest(unittest.TestCase):
    def test_tous_les_exemples_generent_un_devis_exportable(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        exemples = sorted(REQUESTS.glob("*.txt"))
        self.assertGreaterEqual(len(exemples), 5)

        with tempfile.TemporaryDirectory() as tmp:
            for index, chemin in enumerate(exemples, start=1):
                with self.subTest(exemple=chemin.name):
                    texte = chemin.read_text(encoding="utf-8")
                    doc = generer_devis(texte, cfg, id_devis=f"EXEMPLE-{index:02d}")
                    paths = ecrire_exports(doc, Path(tmp) / chemin.stem)

                    self.assertTrue(doc.demande.metier)
                    self.assertTrue(doc.demande.type_chantier)
                    self.assertGreaterEqual(len(doc.lignes), 1)
                    self.assertGreater(doc.totaux.total_ttc, 0)
                    self.assertTrue(paths["json"].exists())
                    self.assertTrue(paths["markdown"].exists())
                    self.assertTrue(paths["html"].exists())

    def test_exemple_incomplet_declenche_des_questions(self) -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        texte = (REQUESTS / "salle_de_bain_incomplete.txt").read_text(encoding="utf-8")

        doc = generer_devis(texte, cfg, id_devis="EXEMPLE-INCOMPLET")

        self.assertGreaterEqual(len(doc.demande.questions), 2)
        self.assertIn("Pour le finaliser", doc.message_client)


if __name__ == "__main__":
    unittest.main()

