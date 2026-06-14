"""Exports JSON, Markdown, HTML imprimable et PDF pour l'agent devis."""

from __future__ import annotations

import html
import json
from pathlib import Path

from agents.common.doc_style import CSS, actions_html, eur, logo_html, qty
from agents.common.pdf import html_to_pdf

from .models import QuoteDocument


def ecrire_exports(doc: QuoteDocument, dossier: Path, ecraser: bool = False) -> dict[str, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    base = dossier / doc.id_devis.lower()
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    html_path = base.with_suffix(".html")
    if json_path.exists() and not ecraser:
        raise FileExistsError(
            f"Le devis {doc.id_devis} existe déjà ({json_path.name}). "
            "Fournir un identifiant explicite pour le ré-éditer volontairement."
        )
    html_str = rendre_html(doc)
    json_path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(rendre_markdown(doc), encoding="utf-8")
    html_path.write_text(html_str, encoding="utf-8")
    (dossier / "dernier-devis.html").write_text(html_str, encoding="utf-8")

    exports = {"json": json_path, "markdown": md_path, "html": html_path}

    pdf_bytes = html_to_pdf(html_str, base_url=str(dossier))
    if pdf_bytes:
        pdf_path = base.with_suffix(".pdf")
        pdf_path.write_bytes(pdf_bytes)
        (dossier / "dernier-devis.pdf").write_bytes(pdf_bytes)
        exports["pdf"] = pdf_path
    return exports


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
        f"- Résumé : {d.resume_pro or d.type_chantier}",
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
        lignes.append(f"| {l.libelle} | {qty(l.quantite)} | {l.unite} | {eur(l.prix_unitaire_ht)} | {eur(l.total_ht)} |")
    ligne_tva_md = (
        "**TVA non applicable, art. 293 B du CGI**"
        if doc.artisan.franchise_tva
        else f"**TVA : {eur(doc.totaux.tva)}**"
    )
    lignes += [
        "",
        f"**Total HT : {eur(doc.totaux.total_ht)}**",
        ligne_tva_md,
        f"**Total TTC : {eur(doc.totaux.total_ttc)}**",
        f"**Acompte recommandé : {eur(doc.totaux.acompte_ttc)} TTC**",
        "",
        "## Conditions",
        "",
    ]
    lignes += [f"- {c}" for c in doc.conditions]
    if doc.notes_artisan:
        lignes += ["", "## Notes artisan", ""]
        lignes += [f"- {n}" for n in doc.notes_artisan]
    lignes += ["", "## Message client", "", doc.message_client, ""]
    return "\n".join(lignes)


def rendre_html(doc: QuoteDocument) -> str:
    d = doc.demande
    rows = "\n".join(
        f"<tr><td>{html.escape(l.libelle)}<span class='poste-desc'>{html.escape(l.description)}</span></td>"
        f"<td class='right'>{qty(l.quantite)}</td><td>{html.escape(l.unite)}</td>"
        f"<td class='right'>{eur(l.prix_unitaire_ht)}</td><td class='right'>{eur(l.total_ht)}</td></tr>"
        for l in doc.lignes
    )
    questions = ""
    if d.questions:
        questions = (
            "<div class='questions'><div class='label'>Questions à poser avant validation</div><ul>"
            + "".join(f"<li>{html.escape(q)}</li>" for q in d.questions)
            + "</ul></div>"
        )
    conditions = "".join(f"<li>{html.escape(c)}</li>" for c in doc.conditions)
    resume = d.resume_pro or (
        f"{d.type_chantier} - {d.metier_libelle}. Prestations : "
        f"{', '.join(d.prestations) if d.prestations else 'à préciser'}."
    )
    logo = logo_html(doc.artisan.logo_path, doc.artisan.nom)
    pid = html.escape(doc.id_devis.lower())
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Devis {html.escape(doc.id_devis)}</title><style>{CSS}</style></head>
<body><main class="page"><div class="accent-bar"></div><div class="inner">
<div class="top">
<div><div class="brand">Devis travaux</div><h1>Devis {html.escape(doc.id_devis)}</h1>
<p class="muted">Émis le {html.escape(doc.date_creation)} · Validité selon conditions ci-dessous</p></div>
<div class="identity">{logo}<div class="company"><strong>{html.escape(doc.artisan.nom)}</strong><br>{html.escape(doc.artisan.adresse)}<br>
{html.escape(doc.artisan.telephone)} · {html.escape(doc.artisan.email)}<br>SIRET : {html.escape(doc.artisan.siret)}<br>{html.escape(doc.artisan.assurance_decennale)}</div></div>
</div>
<section class="grid">
<div class="box"><div class="label">Résumé chantier</div><p>{html.escape(resume)}</p></div>
<div class="box"><div class="label">Informations chantier</div><p>
Lieu : {html.escape(d.adresse or d.ville or 'à préciser')}<br>
Surface : {html.escape(str(d.surface_m2 or 'à préciser'))} m²<br>
Métier : {html.escape(d.metier_libelle)}<br>
Urgence : {html.escape(d.urgence)}</p></div>
</section>
{questions}
<table><thead><tr><th>Poste</th><th class="right">Qté</th><th>Unité</th><th class="right">PU HT</th><th class="right">Total HT</th></tr></thead><tbody>{rows}</tbody></table>
<div class="totals"><div class="total-box">
<div class="total-line"><span>Total HT</span><strong>{eur(doc.totaux.total_ht)}</strong></div>
{_ligne_tva_html(doc)}
<div class="grand-total"><span>Total TTC</span><strong>{eur(doc.totaux.total_ttc)}</strong></div>
<div class="total-line"><span>Acompte recommandé</span><strong>{eur(doc.totaux.acompte_ttc)} TTC</strong></div>
</div></div>
<div class="callout"><strong>Message prêt à envoyer</strong>{html.escape(doc.message_client)}</div>
<h2>Conditions</h2><ul>{conditions}</ul>
<section class="signature"><div class="sign-box">Bon pour accord client<br>Date et signature</div><div class="sign-box">Signature entreprise</div></section>
<p class="footer">Document généré à partir des informations transmises. Les montants restent à valider après visite technique, choix définitif des matériaux et vérification des supports.</p>
{actions_html(pid + ".pdf")}
</div></main></body></html>"""


def _ligne_tva_html(doc: QuoteDocument) -> str:
    if doc.artisan.franchise_tva:
        return (
            "<div class='total-line'><span>TVA</span>"
            "<strong>Non applicable, art. 293 B du CGI</strong></div>"
        )
    return f"<div class='total-line'><span>TVA</span><strong>{eur(doc.totaux.tva)}</strong></div>"
