"""Génération de devis à partir d'une demande artisan brute.

MVP assumé : extraction déterministe + grille tarifaire configurable. Cela évite
d'inventer des prix et prépare proprement le branchement WhatsApp/transcription.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .models import (
    QuoteConfig,
    QuoteDocument,
    QuoteLine,
    QuoteTotals,
    ProjectRequest,
    TradeConfig,
    money,
)


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


def generer_devis(texte: str, cfg: QuoteConfig, id_devis: str | None = None) -> QuoteDocument:
    demande = extraire_demande(texte, cfg)
    lignes = chiffrer(demande, cfg)
    totaux = calculer_totaux(lignes, cfg)
    conditions = conditions_devis(demande, cfg)
    id_final = id_devis or f"ACC-{date.today().strftime('%Y%m%d')}-001"
    return QuoteDocument(
        id_devis=id_final,
        date_creation=date.today().isoformat(),
        artisan=cfg.artisan,
        demande=demande,
        lignes=lignes,
        totaux=totaux,
        conditions=conditions,
        message_client=message_client(id_final, demande, totaux),
    )


def extraire_demande(texte: str, cfg: QuoteConfig) -> ProjectRequest:
    normalise = _norm(texte)
    metier = _detecter_metier(normalise, cfg)
    trade = cfg.metiers[metier]
    ville = _detecter_ville(texte, cfg)
    adresse = _detecter_adresse(texte)
    surface = _detecter_surface(normalise)
    type_chantier = _detecter_type_chantier(normalise)
    urgence = _detecter_urgence(normalise)
    prestations, materiaux = _detecter_prestations(normalise, trade)
    contraintes = _detecter_contraintes(normalise)
    manquants = _infos_manquantes(trade, ville, adresse, surface, prestations, normalise)

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
        questions=[QUESTIONS[m] for m in manquants if m in QUESTIONS],
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
    conditions.extend(trade.conditions)
    conditions.extend(cfg.artisan.mentions)
    return [c for c in conditions if c]


def message_client(id_devis: str, demande: ProjectRequest, totaux: QuoteTotals) -> str:
    lieu = demande.ville or "votre chantier"
    intro = (
        f"Bonjour, voici une première estimation pour {demande.type_chantier} à {lieu} "
        f"(devis {id_devis}) : {totaux.total_ttc} € TTC."
    )
    if demande.questions:
        return intro + " Pour le finaliser proprement, il me manque : " + " ".join(demande.questions)
    return intro + " Si cela vous convient, je vous propose de valider les derniers détails avant envoi du devis PDF."


def _norm(texte: str) -> str:
    return texte.lower().replace("m²", "m2").replace("’", "'")


def _detecter_metier(normalise: str, cfg: QuoteConfig) -> str:
    scores = {}
    for nom, trade in cfg.metiers.items():
        scores[nom] = sum(1 for mot in trade.mots_cles if mot in normalise)
    meilleur = max(scores, key=scores.get)
    return meilleur if scores[meilleur] > 0 else next(iter(cfg.metiers))


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


def _detecter_surface(normalise: str) -> Decimal | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:m2|mètres carrés|metres carres)", normalise)
    if not match:
        return None
    return Decimal(match.group(1).replace(",", "."))


def _detecter_type_chantier(normalise: str) -> str:
    for libelle, mots in CHANTIER_PATTERNS:
        if any(m in normalise for m in mots):
            return libelle
    return "travaux de rénovation"


def _detecter_urgence(normalise: str) -> str:
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

