"""Cockpit des agents : lance chaque agent sur une tâche de test et journalise
ses étapes en direct (via ``activity``), pour les voir travailler depuis le
dashboard.

Chaque runner réutilise les vraies fonctions métier des agents (générateurs,
pipeline). Les étapes affichées sont les vraies sous-opérations : rien n'est
simulé, aucun ``sleep`` artificiel. Les agents rapides finissent vite, l'agent
acquisition (IA + open data) prend naturellement plus de temps.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

from . import activity
from agents.avis_generator.generator import generer_demande_avis
from agents.avis_generator.render import ecrire_exports as ecrire_avis
from agents.crm_tracker.pipeline import build_pipeline
from agents.dashboard.onboarding import load_profile
from agents.devis_generator.config import charger_config as charger_config_devis
from agents.devis_generator.generator import generer_devis
from agents.devis_generator.render import ecrire_exports as ecrire_devis
from agents.facture_generator.generator import generer_facture_depuis_devis
from agents.facture_generator.render import ecrire_exports as ecrire_facture
from agents.lead_acquisition.config import charger_config as charger_config_leads
from agents.lead_acquisition.pipeline import run as run_leads_pipeline
from agents.relance_generator.generator import generer_relances_depuis_devis
from agents.relance_generator.render import ecrire_exports as ecrire_relance
from agents.voice_intake.transcriber import transcrire

RACINE = Path(__file__).resolve().parents[2]

DEMANDE_DEMO = (
    "Bonjour, je veux refaire ma salle de bain à Nantes, environ 6 m2, remplacer la "
    "douche, le meuble vasque et le carrelage. Gamme standard. Photos disponibles."
)
PHRASE_VOCALE_DEMO = (
    "Bonjour, je voudrais un devis pour refaire une salle de bain à Nantes, environ "
    "six mètres carrés, changer la douche, le meuble vasque et le carrelage, en gamme "
    "standard."
)


# ---- Helpers partagés ------------------------------------------------------------------

def _config_devis() -> Path:
    locale = RACINE / "config" / "devis.yaml"
    return locale if locale.exists() else RACINE / "config" / "devis.example.yaml"


def _config_leads() -> Path:
    """Config de l'agent acquisition : la version locale si elle existe (chaque zone a
    la sienne, non versionnée), sinon l'exemple versionné — indispensable en hébergement
    cloud où config.yaml est absent."""
    locale = RACINE / "config" / "config.yaml"
    return locale if locale.exists() else RACINE / "config" / "config.example.yaml"


def _dernier_devis_json() -> Path | None:
    dossier = RACINE / "outputs" / "devis"
    if not dossier.exists():
        return None
    fichiers = [p for p in dossier.glob("*.json") if not p.name.startswith("_")]
    fichiers.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return fichiers[0] if fichiers else None


def _generer_devis_demo():
    cfg = charger_config_devis(_config_devis())
    dossier = RACINE / cfg.dossier_sortie
    doc = generer_devis(DEMANDE_DEMO, cfg, dossier=dossier)
    paths = ecrire_devis(doc, dossier)
    return doc, paths


def _devis_source(run_id: str) -> dict:
    """Renvoie le dernier devis (ou en génère un de démo si aucun n'existe)."""
    chemin = _dernier_devis_json()
    if chemin is None:
        activity.add_step(run_id, "Aucun devis trouvé : génération d'un devis de démonstration", "info")
        doc, _ = _generer_devis_demo()
        return doc.to_dict()
    return json.loads(chemin.read_text(encoding="utf-8"))


# ---- Runners (un par agent) ------------------------------------------------------------

def _run_devis(run_id: str):
    activity.add_step(run_id, "Réception de la demande client (texte ou vocal)", "info")
    activity.add_step(run_id, "Chargement de la grille tarifaire de l'artisan", "info")
    activity.add_step(run_id, "Analyse : métier, ville, surface, prestations…", "info")
    doc, paths = _generer_devis_demo()
    data = doc.to_dict()
    demande = data.get("demande", {}) or {}
    totaux = data.get("totaux", {}) or {}
    lignes = data.get("lignes", []) or []
    activity.add_step(
        run_id,
        f"Détecté : {demande.get('metier_libelle', '?')} · {demande.get('ville', '?')} · "
        f"{demande.get('surface_m2', '?')} m²",
        "ok",
    )
    activity.add_step(run_id, f"Chiffrage : {len(lignes)} postes, TVA et acompte calculés", "ok")
    activity.add_step(run_id, "Documents générés (PDF imprimable, JSON)", "ok")
    exports = {
        "html": f"/outputs/devis/{paths['html'].name}",
        "json": f"/outputs/devis/{paths['json'].name}",
    }
    summary = (
        f"Devis {data.get('id_devis', '')} · {demande.get('metier_libelle', '')} · "
        f"total TTC {totaux.get('total_ttc', 0)} €"
    )
    return summary, exports


def _run_facture(run_id: str):
    activity.add_step(run_id, "Recherche du dernier devis validé", "info")
    devis = _devis_source(run_id)
    activity.add_step(run_id, f"Devis source : {devis.get('id_devis', '?')}", "ok")
    dossier = RACINE / "outputs" / "factures"
    doc = generer_facture_depuis_devis(devis, type_facture="acompte", dossier=dossier)
    paths = ecrire_facture(doc, dossier)
    activity.add_step(run_id, "Montants repris du devis (aucun recalcul par l'IA)", "ok")
    activity.add_step(run_id, "Mentions légales ajoutées (échéance, pénalités, art. 293 B si franchise)", "ok")
    data = doc.to_dict()
    totaux = data.get("totaux", {}) or {}
    exports = {
        "html": f"/outputs/factures/{paths['html'].name}",
        "json": f"/outputs/factures/{paths['json'].name}",
    }
    return f"Facture {data.get('id_facture', '')} (acompte) · TTC {totaux.get('total_ttc', 0)} €", exports


def _run_relance(run_id: str):
    activity.add_step(run_id, "Recherche du dernier devis", "info")
    devis = _devis_source(run_id)
    activity.add_step(run_id, f"Devis source : {devis.get('id_devis', '?')}", "ok")
    plan = generer_relances_depuis_devis(devis)
    paths = ecrire_relance(plan, RACINE / "outputs" / "relances")
    activity.add_step(run_id, "Messages J+3, J+7 et J+15 rédigés (prêts à copier)", "ok")
    exports = {"json": f"/outputs/relances/{paths['json'].name}"}
    return "3 relances prêtes (J+3, J+7, J+15)", exports


def _run_avis(run_id: str):
    activity.add_step(run_id, "Lecture du profil artisan (lien Google)", "info")
    request = generer_demande_avis(
        load_profile(RACINE),
        client="Mme Dupont",
        chantier="la rénovation de votre salle de bain",
    )
    paths = ecrire_avis(request, RACINE / "outputs" / "avis")
    activity.add_step(run_id, "Message de demande d'avis rédigé", "ok")
    exports = {"json": f"/outputs/avis/{paths['json'].name}"}
    return "Message d'avis Google prêt à copier", exports


def _run_crm(run_id: str):
    activity.add_step(run_id, "Lecture des devis générés", "info")
    crm = build_pipeline(RACINE)
    items = crm.get("items", []) or []
    stats = crm.get("stats", {}) or {}
    statuses = crm.get("statuses", {}) or {}
    activity.add_step(run_id, f"Pipeline reconstruit : {len(items)} devis suivis", "ok")
    detail = " · ".join(f"{statuses.get(k, k)} : {v}" for k, v in stats.items() if v)
    summary = f"Pipeline commercial : {len(items)} devis suivis"
    if detail:
        summary += f" ({detail})"
    return summary, {}


def _run_acquisition(run_id: str):
    activity.add_step(run_id, "Vérification de la clé IA…", "info")
    cfg = charger_config_leads(_config_leads())
    provider = cfg.llm_provider
    if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        activity.add_step(run_id, "Clé ANTHROPIC_API_KEY absente dans .env", "error")
        return "Clé IA manquante (ANTHROPIC_API_KEY)", {}
    if provider == "openai_compat":
        base = (cfg.llm_base_url or "").lower()
        local = any(x in base for x in ("localhost", "127.0.0.1", ":11434"))
        if not local and not os.environ.get(cfg.llm_api_key_env):
            activity.add_step(run_id, f"Clé {cfg.llm_api_key_env} absente dans .env", "error")
            return f"Clé IA manquante ({cfg.llm_api_key_env})", {}
    activity.add_step(run_id, f"IA prête (fournisseur : {provider})", "ok")

    def on_step(message: str) -> None:
        activity.add_step(run_id, message, "info")

    # Mode test : on qualifie un échantillon pour voir l'agent travailler vite.
    # Le run quotidien (cron) appelle run(cfg) sans limite et traite tout.
    resultat = run_leads_pipeline(cfg, on_step=on_step, limite_opportunites=6)
    scannes = resultat.get("scannes", 0)
    echantillon = resultat.get("echantillon", scannes)
    livres = resultat.get("livres", 0)
    cout = resultat.get("cost")
    cout_txt = "0 $ (IA gratuite)"
    if isinstance(cout, dict):
        valeur = cout.get("usd") or cout.get("usd_total") or cout.get("cout_usd") or 0
        cout_txt = f"{valeur} $" if valeur else "0 $ (IA gratuite)"
    elif isinstance(cout, (int, float)):
        cout_txt = f"{cout} $" if cout else "0 $ (IA gratuite)"

    exports = {}
    if (RACINE / "outputs" / "index.html").exists():
        exports["leads (HTML)"] = "/outputs/index.html"
    activity.add_step(
        run_id,
        f"{scannes} opportunité(s) scannée(s) · échantillon de {echantillon} qualifié → {livres} lead(s)",
        "ok",
    )
    return (
        f"{livres} lead(s) sur un échantillon de {echantillon} (sur {scannes} scannées) · coût {cout_txt}",
        exports,
    )


def _run_vocal(run_id: str):
    activity.add_step(run_id, "Préparation d'un mémo vocal de démonstration", "info")
    dossier = RACINE / "outputs" / "activity"
    dossier.mkdir(parents=True, exist_ok=True)
    audio = dossier / "memo_demo.aiff"
    if not _synthese_vocale(audio, PHRASE_VOCALE_DEMO):
        activity.add_step(
            run_id,
            "Synthèse vocale du Mac indisponible : dépose un fichier audio pour tester cet agent",
            "warn",
        )
        return "Agent vocal : fournis un mémo audio à transcrire", {}
    activity.add_step(run_id, "Mémo vocal prêt (voix de synthèse du Mac)", "ok")
    activity.add_step(run_id, "Chargement du modèle de transcription (peut être long au 1er lancement)…", "info")
    texte = transcrire(audio, model="base")
    court = (texte[:160] + "…") if len(texte) > 160 else (texte or "(aucun texte détecté)")
    activity.add_step(run_id, f"Texte transcrit : « {court} »", "ok")
    activity.add_step(run_id, "À relire par l'artisan avant tout devis (human-in-the-loop)", "info")
    return f"Transcription : « {court} »", {}


def _synthese_vocale(audio: Path, phrase: str) -> bool:
    """Génère un mémo audio avec la synthèse vocale macOS. Renvoie False si indisponible."""
    for cmd in (["say", "-v", "Thomas", "-o", str(audio), phrase], ["say", "-o", str(audio), phrase]):
        try:
            subprocess.run(cmd, check=True, timeout=30, capture_output=True)
            return audio.exists()
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return False


# ---- Catalogue + orchestration ---------------------------------------------------------

CATALOG = [
    {"key": "devis", "nom": "Agent Devis", "offre": "Fondation",
     "role": "Transforme une demande client en devis chiffré, prêt à imprimer en PDF.",
     "tache": "Devis salle de bain 6 m² à Nantes", "runner": _run_devis},
    {"key": "vocal", "nom": "Agent Vocal", "offre": "Fondation",
     "role": "Transcrit un mémo vocal d'artisan en texte (puis brouillon de devis).",
     "tache": "Transcrire un mémo vocal de démonstration", "runner": _run_vocal},
    {"key": "facture", "nom": "Agent Factures", "offre": "Fondation",
     "role": "Transforme un devis validé en facture d'acompte ou de solde.",
     "tache": "Facture d'acompte depuis le dernier devis", "runner": _run_facture},
    {"key": "relance", "nom": "Agent Relances", "offre": "Fondation",
     "role": "Génère les relances J+3, J+7 et J+15 à partir d'un devis.",
     "tache": "Relances du dernier devis", "runner": _run_relance},
    {"key": "avis", "nom": "Agent Avis Google", "offre": "Fondation",
     "role": "Rédige le message de demande d'avis Google après un chantier.",
     "tache": "Message d'avis pour un client", "runner": _run_avis},
    {"key": "crm", "nom": "Mini CRM", "offre": "Fondation",
     "role": "Suit chaque devis : envoyé, relancé, signé ou perdu.",
     "tache": "Rafraîchir le pipeline commercial", "runner": _run_crm},
    {"key": "acquisition", "nom": "Agent Acquisition", "offre": "Croissance",
     "role": "Trouve des chantiers à démarcher autour de Nantes (open data + IA), et les note.",
     "tache": "Scanner les chantiers du jour autour de Nantes", "runner": _run_acquisition},
]

_BY_KEY = {entry["key"]: entry for entry in CATALOG}


def catalog_public() -> list[dict]:
    """Catalogue sans les fonctions runner (sérialisable pour le navigateur)."""
    return [{k: v for k, v in entry.items() if k != "runner"} for entry in CATALOG]


def _execute(run_id: str, entry: dict) -> None:
    try:
        result = entry["runner"](run_id)
        summary, exports = result if result else ("", {})
        activity.finish_run(run_id, "done", summary, exports)
    except Exception as exc:  # un agent qui plante ne doit jamais tuer le dashboard
        activity.add_step(run_id, f"Erreur : {exc}", "error")
        activity.finish_run(run_id, "error", f"Échec : {exc}")


def start_run(agent_key: str) -> str:
    """Démarre un agent dans un thread dédié. Lève KeyError si l'agent est inconnu."""
    entry = _BY_KEY[agent_key]
    run_id = activity.new_run(entry["key"], entry["nom"], entry["tache"])
    threading.Thread(target=_execute, args=(run_id, entry), daemon=True).start()
    return run_id
