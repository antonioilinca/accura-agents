# Démo Fondation Accura — mode d'emploi

Démo complète de l'offre **Fondation (199 €/mois)** sur un artisan fictif crédible :
**Atelier Rénov Loire**, plombier rénovation à Nantes. Tout est généré en local,
sans clé API, sans aucun envoi automatique. Prix de démonstration, à calibrer avec
les vrais tarifs de l'artisan avant toute vente.

## Lancer la démo

```bash
uv run python examples/demo_fondation.py
```

Le script :

1. configure l'artisan fictif (onboarding) ;
2. archive l'état précédent dans `outputs/_archive_avant_demo_<date>/` (réversible) ;
3. génère un parcours commercial complet pour 3 chantiers ;
4. écrit un récapitulatif dans `outputs/demo/RECAP_DEMO_FONDATION.md`.

Option `--garder-historique` pour cumuler avec les devis déjà présents au lieu de
repartir d'un pipeline propre.

## Ce que la démo produit

| Devis | Chantier | Total TTC | Statut CRM | Documents générés |
|---|---|---:|---|---|
| DEMO-FOND-SDB-DUPONT | Salle de bain, Nantes | 3 909,84 € | Signé | Devis, facture acompte, relances, avis Google |
| DEMO-FOND-ELEC-HERBLAIN | Tableau électrique, Saint-Herblain | 1 742,40 € | Relancé | Devis, relances |
| DEMO-FOND-CARR-VERTOU | Carrelage cuisine, Vertou | 2 006,40 € | Devis envoyé | Devis |

Pipeline CRM résultant : 1 signé, 1 relancé, 1 envoyé.

## Montrer la démo à un artisan

```bash
uv run python -m agents.dashboard.run
# puis ouvrir http://127.0.0.1:8787
```

Parcours à dérouler devant l'artisan, dans l'ordre :

1. **Devis** : « Vous dictez la demande du client, le devis sort structuré et chiffré. »
2. **Factures** : « Le client dit oui, la facture d'acompte se génère depuis le devis,
   sans ressaisir un seul montant. »
3. **Relances** : « S'il ne répond pas, vos relances J+3, J+7 et J+15 sont déjà écrites,
   prêtes à envoyer. »
4. **CRM** : « Vous voyez d'un coup d'œil qui a signé, qui attend, qui relancer. »
5. **Avis Google** : « Chantier fini, le message pour demander un avis est prêt à copier. »

## Argumentaire (langage artisan, zéro jargon)

- Promesse : « Vous gardez vos clients et vos prix. On vous enlève la paperasse. »
- Le gain concret : un devis propre en 2 minutes au lieu d'une soirée, des relances
  qui ne s'oublient plus, des avis Google qui rentrent.
- Rassurer : « Rien ne part tout seul. Vous validez et vous envoyez. Vous restez maître. »
- Le prix : 199 €/mois, sans engagement long, calibré sur vos vrais tarifs dès le départ.

## Garde-fous (à dire si on vous pose la question)

- Aucun message (devis, relance, avis) n'est envoyé automatiquement : tout est « prêt à copier ».
- L'IA aide à comprendre et rédiger. Elle ne décide **jamais** des prix, totaux, TVA ou acompte :
  ces montants viennent de la grille tarifaire de l'artisan.
- Les données client restent en local (`outputs/`), hors du dépôt Git.

## Avant un vrai client

1. Récupérer 2 à 3 vrais devis de l'artisan pour remplacer les prix de démonstration.
2. Renseigner son vrai SIRET, son assurance décennale et son lien d'avis Google dans l'onglet Config.
3. Importer son logo pour des devis et factures à son nom.
