"""Export local des demandes d'avis Google."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import ReviewRequest


def ecrire_exports(request: ReviewRequest, dossier: Path) -> dict[str, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = dossier / f"avis-google-{stamp}.json"
    path.write_text(json.dumps(request.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (dossier / "dernier-avis-google.json").write_text(
        json.dumps(request.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"json": path}

