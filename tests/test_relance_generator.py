from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.relance_generator.generator import generer_relances_depuis_devis
from agents.relance_generator.render import ecrire_exports


ROOT = Path(__file__).resolve().parents[1]


class RelanceGeneratorTest(unittest.TestCase):
    def _devis_payload(self):
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
            cfg,
            id_devis="TEST-RELANCE",
            utiliser_ia=False,
        )
        payload = doc.to_dict()
        payload["date_creation"] = "2026-06-07"
        return payload

    def test_relances_generent_j3_j7_j15(self) -> None:
        plan = generer_relances_depuis_devis(self._devis_payload())

        self.assertEqual([m.jour for m in plan.messages], [3, 7, 15])
        self.assertEqual(plan.messages[0].date_prevue, "2026-06-10")
        self.assertEqual(plan.messages[1].date_prevue, "2026-06-14")
        self.assertEqual(plan.messages[2].date_prevue, "2026-06-22")

    def test_relances_reprennent_montant_et_contexte_du_devis(self) -> None:
        plan = generer_relances_depuis_devis(self._devis_payload())
        text = "\n".join(message.message for message in plan.messages)

        self.assertIn("TEST-RELANCE", text)
        self.assertIn("3 909,84 € TTC", text)
        self.assertIn("rénovation salle de bain à Nantes", text)

    def test_relances_exportent_json(self) -> None:
        plan = generer_relances_depuis_devis(self._devis_payload())

        with tempfile.TemporaryDirectory() as tmp:
            paths = ecrire_exports(plan, Path(tmp))

            self.assertTrue(paths["json"].exists())
            self.assertIn("test-relance-relances", paths["json"].name)


if __name__ == "__main__":
    unittest.main()
