# Onboarding artisan Accura

Objectif : calibrer les agents avant de livrer l'abonnement.

Un artisan ne doit pas juste payer puis recevoir un outil générique. Il doit répondre à un
questionnaire qui transforme son abonnement en configuration exploitable :

- identité entreprise ;
- abonnement Accura ;
- agents activés ;
- métier principal ;
- zone d'intervention ;
- types de chantiers idéaux ;
- chantiers à refuser ;
- prix/postes principaux ;
- TVA, marge, acompte, validité de devis ;
- mentions légales et assurance ;
- lien avis Google ;
- paramètres acquisition si offre Croissance ou supérieure.

## Pourquoi c'est critique

Sans onboarding, les devis seront moyens, les prix seront faux et les relances manqueront
de contexte. Avec onboarding, Accura peut générer des devis et messages qui ressemblent à
l'artisan, pas à une IA générique.

## Dashboard

Lancer :

```bash
uv run python -m agents.dashboard.run
```

Ouvrir :

```text
http://127.0.0.1:8787
```

Aller dans `Config`.

Actions :

- `Sauvegarder profil` écrit `outputs/onboarding/artisan_profile.json`.
- `Importer logo` copie le logo dans `outputs/onboarding/assets/logo.*` et garde le chemin
  dans le profil artisan.
- `Appliquer à l'agent devis` génère `config/devis.yaml`.
- Si `config/devis.yaml` existe déjà, un backup est créé avant écriture.

## Abonnements

### Fondation

Agents activés :

- devis ;
- relances ;
- CRM ;
- avis Google.

### Croissance

Fondation + :

- acquisition de prospects ;
- objectif 2 à 3 prospects qualifiés/semaine.

### Pilotage

Croissance + :

- reporting.

Le nom exact de la troisième offre doit rester aligné avec le site si l'offre évolue.

## Règle de sécurité

Les fichiers générés peuvent contenir les vrais prix et données client. Ils ne doivent pas
être versionnés.

Déjà ignorés par Git :

- `config/devis.yaml`
- `config/devis.generated.yaml`
- `outputs/*`

Les logos artisans sont donc exclus du dépôt. La même ressource `assets.logo_path` pourra
être réutilisée pour les futures factures.
