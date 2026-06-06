# Accura Agents — Agent acquisition de leads

Agents IA d'**Accura Ouest** pour artisans de la rénovation (Nantes & Pays de la Loire).

Premier agent : **acquisition de leads**. Il scanne chaque jour des signaux publics et
légaux (projets de travaux déclarés en mairie + demandes collées à la main), repère les
**opportunités de chantier** pour un métier donné autour de Nantes, leur donne un score
de 0 à 100, et livre les meilleures dans un fichier + un récap, avec un brouillon de
message de prise de contact.

> Type de leads : ce sont des **opportunités à démarcher** (adresse + nature des travaux),
> pas des demandes entrantes. L'artisan approche le prospect (courrier ou visite).

---

## 1. Ce dont tu as besoin

- **Python 3.10+** et **[uv](https://docs.astral.sh/uv/)** (gestionnaire de paquets rapide).
  Installer uv : `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Une **clé API Anthropic** : https://console.anthropic.com/ → Settings → API Keys.

## 2. Installation

```bash
git clone https://github.com/antonioilinca/accura-agents.git
cd accura-agents
uv sync          # crée l'environnement et installe les dépendances
```

## 3. Configuration (2 fichiers à copier)

```bash
# a) La clé API
cp .env.example .env
# puis ouvre .env et colle ta clé Anthropic

# b) La config métier / zone
cp config/config.example.yaml config/config.yaml
```

Dans `config/config.yaml` tu règles, **sans toucher au code** :
- `metier:` → `plombier`, `electricien` ou `couvreur` (fichiers dans `config/metiers/`)
- `zone:` → la liste des communes scannées (par défaut : les 24 communes de Nantes Métropole)
- `qualification.seuil_livraison:` → le score minimum pour qu'un lead soit livré (défaut 60)

> Pour un nouveau métier, copie un fichier de `config/metiers/` et adapte ses mots-clés.

## 4. Lancer

```bash
uv run python -m agents.lead_acquisition.run
```

À la fin, le récap s'affiche et deux fichiers sont écrits dans `outputs/` :
- `leads-AAAA-MM-JJ.json` → les leads livrés (données structurées)
- `recap-AAAA-MM-JJ.md` → le résumé lisible (top leads + brouillons de contact + coût du run)

Un même chantier n'est jamais livré deux fois (historique `outputs/_seen.json`).

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

## Coût
Les données d'urbanisme sont gratuites. Seule l'IA de qualification consomme : un tri
grossier avec Haiku puis un scoring fin avec Sonnet, uniquement sur les opportunités
retenues. Estimation : **~3 à 5 USD / mois** pour un métier et la zone Nantes Métropole.
Le coût réel de chaque run est affiché dans le récap.

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
│       ├── deliver.py           # écriture JSON + récap + déduplication
│       ├── prompts.py           # instructions IA, paramétrées par métier
│       └── models.py            # types de données
├── inbox/                       # demandes collées à la main
├── outputs/                     # leads + récaps (hors dépôt)
└── logs/                        # journaux d'exécution (hors dépôt)
```

Les prochains agents (erreurs, administration, prospection) s'ajouteront sous `agents/`.

## Choix technique
La qualification utilise l'**API Claude directe** (paquet `anthropic`), pas le framework
Agent SDK complet : pour une tâche de tri + scoring c'est la recommandation officielle
d'Anthropic, c'est moins cher, et ça se déploie sur le VPS sans dépendance lourde. L'archi
reste modulaire pour basculer vers des sous-agents quand on ajoutera la génération de devis.
