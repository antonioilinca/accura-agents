"""Journal d'activité des agents pour le cockpit du dashboard.

Registre en mémoire thread-safe : le dashboard est multi-thread (un thread par
requête HTTP, plus un thread dédié par run d'agent). Les étapes s'ajoutent en
direct pendant qu'un agent travaille, et le polling du navigateur lit cet état.

Chaque run terminé est aussi persisté dans ``outputs/activity/runs.json`` pour
garder un historique entre deux redémarrages du dashboard. Aucune donnée
commerciale critique ici : c'est un journal de supervision et de démonstration.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from pathlib import Path

from agents.common.fileio import ecrire_json_atomique, lire_json

RACINE = Path(__file__).resolve().parents[2]
_PERSIST = RACINE / "outputs" / "activity" / "runs.json"
_MAX_RUNS = 40

_LOCK = threading.Lock()
_RUNS: list[dict] = []  # du plus ancien au plus récent


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def new_run(agent: str, agent_label: str, task: str) -> str:
    """Ouvre un run et renvoie son identifiant."""
    run_id = uuid.uuid4().hex[:10]
    run = {
        "id": run_id,
        "agent": agent,
        "agent_label": agent_label,
        "task": task,
        "status": "running",
        "started_at": _now(),
        "ended_at": None,
        "steps": [{"t": _now(), "message": f"Démarrage : {task}", "status": "info"}],
        "summary": "",
        "exports": {},
    }
    with _LOCK:
        _RUNS.append(run)
        del _RUNS[:-_MAX_RUNS]
    return run_id


def add_step(run_id: str, message: str, status: str = "info") -> None:
    """Ajoute une étape horodatée au run en cours (status: info|ok|warn|error)."""
    with _LOCK:
        for run in reversed(_RUNS):
            if run["id"] == run_id:
                run["steps"].append({"t": _now(), "message": message, "status": status})
                return


def finish_run(run_id: str, status: str, summary: str = "", exports: dict | None = None) -> None:
    """Clôt le run (status: done|error) et persiste l'historique."""
    with _LOCK:
        for run in reversed(_RUNS):
            if run["id"] == run_id:
                run["status"] = status
                run["summary"] = summary
                run["exports"] = exports or {}
                run["ended_at"] = _now()
                final = summary or ("Terminé." if status == "done" else "Arrêté sur une erreur.")
                run["steps"].append({
                    "t": _now(),
                    "message": final,
                    "status": "ok" if status == "done" else "error",
                })
                try:
                    ecrire_json_atomique(_PERSIST, _RUNS[-_MAX_RUNS:])
                except OSError:
                    pass
                return


def snapshot(limit: int = 12) -> list[dict]:
    """Runs récents (le plus récent en premier), copies défensives."""
    with _LOCK:
        recents = _RUNS[-limit:][::-1]
        return [dict(run, steps=list(run["steps"])) for run in recents]


def agent_states() -> dict[str, dict]:
    """Dernier état connu par agent (idle si jamais lancé)."""
    states: dict[str, dict] = {}
    with _LOCK:
        for run in _RUNS:  # ancien -> récent : le dernier run de chaque agent gagne
            states[run["agent"]] = {
                "status": run["status"],
                "summary": run["summary"],
                "at": run["ended_at"] or run["started_at"],
                "run_id": run["id"],
            }
    return states


def _charger_historique() -> None:
    data = lire_json(_PERSIST, [], list)
    if isinstance(data, list):
        with _LOCK:
            _RUNS.clear()
            # un run interrompu par un redémarrage ne doit pas rester "running"
            for run in data[-_MAX_RUNS:]:
                if run.get("status") == "running":
                    run["status"] = "error"
                    run["ended_at"] = run.get("ended_at") or run.get("started_at")
                _RUNS.append(run)


_charger_historique()
