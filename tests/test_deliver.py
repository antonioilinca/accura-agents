from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from agents.lead_acquisition.config import Config, Metier
from agents.lead_acquisition.deliver import livrer
from agents.lead_acquisition.models import QualifiedLead, RawLead, Signaux


def _cfg(dossier: Path) -> Config:
    return Config(
        metier=Metier(
            nom="plombier",
            libelle="Plombier",
            travaux_pertinents="Salle de bain, chauffage, rénovation.",
        ),
        communes=["Nantes"],
        rayon_km=20,
        sources={},
        seuil_livraison=60,
        taille_lot_tri=25,
        objectif_hebdo_min=2,
        objectif_hebdo_max=3,
        max_qualif_par_run=60,
        surface_max_artisan=600,
        llm_provider="openai_compat",
        llm_base_url="",
        llm_api_key_env="",
        modele_tri="test",
        modele_qualif="test",
        llm_max_retry_after_seconds=120,
        llm_intervalle_min_s=0,
        dossier_sortie=dossier,
        prix_usd_par_million={},
        racine=dossier.parent,
    )


def _lead(i: int, score: int = 80) -> QualifiedLead:
    raw = RawLead(
        source="test",
        external_id=f"lead-{i}",
        commune="Nantes",
        adresse=f"{i} rue Test",
        description="Extension de maison avec rénovation intérieure.",
        date_signal=date.today().isoformat(),
        type_dossier="Permis de construire",
        surface_plancher=80,
    )
    return QualifiedLead(
        raw=raw,
        metier="plombier",
        score=score,
        justification="Projet pertinent pour un plombier.",
        signaux=Signaux(
            adequation_metier="forte",
            ampleur_travaux="moyenne",
            fraicheur="recent",
            signal_budget="moyen",
            zone_ok=True,
            contactabilite="forte",
        ),
        message_contact="Bonjour, nous avons repéré votre projet.",
        qualified_at=date.today().isoformat(),
        canal_recommande="courrier",
        urgence_contact="cette_semaine",
        valeur_potentielle="moyenne",
        angle_approche="Proposer un devis plomberie pour l'extension.",
        prochaine_action="Envoyer un courrier cette semaine.",
        script_appel="Bonjour, je vous appelle pour votre projet d'extension.",
    )


class DeliverTest(unittest.TestCase):
    def test_weekly_growth_promise_caps_delivery_and_creates_tracking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "outputs"
            dossier.mkdir()
            today = date.today().isoformat()
            (dossier / "_seen.json").write_text(
                json.dumps({"old:1": today, "old:2": today}),
                encoding="utf-8",
            )

            json_path, recap, nouveaux = livrer(
                _cfg(dossier),
                [_lead(1), _lead(2), _lead(3)],
                {"cout_usd_estime": 0, "usage": {}},
                scannes=3,
                tries=3,
            )

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(nouveaux), 1)
            self.assertEqual(payload["promesse_accura"]["livres_cette_semaine"], 3)
            self.assertIn("Promesse Croissance", recap)
            self.assertTrue((dossier / "suivi-prospects-plombier.csv").exists())
            self.assertTrue((dossier / f"bilan-croissance-{payload['semaine']}.md").exists())


if __name__ == "__main__":
    unittest.main()
