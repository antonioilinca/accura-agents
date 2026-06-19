# Plateforme artisan Accura — API back (à relier au site)

Le **site** (accuraouest.com, géré par Younès) s'occupe de la vitrine, de la création de
compte et du **paiement**. Cette **API** gère tout le reste, côté serveur : les **comptes
artisans**, la **sécurité**, et l'accès aux **agents selon le plan acheté**. Le site appelle
cette API ; il ne réimplémente aucune logique métier.

> Tout est en bibliothèque standard Python (aucune dépendance ajoutée).

---

## Démarrer l'API

```bash
python -m agents.platform.run            # local : http://127.0.0.1:8790/api/v1
python -m agents.platform.run --port 9000
```

Au démarrage, la **clé de service** s'affiche dans la console (à donner au site, à garder
secrète). En local, double-cliquer `lancer-plateforme.command` fait la même chose.

---

## Deux niveaux d'accès

| Usage | En-tête | Qui l'utilise |
|---|---|---|
| Créer un compte (après paiement) | `X-Accura-Service-Key: <clé de service>` | Le **serveur** du site, jamais le navigateur |
| Toutes les actions de l'artisan | `Authorization: Bearer <jeton>` | Obtenu via `POST /auth/login` |

---

## Endpoints (base : `/api/v1`)

| Méthode | Chemin | Accès | Rôle |
|---|---|---|---|
| GET | `/health` | public | Sonde de santé |
| POST | `/accounts` | clé service | Créer un compte artisan après paiement |
| POST | `/auth/login` | public | Connexion `{login, password}` → `{token, account}` |
| GET | `/me` | jeton | Compte : entreprise, plan, agents autorisés, compteurs |
| GET/PUT | `/profile` | jeton | Lire / compléter le profil (entreprise, zone, **prix**, postes) |
| POST | `/account/password` | jeton | Changer son mot de passe `{password}` |
| GET/POST | `/devis` | jeton | Lister / créer un devis `{text, id?}` |
| GET/POST | `/factures` | jeton | Lister / créer une facture `{quote_id, type}` |
| POST | `/relances` | jeton | Générer les relances J+3/7/15 `{quote_id}` |
| POST | `/avis` | jeton | Message d'avis Google `{client, chantier}` |
| GET/POST | `/crm` | jeton | Pipeline / mise à jour `{quote_id, status, next_action}` |
| GET | `/leads` | jeton | Leads livrés (offres Croissance / Intégral) |
| GET | `/documents/{type}/{nom}` | jeton | Télécharger un document (devis/factures/relances/avis) |

Une action dont l'agent n'est pas inclus dans le plan renvoie **403** (ex. `/leads` en
Fondation). Sans jeton valide : **401**.

---

## Flux type (côté site)

1. **Paiement validé** → le serveur du site appelle
   `POST /accounts` (clé de service) avec `{company_name, email, plan, main_trade, service_area}`.
   Réponse : `{slug, login, password, account}` — transmettre `login`/`password` à l'artisan
   (le `password` n'est renvoyé qu'une seule fois ; on peut aussi l'imposer en l'envoyant
   dans le body).
2. **Connexion artisan** → `POST /auth/login {login, password}` → `token`.
3. **Espace artisan** → le site utilise le `token` pour `GET /me`, `POST /devis`,
   `GET /devis`, `GET /documents/...`, etc. L'affichage (UI) est libre côté site ; l'API
   ne renvoie que des données + des URLs de documents.

Les plans et leurs agents : **Fondation** (devis, relances, CRM, avis) · **Croissance**
(+ leads) · **Intégral** (+ reporting). Source unique : `agents/dashboard/onboarding.py` → `PLANS`.

---

## Déploiement (à lire avant la mise en ligne)

- **Secrets stables en prod** : définir `ACCURA_PLATFORM_SECRET` (signature des jetons) et
  `ACCURA_PLATFORM_API_KEY` (clé de service) en variables d'environnement. Sinon elles sont
  générées localement et **changeraient à chaque redéploiement** (jetons invalidés).
- **CORS** : si le site appelle l'API depuis le navigateur, définir
  `ACCURA_PLATFORM_ALLOWED_ORIGIN=https://accuraouest.com`. Le plus sûr reste un appel
  **serveur-à-serveur** (la clé de service ne quitte jamais le back du site).
- **Stockage persistant** : comptes et documents sont des fichiers sous
  `outputs/clients/<slug>/`. Pour de **vrais clients payants**, héberger sur un disque
  **persistant** (VPS). Le système de fichiers de Hugging Face Spaces est **éphémère** (les
  comptes seraient perdus au redéploiement) : OK pour une démo, pas pour la production.
- **Aucune dépendance nouvelle** : `requirements.txt` / `Dockerfile` inchangés.
