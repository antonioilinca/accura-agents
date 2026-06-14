"""Conversion HTML -> PDF pour les documents Accura (devis, factures).

Un seul point d'appel, dépendance optionnelle : si weasyprint (ou ses libs
système) n'est pas disponible, on renvoie None et l'appelant garde le HTML
imprimable comme secours (bouton « Imprimer »). Aucun crash possible côté agent.
"""

from __future__ import annotations


def html_to_pdf(html_str: str, base_url: str | None = None) -> bytes | None:
    """Rend un PDF (octets) à partir d'un HTML complet.

    base_url permet de résoudre les chemins relatifs (logo de l'artisan).
    Renvoie None si la génération PDF n'est pas disponible dans l'environnement.
    """
    try:
        from weasyprint import HTML
    except Exception:
        return None
    try:
        return HTML(string=html_str, base_url=base_url).write_pdf()
    except Exception:
        return None
