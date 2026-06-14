"""Exports JSON, Markdown, HTML imprimable et PDF pour les factures Accura."""

from __future__ import annotations

import html
import json
from pathlib import Path

from agents.common.doc_style import CSS, actions_html, eur, logo_html, qty
from agents.common.pdf import html_to_pdf

from .models import InvoiceDocument


def ecrire_exports(doc: InvoiceDocument, dossier: Path, ecraser: bool = False) -> dict[str, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    base = dossier / _file_stem(doc.id_facture)
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    html_path = base.with_suffix(".html")
    if json_path.exists() and not ecraser:
        raise FileExistsError(
            f"La facture {doc.id_facture} existe déjà ({json_path.name}). "
            "Une facture émise ne se remplace pas : générer une nouvelle facture "
            "(ou un avoir) plutôt que d'écraser celle-ci."
        )
    html_str = rendre_html(doc)
    json_path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(rendre_markdown(doc), encoding="utf-8")
    html_path.write_text(html_str, encoding="utf-8")
    (dossier / "derniere-facture.html").write_text(html_str, encoding="utf-8")

    exports = {"json": json_path, "markdown": md_path, "html": html_path}

    pdf_bytes = html_to_pdf(html_str, base_url=str(dossier))
    if pdf_bytes:
        pdf_path = base.with_suffix(".pdf")
        pdf_path.write_bytes(pdf_bytes)
        (dossier / "derniere-facture.pdf").write_bytes(pdf_bytes)
        exports["pdf"] = pdf_path
    return exports


def rendre_markdown(doc: InvoiceDocument) -> str:
    lignes = [
        f"# Facture {doc.id_facture}",
        "",
        f"**Date d'émission :** {doc.date_creation}",
        f"**Date d'échéance :** {doc.date_echeance or doc.date_creation}",
        f"**Type :** {doc.type_facture}",
        f"**Devis source :** {doc.id_devis}",
        f"**Artisan :** {doc.artisan.nom}",
        f"**Client :** {doc.client_nom}",
        f"**Chantier :** {doc.chantier}",
        "",
        "## Lignes",
        "",
        "| Poste | Qté | Unité | PU HT | Total HT |",
        "|---|---:|---|---:|---:|",
    ]
    for line in doc.lignes:
        lignes.append(
            f"| {line.libelle} | {qty(line.quantite)} | {line.unite} | "
            f"{eur(line.prix_unitaire_ht)} | {eur(line.total_ht)} |"
        )
    lignes += ["", f"**Total HT : {eur(doc.totaux.total_ht)}**"]
    if doc.franchise_tva:
        lignes.append("**TVA non applicable, art. 293 B du CGI**")
    else:
        lignes.append(f"**TVA : {eur(doc.totaux.tva)}**")
    lignes.append(f"**Total TTC à régler : {eur(doc.totaux.total_ttc)}**")
    if doc.type_facture == "solde":
        lignes.append(f"**Déjà facturé : {eur(doc.totaux.deja_facture_ttc)} TTC**")
    lignes += ["", "## Conditions", ""]
    lignes += [f"- {c}" for c in doc.conditions]
    if doc.mentions_legales:
        lignes += ["", "## Mentions légales", ""]
        lignes += [f"- {m}" for m in doc.mentions_legales]
    return "\n".join(lignes) + "\n"


def rendre_html(doc: InvoiceDocument) -> str:
    rows = "\n".join(
        f"<tr><td>{html.escape(line.libelle)}<span class='poste-desc'>{html.escape(line.description)}</span></td>"
        f"<td class='right'>{qty(line.quantite)}</td><td>{html.escape(line.unite)}</td>"
        f"<td class='right'>{eur(line.prix_unitaire_ht)}</td><td class='right'>{eur(line.total_ht)}</td></tr>"
        for line in doc.lignes
    )
    logo = logo_html(doc.artisan.logo_path, doc.artisan.nom)
    conditions = "".join(f"<li>{html.escape(c)}</li>" for c in doc.conditions)
    deja_facture = ""
    if doc.type_facture == "solde":
        deja_facture = (
            f"<div class='total-line'><span>Déjà facturé</span>"
            f"<strong>{eur(doc.totaux.deja_facture_ttc)} TTC</strong></div>"
        )
    if doc.franchise_tva:
        ligne_tva = (
            "<div class='total-line'><span>TVA</span>"
            "<strong>Non applicable, art. 293 B du CGI</strong></div>"
        )
    else:
        ligne_tva = (
            f"<div class='total-line'><span>TVA</span><strong>{eur(doc.totaux.tva)}</strong></div>"
        )
    mentions = "".join(f"{html.escape(m)}<br>" for m in doc.mentions_legales)
    fid = html.escape(_file_stem(doc.id_facture))
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Facture {html.escape(doc.id_facture)}</title><style>{CSS}</style></head>
<body><main class="page"><div class="accent-bar"></div><div class="inner">
<div class="top">
<div><div class="brand">Facture travaux</div><h1>Facture {html.escape(doc.id_facture)}</h1>
<p class="muted">Émise le {html.escape(doc.date_creation)} · Date d'échéance : {html.escape(doc.date_echeance or doc.date_creation)} · Devis source : {html.escape(doc.id_devis)}</p></div>
<div class="identity">{logo}<div class="company"><strong>{html.escape(doc.artisan.nom)}</strong><br>{html.escape(doc.artisan.adresse)}<br>
{html.escape(doc.artisan.telephone)} · {html.escape(doc.artisan.email)}<br>SIRET : {html.escape(doc.artisan.siret)}<br>{html.escape(doc.artisan.assurance_decennale)}</div></div>
</div>
<section class="grid">
<div class="box"><div class="label">Client</div><p>{html.escape(doc.client_nom)}</p></div>
<div class="box"><div class="label">Chantier</div><p>{html.escape(doc.chantier)}<br>Type : {html.escape(doc.type_facture)}</p></div>
</section>
<table><thead><tr><th>Poste</th><th class="right">Qté</th><th>Unité</th><th class="right">PU HT</th><th class="right">Total HT</th></tr></thead><tbody>{rows}</tbody></table>
<div class="totals"><div class="total-box">
<div class="total-line"><span>Total HT</span><strong>{eur(doc.totaux.total_ht)}</strong></div>
{ligne_tva}
{deja_facture}
<div class="grand-total"><span>Total TTC à régler</span><strong>{eur(doc.totaux.total_ttc)}</strong></div>
</div></div>
<h2>Conditions</h2><ul>{conditions}</ul>
<p class="footer">{mentions}Document généré à partir du devis validé. Les montants facturés proviennent du devis source et ne sont pas modifiés par une IA.</p>
{actions_html(fid + ".pdf")}
</div></main></body></html>"""


def _file_stem(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
