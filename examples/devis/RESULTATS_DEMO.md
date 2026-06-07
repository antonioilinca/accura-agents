# Résultats démo — Agent Devis Accura

Objectif : montrer depuis un téléphone ce que l'Agent Devis Accura produit à partir de
demandes brutes type vocal WhatsApp.

> Prix de démonstration. À calibrer avec les vrais tarifs d'un artisan avant vente.

## Synthèse

| Cas | Métier détecté | Statut | Total TTC | Acompte conseillé |
|---|---|---:|---:|---:|
| Salle de bain complète à Nantes | Plomberie / salle de bain | Prêt | 3 909,84 € | 1 172,95 € |
| Salle de bain incomplète | Plomberie / salle de bain | Questions à poser | 3 368,64 € | 1 010,59 € |
| Tableau électrique à Saint-Herblain | Électricité | Prêt | 1 742,40 € | 522,72 € |
| Carrelage cuisine à Vertou | Carrelage / faïence | Prêt | 2 006,40 € | 601,92 € |
| Menuiserie à Rezé | Menuiserie | Prêt | 1 557,60 € | 467,28 € |
| Rénovation studio à Nantes | Rénovation générale | Prêt | 4 105,20 € | 1 231,56 € |

---

## 1. Salle de bain complète

**Demande brute**

> Bonjour, devis pour M. Dupont, 12 rue des Lilas à Nantes. Je veux refaire ma salle de
> bain, environ 6m2. Il faut remplacer la douche, poser un meuble vasque, refaire le
> carrelage et adapter la plomberie. Gamme standard. Photos disponibles. Pas spécialement
> urgent.

**Extraction**

- Métier : Plomberie / salle de bain
- Ville : Nantes
- Adresse : 12 rue des Lilas à Nantes
- Surface : 6 m²
- Urgence : standard
- Prestations : dépose, douche, meuble vasque, plomberie, carrelage/faïence

**Lignes de devis**

| Poste | Qté | PU HT | Total HT |
|---|---:|---:|---:|
| Protection du chantier et dépose | 1 forfait | 384,00 € | 384,00 € |
| Fourniture et pose douche standard | 1 forfait | 1 140,00 € | 1 140,00 € |
| Fourniture et pose meuble vasque | 1 forfait | 624,00 € | 624,00 € |
| Adaptation plomberie alimentation / évacuation | 1 forfait | 816,00 € | 816,00 € |
| Pose carrelage / faïence | 6 m² | 98,40 € | 590,40 € |

**Total**

- Total HT : 3 554,40 €
- TVA : 355,44 €
- Total TTC : 3 909,84 €
- Acompte conseillé : 1 172,95 € TTC

**Message client généré**

Bonjour, voici une première estimation pour rénovation salle de bain à Nantes
(devis DEMO-SALLE-DE-BAIN-COMPLETE) : 3 909,84 € TTC. Si cela vous convient,
je vous propose de valider les derniers détails avant envoi du devis PDF.

---

## 2. Salle de bain incomplète

**Demande brute**

> Bonjour, j'ai un client qui veut refaire une salle de bain. Il parle de changer la douche
> et le meuble, mais je n'ai pas encore la surface ni les photos. Il faut lui répondre vite
> avec une première estimation.

**Questions générées**

- Quelle est la ville exacte du chantier ?
- Quelle surface est concernée, en m² ?
- Quelle gamme de matériaux souhaitez-vous : standard, milieu de gamme ou premium ?

**Total indicatif**

- Total HT : 3 062,40 €
- TVA : 306,24 €
- Total TTC : 3 368,64 €
- Acompte conseillé : 1 010,59 € TTC

**Message client généré**

Bonjour, voici une première estimation pour rénovation salle de bain à votre chantier
(devis DEMO-SALLE-DE-BAIN-INCOMPLETE) : 3 368,64 € TTC. Pour le finaliser proprement,
il me manque : Quelle est la ville exacte du chantier ? Quelle surface est concernée,
en m² ? Quelle gamme de matériaux souhaitez-vous : standard, milieu de gamme ou premium ?

---

## 3. Électricité — tableau électrique

**Demande brute**

> Client à Saint-Herblain, rénovation d'un appartement de 35m2. Il faut remplacer le
> tableau électrique et ajouter plusieurs prises dans le salon. Photos disponibles, gamme
> standard, intervention souhaitée le mois prochain.

**Lignes**

- Diagnostic rapide et préparation intervention : 192,00 € HT
- Remplacement tableau électrique standard : 936,00 € HT
- Création/remplacement de 4 points électriques : 456,00 € HT

**Total TTC : 1 742,40 €**

---

## 4. Carrelage — Vertou

**Demande brute**

> Chantier à Vertou. Pose carrelage standard sur sol de cuisine, environ 20m2. Support
> propre, photos disponibles, client veut une estimation rapide.

**Lignes**

- Préparation support et protection : 432,00 € HT
- Pose carrelage standard : 1 392,00 € HT

**Total TTC : 2 006,40 €**

---

## 5. Menuiserie — Rezé

**Demande brute**

> Demande client à Rezé. Pose d'une porte intérieure premium et création d'un petit placard
> sur mesure dans l'entrée. Photos disponibles, cotes à confirmer sur place.

**Lignes**

- Prise de cotes et préparation commande : 168,00 € HT
- Pose porte intérieure standard : 312,00 € HT
- Création placard simple sur mesure : 936,00 € HT

**Total TTC : 1 557,60 €**

---

## 6. Rénovation générale — Nantes

**Demande brute**

> Rénovation d'un studio à Nantes, 28m2. Il faut refaire une partie des travaux intérieurs :
> préparation chantier, peinture, petites finitions et coordination. Photos disponibles,
> gamme standard, chantier habité.

**Lignes**

- Préparation, coordination et protection chantier : 540,00 € HT
- Main-d'oeuvre rénovation intérieure estimative : 3 192,00 € HT

**Total TTC : 4 105,20 €**

---

## Verdict business

Le MVP démontre la promesse Fondation :

- un artisan dicte une demande brute ;
- l'agent comprend le métier et le chantier ;
- il chiffre avec une grille modifiable ;
- il pose des questions si le dossier est incomplet ;
- il sort un message client prêt à envoyer.

La prochaine étape rentable n'est pas d'ajouter plus de code. C'est de récupérer 2 à 3
vrais devis d'un artisan pour remplacer les prix démo par ses prix réels.
