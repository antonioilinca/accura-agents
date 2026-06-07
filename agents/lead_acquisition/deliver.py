"""Livraison : déduplication historique, écriture du JSON typé et du récap lisible.

L'historique (_seen.json) garantit qu'un même chantier n'est jamais livré deux fois,
même sur plusieurs jours. HubSpot et la notification WhatsApp sont prévus en V2 (stubs).
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import date
from pathlib import Path

from .config import Config
from .html_report import rendre_html
from .models import QualifiedLead

log = logging.getLogger(__name__)


def _charger_seen(chemin: Path) -> dict:
    if chemin.exists():
        try:
            return json.loads(chemin.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("_seen.json illisible, réinitialisé")
    return {}


def _semaine_iso(jour: date | str) -> str:
    if isinstance(jour, str):
        jour = date.fromisoformat(jour)
    annee, semaine, _ = jour.isocalendar()
    return f"{annee}-W{semaine:02d}"


def _livres_cette_semaine(seen: dict, semaine: str) -> int:
    total = 0
    for valeur in seen.values():
        if isinstance(valeur, dict):
            valeur = valeur.get("date")
        if not isinstance(valeur, str):
            continue
        try:
            if _semaine_iso(valeur) == semaine:
                total += 1
        except ValueError:
            continue
    return total


def livrer(
    cfg: Config,
    qualifies: list[QualifiedLead],
    cout: dict,
    scannes: int,
    tries: int,
) -> tuple[Path, str, list[QualifiedLead]]:
    cfg.dossier_sortie.mkdir(parents=True, exist_ok=True)
    seen_path = cfg.dossier_sortie / "_seen.json"
    seen = _charger_seen(seen_path)
    date_run = date.today()
    aujourd = date_run.isoformat()
    semaine = _semaine_iso(date_run)
    deja_livres_semaine = _livres_cette_semaine(seen, semaine)
    places_semaine = max(0, cfg.objectif_hebdo_max - deja_livres_semaine)

    eligibles = [
        l for l in qualifies
        if l.score >= cfg.seuil_livraison and l.raw.dedup_key not in seen
    ]
    nouveaux = eligibles[:places_semaine]

    payload = {
        "date": aujourd,
        "semaine": semaine,
        "metier": cfg.metier.nom,
        "zone": cfg.communes,
        "seuil": cfg.seuil_livraison,
        "promesse_accura": {
            "offre": "Croissance",
            "objectif_hebdo_min": cfg.objectif_hebdo_min,
            "objectif_hebdo_max": cfg.objectif_hebdo_max,
            "deja_livres_cette_semaine": deja_livres_semaine,
            "livres_cette_semaine": deja_livres_semaine + len(nouveaux),
            "places_restantes_cette_semaine": max(
                0, cfg.objectif_hebdo_max - deja_livres_semaine - len(nouveaux)
            ),
            "candidats_eligibles_ce_run": len(eligibles),
        },
        "stats": {
            "scannes": scannes,
            "tries": tries,
            "qualifies": len(qualifies),
            "eligibles": len(eligibles),
            "livres": len(nouveaux),
        },
        "cout": cout,
        "leads": [l.to_dict() for l in nouveaux],
    }

    json_path = cfg.dossier_sortie / f"leads-{aujourd}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for l in nouveaux:
        seen[l.raw.dedup_key] = aujourd
    seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")

    _mettre_a_jour_suivi(cfg, nouveaux, aujourd, semaine)
    _ecrire_bilan_croissance(cfg, aujourd, semaine, payload, nouveaux)

    recap = _recap(cfg, payload, nouveaux)
    (cfg.dossier_sortie / f"recap-{aujourd}.md").write_text(recap, encoding="utf-8")

    # Page HTML visuelle (pour Younès / l'artisan). index.html = toujours la plus récente.
    page = rendre_html(payload)
    (cfg.dossier_sortie / f"leads-{aujourd}.html").write_text(page, encoding="utf-8")
    (cfg.dossier_sortie / "index.html").write_text(page, encoding="utf-8")

    # --- V2 (non actif) : pousser les leads vers HubSpot (gratuit) + notifier WhatsApp ---
    # _push_hubspot(nouveaux)
    # _notifier_whatsapp(recap)

    return json_path, recap, nouveaux


def _recap(cfg: Config, payload: dict, nouveaux: list[QualifiedLead]) -> str:
    s = payload["stats"]
    promesse = payload.get("promesse_accura", {}) or {}
    cout = payload["cout"].get("cout_usd_estime", 0)
    lignes = [
        f"# Récap leads {cfg.metier.libelle} — {payload['date']}",
        "",
        f"- Scannés : {s['scannes']}  |  Triés : {s['tries']}  |  "
        f"Qualifiés : {s['qualifies']}  |  Éligibles : {s.get('eligibles', 0)}  |  "
        f"**Livrés (>= {cfg.seuil_livraison}) : {s['livres']}**",
        f"- Promesse Croissance : {promesse.get('livres_cette_semaine', s['livres'])}/"
        f"{promesse.get('objectif_hebdo_max', cfg.objectif_hebdo_max)} prospect(s) livré(s) cette semaine",
        f"- Coût estimé de ce run : ~{cout} USD",
        "",
    ]
    if not nouveaux:
        if promesse.get("places_restantes_cette_semaine", 0) == 0:
            lignes.append("_Objectif hebdomadaire déjà atteint. Aucun nouveau prospect livré aujourd'hui._")
        else:
            lignes.append("_Aucun nouveau prospect exploitable au-dessus du seuil aujourd'hui._")
        return "\n".join(lignes)

    lignes.append("## Leads livrés (du meilleur au moins bon)")
    lignes.append("")
    for l in nouveaux:
        d = l.to_dict()
        message = " ".join(d["message_contact"].split())
        lignes += [
            f"### {d['score']}/100 — {d['commune'] or 'commune ?'} — {d.get('type_dossier') or ''}",
            f"- Adresse : {d['adresse'] or 'inconnue'}",
            f"- Type : {d.get('type_opportunite', 'opportunité à démarcher')} · "
            f"Canal : {d.get('canal_recommande', 'à vérifier')} · "
            f"Urgence : {d.get('urgence_contact', 'cette semaine')} · "
            f"Valeur potentielle : {d.get('valeur_potentielle', 'inconnue')}",
            f"- Projet : {d['description']}",
            f"- Signaux : {d['signaux']}",
            f"- Pourquoi : {d['justification']}",
            f"- Angle d'approche : {d.get('angle_approche') or 'à adapter'}",
            f"- Prochaine action : {d.get('prochaine_action') or 'à contacter'}",
            f"- Brouillon de contact : {message}",
            f"- Script appel/visite : {' '.join((d.get('script_appel') or '').split())}",
            "",
        ]
    return "\n".join(lignes)


def _mettre_a_jour_suivi(
    cfg: Config,
    nouveaux: list[QualifiedLead],
    aujourd: str,
    semaine: str,
) -> None:
    if not nouveaux:
        return
    chemin = cfg.dossier_sortie / f"suivi-prospects-{cfg.metier.nom}.csv"
    champs = [
        "id", "date_livraison", "semaine", "statut", "metier", "score",
        "commune", "adresse", "type_opportunite", "canal_recommande",
        "urgence_contact", "valeur_potentielle", "prochaine_action",
        "source", "id_source",
    ]
    ids_existants: set[str] = set()
    if chemin.exists():
        with chemin.open("r", encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                if ligne.get("id"):
                    ids_existants.add(ligne["id"])

    mode = "a" if chemin.exists() else "w"
    with chemin.open(mode, encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=champs)
        if mode == "w":
            writer.writeheader()
        for lead in nouveaux:
            identifiant = lead.raw.dedup_key
            if identifiant in ids_existants:
                continue
            writer.writerow({
                "id": identifiant,
                "date_livraison": aujourd,
                "semaine": semaine,
                "statut": "a_contacter",
                "metier": lead.metier,
                "score": lead.score,
                "commune": lead.raw.commune,
                "adresse": lead.raw.adresse,
                "type_opportunite": lead.type_opportunite,
                "canal_recommande": lead.canal_recommande,
                "urgence_contact": lead.urgence_contact,
                "valeur_potentielle": lead.valeur_potentielle,
                "prochaine_action": lead.prochaine_action,
                "source": lead.raw.source,
                "id_source": lead.raw.external_id,
            })


def _ecrire_bilan_croissance(
    cfg: Config,
    aujourd: str,
    semaine: str,
    payload: dict,
    nouveaux: list[QualifiedLead],
) -> None:
    promesse = payload.get("promesse_accura", {}) or {}
    lignes = [
        f"# Bilan Croissance — {cfg.metier.libelle} — {semaine}",
        "",
        f"- Date du dernier run : {aujourd}",
        f"- Objectif vendu : {cfg.objectif_hebdo_min} à {cfg.objectif_hebdo_max} prospects qualifiés / semaine",
        f"- Livrés cette semaine : {promesse.get('livres_cette_semaine', len(nouveaux))}",
        f"- Restants avant plafond : {promesse.get('places_restantes_cette_semaine', 0)}",
        f"- Candidats éligibles sur le dernier run : {promesse.get('candidats_eligibles_ce_run', 0)}",
        "",
        "## Nouveaux prospects à traiter",
        "",
    ]
    if not nouveaux:
        lignes.append("_Aucun nouveau prospect livré sur ce run._")
    for lead in nouveaux:
        d = lead.to_dict()
        lignes += [
            f"### {d['score']}/100 — {d.get('commune') or 'commune ?'} — {d.get('adresse') or 'adresse ?'}",
            f"- Statut initial : a_contacter",
            f"- Canal recommandé : {d.get('canal_recommande')}",
            f"- Urgence : {d.get('urgence_contact')}",
            f"- Prochaine action : {d.get('prochaine_action')}",
            "",
        ]

    lignes += [
        "",
        "## Statuts à tenir à jour",
        "",
        "`a_contacter` → `contacte` → `relance` → `devis_envoye` → `signe` ou `perdu`",
        "",
        "Ce fichier sert à prouver la valeur Accura : prospects livrés, actions faites, devis générés, chantiers signés.",
    ]
    (cfg.dossier_sortie / f"bilan-croissance-{semaine}.md").write_text(
        "\n".join(lignes), encoding="utf-8"
    )
