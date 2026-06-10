"""Exports JSON, Markdown et HTML imprimable pour les factures Accura."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .models import InvoiceDocument


CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:#172033;background:#eef2f6;margin:0}
.page{max-width:900px;margin:28px auto;background:#fff;padding:38px;border:1px solid #d9dee7;box-shadow:0 12px 36px rgba(15,23,42,.08)}
.top{display:flex;justify-content:space-between;gap:28px;border-bottom:3px solid #172033;padding-bottom:22px}
.brand{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:700}
.identity{display:flex;align-items:flex-start;gap:16px}.artisan-logo{max-width:132px;max-height:78px;object-fit:contain;border:1px solid #e2e8f0;padding:7px;background:#fff}
h1{font-size:34px;margin:4px 0 8px;letter-spacing:0}h2{font-size:17px;margin:0 0 10px}
.muted{color:#64748b}.company{text-align:right;line-height:1.45;font-size:13px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:22px 0}
.box{background:#f8fafc;border:1px solid #e2e8f0;padding:16px;border-radius:8px}.box p{margin:0;line-height:1.5}
.label{font-size:12px;color:#64748b;text-transform:uppercase;font-weight:700;letter-spacing:.04em}
table{width:100%;border-collapse:collapse;margin-top:18px}th,td{border-bottom:1px solid #e2e8f0;padding:12px 10px;text-align:left;vertical-align:top}
th{background:#f8fafc;color:#475569;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
small{color:#64748b}.right{text-align:right}.total-box{margin-left:auto;margin-top:18px;max-width:380px}
.total-line{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #e2e8f0}
.grand-total{font-size:20px;font-weight:800;color:#0f172a}.footer{margin-top:24px;color:#64748b;font-size:12px;line-height:1.5}
@media print{body{background:#fff}.page{margin:0;border:0;box-shadow:none}.no-print{display:none}}
@media(max-width:760px){.page{margin:0;padding:22px}.top,.grid{grid-template-columns:1fr;display:grid}.company{text-align:left}.total-box{max-width:none}}
"""


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
    json_path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(rendre_markdown(doc), encoding="utf-8")
    html_path.write_text(rendre_html(doc), encoding="utf-8")
    (dossier / "derniere-facture.html").write_text(rendre_html(doc), encoding="utf-8")
    return {"json": json_path, "markdown": md_path, "html": html_path}


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
            f"| {line.libelle} | {_qty(line.quantite)} | {line.unite} | "
            f"{_eur(line.prix_unitaire_ht)} | {_eur(line.total_ht)} |"
        )
    lignes += ["", f"**Total HT : {_eur(doc.totaux.total_ht)}**"]
    if doc.franchise_tva:
        lignes.append("**TVA non applicable, art. 293 B du CGI**")
    else:
        lignes.append(f"**TVA : {_eur(doc.totaux.tva)}**")
    lignes.append(f"**Total TTC à régler : {_eur(doc.totaux.total_ttc)}**")
    if doc.type_facture == "solde":
        lignes.append(f"**Déjà facturé : {_eur(doc.totaux.deja_facture_ttc)} TTC**")
    lignes += ["", "## Conditions", ""]
    lignes += [f"- {c}" for c in doc.conditions]
    if doc.mentions_legales:
        lignes += ["", "## Mentions légales", ""]
        lignes += [f"- {m}" for m in doc.mentions_legales]
    return "\n".join(lignes) + "\n"


def rendre_html(doc: InvoiceDocument) -> str:
    rows = "\n".join(
        f"<tr><td>{html.escape(line.libelle)}<br><small>{html.escape(line.description)}</small></td>"
        f"<td class='right'>{_qty(line.quantite)}</td><td>{html.escape(line.unite)}</td>"
        f"<td class='right'>{_eur(line.prix_unitaire_ht)}</td><td class='right'>{_eur(line.total_ht)}</td></tr>"
        for line in doc.lignes
    )
    logo = _logo_html(doc.artisan.logo_path, doc.artisan.nom)
    conditions = "".join(f"<li>{html.escape(c)}</li>" for c in doc.conditions)
    deja_facture = ""
    if doc.type_facture == "solde":
        deja_facture = (
            f"<div class='total-line'><span>Déjà facturé</span>"
            f"<strong>{_eur(doc.totaux.deja_facture_ttc)} TTC</strong></div>"
        )
    if doc.franchise_tva:
        ligne_tva = (
            "<div class='total-line'><span>TVA</span>"
            "<strong>Non applicable, art. 293 B du CGI</strong></div>"
        )
    else:
        ligne_tva = (
            f"<div class='total-line'><span>TVA</span><strong>{_eur(doc.totaux.tva)}</strong></div>"
        )
    mentions = "".join(f"{html.escape(m)}<br>" for m in doc.mentions_legales)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Facture {html.escape(doc.id_facture)}</title><style>{CSS}</style></head>
<body><main class="page">
<div class="top"><div><div class="brand">Facture travaux</div><h1>Facture {html.escape(doc.id_facture)}</h1>
<p class="muted">Date d'émission : {html.escape(doc.date_creation)} · Date d'échéance : {html.escape(doc.date_echeance or doc.date_creation)} · Devis source : {html.escape(doc.id_devis)}</p></div>
<div class="identity">{logo}<div class="company"><strong>{html.escape(doc.artisan.nom)}</strong><br>{html.escape(doc.artisan.adresse)}<br>
{html.escape(doc.artisan.telephone)} · {html.escape(doc.artisan.email)}<br>SIRET : {html.escape(doc.artisan.siret)}<br>{html.escape(doc.artisan.assurance_decennale)}</div></div></div>
<section class="grid">
<div class="box"><div class="label">Client</div><p>{html.escape(doc.client_nom)}</p></div>
<div class="box"><div class="label">Chantier</div><p>{html.escape(doc.chantier)}<br>Type : {html.escape(doc.type_facture)}</p></div>
</section>
<table><thead><tr><th>Poste</th><th class="right">Qté</th><th>Unité</th><th class="right">PU HT</th><th class="right">Total HT</th></tr></thead><tbody>{rows}</tbody></table>
<div class="total-box">
<div class="total-line"><span>Total HT</span><strong>{_eur(doc.totaux.total_ht)}</strong></div>
{ligne_tva}
{deja_facture}
<div class="total-line grand-total"><span>Total TTC à régler</span><strong>{_eur(doc.totaux.total_ttc)}</strong></div>
</div>
<h2>Conditions</h2><ul>{conditions}</ul>
<p class="footer">{mentions}Document généré à partir du devis validé. Les montants facturés proviennent du devis source et ne sont pas modifiés par une IA.</p>
<button class="no-print" onclick="window.print()">Imprimer / enregistrer en PDF</button>
</main></body></html>"""


def _file_stem(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _eur(value) -> str:
    txt = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
    return f"{txt} €"


def _qty(value) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(value).replace(".", ",")


def _logo_html(logo_path: str, artisan_name: str) -> str:
    src = _logo_src(logo_path)
    if not src:
        return ""
    return f"<img class='artisan-logo' src='{html.escape(src)}' alt='Logo {html.escape(artisan_name)}'>"


def _logo_src(logo_path: str) -> str:
    path = str(logo_path or "").strip().replace("\\", "/")
    if not path:
        return ""
    if path.startswith("outputs/"):
        return "../" + path.removeprefix("outputs/")
    if path.startswith("/outputs/"):
        return path
    return path

