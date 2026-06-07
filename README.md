# Accura Agents — agents Accura Ouest

Agents IA d'**Accura Ouest** pour artisans de la rénovation (Nantes & Pays de la Loire).

Agents disponibles :

- **Agent acquisition de leads** : sert la promesse **Croissance** (2 à 3 prospects
  qualifiés / semaine).
- **Agent Devis Accura** : sert la promesse **Fondation** (demande brute ou transcription
  vocale -> devis structuré prêt à envoyer).
- **Agent Factures Accura** : sert la promesse **Fondation** (devis validé -> facture
  d'acompte ou de solde imprimable).
- **Agent Relances Accura** : sert la promesse **Fondation** (devis envoyé -> messages
  J+3 / J+7 / J+15 prêts à copier).
- **Mini CRM Accura** : sert la promesse **Fondation** (suivi devis envoyé -> relancé ->
  signé -> perdu).
- **Dashboard artisan local** : interface pour tester les agents en temps réel dans le
  navigateur.

---

## Agent acquisition de leads

Premier agent : **acquisition de leads**. Il sert directement la promesse du pack
**Croissance** vendu sur accuraouest.com : **2 à 3 prospects qualifiés livrés chaque
semaine** à l'artisan abonné.

Il scanne chaque jour des signaux publics et légaux (projets de travaux déclarés en mairie
+ demandes collées à la main), repère les opportunités de chantier pour un métier donné
autour de Nantes, les qualifie, puis livre une **fiche prospect actionnable** : score,
raison, valeur potentielle, canal recommandé, urgence, prochaine action, message de
contact et script court d'appel / visite.

> Type de leads : ce sont des **opportunités à démarcher** (adresse + nature des travaux),
> pas des demandes entrantes. L'artisan approche le prospect (courrier ou visite).

---

## 1. Ce dont tu as besoin

- **Python 3.10+** et **[uv](https://docs.astral.sh/uv/)** (gestionnaire de paquets rapide).
  Installer uv : `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Une **clé d'IA gratuite**. Par défaut : **Groq** (Llama 3.3 70B, gratuit) →
  https://console.groq.com/keys. (Alternatives : Mistral, Ollama local, ou Claude payant — voir plus bas.)

## 2. Installation

```bash
git clone https://github.com/antonioilinca/accura-agents.git
cd accura-agents
uv sync          # crée l'environnement et installe les dépendances
```

## 3. Configuration (2 fichiers à copier)

```bash
# a) La clé d'IA
cp .env.example .env
# puis ouvre .env et colle ta clé Groq (gratuite) sur la ligne GROQ_API_KEY

# b) La config métier / zone
cp config/config.example.yaml config/config.yaml
```

Dans `config/config.yaml` tu règles, **sans toucher au code** :
- `metier:` → `plombier`, `electricien` ou `couvreur` (fichiers dans `config/metiers/`)
- `zone:` → la liste des communes scannées (par défaut : les 24 communes de Nantes Métropole)
- `qualification.seuil_livraison:` → le score minimum pour qu'un lead soit livré (défaut 60)
- `qualification.objectif_hebdo_min/max:` → promesse Croissance (défaut 2 à 3 prospects
  qualifiés / semaine). L'agent ne dépasse pas le plafond hebdomadaire.

> Pour un nouveau métier, copie un fichier de `config/metiers/` et adapte ses mots-clés.

## 4. Lancer

```bash
uv run python -m agents.lead_acquisition.run
```

À la fin, le récap s'affiche et plusieurs fichiers sont écrits dans `outputs/` :
- `leads-AAAA-MM-JJ.json` → les leads livrés (données structurées)
- `recap-AAAA-MM-JJ.md` → le résumé lisible (top leads + brouillons de contact + coût du run)
- `leads-AAAA-MM-JJ.html` et `index.html` → page visuelle à ouvrir pour Younès / l'artisan
- `suivi-prospects-METIER.csv` → pipeline commercial à tenir à jour
- `bilan-croissance-AAAA-WSS.md` → preuve hebdomadaire de la promesse Croissance

Un même chantier n'est jamais livré deux fois (historique `outputs/_seen.json`).

Statuts recommandés dans le suivi : `a_contacter` → `contacte` → `relance` →
`devis_envoye` → `signe` ou `perdu`. C'est ce suivi qui prouve la valeur Accura :
prospects livrés, actions faites, devis générés, chantiers signés.

## 5. Lancer tous les jours (automatique, sur le VPS)

Avec cron, 1 fois par jour à 7h :

```bash
crontab -e
# ajoute la ligne (adapte le chemin) :
0 7 * * * cd /chemin/vers/accura-agents && /usr/bin/uv run python -m agents.lead_acquisition.run >> logs/cron.log 2>&1
```

---

## Les sources de leads

| Source | État | Ce qu'elle fait |
|---|---|---|
| **urbanisme_nantes** | ✅ active | Open data public de Nantes Métropole : déclarations préalables et permis de construire des 3 derniers mois. Gratuit, légal, frais. **C'est le socle.** |
| **inbox_manuelle** | ✅ active | Les demandes que tu repères dans les groupes Facebook locaux, tu les colles dans `inbox/leads_manuels.md` et l'agent les qualifie. |
| **sitadel** | ⏸️ à valider | Base nationale (data.gouv.fr) pour étendre la zone hors Nantes Métropole. Désactivée tant qu'elle n'est pas testée. |

### Pourquoi pas de scraping automatique de Facebook / Leboncoin / Nextdoor ?
C'est interdit par leurs conditions d'utilisation et risqué côté RGPD (revendre les données
personnelles de gens qui n'ont rien demandé). La voie propre : **toi**, déjà membre des
groupes, tu copies les 2-3 demandes pertinentes du jour dans `inbox/leads_manuels.md`.
Voir `inbox/leads_manuels.example.md` pour le format.

## Conformité (RGPD)
L'open data de Nantes Métropole **anonymise déjà** le demandeur particulier
(`"RGPD - Personne physique"`). L'agent ne récupère donc que l'**opportunité** (adresse du
terrain + nature des travaux + ampleur + date), **sans nom ni coordonnées**. Aucune donnée
personnelle n'est stockée dans le dépôt (`outputs/` et `inbox/leads_manuels.md` sont exclus
du dépôt par `.gitignore`).

## Quel modèle / fournisseur d'IA ?
Le fournisseur se règle dans `config.yaml` (bloc `llm:`), **sans toucher au code**. Tant
qu'il n'y a pas de client, on reste sur du **gratuit** ; on bascule sur Claude quand un
client paie.

| Fournisseur | Coût | Qualité | `provider` / `base_url` |
|---|---|---|---|
| **Groq** (défaut, Llama 3.3 70B) | gratuit (~14k req/jour) | très bonne | `openai_compat` / `api.groq.com/openai/v1` |
| **Mistral** (européen, RGPD) | gratuit (free tier) | bonne | `openai_compat` / `api.mistral.ai/v1` |
| **Ollama** (local) | gratuit, illimité, offline | moyenne (petits modèles) | `openai_compat` / `localhost:11434/v1` |
| **Claude** (Haiku + Sonnet) | payant (~3-5 USD/mois) | maximale | `anthropic` |

Les données d'urbanisme, elles, sont toujours gratuites. Le coût réel de chaque run est
affiché dans le récap (0 sur un fournisseur gratuit).

---

## Structure du dépôt

```
accura-agents/
├── config/
│   ├── config.example.yaml      # modèle de configuration (à copier en config.yaml)
│   └── metiers/                 # critères par métier (plombier, electricien, couvreur)
├── agents/
│   └── lead_acquisition/
│       ├── run.py               # point d'entrée (1 run / jour)
│       ├── pipeline.py          # orchestration génération -> qualif -> livraison
│       ├── sources/             # connecteurs (urbanisme_nantes, sitadel, inbox_manuelle)
│       ├── qualify.py           # tri Haiku + scoring Sonnet (sortie structurée)
│       ├── deliver.py           # JSON + récap + HTML + suivi commercial + quota hebdo
│       ├── prompts.py           # instructions IA, paramétrées par métier
│       └── models.py            # types de données
├── inbox/                       # demandes collées à la main
├── outputs/                     # leads + récaps (hors dépôt)
└── logs/                        # journaux d'exécution (hors dépôt)
```

Les prochains agents (erreurs, administration, prospection) s'ajouteront sous `agents/`.

## Choix technique
La qualification passe par une **couche LLM unique** (`llm.py`) qui parle soit à un
fournisseur compatible OpenAI (Groq, Mistral, Ollama — via `requests`, sans dépendance
lourde), soit à l'API Claude (tool use). Pour une tâche de tri + scoring, un appel par
opportunité suffit : pas besoin du framework Agent SDK complet (plus cher, dépendance Node
sur le VPS). L'archi reste modulaire pour basculer vers des sous-agents quand on ajoutera
la génération de devis.

---

## Agent Devis Accura

L'agent devis transforme une demande artisan brute en **devis clair et vérifiable** :

- input texte ou transcription vocale simulée ;
- extraction du métier, type de chantier, ville/adresse, surface, prestations, matériaux,
  contraintes, urgence et infos manquantes ;
- questions de clarification si le devis n'est pas assez sûr ;
- lignes de devis structurées avec prix configurables ;
- calcul total HT, TVA, total TTC et acompte ;
- exports JSON, Markdown et HTML imprimable en PDF.

Il ne dépend pas encore de WhatsApp. Le branchement futur sera simple : WhatsApp/transcription
devra seulement fournir un texte brut à `agents.devis_generator`.

### Configuration devis

La configuration exemple est versionnée ici :

```bash
config/devis.example.yaml
```

Pour un vrai artisan, copie-la puis adapte les prix et mentions :

```bash
cp config/devis.example.yaml config/devis.yaml
```

Dans `config/devis.yaml`, tu peux modifier sans toucher au code :

- l'identité et les mentions légales de l'artisan ;
- le taux de TVA ;
- le taux de marge ;
- le taux horaire ;
- l'acompte recommandé ;
- les postes types par métier ;
- les villes connues autour de Nantes.
- le fournisseur IA de finition (`llm:`), sans toucher au chiffrage.

`config/devis.yaml` n'est pas versionné, car il peut contenir les vrais tarifs d'un client.

### Activer la finition IA plus tard

Par défaut, l'agent devis fonctionne sans clé API. Le moteur local extrait, chiffre et
exporte le devis.

Quand un client paie, ajoute simplement une clé dans `.env` :

```bash
OPENAI_API_KEY=sk-...
```

Avec `llm.provider: auto` dans `config/devis.yaml`, l'agent utilise alors OpenAI pour
améliorer la rédaction du résumé, des questions et du message client. Si tu préfères
Claude, ajoute `ANTHROPIC_API_KEY` et règle `provider: anthropic`.

Garde-fou important : l'IA ne modifie jamais les lignes de prix, la TVA, le total TTC ou
l'acompte. Ces montants restent verrouillés par la config artisan.

### Lancer un devis

```bash
uv run python -m agents.devis_generator.run --input "Bonjour, je veux refaire ma salle de bain à Nantes, environ 6m2, remplacer douche, meuble vasque, carrelage, plomberie. Gamme standard. Photos disponibles."
```

Ou depuis un fichier :

```bash
uv run python -m agents.devis_generator.run --input-file demande.txt
```

Les sorties sont écrites dans `outputs/devis/` :

- `ACC-...json` : données structurées pour CRM / automatisation ;
- `ACC-...md` : version lisible et éditable ;
- `ACC-...html` : version propre à imprimer ou enregistrer en PDF ;
- `dernier-devis.html` : dernier devis généré.

---

## Agent Factures Accura

L'agent factures transforme un devis JSON existant en **facture d'acompte** ou **facture de
solde** :

- identité artisan, logo, SIRET et assurance repris du devis ;
- total HT, TVA, total TTC, acompte et solde repris du devis source ;
- exports JSON, Markdown et HTML imprimable en PDF dans `outputs/factures/`.

Il n'utilise pas l'IA : les montants facturés restent contrôlés par le devis/config.

### Lancer une facture

```bash
uv run python -m agents.facture_generator.run \
  --quote outputs/devis/acc-20260607-001.json \
  --type acompte
```

Pour le solde :

```bash
uv run python -m agents.facture_generator.run \
  --quote outputs/devis/acc-20260607-001.json \
  --type solde
```

---

## Agent Relances Accura

L'agent relances transforme un devis JSON existant en **3 messages prêts à copier** :

- J+3 : relance courte après envoi ;
- J+7 : relance de décision ;
- J+15 : dernière relance avant mise en attente.

Il n'envoie rien automatiquement. L'artisan copie le message depuis le dashboard ou depuis
la sortie terminal. C'est volontaire : l'automatisation WhatsApp viendra seulement quand le
cadre Meta Business et le consentement client seront propres.

### Lancer les relances

```bash
uv run python -m agents.relance_generator.run \
  --quote outputs/devis/acc-20260607-001.json
```

---

## Mini CRM Accura

Le mini CRM suit les devis générés localement :

- statut : `devis_envoye`, `relance`, `signe`, `perdu` ;
- prochaine action commerciale ;
- montant TTC et chantier repris du devis source.

Le stockage est local et non versionné :

```text
outputs/crm/pipeline.json
```

Le CRM ne modifie pas les prix ni les documents. Il sert à piloter le suivi commercial dans
le dashboard.

### Exemples de démonstration

Des demandes réalistes sont disponibles dans `examples/devis/requests/`.

Exemple :

```bash
uv run python -m agents.devis_generator.run \
  --id DEMO-SDB-NANTES \
  --input-file examples/devis/requests/salle_de_bain_complete.txt
```

Ces exemples couvrent salle de bain, électricité, carrelage, menuiserie et rénovation
générale. Ils sont aussi utilisés par les tests pour vérifier que l'agent reste vendable
quand on le modifie.

### Pourquoi l'agent devis n'appelle pas encore un LLM ?

Pour un devis, le risque n'est pas de manquer de créativité : c'est d'inventer un prix ou
un périmètre. Le MVP utilise donc une extraction simple + une grille tarifaire modifiable.
Quand un artisan paie et fournit ses vrais modèles, on pourra ajouter une couche LLM pour
mieux comprendre les vocaux, mais le chiffrage restera contrôlé par la config.

### Structure ajoutée

```
agents/devis_generator/
├── config.py       # chargement config devis YAML
├── generator.py    # extraction + chiffrage + totaux
├── models.py       # types structurés
├── render.py       # exports JSON / Markdown / HTML
└── run.py          # point d'entrée local
```

---

## Dashboard artisan local

Le dashboard sert à montrer Accura comme un vrai outil artisan, pas comme un script.

Il permet de :

- coller une demande client ou transcription vocale simulée ;
- charger des exemples métier ;
- générer un devis en temps réel ;
- voir les questions manquantes, lignes de devis, total HT/TVA/TTC et acompte ;
- copier le message client ;
- ouvrir les exports JSON, Markdown et HTML imprimable ;
- voir les derniers devis générés ;
- afficher une première vue des prospects issus de l'agent acquisition.
- remplir l'onboarding artisan et générer une config `config/devis.yaml`.

Lancer le dashboard :

```bash
uv run python -m agents.dashboard.run
```

Puis ouvrir :

```text
http://127.0.0.1:8787
```

Le dashboard utilise `config/devis.yaml` si le fichier existe, sinon
`config/devis.example.yaml`.

Voir aussi : `docs/ONBOARDING_ARTISAN.md`.
