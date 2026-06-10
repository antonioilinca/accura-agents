"""Écritures JSON atomiques et verrou de fichier simple.

Les registres locaux (pipeline CRM, profil artisan, historique de leads, compteurs
de numérotation) sont la seule mémoire commerciale d'un client : une écriture
interrompue ou deux écritures simultanées ne doivent jamais pouvoir les corrompre.

- `ecrire_json_atomique` : écrit dans un fichier temporaire puis remplace d'un coup
  (`os.replace`), pour qu'un crash ne laisse jamais un fichier vide ou tronqué.
- `lire_json` : lecture défensive, retourne la valeur par défaut si le fichier est
  absent, illisible ou n'a pas le type attendu.
- `verrou_fichier` : verrou inter-process par fichier `<nom>.lock`, avec reprise
  automatique d'un verrou orphelin (process tué) après `STALE_LOCK_SECONDS`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

STALE_LOCK_SECONDS = 30.0


def ecrire_json_atomique(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def lire_json(path: Path, defaut: Any, type_attendu: type = dict) -> Any:
    if not path.exists():
        return defaut
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defaut
    return data if isinstance(data, type_attendu) else defaut


class verrou_fichier:
    """Verrou exclusif inter-process : `with verrou_fichier(chemin):`.

    Portable (pas de fcntl) : création exclusive d'un fichier `<nom>.lock`.
    Un verrou plus vieux que STALE_LOCK_SECONDS est considéré orphelin et repris.
    """

    def __init__(self, path: Path, timeout: float = 10.0) -> None:
        self.lock_path = path.with_name(path.name + ".lock")
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "verrou_fichier":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        debut = time.monotonic()
        while True:
            try:
                self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, str(os.getpid()).encode("ascii"))
                return self
            except FileExistsError:
                if self._verrou_orphelin():
                    continue
                if time.monotonic() - debut > self.timeout:
                    raise TimeoutError(
                        f"Verrou occupé depuis trop longtemps : {self.lock_path}"
                    ) from None
                time.sleep(0.05)

    def __exit__(self, *exc_info: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass

    def _verrou_orphelin(self) -> bool:
        try:
            age = time.time() - self.lock_path.stat().st_mtime
        except FileNotFoundError:
            return True
        if age <= STALE_LOCK_SECONDS:
            return False
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass
        return True
