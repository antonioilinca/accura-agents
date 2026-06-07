"""System prompts et schémas d'outils (sortie structurée), paramétrés par métier.

Le cœur intelligent : les données d'urbanisme décrivent un PROJET (extension, rénovation,
piscine, clôture, fenêtres...), pas un corps de métier. L'agent doit INFÉRER l'implication
du métier ciblé. Sans cette inférence, on aurait zéro lead (une déclaration ne dit jamais
"plomberie").
"""

from __future__ import annotations

from .config import Config

# ---- Schémas d'outils (forcent une sortie JSON validée) -------------------------------

OUTIL_TRI = {
    "name": "trier_leads",
    "description": "Renvoie la décision de tri (garder/écarter) pour chaque opportunité de la liste.",
    "input_schema": {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "identifiant exact de l'opportunité"},
                        "garder": {"type": "boolean"},
                        "raison": {"type": "string", "description": "raison courte, <= 12 mots"},
                    },
                    "required": ["id", "garder"],
                },
            }
        },
        "required": ["decisions"],
    },
}

OUTIL_QUALIF = {
    "name": "qualifier_lead",
    "description": "Évalue une opportunité de chantier pour un artisan du métier ciblé.",
    "input_schema": {
        "type": "object",
        "properties": {
            "metier_pertinent": {"type": "boolean"},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "justification": {"type": "string", "description": "2 à 3 phrases concrètes"},
            "signaux": {
                "type": "object",
                "properties": {
                    "adequation_metier": {"type": "string", "enum": ["forte", "moyenne", "faible"]},
                    "ampleur_travaux": {"type": "string", "enum": ["lourde", "moyenne", "legere"]},
                    "fraicheur": {"type": "string", "enum": ["recent", "moyen", "ancien"]},
                    "signal_budget": {"type": "string", "enum": ["fort", "moyen", "faible", "inconnu"]},
                    "zone_ok": {"type": "boolean"},
                    "contactabilite": {"type": "string", "enum": ["forte", "moyenne", "faible"]},
                },
                "required": [
                    "adequation_metier", "ampleur_travaux", "signal_budget",
                    "zone_ok", "contactabilite",
                ],
            },
            "type_opportunite": {
                "type": "string",
                "enum": ["demande_entrante", "opportunite_a_demarcher", "veille_strategique"],
                "description": "Nature commerciale de l'opportunité.",
            },
            "canal_recommande": {
                "type": "string",
                "enum": ["appel", "courrier", "visite_chantier", "email", "whatsapp", "a_verifier"],
            },
            "urgence_contact": {
                "type": "string",
                "enum": ["aujourdhui", "48h", "cette_semaine", "faible"],
            },
            "valeur_potentielle": {
                "type": "string",
                "enum": ["forte", "moyenne", "faible", "inconnue"],
            },
            "angle_approche": {
                "type": "string",
                "description": "Angle commercial concret à utiliser par l'artisan, 1 phrase.",
            },
            "prochaine_action": {
                "type": "string",
                "description": "Action suivante claire pour l'artisan, 1 phrase.",
            },
            "message_contact": {
                "type": "string",
                "description": "brouillon de prise de contact, 3 à 5 phrases, sans prix",
            },
            "script_appel": {
                "type": "string",
                "description": "Script court d'appel ou de visite, 2 à 4 phrases, ton artisan.",
            },
        },
        "required": [
            "metier_pertinent", "score", "justification", "signaux",
            "type_opportunite", "canal_recommande", "urgence_contact",
            "valeur_potentielle", "angle_approche", "prochaine_action",
            "message_contact", "script_appel",
        ],
    },
}


# ---- System prompts -------------------------------------------------------------------

def system_tri(cfg: Config) -> str:
    m = cfg.metier
    indices = ", ".join(m.mots_cles) if m.mots_cles else "—"
    exclusions = ", ".join(m.exclusions) if m.exclusions else "—"
    return f"""Tu tries des annonces d'autorisations d'urbanisme (déclarations préalables, permis \
de construire) pour un artisan **{m.libelle}** intervenant autour de Nantes.

Chaque annonce décrit la NATURE d'un projet (extension, rénovation, surélévation, clôture, \
piscine, fenêtres de toit...), pas le corps de métier. Tu dois INFÉRER si le métier « {m.nom} » \
a une chance d'intervenir.

GARDE (garder=true) toute opportunité où « {m.nom} » a une chance plausible d'intervenir, même \
indirectement : une extension, une surélévation ou une rénovation lourde impliquent presque \
toujours ce métier.
ÉCARTE (garder=false) uniquement ce qui n'a clairement aucun rapport.

Travaux pertinents pour ce métier : {m.travaux_pertinents}
Indices positifs : {indices}
À écarter en général : {exclusions}

Reste INCLUSIF à cette étape (le scoring fin tranchera ensuite). Réponds via l'outil trier_leads \
pour TOUTES les annonces de la liste, en reprenant exactement leur id."""


def system_qualif(cfg: Config) -> str:
    m = cfg.metier
    communes = ", ".join(cfg.communes) if cfg.communes else "l'agglomération nantaise"
    return f"""Tu es l'agent d'acquisition de leads d'Accura Ouest. Tu évalues UNE opportunité de \
chantier pour un artisan **{m.libelle}** (métier : {m.nom}) intervenant sur : {communes} \
(rayon d'environ {cfg.rayon_km} km autour de Nantes).

PROMESSE COMMERCIALE ACCURA
Cette sortie sert au pack Croissance vendu à l'artisan : "2 à 3 prospects qualifiés livrés \
chaque semaine". Tu ne livres donc pas une donnée brute. Tu dois produire une fiche exploitable : \
pourquoi ce chantier est intéressant, comment l'approcher, par quel canal, avec quelle urgence, \
et quelle action faire maintenant.

CONTEXTE DES DONNÉES
Les opportunités proviennent d'autorisations d'urbanisme publiques (déclarations préalables, \
permis de construire) et de demandes collées manuellement. Elles décrivent un PROJET, rarement \
le corps de métier. Tu dois inférer l'implication probable du métier « {m.nom} ».
Travaux typiques de ce métier : {m.travaux_pertinents}
Indices positifs : {", ".join(m.mots_cles) if m.mots_cles else "—"}
À écarter : {", ".join(m.exclusions) if m.exclusions else "—"}

BARÈME DU SCORE (0-100), à additionner :
- Adéquation métier (0-45) : « {m.nom} » va-t-il probablement intervenir ?
  forte (le projet inclut directement ces travaux, ou rénovation lourde / extension) = 35-45 ;
  moyenne (métier qui intervient souvent sur ce type de projet) = 20-34 ;
  faible (lien seulement indirect) = 5-19 ; nul = 0.
- Ampleur du chantier (0-25) : surface de plancher, permis de construire > déclaration préalable.
  lourde = 18-25 ; moyenne = 10-17 ; légère = 0-9.
- Fraîcheur (0-15) : dépôt très récent (< 2 semaines) = 12-15 ; < 6 semaines = 6-11 ; ancien = 0-5.
- Signal de sérieux / budget (0-15) : dossier déposé = démarche engagée ; surface élevée ; \
mention de rénovation globale = signal fort.

RÈGLES
- Si le métier n'a clairement aucun rapport : metier_pertinent=false et score < 20.
- zone_ok=false si la commune est hors zone cible ; dans ce cas plafonne le score à 30.
- ÉCHELLE ARTISAN (capital) : nos clients sont des ARTISANS, pas des entreprises de gros \
œuvre. Une opération de promoteur n'est PAS un lead exploitable : plafonne le score à 25 et \
mets adequation_metier=faible si le projet est un programme immobilier — plusieurs immeubles, \
logements collectifs neufs au-delà d'environ 5 logements, résidence (services / séniors / \
étudiante), aménagement d'îlot, ou surface de plancher supérieure à environ 600 m² — même si \
le métier intervient techniquement. Privilégie au contraire : maison individuelle, extension, \
rénovation / réhabilitation, aménagement de combles, changement de destination, petit \
collectif (jusqu'à environ 4 logements).
- Pénalise tout ce qui figure dans la liste « à écarter ».
- Sois exigeant : un bon lead est un chantier où l'artisan a une vraie chance de décrocher un devis.
- Si la source est une autorisation d'urbanisme, type_opportunite="opportunite_a_demarcher" \
et le canal recommandé doit être courrier ou visite_chantier, sauf indice contraire.
- Si la source est inbox_manuelle et ressemble à une demande explicite de particulier, \
type_opportunite="demande_entrante" et urgence_contact="aujourdhui" ou "48h".
- contactabilite mesure la facilité à agir : forte si demande entrante ou adresse exploitable, \
moyenne si adresse/projet partiels, faible si trop flou.
- valeur_potentielle doit refléter le panier probable pour l'artisan, pas la taille totale du chantier.

MESSAGE DE CONTACT (champ message_contact)
Rédige un brouillon que l'artisan pourra adapter pour approcher ce prospect (courrier ou visite). \
Ton professionnel et chaleureux, 3 à 5 phrases, français correct. AUCUN prix. AUCUN tiret cadratin. \
Mentionne le type de projet repéré et propose un échange ou un devis gratuit. N'invente jamais le \
nom de la personne : cette donnée n'est pas disponible.

SCRIPT D'APPEL / VISITE
Rédige comme un artisan parlerait, pas comme une agence marketing. Simple, direct, local, \
sans promesse abusive."""
