from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.voice_intake import transcriber
from agents.voice_intake.transcriber import transcrire


class VoiceIntakeTest(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
        handle.write(b"faux audio")
        handle.close()
        self.audio = handle.name

    def tearDown(self) -> None:
        Path(self.audio).unlink(missing_ok=True)

    def test_audio_absent_leve_erreur(self) -> None:
        with self.assertRaises(FileNotFoundError):
            transcrire("/tmp/inexistant-accura-987654.m4a")

    def test_provider_inconnu_leve_erreur(self) -> None:
        with self.assertRaises(ValueError):
            transcrire(self.audio, provider="martien")

    def test_routage_local_par_defaut(self) -> None:
        with patch.object(transcriber, "_transcrire_local", return_value="texte local") as faux:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ACCURA_TRANSCRIBE_PROVIDER", None)
                sortie = transcrire(self.audio)
        self.assertEqual(sortie, "texte local")
        faux.assert_called_once()

    def test_routage_openai_explicite(self) -> None:
        with patch.object(transcriber, "_transcrire_openai", return_value="texte openai") as faux:
            sortie = transcrire(self.audio, provider="openai")
        self.assertEqual(sortie, "texte openai")
        faux.assert_called_once()

    def test_openai_sans_cle_leve_erreur(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with self.assertRaises(RuntimeError):
                transcrire(self.audio, provider="openai")


if __name__ == "__main__":
    unittest.main()
