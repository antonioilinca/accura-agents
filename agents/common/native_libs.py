"""Rend les libs Homebrew de weasyprint trouvables sur macOS (PDF natif en local).

weasyprint charge pango / cairo / gdk-pixbuf par leur nom court (ex
``libgobject-2.0-0``). Sur macOS, dyld ne sait pas les résoudre sans
``DYLD_FALLBACK_LIBRARY_PATH`` — une variable lue au démarrage du process, donc
non modifiable une fois Python lancé. On la règle puis on relance le process une
seule fois (garde anti-boucle), assez tôt pour que ce soit transparent.

No-op dans tous les autres cas :
- hors macOS (Linux/Docker : les libs sont déjà dans le chemin standard) ;
- si Homebrew n'est pas installé (dossiers absents) ;
- si le chemin est déjà correctement réglé.

À appeler tout en haut d'un point d'entrée qui produit des PDF (devis, factures,
dashboard), AVANT tout import de weasyprint. Si quoi que ce soit échoue, l'agent
retombe proprement sur le HTML imprimable : aucune régression possible.
"""

from __future__ import annotations

import os
import sys

_FLAG = "_ACCURA_PDF_DYLD_OK"
_LIBDIRS = ("/opt/homebrew/lib", "/usr/local/lib")


def assurer_libs_pdf() -> None:
    """Configure DYLD pour Homebrew sur macOS et relance le process si nécessaire."""
    if sys.platform != "darwin" or os.environ.get(_FLAG):
        return

    libdirs = [d for d in _LIBDIRS if os.path.isdir(d)]
    if not libdirs:
        return

    actuel = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    deja = actuel.split(os.pathsep) if actuel else []
    if all(d in deja for d in libdirs):
        return  # chemin déjà complet : rien à faire

    # On ne relance QUE si le point d'entrée principal est un module « agents.* »
    # (lancé via « python -m agents.… »). Sous un test runner (pytest/unittest) ou un
    # REPL qui appellerait un main(), __main__ n'est pas un module agents : on ne touche
    # alors à rien, pour ne jamais remplacer le process de test.
    spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    nom_entree = spec.name if spec is not None else ""
    if not nom_entree.startswith("agents."):
        return

    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(libdirs + deja)
    os.environ[_FLAG] = "1"
    try:
        os.execv(sys.executable, [sys.executable, "-m", nom_entree, *sys.argv[1:]])
    except OSError:
        # Re-exec impossible : on continue sans PDF natif (fallback HTML).
        return
