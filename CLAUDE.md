# Accura Ouest — relais Claude Code

## Dossier et repo

- Projet local principal : `/Users/antonioilinca/Desktop/Claude Workspace/08-ACCURA-OUEST/accura-agents`
- Repo GitHub : `antonioilinca/accura-agents`
- Site à respecter : `https://accuraouest.com/`
- Dossier business parent : `/Users/antonioilinca/Desktop/Claude Workspace/08-ACCURA-OUEST`

Quand Antonio dit "Accura", "Accura Ouest" ou "accuraouest", travailler d'abord dans ce repo.

## Promesses commerciales à respecter

- Offre Fondation 199 €/mois : vocal WhatsApp -> devis PDF en 2 min, factures/acompte,
  relances J+3/J+7/J+15, CRM, avis Google, support WhatsApp.
- Offre Croissance 349 €/mois : Fondation + 2 à 3 prospects qualifiés/semaine.

Ne pas construire une fonctionnalité qui ne sert pas directement Fondation ou Croissance.

## Agents existants

### Agent acquisition

- Dossier : `agents/lead_acquisition`
- Commande : `uv run python -m agents.lead_acquisition.run`
- Sert la promesse Croissance.
- Dernier alignement important : `30226b0 feat: align acquisition agent with growth promise`

### Agent Devis Accura

- Dossier : `agents/devis_generator`
- Commande terminal :
  `uv run python -m agents.devis_generator.run --input "Client à Nantes, salle de bain 6m2..."`
- Sert la promesse Fondation.
- Entrée : texte brut ou transcription vocale simulée.
- Sorties : JSON, Markdown, HTML imprimable PDF dans `outputs/devis/`.
- Config : `config/devis.example.yaml`, à copier en `config/devis.yaml` pour un vrai artisan.

### Agent Factures Accura

- Dossier : `agents/facture_generator`
- Commande terminal :
  `uv run python -m agents.facture_generator.run --quote outputs/devis/ACC-...json --type acompte`
- Sert la promesse Fondation.
- Entrée : JSON d'un devis existant.
- Sorties : JSON, Markdown, HTML imprimable PDF dans `outputs/factures/`.
- Types supportés : `acompte` et `solde`.
- Important : les montants viennent du devis source ; aucune IA ne modifie total HT, TVA,
  total TTC, acompte ou solde.

### Dashboard artisan local

- Dossier : `agents/dashboard`
- Commande : `uv run python -m agents.dashboard.run`
- URL locale : `http://127.0.0.1:8787`
- Permet de tester l'agent devis en temps réel depuis le navigateur.
- Onglets prévus : Devis, Prospects, Relances, Avis Google, CRM, Config.
- Onglet `Config` = onboarding artisan. Il sauvegarde `outputs/onboarding/artisan_profile.json`
  et peut générer `config/devis.yaml` avec backup.

### Onboarding artisan

- Code : `agents/dashboard/onboarding.py`
- Doc : `docs/ONBOARDING_ARTISAN.md`
- Rôle : transformer l'abonnement en agents activés + configuration prix/métier/zone.
- Important : aucun vrai client ne doit être onboardé sans remplir ces informations.

## Tests

Commande de validation :

```bash
uv run python -m unittest discover
```

État au 7 juin 2026 : 10 tests passent.

## Règle technique importante

Pour les devis :

- l'IA peut améliorer compréhension, résumé, questions et rédaction ;
- l'IA ne doit jamais modifier les lignes de prix, TVA, total HT/TTC ou acompte ;
- le chiffrage doit rester contrôlé par la config artisan ;
- sans clé API, le mode local doit continuer à fonctionner.

Objectif architectural demandé par Antonio : quand les clés OpenAI/Anthropic seront ajoutées,
le système doit fonctionner sans refactor lourd.

Règle permanente Accura : chaque nouvelle brique doit être conçue pour que l'ajout de clés
`OPENAI_API_KEY` et/ou `ANTHROPIC_API_KEY` suffise à activer la couche IA en production.
Pas de logique métier critique cachée dans les prompts : prix, totaux, TVA, acompte,
droits d'accès et chemins de fichiers restent contrôlés par la config et le code local.

## Priorités suivantes

1. Rendre les devis plus professionnels et moins "IA visible".
2. Ajouter relances devis J+3/J+7/J+15 avec boutons copier.
3. Ajouter mini CRM devis envoyé -> signé -> perdu.
4. Calibrer les prix avec 2 à 3 vrais devis d'artisans.
5. Brancher ensuite WhatsApp/transcription seulement quand Meta Business est validé.
