import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import app as video_app


class TranscriptionVadPolicyTests(unittest.TestCase):
    def test_generated_narration_qc_can_disable_vad_filter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            audio = folder / "voice.wav"
            audio.write_bytes(b"source audio")
            captured = {}

            def fake_run(command, timeout=240):
                output_pattern = Path(command[-1])
                output_pattern.parent.mkdir(parents=True, exist_ok=True)
                (output_pattern.parent / "speech-0000.mp3").write_bytes(b"audio chunk")
                return b""

            class FakeResponse(io.BytesIO):
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

            def fake_urlopen(request, timeout=55):
                captured.update(json.loads(request.data.decode("utf-8")))
                return FakeResponse(json.dumps({
                    "result": {"text": "আমি কখনো হাল ছাড়ব না"}
                }).encode("utf-8"))

            with (
                patch.dict("os.environ", {
                    "CLOUDFLARE_ACCOUNT_ID": "test-account",
                    "CLOUDFLARE_AI_API_TOKEN": "test-token",
                }),
                patch.object(video_app, "run", side_effect=fake_run),
                patch.object(video_app.urllib.request, "urlopen", side_effect=fake_urlopen),
            ):
                result = video_app.transcribe_uploaded_audio(
                    audio, folder, return_details=True, language_hint="bn", vad_filter=False
                )

            self.assertEqual(result["text"], "আমি কখনো হাল ছাড়ব না")
            self.assertIs(captured["vad_filter"], False)
            self.assertEqual(captured["language"], "bn")

    def test_uploaded_audio_keeps_existing_vad_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            audio = folder / "voice.wav"
            audio.write_bytes(b"source audio")
            captured = {}

            def fake_run(command, timeout=240):
                output_pattern = Path(command[-1])
                output_pattern.parent.mkdir(parents=True, exist_ok=True)
                (output_pattern.parent / "speech-0000.mp3").write_bytes(b"audio chunk")
                return b""

            class FakeResponse(io.BytesIO):
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

            def fake_urlopen(request, timeout=55):
                captured.update(json.loads(request.data.decode("utf-8")))
                return FakeResponse(json.dumps({
                    "result": {"text": "আমি আজ কথা বলছি"}
                }).encode("utf-8"))

            with (
                patch.dict("os.environ", {
                    "CLOUDFLARE_ACCOUNT_ID": "test-account",
                    "CLOUDFLARE_AI_API_TOKEN": "test-token",
                }),
                patch.object(video_app, "run", side_effect=fake_run),
                patch.object(video_app.urllib.request, "urlopen", side_effect=fake_urlopen),
            ):
                video_app.transcribe_uploaded_audio(audio, folder)

            self.assertIs(captured["vad_filter"], True)


if __name__ == "__main__":
    unittest.main()
