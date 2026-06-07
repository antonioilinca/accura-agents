"""Génère une page HTML lisible des leads (pour un humain : Younès / l'artisan).

Aucune dépendance, aucun serveur : un simple fichier .html à ouvrir dans le navigateur.
"""

from __future__ import annotations

import html

CSS = """
:root { --bg:#eef1f5; --card:#ffffff; --ink:#0f172a; --muted:#64748b; --line:#e2e8f0;
        --accent:#1e40af; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--bg); color:var(--ink); line-height:1.5; padding-bottom:60px; }
header { background:linear-gradient(135deg,#0f172a,#1e3a8a); color:#fff;
         padding:32px 24px 26px; }
header .wrap { max-width:1120px; margin:0 auto; }
.brand { font-weight:700; letter-spacing:.3px; font-size:15px; opacity:.85; }
.brand span { font-weight:400; opacity:.7; }
header h1 { font-size:26px; margin:6px 0 18px; font-weight:700; text-transform:capitalize; }
.stats { display:flex; gap:14px; flex-wrap:wrap; }
.stat { background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.14);
        border-radius:12px; padding:10px 16px; min-width:90px; }
.stat b { display:block; font-size:22px; line-height:1.1; }
.stat span { font-size:12px; opacity:.8; }
main { max-width:1120px; margin:26px auto 0; padding:0 24px;
       display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:18px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:16px;
        padding:18px 18px 16px; box-shadow:0 1px 2px rgba(15,23,42,.04);
        transition:transform .12s ease, box-shadow .12s ease; display:flex; flex-direction:column; }
.card:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(15,23,42,.10); }
.card-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
.commune { font-size:18px; font-weight:700; }
.meta { font-size:12.5px; color:var(--muted); margin-top:2px; }
.score { color:#fff; font-weight:700; font-size:20px; min-width:46px; height:46px;
         border-radius:12px; display:flex; align-items:center; justify-content:center; }
.addr { font-size:13px; color:var(--muted); margin:12px 0 8px; }
.projet { font-size:14px; background:#f8fafc; border:1px solid var(--line);
          border-radius:10px; padding:10px 12px; }
.tags { display:flex; flex-wrap:wrap; gap:6px; margin:12px 0; }
.tag { font-size:11.5px; background:#eef2ff; color:#3730a3; border-radius:999px;
       padding:3px 10px; }
.tag b { font-weight:700; }
.why { font-size:13px; color:#334155; margin:2px 0 12px; }
.why b { color:var(--ink); }
.action { font-size:13px; background:#fff7ed; border:1px solid #fed7aa; border-radius:10px;
          padding:10px 12px; margin:0 0 12px; color:#431407; }
.action b { color:#9a3412; }
.contact { margin-top:auto; background:#f0f7ff; border:1px solid #cfe0fb; border-radius:10px;
           padding:10px 12px; }
.contact-head { display:flex; justify-content:space-between; align-items:center;
                font-size:12.5px; font-weight:700; color:var(--accent); margin-bottom:6px; }
.contact-head button { font:inherit; font-size:11.5px; font-weight:600; cursor:pointer;
        border:1px solid var(--accent); color:var(--accent); background:#fff;
        border-radius:8px; padding:3px 10px; }
.contact-head button:hover { background:var(--accent); color:#fff; }
.contact p { font-size:13px; color:#1e293b; }
.empty { max-width:1120px; margin:40px auto; padding:0 24px; text-align:center; color:var(--muted); }
footer { max-width:1120px; margin:30px auto 0; padding:18px 24px 0; color:var(--muted);
         font-size:12px; border-top:1px solid var(--line); }
"""

JS = """
function cp(b){
  var t = b.parentElement.nextElementSibling.innerText;
  navigator.clipboard.writeText(t).then(function(){
    var o=b.textContent; b.textContent='Copié \\u2713';
    setTimeout(function(){ b.textContent=o; },1500);
  });
}
"""


def _fr_date(iso: str) -> str:
    parts = (iso or "").split("-")
    return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else iso


def _badge(score: int) -> str:
    if score >= 80:
        return "#16a34a"
    if score >= 65:
        return "#d97706"
    return "#64748b"


def _tag(label: str, value) -> str:
    return f'<span class="tag"><b>{html.escape(label)}</b> {html.escape(str(value))}</span>'


def _carte(l: dict) -> str:
    score = int(l.get("score", 0))
    sig = l.get("signaux", {}) or {}
    surface = l.get("surface_plancher")
    surface_txt = f" · {surface:.0f} m²" if isinstance(surface, (int, float)) and surface else ""
    tags = "".join([
        _tag("Métier", sig.get("adequation_metier", "?")),
        _tag("Ampleur", sig.get("ampleur_travaux", "?")),
        _tag("Fraîcheur", sig.get("fraicheur", "?")),
        _tag("Budget", sig.get("signal_budget", "?")),
        _tag("Contact", sig.get("contactabilite", "?")),
        _tag("Canal", l.get("canal_recommande", "?")),
    ])
    return f"""<article class="card">
  <div class="card-head">
    <div>
      <div class="commune">{html.escape(l.get('commune') or 'Commune ?')}</div>
      <div class="meta">{html.escape(l.get('type_dossier') or '')}{surface_txt}</div>
    </div>
    <div class="score" style="background:{_badge(score)}">{score}</div>
  </div>
  <div class="addr">📍 {html.escape(l.get('adresse') or 'Adresse non précisée')}</div>
  <div class="projet">{html.escape(l.get('description') or '')}</div>
  <div class="tags">{tags}</div>
  <div class="why"><b>Pourquoi ce lead</b><br>{html.escape(l.get('justification') or '')}</div>
  <div class="action">
    <b>Action recommandée</b><br>{html.escape(l.get('prochaine_action') or 'À contacter')}
    <br><b>Angle</b><br>{html.escape(l.get('angle_approche') or 'À adapter')}
  </div>
  <div class="contact">
    <div class="contact-head"><span>Message de contact</span><button onclick="cp(this)">Copier</button></div>
    <p>{html.escape(l.get('message_contact') or '')}</p>
  </div>
  <div class="contact" style="margin-top:10px">
    <div class="contact-head"><span>Script appel / visite</span><button onclick="cp(this)">Copier</button></div>
    <p>{html.escape(l.get('script_appel') or '')}</p>
  </div>
</article>"""


def rendre_html(payload: dict) -> str:
    metier = payload.get("metier", "")
    date = _fr_date(payload.get("date", ""))
    s = payload.get("stats", {}) or {}
    p = payload.get("promesse_accura", {}) or {}
    cout = payload.get("cout", {}).get("cout_usd_estime", 0)
    leads = payload.get("leads", []) or []

    if leads:
        corps = '<main>' + "\n".join(_carte(l) for l in leads) + '</main>'
    else:
        corps = '<p class="empty">Aucun lead au-dessus du seuil pour cette journée.</p>'

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Leads {html.escape(metier)} — {date}</title>
<style>{CSS}</style></head><body>
<header><div class="wrap">
  <div class="brand">Accura Ouest <span>· prospects qualifiés Croissance</span></div>
  <h1>{html.escape(metier)} · {date}</h1>
  <div class="stats">
    <div class="stat"><b>{s.get('scannes', 0)}</b><span>scannés</span></div>
    <div class="stat"><b>{s.get('tries', 0)}</b><span>triés</span></div>
    <div class="stat"><b>{s.get('eligibles', 0)}</b><span>éligibles</span></div>
    <div class="stat"><b>{s.get('livres', 0)}</b><span>livrés ce run</span></div>
    <div class="stat"><b>{p.get('livres_cette_semaine', s.get('livres', 0))}/{p.get('objectif_hebdo_max', 3)}</b><span>promesse semaine</span></div>
    <div class="stat"><b>${cout}</b><span>coût du run</span></div>
  </div>
</div></header>
{corps}
<footer>Source : open data autorisations d'urbanisme Nantes Métropole (données publiques anonymisées).
Page générée automatiquement par l'agent acquisition de leads — Accura Ouest.</footer>
<script>{JS}</script>
</body></html>"""
