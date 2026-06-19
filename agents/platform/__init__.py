"""Plateforme artisan Accura — le « derrière » (back) de l'espace client.

Le site public (accuraouest.com, géré par Younès) s'occupe de la vitrine, de la
création de compte et du paiement. Ce module fournit tout le back :

- `auth`   : mots de passe hachés, jetons de session signés, clé de service ;
- `api`    : provisioning d'un compte, authentification, et toutes les actions
             self-service de l'artisan (devis, factures, relances, avis, CRM,
             leads) — cloisonnées par compte et filtrées selon le plan acheté ;
- `server` : API REST JSON que le site de Younès appellera (« on lie tout »).

Aucune dépendance externe : tout repose sur la bibliothèque standard.
"""
