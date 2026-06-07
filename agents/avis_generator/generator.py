"""Génération de messages de demande d'avis Google."""

from __future__ import annotations

from typing import Any

from .models import ReviewRequest


def generer_demande_avis(profile: dict[str, Any], client: str = "", chantier: str = "") -> ReviewRequest:
    company = profile.get("company", {}) or {}
    artisan_name = str(company.get("name") or "notre entreprise").strip()
    google_url = str(company.get("google_review_url") or "").strip()
    client_label = str(client or "Bonjour").strip()
    chantier_label = str(chantier or "les travaux réalisés").strip()

    salutation = client_label if client_label.lower().startswith("bonjour") else f"Bonjour {client_label},"
    if google_url:
        message = (
            f"{salutation}\n\n"
            f"Merci encore pour votre confiance pour {chantier_label}. "
            f"Si vous êtes satisfait du travail réalisé par {artisan_name}, votre avis Google nous aiderait beaucoup.\n\n"
            f"Vous pouvez laisser votre avis ici : {google_url}\n\n"
            "Merci d'avance et bonne journée."
        )
    else:
        message = (
            f"{salutation}\n\n"
            f"Merci encore pour votre confiance pour {chantier_label}. "
            f"Si vous êtes satisfait du travail réalisé par {artisan_name}, un avis Google nous aiderait beaucoup.\n\n"
            f"Vous pouvez rechercher \"{artisan_name}\" sur Google et cliquer sur \"Donner un avis\".\n\n"
            "Merci d'avance et bonne journée."
        )

    return ReviewRequest(
        artisan_name=artisan_name,
        google_review_url=google_url,
        client=client_label,
        chantier=chantier_label,
        message=message,
    )

