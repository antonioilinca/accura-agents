"""Exports JSON, Markdown et HTML imprimable pour l'agent devis."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .models import QuoteDocument


CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:#172033;background:#f3f5f7;margin:0}
.page{max-width:920px;margin:28px auto;background:#fff;padding:34px;border:1px solid #d9dee7}
.top{display:flex;justify-content:space-between;gap:24px;border-bottom:2px solid #172033;padding-bottom:18px}
h1{font-size:28px;margin:0 0 8px}.muted{color:#64748b}.box{background:#f8fafc;border:1px solid #e2e8f0;padding:14px;margin:20px 0}
table{width:100%;border-collapse:collapse;margin-top:18px}th,td{border-bottom:1px solid #e2e8f0;padding:10px;text-align:left}th{background:#f8fafc}
.right{text-align:right}.total{font-size:18px;font-weight:700}.questions{border-left:4px solid #d97706;padding-left:12px}
@media print{body{background:#fff}.page{margin:0;border:0}.no-print{display:none}}
"""


def ecrire_exports(doc: QuoteDocument, dossier: Path) -> dict[str, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    base = dossier / doc.id_devis.lower()
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    html_path = base.with_suffix(".html")
    json_path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(rendre_markdown(doc), encoding="utf-8")
    html_path.write_text(rendre_html(doc), encoding="utf-8")
    (dossier / "dernier-devis.html").write_text(rendre_html(doc), encoding="utf-8")
    return {"json": json_path, "markdown": md_path, "html": html_path}


def rendre_markdown(doc: QuoteDocument) -> str:
    d = doc.demande
    lignes = [
        f"# Devis {doc.id_devis}",
        "",
        f"**Date :** {doc.date_creation}",
        f"**Artisan :** {doc.artisan.nom}",
        f"**Chantier :** {d.type_chantier} — {d.ville or 'ville à préciser'}",
        "",
        "## Résumé chantier",
        "",
        f"- Métier : {d.metier_libelle}",
        f"- Adresse : {d.adresse or 'à préciser'}",
        f"- Surface : {d.surface_m2 or 'à préciser'} m²",
        f"- Urgence : {d.urgence}",
        f"- Prestations : {', '.join(d.prestations) if d.prestations else 'à préciser'}",
        f"- Matériaux probables : {', '.join(d.materiaux_probables) if d.materiaux_probables else 'à valider'}",
        "",
    ]
    if d.questions:
        lignes += ["## Questions à poser", ""]
        lignes += [f"- {q}" for q in d.questions]
        lignes.append("")

    lignes += ["## Lignes de devis", "", "| Poste | Qté | Unité | PU HT | Total HT |", "|---|---:|---|---:|---:|"]
    for l in doc.lignes:
        lignes.append(f"| {l.libelle} | {l.quantite} | {l.unite} | {l.prix_unitaire_ht} € | {l.total_ht} € |")
    lignes += [
        "",
        f"**Total HT : {doc.totaux.total_ht} €**",
        f"**TVA : {doc.totaux.tva} €**",
        f"**Total TTC : {doc.totaux.total_ttc} €**",
        f"**Acompte recommandé : {doc.totaux.acompte_ttc} € TTC**",
        "",
        "## Conditions",
        "",
    ]
    lignes += [f"- {c}" for c in doc.conditions]
    lignes += ["", "## Message client", "", doc.message_client, ""]
    return "\n".join(lignes)


def rendre_html(doc: QuoteDocument) -> str:
    d = doc.demande
    rows = "\n".join(
        f"<tr><td>{html.escape(l.libelle)}<br><small>{html.escape(l.description)}</small></td>"
        f"<td class='right'>{l.quantite}</td><td>{html.escape(l.unite)}</td>"
        f"<td class='right'>{l.prix_unitaire_ht} €</td><td class='right'>{l.total_ht} €</td></tr>"
        for l in doc.lignes
    )
    questions = ""
    if d.questions:
        questions = "<div class='box questions'><h2>Questions à poser</h2><ul>" + "".join(
            f"<li>{html.escape(q)}</li>" for q in d.questions
        ) + "</ul></div>"
    conditions = "".join(f"<li>{html.escape(c)}</li>" for c in doc.conditions)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Devis {html.escape(doc.id_devis)}</title><style>{CSS}</style></head>
<body><main class="page">
<div class="top"><div><h1>Devis {html.escape(doc.id_devis)}</h1>
<p class="muted">{html.escape(doc.date_creation)} · {html.escape(doc.statut)}</p></div>
<div><strong>{html.escape(doc.artisan.nom)}</strong><br>{html.escape(doc.artisan.adresse)}<br>
{html.escape(doc.artisan.telephone)} · {html.escape(doc.artisan.email)}<br>SIRET : {html.escape(doc.artisan.siret)}</div></div>
<div class="box"><strong>Résumé chantier</strong><br>
{html.escape(d.type_chantier)} · {html.escape(d.metier_libelle)}<br>
Lieu : {html.escape(d.adresse or d.ville or 'à préciser')} · Surface : {html.escape(str(d.surface_m2 or 'à préciser'))} m²<br>
Prestations : {html.escape(', '.join(d.prestations) if d.prestations else 'à préciser')}</div>
{questions}
<table><thead><tr><th>Poste</th><th class="right">Qté</th><th>Unité</th><th class="right">PU HT</th><th class="right">Total HT</th></tr></thead><tbody>{rows}</tbody></table>
<p class="right">Total HT : <strong>{doc.totaux.total_ht} €</strong><br>TVA : <strong>{doc.totaux.tva} €</strong><br>
<span class="total">Total TTC : {doc.totaux.total_ttc} €</span><br>Acompte recommandé : {doc.totaux.acompte_ttc} € TTC</p>
<div class="box"><strong>Message prêt à envoyer</strong><br>{html.escape(doc.message_client)}</div>
<h2>Conditions</h2><ul>{conditions}</ul>
<button class="no-print" onclick="window.print()">Imprimer / enregistrer en PDF</button>
</main></body></html>"""

