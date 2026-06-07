"""Exports JSON, Markdown et HTML imprimable pour l'agent devis."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .models import QuoteDocument


CSS = """
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:#172033;background:#eef2f6;margin:0}
.page{max-width:960px;margin:28px auto;background:#fff;padding:38px;border:1px solid #d9dee7;box-shadow:0 12px 36px rgba(15,23,42,.08)}
.top{display:flex;justify-content:space-between;gap:28px;border-bottom:3px solid #172033;padding-bottom:22px}
.brand{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:700}
.identity{display:flex;align-items:flex-start;gap:16px}.artisan-logo{max-width:132px;max-height:78px;object-fit:contain;border:1px solid #e2e8f0;padding:7px;background:#fff}
h1{font-size:34px;margin:4px 0 8px;letter-spacing:0}h2{font-size:17px;margin:0 0 10px}h3{font-size:14px;margin:0 0 8px}
.muted{color:#64748b}.company{text-align:right;line-height:1.45;font-size:13px}
.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:18px;margin:22px 0}
.box{background:#f8fafc;border:1px solid #e2e8f0;padding:16px;border-radius:8px}
.box p{margin:0;line-height:1.5}.label{font-size:12px;color:#64748b;text-transform:uppercase;font-weight:700;letter-spacing:.04em}
table{width:100%;border-collapse:collapse;margin-top:18px}th,td{border-bottom:1px solid #e2e8f0;padding:12px 10px;text-align:left;vertical-align:top}
th{background:#f8fafc;color:#475569;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
small{color:#64748b}.right{text-align:right}.total-box{margin-left:auto;margin-top:18px;max-width:360px}
.total-line{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #e2e8f0}
.grand-total{font-size:20px;font-weight:800;color:#0f172a}.questions{border-left:4px solid #d97706}.footer{margin-top:24px;color:#64748b;font-size:12px;line-height:1.5}
.signature{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:26px}.sign-box{height:86px;border:1px dashed #cbd5e1;border-radius:8px;padding:10px;color:#64748b;font-size:12px}
@media print{body{background:#fff}.page{margin:0;border:0;box-shadow:none}.no-print{display:none}}
@media(max-width:760px){.page{margin:0;padding:22px}.top,.grid,.signature{grid-template-columns:1fr;display:grid}.company{text-align:left}.total-box{max-width:none}}
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
        lignes.append(f"| {l.libelle} | {_qty(l.quantite)} | {l.unite} | {_eur(l.prix_unitaire_ht)} | {_eur(l.total_ht)} |")
    lignes += [
        "",
        f"**Total HT : {_eur(doc.totaux.total_ht)}**",
        f"**TVA : {_eur(doc.totaux.tva)}**",
        f"**Total TTC : {_eur(doc.totaux.total_ttc)}**",
        f"**Acompte recommandé : {_eur(doc.totaux.acompte_ttc)} TTC**",
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
        f"<tr><td>{html.escape(l.libelle)}<br><small>{html.escape(l.description)}</small></td>"
        f"<td class='right'>{_qty(l.quantite)}</td><td>{html.escape(l.unite)}</td>"
        f"<td class='right'>{_eur(l.prix_unitaire_ht)}</td><td class='right'>{_eur(l.total_ht)}</td></tr>"
        for l in doc.lignes
    )
    questions = ""
    if d.questions:
        questions = "<div class='box questions'><h2>Questions à poser</h2><ul>" + "".join(
            f"<li>{html.escape(q)}</li>" for q in d.questions
        ) + "</ul></div>"
    conditions = "".join(f"<li>{html.escape(c)}</li>" for c in doc.conditions)
    resume = d.resume_pro or (
        f"{d.type_chantier} - {d.metier_libelle}. Prestations : "
        f"{', '.join(d.prestations) if d.prestations else 'à préciser'}."
    )
    logo = _logo_html(doc.artisan.logo_path, doc.artisan.nom)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Devis {html.escape(doc.id_devis)}</title><style>{CSS}</style></head>
<body><main class="page">
<div class="top"><div><div class="brand">Devis travaux</div><h1>Devis {html.escape(doc.id_devis)}</h1>
<p class="muted">Date d'émission : {html.escape(doc.date_creation)} · Validité selon conditions ci-dessous</p></div>
<div class="identity">{logo}<div class="company"><strong>{html.escape(doc.artisan.nom)}</strong><br>{html.escape(doc.artisan.adresse)}<br>
{html.escape(doc.artisan.telephone)} · {html.escape(doc.artisan.email)}<br>SIRET : {html.escape(doc.artisan.siret)}<br>{html.escape(doc.artisan.assurance_decennale)}</div></div></div>
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
<div class="total-box">
<div class="total-line"><span>Total HT</span><strong>{_eur(doc.totaux.total_ht)}</strong></div>
<div class="total-line"><span>TVA</span><strong>{_eur(doc.totaux.tva)}</strong></div>
<div class="total-line grand-total"><span>Total TTC</span><strong>{_eur(doc.totaux.total_ttc)}</strong></div>
<div class="total-line"><span>Acompte recommandé</span><strong>{_eur(doc.totaux.acompte_ttc)} TTC</strong></div>
</div>
<div class="box"><strong>Message prêt à envoyer</strong><br>{html.escape(doc.message_client)}</div>
<h2>Conditions</h2><ul>{conditions}</ul>
<section class="signature"><div class="sign-box">Bon pour accord client<br>Date et signature</div><div class="sign-box">Signature entreprise</div></section>
<p class="footer">Document généré à partir des informations transmises. Les montants restent à valider après visite technique, choix définitif des matériaux et vérification des supports.</p>
<button class="no-print" onclick="window.print()">Imprimer / enregistrer en PDF</button>
</main></body></html>"""


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
