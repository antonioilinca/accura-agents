# Déployer le cockpit Accura sur un lien public (Render)

Le cockpit (`agents/dashboard`) est un serveur Python qui tourne en continu. On
l'héberge sur **Render** (gratuit, sans carte bancaire) pour avoir une URL HTTPS
fixe, accessible par Antonio et Younès, indépendante du Mac.

> Pourquoi pas Vercel : Vercel sert des sites et des fonctions courtes, pas un
> serveur qui reste allumé et garde l'activité des agents en mémoire. Render le fait.

## Ce qui tourne en ligne
- ✅ Agents Fondation : Devis, Factures, Relances, Avis Google, Mini CRM.
- ✅ Agent Acquisition (Groq gratuit) dès que `GROQ_API_KEY` est fournie.
- ⚠️ Agent Vocal : bridé en ligne (pas de synthèse vocale macOS ni Whisper côté
  serveur). Il s'affiche mais demande un fichier audio ; à utiliser en local.

## Limites du plan gratuit (à connaître)
- Le service **s'endort après 15 min** sans visite : la première ouverture
  suivante prend ~30-60 s, puis c'est instantané.
- Le **stockage est éphémère** : les devis/factures générés EN LIGNE sont effacés
  à chaque redéploiement. Parfait pour une démo interne ; pour de la vraie donnée
  client, passer à un disque persistant (payant) ou à un VPS.

## Déploiement (3 étapes)
1. Aller sur https://render.com -> **Get Started** -> se connecter avec GitHub.
2. **New** -> **Blueprint** -> choisir le dépôt `antonioilinca/accura-agents`.
   Render lit `render.yaml` et propose le service `accura-cockpit`.
3. Renseigner les 3 variables demandées, puis **Apply** :
   - `ACCURA_DASHBOARD_USER` : identifiant de connexion (ex : `accura`).
   - `ACCURA_DASHBOARD_PASSWORD` : un mot de passe fort (l'accès au cockpit).
   - `GROQ_API_KEY` : la clé Groq gratuite (pour l'agent Acquisition).

Render build puis donne l'URL : `https://accura-cockpit.onrender.com`
(protégée par identifiant + mot de passe).

## Mise à jour
`autoDeploy` est activé : chaque `git push` sur `main` redéploie automatiquement.

## Local (Mac) — inchangé
En local, rien ne change : `uv run python -m agents.dashboard.run` ouvre toujours
`http://127.0.0.1:8787` (écoute privée, sans mot de passe si non défini).
