from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.dashboard import clients
from agents.dashboard import run as dashboard_run

REPO_ROOT = Path(__file__).resolve().parents[1]


def _seed_config(root: Path) -> None:
    """Copie config/ du repo dans un RACINE temporaire patché (devis.example.yaml + métiers)."""
    import shutil
    shutil.copytree(REPO_ROOT / "config", root / "config")


class ClientsModuleTest(unittest.TestCase):
    def test_slugify_handles_accents_and_symbols(self) -> None:
        self.assertEqual(clients.slugify("Plomberie Légère & Co !"), "plomberie-legere-co")
        self.assertEqual(clients.slugify("   "), "client")

    def test_create_client_creates_workspace_profile_and_fiche(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fiche = clients.create_client(root, {
                "company_name": "Plomberie Test",
                "main_trade": "plomberie",
                "service_area": "Nantes, Rezé",
                "plan": "croissance",
            })

            self.assertEqual(fiche["slug"], "plomberie-test")
            self.assertEqual(fiche["status"], "prospect")  # statut par défaut
            self.assertEqual(fiche["service_area"], ["Nantes", "Rezé"])
            self.assertTrue(clients.client_file(root, "plomberie-test").exists())

            # Le profil d'onboarding du client est initialisé dans SON espace.
            profil = root / "outputs" / "clients" / "plomberie-test" / "onboarding" / "artisan_profile.json"
            self.assertTrue(profil.exists())
            data = json.loads(profil.read_text(encoding="utf-8"))
            self.assertEqual(data["company"]["name"], "Plomberie Test")
            self.assertEqual(data["business"]["main_trade"], "plomberie")
            self.assertEqual(data["plan"], "croissance")

    def test_create_client_generates_unique_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = clients.create_client(root, {"company_name": "Dupont"})
            b = clients.create_client(root, {"company_name": "Dupont"})
            self.assertEqual(a["slug"], "dupont")
            self.assertEqual(b["slug"], "dupont-2")

    def test_create_client_requires_company_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                clients.create_client(Path(tmp), {"company_name": "   "})

    def test_list_clients_sorted_recent_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from datetime import datetime
            clients.create_client(root, {"company_name": "Ancien"}, now=datetime(2026, 1, 1, 9, 0, 0))
            clients.create_client(root, {"company_name": "Recent"}, now=datetime(2026, 6, 1, 9, 0, 0))
            noms = [c["company_name"] for c in clients.list_clients(root)]
            self.assertEqual(noms, ["Recent", "Ancien"])

    def test_active_workspace_defaults_to_outputs_when_no_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(clients.active_workspace(root), root / "outputs")
            self.assertIsNone(clients.get_active(root))

    def test_set_and_clear_active_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clients.create_client(root, {"company_name": "Plomberie Test"})
            clients.set_active(root, "plomberie-test")
            self.assertEqual(clients.get_active(root), "plomberie-test")
            self.assertEqual(
                clients.active_workspace(root),
                root / "outputs" / "clients" / "plomberie-test",
            )
            clients.set_active(root, None)
            self.assertIsNone(clients.get_active(root))
            self.assertEqual(clients.active_workspace(root), root / "outputs")

    def test_set_active_unknown_client_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                clients.set_active(Path(tmp), "inconnu")

    def test_active_pointer_ignored_when_client_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clients.create_client(root, {"company_name": "Plomberie Test"})
            clients.set_active(root, "plomberie-test")
            # Suppression "à la main" de la fiche : le pointeur ne doit plus pointer dessus.
            clients.client_file(root, "plomberie-test").unlink()
            self.assertIsNone(clients.get_active(root))
            self.assertEqual(clients.active_workspace(root), root / "outputs")

    def test_update_client_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clients.create_client(root, {"company_name": "Plomberie Test"})
            fiche = clients.update_client(root, "plomberie-test", {"status": "actif"})
            self.assertEqual(fiche["status"], "actif")
            self.assertEqual(clients.get_client(root, "plomberie-test")["status"], "actif")

    def test_update_client_rejects_bad_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clients.create_client(root, {"company_name": "Plomberie Test"})
            with self.assertRaises(ValueError):
                clients.update_client(root, "plomberie-test", {"status": "n_importe_quoi"})


class ClientRecontextualizationTest(unittest.TestCase):
    """Vérifie que le serveur écrit BIEN dans l'espace du client actif."""

    def test_quote_lands_in_active_client_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_config(root)
            with patch.object(dashboard_run, "RACINE", root):
                clients.create_client(root, {
                    "company_name": "Plomberie Test",
                    "main_trade": "plomberie",
                    "service_area": "Nantes",
                })
                clients.set_active(root, "plomberie-test")

                with patch.dict("os.environ", {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
                    payload = dashboard_run._generate_quote(
                        "Salle de bain à Nantes 6m2, douche, vasque, carrelage, "
                        "plomberie, gamme standard, photos disponibles.",
                        quote_id="TEST-CLIENT-DEVIS",
                    )

            # Le devis est rangé dans l'espace du client, pas dans outputs/devis.
            client_devis = root / "outputs" / "clients" / "plomberie-test" / "devis"
            self.assertTrue((client_devis / "test-client-devis.json").exists())
            self.assertFalse((root / "outputs" / "devis" / "test-client-devis.json").exists())
            # L'URL d'export pointe vers l'espace client.
            self.assertTrue(payload["exports"]["json"].startswith("/outputs/clients/plomberie-test/devis/"))

    def test_quote_lands_in_outputs_when_no_active_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_config(root)
            with patch.object(dashboard_run, "RACINE", root):
                with patch.dict("os.environ", {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
                    payload = dashboard_run._generate_quote(
                        "Salle de bain à Nantes 6m2, douche, vasque, carrelage, "
                        "plomberie, gamme standard, photos disponibles.",
                        quote_id="TEST-DEMO-DEVIS",
                    )

            # Rétrocompat : sans client actif, on retombe sur outputs/devis.
            self.assertTrue((root / "outputs" / "devis" / "test-demo-devis.json").exists())
            self.assertEqual(payload["exports"]["json"], "/outputs/devis/test-demo-devis.json")

    def test_crm_isolated_per_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_config(root)
            with patch.object(dashboard_run, "RACINE", root):
                clients.create_client(root, {"company_name": "Plomberie Test", "main_trade": "plomberie"})
                clients.set_active(root, "plomberie-test")
                with patch.dict("os.environ", {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
                    dashboard_run._generate_quote(
                        "Salle de bain à Nantes 6m2, douche, vasque, carrelage, "
                        "plomberie, gamme standard, photos disponibles.",
                        quote_id="TEST-CLIENT-CRM",
                    )
                pipeline = dashboard_run._update_crm("TEST-CLIENT-CRM", "signe", "Préparer facture")

            item = next(i for i in pipeline["items"] if i["id"] == "TEST-CLIENT-CRM")
            self.assertEqual(item["status"], "signe")
            # Le pipeline CRM du client vit dans son espace, pas dans outputs/crm.
            self.assertTrue(
                (root / "outputs" / "clients" / "plomberie-test" / "crm" / "pipeline.json").exists()
            )
            self.assertFalse((root / "outputs" / "crm" / "pipeline.json").exists())


if __name__ == "__main__":
    unittest.main()
