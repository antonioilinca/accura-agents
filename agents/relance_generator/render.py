"""Export local des plans de relance Accura."""

from __future__ import annotations

import json
from pathlib import Path

from .models import FollowupPlan


def ecrire_exports(plan: FollowupPlan, dossier: Path) -> dict[str, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    path = dossier / f"{_file_stem(plan.id_devis)}-relances.json"
    path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"json": path}


def _file_stem(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")

