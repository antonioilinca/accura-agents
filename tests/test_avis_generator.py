from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.avis_generator.generator import generer_demande_avis
from agents.avis_generator.render import ecrire_exports
from agents.dashboard.onboarding import DEFAULT_PROFILE


class AvisGeneratorTest(unittest.TestCase):
    def test_message_avis_contient_lien_google_si_present(self) -> None:
        profile = {
            **DEFAULT_PROFILE,
            "company": {
                **DEFAULT_PROFILE["company"],
                "name": "Plomberie Test",
                "google_review_url": "https://g.page/r/test-review",
            },
        }

        request = generer_demande_avis(profile, client="Mme Dupont", chantier="la salle de bain")

        self.assertIn("Bonjour Mme Dupont", request.message)
        self.assertIn("la salle de bain", request.message)
        self.assertIn("https://g.page/r/test-review", request.message)

    def test_message_avis_fallback_sans_lien_google(self) -> None:
        request = generer_demande_avis(DEFAULT_PROFILE, client="", chantier="")

        self.assertIn("rechercher", request.message)
        self.assertIn(DEFAULT_PROFILE["company"]["name"], request.message)

    def test_message_avis_exporte_json(self) -> None:
        request = generer_demande_avis(DEFAULT_PROFILE, client="M. Martin", chantier="le chantier")

        with tempfile.TemporaryDirectory() as tmp:
            paths = ecrire_exports(request, Path(tmp))

            self.assertTrue(paths["json"].exists())
            self.assertIn("avis-google", paths["json"].name)


if __name__ == "__main__":
    unittest.main()

