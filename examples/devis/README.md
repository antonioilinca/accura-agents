# Exemples Agent Devis Accura

Ces exemples servent à tester et démontrer la promesse Fondation :

> demande brute ou transcription vocale -> devis structuré -> JSON / Markdown / HTML imprimable.

Chaque fichier dans `requests/` contient une demande comme un artisan pourrait la dicter
depuis son téléphone.

## Lancer un exemple

```bash
uv run python -m agents.devis_generator.run \
  --id DEMO-SDB-NANTES \
  --input-file examples/devis/requests/salle_de_bain_complete.txt
```

Les fichiers générés arrivent dans `outputs/devis/`.

## Scénarios inclus

- `salle_de_bain_complete.txt` : cas plomberie complet, prêt à chiffrer.
- `salle_de_bain_incomplete.txt` : cas volontairement incomplet, doit générer des questions.
- `electricite_tableau.txt` : cas électricien.
- `carrelage_vertou.txt` : cas carreleur.
- `menuiserie_reze.txt` : cas menuisier.
- `renovation_generale_nantes.txt` : cas rénovation plus large.

## Vérification automatique

Les tests lisent tous ces exemples et vérifient que chaque demande produit :

- un métier détecté ;
- au moins une ligne de devis ;
- un total TTC positif ;
- des exports JSON, Markdown et HTML.

