"""Tests de la plateforme artisan : sécurité (mots de passe, jetons, isolation,
filtrage par plan) et actions self-service de base."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.platform import api, auth


class AuthCryptoTest(unittest.TestCase):
    def test_password_hash_et_verif(self) -> None:
        record = auth.hash_password("motdepasse-solide")
        self.assertNotIn("motdepasse", str(record))  # jamais en clair
        self.assertTrue(auth.verify_password("motdepasse-solide", record))
        self.assertFalse(auth.verify_password("mauvais", record))

    def test_password_trop_court_refuse(self) -> None:
        with self.assertRaises(ValueError):
            auth.hash_password("court")

    def test_jeton_signe_valide_et_detecte_falsification(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            token = auth.issue_token(root, "artisan-x", now=1_000_000)
            self.assertEqual(auth.verify_token(root, token, now=1_000_100), "artisan-x")
            # falsification du corps → rejet
            corps, sig = token.split(".")
            falsifie = corps[:-1] + ("A" if corps[-1] != "A" else "B") + "." + sig
            self.assertIsNone(auth.verify_token(root, falsifie, now=1_000_100))

    def test_jeton_expire(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            token = auth.issue_token(root, "artisan-x", ttl=10, now=1_000_000)
            self.assertIsNone(auth.verify_token(root, token, now=1_000_011))

    def test_cle_de_service(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cle = auth.service_api_key(root)
            self.assertTrue(auth.verify_service_key(root, cle))
            self.assertFalse(auth.verify_service_key(root, "mauvaise"))
            self.assertFalse(auth.verify_service_key(root, ""))


class ProvisioningTest(unittest.TestCase):
    def test_provision_puis_authentifie(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            res = api.provision_account(root, {
                "company_name": "Plomberie Test",
                "plan": "fondation",
                "email": "test@plomberie.fr",
            })
            self.assertTrue(res["slug"])
            self.assertTrue(res["password"])  # généré et renvoyé une fois
            self.assertEqual(res["client"]["status"], "actif")

            token = api.authenticate(root, "test@plomberie.fr", res["password"])
            self.assertEqual(auth.verify_token(root, token), res["slug"])

            with self.assertRaises(api.AuthError):
                api.authenticate(root, "test@plomberie.fr", "mauvais-mot-de-passe")

    def test_email_en_double_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            api.provision_account(root, {"company_name": "A", "email": "x@y.fr"})
            with self.assertRaises(api.PlatformError):
                api.provision_account(root, {"company_name": "B", "email": "x@y.fr"})


class PlanGatingTest(unittest.TestCase):
    def test_fondation_na_pas_les_leads_mais_croissance_oui(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = api.provision_account(root, {"company_name": "Fond", "email": "f@a.fr", "plan": "fondation"})
            c = api.provision_account(root, {"company_name": "Croi", "email": "c@a.fr", "plan": "croissance"})
            with self.assertRaises(api.PlanError):
                api.list_leads(root, f["slug"])
            self.assertEqual(api.list_leads(root, c["slug"]), [])  # autorisé, vide pour l'instant


class IsolationTest(unittest.TestCase):
    def test_un_artisan_ne_voit_pas_les_documents_d_un_autre(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "GROQ_API_KEY": ""}):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                a = api.provision_account(root, {"company_name": "Alpha", "email": "a@a.fr"})["slug"]
                b = api.provision_account(root, {"company_name": "Beta", "email": "b@b.fr"})["slug"]

                devis = api.create_quote(
                    root, a,
                    "Salle de bain à Nantes 6m2, douche, vasque, carrelage, gamme standard.",
                )
                # le devis de A existe et est listé pour A
                noms = [q["id"] for q in api.list_quotes(root, a)]
                self.assertIn(devis["id_devis"], noms)
                # B n'a aucun devis
                self.assertEqual(api.list_quotes(root, b), [])

                # le fichier JSON de A
                fichier = next((root / "outputs" / "clients" / a / "devis").glob("*.json"))
                # A peut le télécharger…
                self.assertTrue(api.document_path(root, a, "devis", fichier.name).is_file())
                # …mais pas B (document hors de son espace)
                with self.assertRaises(api.NotFoundError):
                    api.document_path(root, b, "devis", fichier.name)

    def test_traversee_de_chemin_bloquee(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = api.provision_account(root, {"company_name": "Alpha", "email": "a@a.fr"})["slug"]
            with self.assertRaises(api.NotFoundError):
                api.document_path(root, a, "devis", "../../../../etc/hosts")
            with self.assertRaises(api.NotFoundError):
                api.document_path(root, a, "secrets", "auth.json")


class SelfServiceTest(unittest.TestCase):
    def test_devis_puis_facture_scopes(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "", "GROQ_API_KEY": ""}):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                slug = api.provision_account(root, {"company_name": "Gamma", "email": "g@g.fr"})["slug"]
                devis = api.create_quote(
                    root, slug,
                    "Rénovation salle de bain à Rezé, 5m2, douche italienne, vasque, carrelage.",
                )
                self.assertGreater(devis["totaux"]["total_ttc"], 0)
                facture = api.create_invoice(root, slug, devis["id_devis"], "acompte")
                # la facture reprend bien un montant du devis (jamais recalculé par l'IA)
                self.assertGreater(facture["totaux"]["total_ttc"], 0)
                self.assertEqual(len(api.list_invoices(root, slug)), 1)

    def test_demande_trop_courte_refusee(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            slug = api.provision_account(root, {"company_name": "Delta", "email": "d@d.fr"})["slug"]
            with self.assertRaises(api.PlatformError):
                api.create_quote(root, slug, "court")


if __name__ == "__main__":
    unittest.main()
