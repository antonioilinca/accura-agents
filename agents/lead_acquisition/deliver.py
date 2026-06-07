"""Livraison : déduplication historique, écriture du JSON typé et du récap lisible.

L'historique (_seen.json) garantit qu'un même chantier n'est jamais livré deux fois,
même sur plusieurs jours. HubSpot et la notification WhatsApp sont prévus en V2 (stubs).
"""

from __future__ import annotations

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
    aujourd = date.today().isoformat()

    nouveaux = [
        l for l in qualifies
        if l.score >= cfg.seuil_livraison and l.raw.dedup_key not in seen
    ]

    payload = {
        "date": aujourd,
        "metier": cfg.metier.nom,
        "zone": cfg.communes,
        "seuil": cfg.seuil_livraison,
        "stats": {
            "scannes": scannes,
            "tries": tries,
            "qualifies": len(qualifies),
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
    cout = payload["cout"].get("cout_usd_estime", 0)
    lignes = [
        f"# Récap leads {cfg.metier.libelle} — {payload['date']}",
        "",
        f"- Scannés : {s['scannes']}  |  Triés : {s['tries']}  |  "
        f"Qualifiés : {s['qualifies']}  |  **Livrés (>= {cfg.seuil_livraison}) : {s['livres']}**",
        f"- Coût estimé de ce run : ~{cout} USD",
        "",
    ]
    if not nouveaux:
        lignes.append("_Aucun nouveau lead au-dessus du seuil aujourd'hui._")
        return "\n".join(lignes)

    lignes.append("## Leads livrés (du meilleur au moins bon)")
    lignes.append("")
    for l in nouveaux:
        d = l.to_dict()
        message = " ".join(d["message_contact"].split())
        lignes += [
            f"### {d['score']}/100 — {d['commune'] or 'commune ?'} — {d.get('type_dossier') or ''}",
            f"- Adresse : {d['adresse'] or 'inconnue'}",
            f"- Projet : {d['description']}",
            f"- Signaux : {d['signaux']}",
            f"- Pourquoi : {d['justification']}",
            f"- Brouillon de contact : {message}",
            "",
        ]
    return "\n".join(lignes)
