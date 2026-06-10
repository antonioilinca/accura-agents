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
- Ids séquentiels par jour (`ACC-AAAAMMJJ-NNN`, compteur `outputs/devis/_sequence.json`) :
  plus de collision possible entre deux devis du même jour. Sans id explicite, un devis
  existant ne s'écrase pas ; un id fourni à la main = ré-édition volontaire.
- Garde-fous d'entrée (questions de confirmation, jamais de chiffrage aveugle) :
  demande < 12 caractères refusée ; surface hors 1-500 m² → question, pas de quantité ;
  métier non reconnu → question ; montant/quantité dicté en toutes lettres
  (« deux mille euros ») → question. C'est ce dernier garde-fou qui tient la promesse
  vocal « un nombre dicté en lettres fait poser une question plutôt qu'une invention ».

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
- Numérotation LÉGALE : séquentielle continue `FAC-AAAA-NNNN` via le compteur persistant
  `outputs/factures/_sequence.json` (verrouillé). Une facture émise ne s'écrase jamais
  (`ecrire_exports` refuse, pas d'avoir automatique en V1). La démo n'utilise PAS le
  compteur (ids dérivés du devis) pour ne jamais créer de trous dans la numérotation.
- Mentions obligatoires intégrées : date d'échéance (30 j par défaut), pénalités de
  retard + indemnité 40 € (L441-10), et « TVA non applicable, art. 293 B » si
  l'artisan est en franchise (`artisan.franchise_tva: true` dans la config devis,
  case dédiée dans l'onglet Config). Incohérence franchise + TVA > 0 → erreur.

### Agent Relances Accura

- Dossier : `agents/relance_generator`
- Commande terminal :
  `uv run python -m agents.relance_generator.run --quote outputs/devis/ACC-...json`
- Sert la promesse Fondation.
- Entrée : JSON d'un devis existant.
- Sortie : messages J+3, J+7 et J+15 prêts à copier, sauvegardés dans `outputs/relances/`.
- Important : pas d'envoi automatique tant que WhatsApp/Meta Business et le consentement
  client ne sont pas cadrés. Les messages restent copiables depuis le dashboard.

### Mini CRM Accura

- Dossier : `agents/crm_tracker`
- Sert la promesse Fondation.
- Source de vérité : devis JSON dans `outputs/devis/`.
- Stockage local hors Git : `outputs/crm/pipeline.json`.
- Statuts supportés : `devis_envoye`, `relance`, `signe`, `perdu`.
- Rôle : suivre montant TTC, client/chantier, statut et prochaine action sans dupliquer les
  prix ni modifier les documents.

### Agent Avis Google Accura

- Dossier : `agents/avis_generator`
- Commande terminal :
  `uv run python -m agents.avis_generator.run --client "Mme Dupont" --chantier "la salle de bain"`
- Sert la promesse Fondation.
- Entrée : profil artisan + client/chantier optionnels.
- Sortie : message de demande d'avis Google prêt à copier, sauvegardé dans `outputs/avis/`.
- Le lien `company.google_review_url` est renseigné depuis l'onboarding. Si absent, le
  message propose de rechercher l'entreprise sur Google.

### Agent Vocal Accura

- Dossier : `agents/voice_intake`
- Commande terminal :
  `uv run --extra voice python -m agents.voice_intake.run --audio memo.m4a --devis`
- Sert la promesse Fondation : c'est le canal d'entrée « vous dictez, le devis sort ».
- Entrée : un fichier audio (mémo vocal). Sortie : texte transcrit à RELIRE, puis devis
  brouillon optionnel avec `--devis`.
- Transcription pluggable (comme la couche LLM) via `ACCURA_TRANSCRIBE_PROVIDER` :
  - `local` (défaut) : faster-whisper, gratuit, hors-ligne. Extra `voice` à installer
    (`uv pip install faster-whisper`). Modèle via `ACCURA_WHISPER_MODEL` (défaut `small`).
  - `openai` : API Whisper (`OPENAI_API_KEY`), qualité maximale, payant, à activer plus tard.
- Important : human-in-the-loop. Le texte est relu/corrigé par l'artisan avant tout envoi.
  L'IA ne décide jamais des prix ; un nombre dicté en lettres fait poser une question de
  confirmation plutôt qu'une invention. La qualité dépend de la clarté de la voix.

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

## Briques partagées

`agents/common/fileio.py` : écritures JSON atomiques (`os.replace`) + verrou de fichier
inter-process. OBLIGATOIRE pour tout registre local (CRM `pipeline.json`, `_seen.json`,
profil artisan, compteurs `_sequence.json`) : un crash ou deux écritures simultanées ne
doivent jamais corrompre la mémoire commerciale d'un client.

Côté agent leads (`agents/lead_acquisition/llm.py`) : la couche réseau retente les pannes
transitoires (SSL/timeout/5xx), lit `Retry-After` en secondes ET en date HTTP, et espace
les appels (`llm.intervalle_min_s`) pour ne pas saturer le free tier. Qualification
plafonnée par run (`qualification.max_qualif_par_run`), surplus reporté ; échelle artisan
garantie en code (`qualification.surface_max_artisan`). Fenêtre source `jours_recents`
à garder >= 2x l'intervalle entre runs.

## Tests

Commande de validation :

```bash
uv run python -m unittest discover
```

État au 11 juin 2026 : 67 tests passent.

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
2. Calibrer les prix avec 2 à 3 vrais devis d'artisans.
3. Préparer une démo Fondation complète avec un artisan fictif crédible.
4. Brancher ensuite WhatsApp/transcription seulement quand Meta Business est validé.
