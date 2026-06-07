"""Transcription vocale pluggable pour Accura : vocal d'artisan -> texte.

Même esprit que la couche LLM (`lead_acquisition/llm.py`) : un seul point d'appel,
fournisseur réglable, défaut gratuit, bascule payante quand un client paie.

Fournisseurs (variable d'env `ACCURA_TRANSCRIBE_PROVIDER`) :

- `local`  : faster-whisper, 100 % local, GRATUIT, hors-ligne. **Défaut.**
             Modèle réglable via `ACCURA_WHISPER_MODEL` (tiny|base|small|medium ; défaut `small`).
             Nécessite l'extra `voice` : `uv pip install faster-whisper`.
- `openai` : API Whisper (`OPENAI_API_KEY`). Qualité maximale, payant. À activer plus tard.

Règle Accura : on ne fait QUE convertir la voix en texte. Aucun prix, total, TVA ou
acompte n'est décidé ici. Le texte est destiné à être RELU par l'artisan avant la
génération du devis (human-in-the-loop), car une transcription n'est jamais parfaite.
"""

from __future__ import annotations

import os
from pathlib import Path

# Cache des modèles locaux déjà chargés (le chargement coûte plusieurs secondes).
_MODELES_LOCAUX: dict[str, object] = {}


def transcrire(audio_path: str | Path, *, provider: str | None = None, model: str | None = None) -> str:
    """Transcrit un fichier audio en texte français. Lève une erreur claire si indisponible."""
    chemin = Path(audio_path)
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier audio introuvable : {chemin}")

    provider = (provider or os.environ.get("ACCURA_TRANSCRIBE_PROVIDER") or "local").strip().lower()
    if provider == "openai":
        return _transcrire_openai(chemin, model)
    if provider == "local":
        return _transcrire_local(chemin, model)
    raise ValueError(f"Fournisseur de transcription inconnu : {provider!r} (attendu : local | openai)")


def _transcrire_local(chemin: Path, model: str | None) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Mode vocal local indisponible : installe faster-whisper "
            "(`uv pip install faster-whisper`) ou bascule sur ACCURA_TRANSCRIBE_PROVIDER=openai."
        ) from exc

    taille = (model or os.environ.get("ACCURA_WHISPER_MODEL") or "small").strip()
    moteur = _MODELES_LOCAUX.get(taille)
    if moteur is None:
        moteur = WhisperModel(taille, device="cpu", compute_type="int8")
        _MODELES_LOCAUX[taille] = moteur

    segments, _info = moteur.transcribe(
        str(chemin),
        language="fr",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def _transcrire_openai(chemin: Path, model: str | None) -> str:
    import requests

    cle = os.environ.get("OPENAI_API_KEY", "")
    if not cle:
        raise RuntimeError("OPENAI_API_KEY manquant pour le fournisseur openai.")

    with chemin.open("rb") as fichier:
        reponse = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {cle}"},
            files={"file": (chemin.name, fichier)},
            data={"model": model or "whisper-1", "language": "fr"},
            timeout=120,
        )
    reponse.raise_for_status()
    return str(reponse.json().get("text", "")).strip()
