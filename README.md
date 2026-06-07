# Accura Agents — Agent acquisition de leads

Agents IA d'**Accura Ouest** pour artisans de la rénovation (Nantes & Pays de la Loire).

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
