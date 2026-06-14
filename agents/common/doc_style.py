"""Style et helpers partagés des documents Accura (devis, factures).

CSS premium unique (sobre, professionnel, rassurant pour un artisan — pas un
style « startup ») + helpers de formatage. Couleurs en dur (pas de variables CSS)
pour un rendu identique à l'écran (Chrome) ET en PDF (weasyprint).

Règles tenues pour la non-régression des tests :
- logo_html garde exactement `class='artisan-logo'` et le chemin `../onboarding/...`
- aucune autre balise <img> n'est introduite (design 100 % CSS).
"""

from __future__ import annotations

import html

NBSP = " "  # espace insécable : empêche « 1 140,00 € » de se couper en fin de ligne.

CSS = """
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#0f172a;background:#eef2f6;margin:0;font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
.page{max-width:820px;margin:24px auto;background:#fff;border:1px solid #dfe5ee;border-radius:14px;box-shadow:0 18px 50px rgba(15,23,42,.10);overflow:hidden}
.accent-bar{height:6px;background:linear-gradient(90deg,#1d4ed8,#3b82f6)}
.inner{padding:42px 46px}
.top{display:flex;justify-content:space-between;gap:32px;align-items:flex-start;border-bottom:1px solid #e2e8f0;padding-bottom:24px}
.brand{font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:#1d4ed8;font-weight:800}
h1{font-size:26px;margin:6px 0 8px;letter-spacing:-.01em;line-height:1.15;word-break:break-word}
.muted{color:#64748b}
.identity{display:flex;align-items:flex-start;gap:14px}
.artisan-logo{max-width:120px;max-height:74px;object-fit:contain;border:1px solid #e2e8f0;border-radius:8px;padding:6px;background:#fff}
.company{line-height:1.5;font-size:12.5px;color:#334155;text-align:right}
.company strong{color:#0f172a;font-size:14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:24px 0}
.box{background:#f8fafc;border:1px solid #e2e8f0;padding:16px 18px;border-radius:10px}
.box p{margin:0;line-height:1.55}
.label{font-size:11px;color:#64748b;text-transform:uppercase;font-weight:800;letter-spacing:.06em;margin-bottom:6px}
table{width:100%;border-collapse:collapse;margin-top:10px}
thead th{background:#eff4ff;color:#1e3a8a;font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:800;padding:11px 12px;text-align:left}
th.right,td.right{text-align:right}
tbody td{border-bottom:1px solid #e2e8f0;padding:13px 12px;vertical-align:top}
tbody tr:nth-child(even){background:#fcfdfe}
td.right{white-space:nowrap}
.poste-desc{color:#64748b;font-size:12px;display:block;margin-top:3px}
.totals{display:flex;justify-content:flex-end;margin-top:18px}
.total-box{width:340px;max-width:100%}
.total-line{display:flex;justify-content:space-between;gap:24px;padding:9px 2px;border-bottom:1px solid #e2e8f0}
.total-line span{color:#475569}
.total-line strong{white-space:nowrap}
.grand-total{display:flex;justify-content:space-between;align-items:center;gap:24px;margin-top:10px;padding:14px 16px;background:#eff4ff;border:1px solid #dbe5ff;border-radius:10px}
.grand-total span{font-weight:700;color:#0f172a}
.grand-total strong{font-size:20px;font-weight:800;color:#1d4ed8;white-space:nowrap}
.callout{margin-top:22px;background:#f8fafc;border:1px solid #e2e8f0;border-left:3px solid #1d4ed8;padding:14px 16px;border-radius:8px;line-height:1.55}
.callout strong{display:block;margin-bottom:4px}
.questions{margin-top:8px;background:#fffbeb;border:1px solid #fde68a;border-left:3px solid #d97706;padding:14px 16px;border-radius:8px}
.questions .label{color:#b45309}
h2{font-size:15px;margin:26px 0 10px}
ul{margin:0;padding-left:20px}
li{margin:5px 0;line-height:1.5}
.signature{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:28px}
.sign-box{height:96px;border:1px dashed #cbd5e1;border-radius:10px;padding:12px;color:#64748b;font-size:12px}
.footer{margin-top:26px;padding-top:16px;border-top:1px solid #e2e8f0;color:#64748b;font-size:11.5px;line-height:1.55}
.actions{margin-top:26px;display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-block;background:#1d4ed8;color:#fff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 22px;border-radius:10px;border:0;cursor:pointer}
.btn.secondary{background:#fff;color:#0f172a;border:1px solid #cbd5e1}
@page{size:A4;margin:14mm}
@media print{
  body{background:#fff;font-size:12px}
  .page{margin:0;border:0;border-radius:0;box-shadow:none;max-width:none}
  .inner{padding:0}
  .accent-bar{display:none}
  .no-print{display:none!important}
  thead{display:table-header-group}
  tr{break-inside:avoid}
  h2{break-after:avoid}
  ul{break-inside:avoid}
  .box,.total-box,.signature,.callout,.grand-total,.questions{break-inside:avoid}
}
@media(max-width:680px){
  .inner{padding:26px 20px}
  .top{flex-direction:column;gap:16px}
  .company{text-align:left}
  .grid{grid-template-columns:1fr}
  h1{font-size:22px}
  thead th,tbody td{padding:9px 8px;font-size:12.5px}
  .total-box{width:100%}
}
"""


def eur(value) -> str:
    """Montant en euros, format français, avec espaces insécables (jamais coupé)."""
    txt = f"{float(value):,.2f}".replace(",", NBSP).replace(".", ",")
    return f"{txt}{NBSP}€"


def qty(value) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(value).replace(".", ",")


def logo_html(logo_path, artisan_name: str) -> str:
    src = logo_src(logo_path)
    if not src:
        return ""
    return f"<img class='artisan-logo' src='{html.escape(src)}' alt='Logo {html.escape(artisan_name)}'>"


def logo_src(logo_path) -> str:
    path = str(logo_path or "").strip().replace("\\", "/")
    if not path:
        return ""
    if path.startswith("outputs/"):
        return "../" + path.removeprefix("outputs/")
    if path.startswith("/outputs/"):
        return path
    return path


def actions_html(pdf_filename: str) -> str:
    """Boutons d'action (cachés à l'impression) : vrai téléchargement PDF + impression."""
    return (
        "<div class='actions no-print'>"
        f"<a class='btn' href='{html.escape(pdf_filename)}' download>Télécharger le PDF</a>"
        "<button class='btn secondary' onclick='window.print()'>Imprimer</button>"
        "</div>"
    )
