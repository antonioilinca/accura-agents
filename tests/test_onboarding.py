from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents.dashboard.onboarding import (
    apply_profile_to_devis_config,
    build_devis_yaml,
    load_profile,
    save_logo_asset,
    save_profile,
)
from agents.devis_generator.config import charger_config
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import rendre_html


PNG_BYTES = b"\x89PNG\r\n\x1a\nlogo-test"


class OnboardingTest(unittest.TestCase):
    def test_default_profile_maps_plan_to_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = load_profile(Path(tmp))

            self.assertEqual(profile["plan"], "fondation")
            self.assertIn("devis", profile["plan_capabilities"]["agents"])
            self.assertNotIn("acquisition", profile["plan_capabilities"]["agents"])

    def test_growth_plan_enables_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = save_profile(root, {"plan": "croissance"})

            self.assertTrue(profile["acquisition"]["enabled"])
            self.assertIn("acquisition", profile["plan_capabilities"]["agents"])

    def test_build_devis_yaml_contains_artisan_prices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = save_profile(Path(tmp), {
                "company": {"name": "Plomberie Test", "siret": "123"},
                "business": {"main_trade": "plomberie", "service_area": ["Nantes"]},
                "quote_items": [{
                    "code": "douche_test",
                    "label": "Pose douche test",
                    "unit": "forfait",
                    "unit_price_ht": 700,
                    "keywords": ["douche"],
                }],
            })
            data = build_devis_yaml(profile)

            self.assertEqual(data["artisan"]["nom"], "Plomberie Test")
            self.assertEqual(data["metiers"]["plomberie"]["postes"][0]["prix_unitaire_ht"], "700")

    def test_profile_with_logo_is_saved_locally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logo = save_logo_asset(root, "artisan.png", PNG_BYTES)
            profile = save_profile(root, {"assets": logo})
            payload = json.loads((root / "outputs" / "onboarding" / "artisan_profile.json").read_text(encoding="utf-8"))

            self.assertEqual(profile["assets"]["logo_path"], "outputs/onboarding/assets/logo.png")
            self.assertEqual(payload["assets"]["logo_path"], "outputs/onboarding/assets/logo.png")
            self.assertTrue((root / "outputs" / "onboarding" / "assets" / "logo.png").exists())

    def test_devis_config_contains_logo_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = save_profile(root, {
                "assets": {"logo_path": "outputs/onboarding/assets/logo.png"},
                "company": {"name": "Plomberie Test"},
                "business": {"main_trade": "plomberie", "service_area": ["Nantes"]},
            })

            data = build_devis_yaml(profile)
            paths = apply_profile_to_devis_config(root, profile)
            cfg = charger_config(paths["devis_config"])

            self.assertEqual(data["artisan"]["logo_path"], "outputs/onboarding/assets/logo.png")
            self.assertEqual(cfg.artisan.logo_path, "outputs/onboarding/assets/logo.png")

    def test_html_render_contains_logo_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = save_profile(root, {
                "assets": {"logo_path": "outputs/onboarding/assets/logo.png"},
                "company": {"name": "Plomberie Test"},
                "business": {"main_trade": "plomberie", "service_area": ["Nantes"]},
                "quote_items": [{
                    "code": "douche_test",
                    "label": "Pose douche test",
                    "unit": "forfait",
                    "unit_price_ht": 700,
                    "keywords": ["douche"],
                }],
            })
            paths = apply_profile_to_devis_config(root, profile)
            cfg = charger_config(paths["devis_config"])
            doc = generer_devis(
                "Client à Nantes, douche à remplacer, gamme standard, photos disponibles.",
                cfg,
                id_devis="TEST-LOGO",
                utiliser_ia=False,
            )

            html = rendre_html(doc)

            self.assertIn("class='artisan-logo'", html)
            self.assertIn("../onboarding/assets/logo.png", html)

    def test_apply_profile_creates_devis_config_loadable_by_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = save_profile(root, {
                "company": {"name": "Plomberie Test"},
                "business": {"main_trade": "plomberie", "service_area": ["Nantes"]},
                "quote_items": [{
                    "code": "douche_test",
                    "label": "Pose douche test",
                    "unit": "forfait",
                    "unit_price_ht": 700,
                    "keywords": ["douche"],
                }],
            })

            paths = apply_profile_to_devis_config(root, profile)
            cfg = charger_config(paths["devis_config"])
            doc = generer_devis(
                "Client à Nantes, douche à remplacer, gamme standard, photos disponibles.",
                cfg,
                id_devis="TEST-ONBOARDING",
                utiliser_ia=False,
            )

            self.assertEqual(cfg.artisan.nom, "Plomberie Test")
            self.assertGreater(doc.totaux.total_ttc, 0)
            self.assertTrue(any("douche" in ligne.libelle.lower() for ligne in doc.lignes))


if __name__ == "__main__":
    unittest.main()
