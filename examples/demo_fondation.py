"""Démo Fondation Accura — parcours complet pour un artisan fictif crédible.

Objectif commercial : montrer en une commande tout ce que l'offre Fondation
(199 €/mois) produit pour un artisan, à partir de demandes brutes type vocal
WhatsApp. Tout est généré en local, sans clé API, sans envoi automatique.

Artisan de démonstration : Atelier Rénov Loire (fictif, plomberie / salle de bain,
Nantes Métropole). Le SIRET est volontairement factice (que des zéros) pour ne
jamais usurper une vraie entreprise.

Lancer :

    uv run python examples/demo_fondation.py

Puis ouvrir le dashboard pour la présentation :

    uv run python -m agents.dashboard.run
    http://127.0.0.1:8787

Tout est écrit dans outputs/ (ignoré par Git). Le profil onboarding existant est
sauvegardé avant la démo et restaurable depuis outputs/onboarding/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from agents.crm_tracker.pipeline import build_pipeline, update_item  # noqa: E402
from agents.dashboard.onboarding import load_profile, profile_path, save_profile  # noqa: E402
from agents.devis_generator.config import charger_config  # noqa: E402
from agents.devis_generator.generator import generer_devis  # noqa: E402
from agents.devis_generator.render import ecrire_exports  # noqa: E402
from agents.facture_generator.generator import generer_facture_depuis_devis  # noqa: E402
from agents.facture_generator.render import ecrire_exports as ecrire_exports_facture  # noqa: E402
from agents.relance_generator.generator import generer_relances_depuis_devis  # noqa: E402
from agents.relance_generator.render import ecrire_exports as ecrire_exports_relance  # noqa: E402
from agents.avis_generator.generator import generer_demande_avis  # noqa: E402
from agents.avis_generator.render import ecrire_exports as ecrire_exports_avis  # noqa: E402


ARTISAN_DEMO = {
    "plan": "fondation",
    "company": {
        "name": "Atelier Rénov Loire",
        "legal_name": "Atelier Rénov Loire (SARL de démonstration)",
        "siret": "000 000 000 00000 (profil de démonstration)",
        "insurance": "Assurance décennale MAAF Pro n° DEMO-0000 (exemple)",
        "address": "8 rue de la Loire, 44000 Nantes",
        "phone": "02 40 00 00 00",
        "email": "contact@atelier-renov-loire.fr",
        "google_review_url": "https://g.page/r/atelier-renov-loire-demo/review",
    },
    "business": {
        "main_trade": "plomberie",
        "secondary_trades": ["carrelage", "electricite"],
        "service_area": ["Nantes", "Saint-Herblain", "Rezé", "Vertou", "Orvault", "Carquefou"],
        "ideal_jobs": ["salle de bain", "rénovation intérieure", "douche à l'italienne"],
        "excluded_jobs": ["urgence de nuit", "dépannage non rentable"],
        "minimum_job_ttc": 800,
    },
}

# (id_devis, fichier de demande, statut CRM, prochaine action, parcours étendu)
CAS = [
    {
        "id": "DEMO-FOND-SDB-DUPONT",
        "demande": "salle_de_bain_complete.txt",
        "statut": "signe",
        "action": "Acompte encaissé, chantier planifié. Demander l'avis Google à la fin.",
        "facture": True,
        "relances": True,
        "avis": {"client": "M. Dupont", "chantier": "la rénovation de votre salle de bain"},
    },
    {
        "id": "DEMO-FOND-ELEC-HERBLAIN",
        "demande": "electricite_tableau.txt",
        "statut": "relance",
        "action": "Relance J+7 envoyée. Rappeler par téléphone si pas de retour à J+10.",
        "facture": False,
        "relances": True,
        "avis": None,
    },
    {
        "id": "DEMO-FOND-CARR-VERTOU",
        "demande": "carrelage_vertou.txt",
        "statut": "devis_envoye",
        "action": "Devis envoyé ce jour. Relance automatique prévue à J+3.",
        "facture": False,
        "relances": False,
        "avis": None,
    },
]


def section(titre: str) -> None:
    print(f"\n{'=' * 4} {titre} {'=' * 4}")


def euros(valeur) -> str:
    return f"{float(valeur or 0):,.2f} €".replace(",", " ").replace(".", ",", 1)


def preparer_config_demo() -> Path:
    """Construit une config devis à l'en-tête de l'artisan démo (tous métiers conservés)."""
    base = yaml.safe_load((RACINE / "config" / "devis.example.yaml").read_text(encoding="utf-8"))
    company = ARTISAN_DEMO["company"]
    base["artisan"] = {
        "nom": company["name"],
        "adresse": company["address"],
        "telephone": company["phone"],
        "email": company["email"],
        "siret": company["siret"],
        "assurance_decennale": company["insurance"],
        "logo_path": "",
        "mentions": [
            "Acompte de 30 % à la signature, solde à réception des travaux.",
            "Prix fermes 30 jours. Délais confirmés après visite technique.",
            "Atelier Rénov Loire — artisan équipé par Accura Ouest.",
        ],
    }
    # Démo 100 % locale et déterministe : pas d'appel IA.
    base.setdefault("llm", {})["actif"] = False
    dossier = RACINE / "outputs" / "demo"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / "devis_demo.yaml"
    chemin.write_text(yaml.safe_dump(base, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return chemin


def sauvegarder_profil_existant() -> None:
    actuel = profile_path(RACINE)
    if actuel.exists():
        backup = actuel.with_name("artisan_profile.avant-demo.json")
        shutil.copy2(actuel, backup)
        print(f"Profil onboarding existant sauvegardé : {backup}")


def archiver_et_nettoyer() -> None:
    """Archive l'état outputs existant puis vide les dossiers pour une démo propre.

    Réversible : tout est copié dans outputs/_archive_avant_demo_<horodatage>/ avant
    suppression. On ne touche qu'aux artefacts régénérables (devis, factures, relances,
    avis) et on réinitialise le pipeline CRM. Profil onboarding et config sont préservés.
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = RACINE / "outputs" / f"_archive_avant_demo_{stamp}"
    cibles = ["devis", "factures", "relances", "avis"]
    deplaces = 0
    for nom in cibles:
        source = RACINE / "outputs" / nom
        if not source.exists():
            continue
        fichiers = [p for p in source.iterdir() if p.is_file()]
        if not fichiers:
            continue
        dest = archive / nom
        dest.mkdir(parents=True, exist_ok=True)
        for fichier in fichiers:
            shutil.move(str(fichier), str(dest / fichier.name))
            deplaces += 1
    crm = RACINE / "outputs" / "crm" / "pipeline.json"
    if crm.exists():
        (archive / "crm").mkdir(parents=True, exist_ok=True)
        shutil.copy2(crm, archive / "crm" / "pipeline.json")
        crm.write_text("{}\n", encoding="utf-8")
    if deplaces:
        print(f"État précédent archivé ({deplaces} fichiers) : {archive}")
    else:
        print("Dossiers outputs déjà propres, rien à archiver.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Démo Fondation Accura (artisan fictif)")
    parser.add_argument(
        "--garder-historique",
        action="store_true",
        help="ne pas nettoyer les devis/factures existants (pipeline cumulé)",
    )
    args = parser.parse_args()

    section("DÉMO FONDATION ACCURA — Atelier Rénov Loire (fictif)")
    print("Génération locale, sans clé API, sans envoi automatique.")

    sauvegarder_profil_existant()
    if not args.garder_historique:
        archiver_et_nettoyer()
    profil = save_profile(RACINE, ARTISAN_DEMO)
    print(f"Artisan configuré : {profil['company']['name']} — {profil['company']['email']}")

    config_path = preparer_config_demo()
    cfg = charger_config(config_path)
    dossier_devis = RACINE / cfg.dossier_sortie

    recap_lignes = [
        "# Démo Fondation Accura — Atelier Rénov Loire",
        "",
        f"_Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')} — données de démonstration, prix à calibrer._",
        "",
        "| Devis | Chantier | Total TTC | Statut | Documents |",
        "|---|---|---:|---|---|",
    ]

    for cas in CAS:
        section(f"Devis {cas['id']}")
        texte = (RACINE / "examples" / "devis" / "requests" / cas["demande"]).read_text(encoding="utf-8").strip()
        doc = generer_devis(texte, cfg, id_devis=cas["id"], utiliser_ia=False)
        ecrire_exports(doc, dossier_devis)
        devis = json.loads((dossier_devis / f"{cas['id']}.json").read_text(encoding="utf-8"))
        totaux = devis.get("totaux", {})
        demande = devis.get("demande", {})
        print(f"  Métier   : {demande.get('metier_libelle', '-')}")
        print(f"  Ville    : {demande.get('ville', 'à préciser')}")
        print(f"  Total TTC: {euros(totaux.get('total_ttc'))}")
        docs = ["devis"]

        if cas["facture"]:
            facture = generer_facture_depuis_devis(devis, type_facture="acompte")
            ecrire_exports_facture(facture, RACINE / "outputs" / "factures")
            fdict = facture.to_dict()
            print(f"  Facture acompte : {euros(fdict.get('totaux', {}).get('total_ttc'))}")
            docs.append("facture acompte")

        if cas["relances"]:
            plan = generer_relances_depuis_devis(devis)
            ecrire_exports_relance(plan, RACINE / "outputs" / "relances")
            jours = [m.get("jour") for m in plan.to_dict().get("messages", [])]
            print(f"  Relances prêtes : J+{', J+'.join(str(j) for j in jours)}")
            docs.append("relances")

        if cas["avis"]:
            avis = generer_demande_avis(load_profile(RACINE), **cas["avis"])
            ecrire_exports_avis(avis, RACINE / "outputs" / "avis")
            print("  Message avis Google : prêt à copier")
            docs.append("avis Google")

        update_item(RACINE, cas["id"], cas["statut"], cas["action"])
        print(f"  CRM : {cas['statut']} — {cas['action']}")

        recap_lignes.append(
            f"| {cas['id']} | {demande.get('type_chantier', '-')} {demande.get('ville', '')} "
            f"| {euros(totaux.get('total_ttc'))} | {cas['statut']} | {', '.join(docs)} |"
        )

    section("CRM — pipeline résultant")
    pipeline = build_pipeline(RACINE)
    for key, label in pipeline["statuses"].items():
        print(f"  {label:14s}: {pipeline['stats'].get(key, 0)}")

    recap_lignes += [
        "",
        "## Parcours démontré (promesse Fondation 199 €/mois)",
        "",
        "1. Demande brute (vocal/WhatsApp simulé) -> devis structuré prêt à envoyer.",
        "2. Devis signé -> facture d'acompte (montants repris du devis, jamais recalculés par l'IA).",
        "3. Relances J+3 / J+7 / J+15 prêtes à copier, aucun envoi automatique.",
        "4. Mini CRM : pipeline devis envoyé -> relancé -> signé.",
        "5. Chantier terminé -> message de demande d'avis Google prêt à copier.",
        "",
        "## Montrer la démo",
        "",
        "```bash",
        "uv run python -m agents.dashboard.run",
        "# puis http://127.0.0.1:8787",
        "```",
        "",
        "Onglets à parcourir devant l'artisan : Devis -> Factures -> Relances -> CRM -> Avis Google.",
    ]

    dossier_demo = RACINE / "outputs" / "demo"
    dossier_demo.mkdir(parents=True, exist_ok=True)
    recap_path = dossier_demo / "RECAP_DEMO_FONDATION.md"
    recap_path.write_text("\n".join(recap_lignes) + "\n", encoding="utf-8")

    section("DÉMO PRÊTE")
    print(f"Récap : {recap_path}")
    print("Dashboard : uv run python -m agents.dashboard.run  ->  http://127.0.0.1:8787")
    print("Onglets : Devis -> Factures -> Relances -> CRM -> Avis Google")


if __name__ == "__main__":
    main()
