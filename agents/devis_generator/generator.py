"""Génération de devis à partir d'une demande artisan brute.

MVP assumé : extraction déterministe + grille tarifaire configurable. Cela évite
d'inventer des prix et prépare proprement le branchement WhatsApp/transcription.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from agents.common.fileio import ecrire_json_atomique, lire_json, verrou_fichier

from .models import (
    QuoteConfig,
    QuoteDocument,
    QuoteLine,
    QuoteTotals,
    ProjectRequest,
    TradeConfig,
    money,
)
from .ai_refiner import StructuredClient, ameliorer_devis_avec_ia


CHANTIER_PATTERNS = [
    ("rénovation salle de bain", ["salle de bain", "sdb", "douche", "vasque"]),
    ("remplacement chauffe-eau", ["chauffe-eau", "ballon d'eau chaude"]),
    ("rénovation électrique", ["tableau électrique", "mise aux normes", "électricité"]),
    ("peinture intérieure", ["peinture", "murs", "plafond"]),
    ("menuiserie", ["menuiserie", "fenêtre", "porte", "placard"]),
    ("carrelage", ["carrelage", "faïence"]),
    ("rénovation générale", ["rénovation", "refaire", "rénover"]),
]

CONTRAINTES = {
    "chantier occupe": ["habité", "occupé", "client sur place"],
    "accès difficile": ["étage", "sans ascenseur", "accès difficile"],
    "délais serrés": ["urgent", "rapidement", "avant", "cette semaine"],
    "dépose existant": ["dépose", "retirer", "remplacer", "enlever"],
}

QUESTIONS = {
    "ville": "Quelle est la ville exacte du chantier ?",
    "adresse": "Quelle est l'adresse complète du chantier ?",
    "surface": "Quelle surface est concernée, en m² ?",
    "prestations": "Quelles prestations précises faut-il chiffrer ?",
    "gamme_materiaux": "Quelle gamme de matériaux souhaitez-vous : standard, milieu de gamme ou premium ?",
    "photos": "Pouvez-vous envoyer 2 ou 3 photos de l'existant ?",
    "delai": "Y a-t-il une date souhaitée pour le début ou la fin du chantier ?",
}


TEXTE_MINIMUM = 12

# Une facture/un devis numéroté ne doit jamais entrer en collision : le compteur
# journalier est persistant et verrouillé (même mécanique que les factures).
SEQUENCE_FILE = "_sequence.json"


def prochain_id_devis(dossier: Path, jour: date | None = None) -> str:
    jour = jour or date.today()
    cle_jour = jour.strftime("%Y%m%d")
    dossier.mkdir(parents=True, exist_ok=True)
    registre = dossier / SEQUENCE_FILE
    with verrou_fichier(registre):
        etat = lire_json(registre, {"jour": cle_jour, "compteur": 0})
        compteur = int(etat.get("compteur", 0)) if etat.get("jour") == cle_jour else 0
        compteur += 1
        ecrire_json_atomique(registre, {"jour": cle_jour, "compteur": compteur})
    return f"ACC-{cle_jour}-{compteur:03d}"


def generer_devis(
    texte: str,
    cfg: QuoteConfig,
    id_devis: str | None = None,
    utiliser_ia: bool = True,
    client_ia: StructuredClient | None = None,
    modele_ia: str | None = None,
    dossier: Path | None = None,
) -> QuoteDocument:
    if len(str(texte or "").strip()) < TEXTE_MINIMUM:
        raise ValueError(
            "Demande trop courte pour générer un devis fiable : décrivez le chantier "
            "en une phrase au minimum (travaux, lieu, surface si connue)."
        )
    demande = extraire_demande(texte, cfg)
    lignes = chiffrer(demande, cfg)
    totaux = calculer_totaux(lignes, cfg)
    conditions = conditions_devis(demande, cfg)
    if id_devis:
        id_final = id_devis
    elif dossier is not None:
        id_final = prochain_id_devis(dossier)
    else:
        id_final = f"ACC-{date.today().strftime('%Y%m%d')}-001"
    doc = QuoteDocument(
        id_devis=id_final,
        date_creation=date.today().isoformat(),
        artisan=cfg.artisan,
        demande=demande,
        lignes=lignes,
        totaux=totaux,
        conditions=conditions,
        message_client=message_client(demande, totaux),
    )
    if utiliser_ia:
        doc = ameliorer_devis_avec_ia(doc, cfg, client=client_ia, modele=modele_ia)
    return doc


def extraire_demande(texte: str, cfg: QuoteConfig) -> ProjectRequest:
    normalise = _norm(texte)
    metier, metier_sur = _detecter_metier(normalise, cfg)
    trade = cfg.metiers[metier]
    ville = _detecter_ville(texte, cfg)
    adresse = _detecter_adresse(texte)
    surface, alerte_surface = _detecter_surface(normalise)
    type_chantier = _detecter_type_chantier(normalise)
    if metier == "renovation_generale" and (
        "rénovation" in normalise or "renovation" in normalise
    ):
        type_chantier = "rénovation générale"
    urgence = _detecter_urgence(normalise)
    prestations, materiaux = _detecter_prestations(normalise, trade)
    contraintes = _detecter_contraintes(normalise)
    manquants = _infos_manquantes(trade, ville, adresse, surface, prestations, normalise)

    questions = [QUESTIONS[m] for m in manquants if m in QUESTIONS]
    if alerte_surface:
        questions = [q for q in questions if q != QUESTIONS["surface"]]
        questions.append(alerte_surface)
    if not metier_sur:
        questions.append(
            f"Confirmer le métier concerné (proposé par défaut : {trade.libelle})."
        )
    if _nombres_en_lettres(normalise):
        questions.append(
            "Des montants ou quantités semblent dictés en toutes lettres : "
            "confirmer les chiffres exacts avant envoi."
        )

    return ProjectRequest(
        texte_source=texte.strip(),
        metier=metier,
        metier_libelle=trade.libelle,
        type_chantier=type_chantier,
        ville=ville,
        adresse=adresse,
        surface_m2=surface,
        prestations=prestations,
        materiaux_probables=sorted(set(materiaux)),
        contraintes=contraintes,
        urgence=urgence,
        infos_manquantes=manquants,
        questions=questions,
    )


def chiffrer(demande: ProjectRequest, cfg: QuoteConfig) -> list[QuoteLine]:
    trade = cfg.metiers[demande.metier]
    lignes: list[QuoteLine] = []
    for item in trade.postes:
        if not _item_concerne(item.mots_cles, demande.texte_source, demande.prestations):
            continue
        quantite = item.quantite_defaut
        if item.quantite_depuis == "surface_m2" and demande.surface_m2:
            quantite = demande.surface_m2
        prix_unitaire = money(item.prix_unitaire_ht * (Decimal("1") + cfg.pricing.taux_marge))
        total = money(prix_unitaire * quantite)
        lignes.append(
            QuoteLine(
                code=item.code,
                libelle=item.libelle,
                quantite=quantite,
                unite=item.unite,
                prix_unitaire_ht=prix_unitaire,
                total_ht=total,
                description=item.description,
            )
        )

    if not lignes:
        prix = money(cfg.pricing.main_oeuvre_heure_ht * Decimal("2"))
        lignes.append(
            QuoteLine(
                code="etude_chiffrage",
                libelle="Préparation du devis détaillé après relevé technique",
                quantite=Decimal("1"),
                unite="forfait",
                prix_unitaire_ht=prix,
                total_ht=prix,
                description="Ligne provisoire à remplacer après visite ou photos.",
            )
        )
    return lignes


def calculer_totaux(lignes: list[QuoteLine], cfg: QuoteConfig) -> QuoteTotals:
    total_ht = money(sum((l.total_ht for l in lignes), Decimal("0")))
    if cfg.artisan.franchise_tva:
        tva = money("0")
    else:
        tva = money(total_ht * cfg.pricing.taux_tva)
    total_ttc = money(total_ht + tva)
    acompte = money(total_ttc * cfg.pricing.acompte_pourcentage)
    return QuoteTotals(total_ht=total_ht, tva=tva, total_ttc=total_ttc, acompte_ttc=acompte)


def conditions_devis(demande: ProjectRequest, cfg: QuoteConfig) -> list[str]:
    trade = cfg.metiers[demande.metier]
    conditions = [
        f"Devis valable {cfg.pricing.validite_jours} jours.",
        "Sous réserve de visite technique, accès chantier normal et supports en état correct.",
        "Les prix sont estimatifs tant que les photos, mesures et choix matériaux ne sont pas validés.",
    ]
    if cfg.artisan.franchise_tva:
        conditions.insert(0, "TVA non applicable, art. 293 B du CGI.")
    conditions.extend(trade.conditions)
    conditions.extend(cfg.artisan.mentions)
    return [c for c in conditions if c]


def message_client(demande: ProjectRequest, totaux: QuoteTotals) -> str:
    chantier = _chantier_client(demande.type_chantier)
    intro = (
        f"Bonjour, voici une première estimation pour {chantier} : "
        f"{_eur(totaux.total_ttc)} TTC."
    )
    if demande.questions:
        return intro + " Pour le finaliser, il me manque juste : " + " ".join(demande.questions)
    return intro + " Si cela vous convient, on valide les derniers détails ensemble et je vous envoie le devis complet."


# Formulation naturelle côté client : on parle du chantier, jamais du type technique
# ni de la référence interne du devis. Fallback neutre pour tout type non listé.
_CHANTIER_CLIENT = {
    "rénovation salle de bain": "votre salle de bain",
    "remplacement chauffe-eau": "votre chauffe-eau",
    "rénovation électrique": "vos travaux d'électricité",
    "peinture intérieure": "vos travaux de peinture",
    "menuiserie": "vos travaux de menuiserie",
    "carrelage": "votre carrelage",
    "rénovation générale": "votre projet de rénovation",
    "travaux de rénovation": "votre projet de rénovation",
}


def _chantier_client(type_chantier: str) -> str:
    cle = str(type_chantier or "").strip().lower()
    return _CHANTIER_CLIENT.get(cle, "vos travaux")


def _norm(texte: str) -> str:
    return texte.lower().replace("m²", "m2").replace("’", "'")


def _eur(value: Decimal) -> str:
    txt = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
    return f"{txt} €"


def _detecter_metier(normalise: str, cfg: QuoteConfig) -> tuple[str, bool]:
    """Retourne (métier, détection_fiable). Aucun mot-clé reconnu → repli sur le
    premier métier configuré, signalé comme incertain pour question à l'artisan."""
    scores = {}
    for nom, trade in cfg.metiers.items():
        scores[nom] = sum(1 for mot in trade.mots_cles if mot in normalise)
    meilleur = max(scores, key=scores.get)
    if scores[meilleur] > 0:
        return meilleur, True
    return next(iter(cfg.metiers)), False


def _detecter_ville(texte: str, cfg: QuoteConfig) -> str | None:
    bas = _norm(texte)
    for ville in sorted(cfg.villes_connues, key=len, reverse=True):
        if ville.lower() in bas:
            return ville
    match = re.search(r"\b(?:a|à|sur|près de|proche de)\s+([A-ZÉÈÀÂÎÏÔÛÙÇ][\wÉÈÀÂÎÏÔÛÙÇ' -]{2,})", texte)
    if match:
        return match.group(1).strip(" .,")
    return None


def _detecter_adresse(texte: str) -> str | None:
    match = re.search(
        r"\b\d{1,4}\s+(?:rue|avenue|av\.|boulevard|bd|impasse|chemin|route|place|allée|allee)\s+[^,.;\n]+",
        texte,
        flags=re.IGNORECASE,
    )
    return match.group(0).strip() if match else None


SURFACE_MIN = Decimal("1")
SURFACE_MAX = Decimal("500")

# Mots-nombres français de base : leur présence près d'une unité signale un montant
# dicté en toutes lettres, que l'extraction chiffrée ne sait pas lire.
_MOTS_NOMBRES = re.compile(
    r"\b(?:dix|vingt|trente|quarante|cinquante|soixante|cent|cents|mille)\b"
)


def _detecter_surface(normalise: str) -> tuple[Decimal | None, str | None]:
    """Retourne (surface, alerte). Une valeur négative ou hors plage plausible
    n'est jamais chiffrée : elle déclenche une question de confirmation."""
    match = re.search(
        r"(?<![\d,.-])(\d+(?:[,.]\d+)?)\s*(?:m2|mètres carrés|metres carres)", normalise
    )
    if not match:
        return None, None
    valeur = Decimal(match.group(1).replace(",", "."))
    if valeur < SURFACE_MIN or valeur > SURFACE_MAX:
        return None, (
            f"La surface détectée ({match.group(1)} m²) semble inhabituelle : "
            "pouvez-vous confirmer la surface exacte ?"
        )
    return valeur, None


def _nombres_en_lettres(normalise: str) -> bool:
    if not _MOTS_NOMBRES.search(normalise):
        return False
    return any(u in normalise for u in ("euro", "€", "m2", "mètre", "metre"))


def _detecter_type_chantier(normalise: str) -> str:
    for libelle, mots in CHANTIER_PATTERNS:
        if any(m in normalise for m in mots):
            return libelle
    return "travaux de rénovation"


def _detecter_urgence(normalise: str) -> str:
    if any(m in normalise for m in ["pas urgent", "pas spécialement urgent", "pas specialement urgent", "non urgent"]):
        return "standard"
    if any(m in normalise for m in ["urgent", "urgence", "cette semaine", "rapidement"]):
        return "urgent"
    if any(m in normalise for m in ["mois prochain", "dans 1 mois", "dans un mois"]):
        return "sous_30_jours"
    return "standard"


def _detecter_prestations(normalise: str, trade: TradeConfig) -> tuple[list[str], list[str]]:
    prestations: list[str] = []
    materiaux: list[str] = []
    for item in trade.postes:
        if any(mot in normalise for mot in item.mots_cles):
            prestations.append(item.libelle)
            materiaux.extend(item.materiaux)
    return prestations, materiaux


def _detecter_contraintes(normalise: str) -> list[str]:
    contraintes = []
    for libelle, mots in CONTRAINTES.items():
        if any(m in normalise for m in mots):
            contraintes.append(libelle)
    return contraintes


def _infos_manquantes(
    trade: TradeConfig,
    ville: str | None,
    adresse: str | None,
    surface: Decimal | None,
    prestations: list[str],
    normalise: str,
) -> list[str]:
    manquants = []
    for champ in trade.questions_requises:
        if champ == "ville" and not ville:
            manquants.append(champ)
        elif champ == "adresse" and not adresse:
            manquants.append(champ)
        elif champ == "surface" and surface is None:
            manquants.append(champ)
        elif champ == "prestations" and not prestations:
            manquants.append(champ)
        elif champ == "gamme_materiaux" and not any(
            m in normalise for m in ["standard", "milieu de gamme", "premium", "haut de gamme"]
        ):
            manquants.append(champ)
        elif champ == "photos" and "photo" not in normalise:
            manquants.append(champ)
        elif champ == "delai" and "urgent" not in normalise and "avant" not in normalise:
            manquants.append(champ)
    return manquants


def _item_concerne(mots_cles: list[str], texte: str, prestations: list[str]) -> bool:
    normalise = _norm(texte)
    if any(mot in normalise for mot in mots_cles):
        return True
    prestations_norm = _norm(" ".join(prestations))
    return any(mot in prestations_norm for mot in mots_cles)
