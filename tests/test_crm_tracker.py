from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents.crm_tracker.pipeline import build_pipeline, update_item
from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import ecrire_exports


ROOT = Path(__file__).resolve().parents[1]


class CRMTrackerTest(unittest.TestCase):
    def test_pipeline_reads_quotes_with_default_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = charger_config(ROOT / "config" / "devis.example.yaml")
            doc = generer_devis(
                "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
                cfg,
                id_devis="TEST-CRM",
                utiliser_ia=False,
            )
            ecrire_exports(doc, root / "outputs" / "devis")

            pipeline = build_pipeline(root)

            self.assertEqual(pipeline["items"][0]["id"], "TEST-CRM")
            self.assertEqual(pipeline["items"][0]["status"], "devis_envoye")
            self.assertGreater(pipeline["items"][0]["total_ttc"], 0)

    def _root_avec_devis(self, root: Path, quote_id: str = "TEST-CRM") -> None:
        cfg = charger_config(ROOT / "config" / "devis.example.yaml")
        doc = generer_devis(
            "Salle de bain à Nantes 6m2, douche, vasque, carrelage, plomberie, gamme standard, photos disponibles.",
            cfg,
            id_devis=quote_id,
            utiliser_ia=False,
        )
        ecrire_exports(doc, root / "outputs" / "devis")

    def test_update_item_persists_status_and_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._root_avec_devis(root)

            update_item(root, "TEST-CRM", "signe", "Envoyer facture acompte")
            state = json.loads((root / "outputs" / "crm" / "pipeline.json").read_text(encoding="utf-8"))

            self.assertEqual(state["TEST-CRM"]["status"], "signe")
            self.assertEqual(state["TEST-CRM"]["next_action"], "Envoyer facture acompte")

    def test_update_item_refuse_devis_inconnu(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                update_item(Path(tmp), "DEVIS-FANTOME", "signe")
            self.assertIn("inconnu", str(ctx.exception))

    def test_update_item_protege_les_statuts_terminaux(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._root_avec_devis(root)
            update_item(root, "TEST-CRM", "signe")

            with self.assertRaises(ValueError) as ctx:
                update_item(root, "TEST-CRM", "relance")
            self.assertIn("Signé", str(ctx.exception))
            # Re-poser le même statut terminal reste permis (idempotent).
            update_item(root, "TEST-CRM", "signe", "RAS")

    def test_save_state_n_ecrit_jamais_de_fichier_corrompu(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._root_avec_devis(root)
            update_item(root, "TEST-CRM", "relance")
            path = root / "outputs" / "crm" / "pipeline.json"

            # L'écriture atomique ne laisse ni fichier temporaire ni JSON tronqué.
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
            json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

