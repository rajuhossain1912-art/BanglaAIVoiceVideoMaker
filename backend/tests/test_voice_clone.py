import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import app as video_app


class VoiceCloneUnitTests(unittest.TestCase):
    def test_split_voice_clone_text_respects_limit_and_preserves_text(self):
        script = ("বাংলাদেশের উন্নয়ন মানুষের সম্মিলিত প্রচেষ্টার ওপর নির্ভর করে। " * 12).strip()
        chunks = video_app._split_voice_clone_text(script, max_chars=80)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 80 for chunk in chunks))
        self.assertEqual(" ".join(chunks), script)

    def test_provider_fallback_tries_next_space_after_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            good_audio = folder / "good.wav"
            good_audio.write_bytes(b"valid audio" * 20)
            calls = []

            def fake_clone(script, normalized, space):
                calls.append(space)
                if space == "first-space":
                    raise TimeoutError("space is busy")
                return str(good_audio)

            result, selected = video_app._clone_with_provider_fallback(
                "পরীক্ষা", folder / "reference.wav",
                ["first-space", "second-space"], fake_clone,
                "bn", folder, "unit-test"
            )

            self.assertEqual(calls, ["first-space", "second-space"])
            self.assertEqual(selected, "second-space")
            self.assertEqual(result, good_audio)

    def test_clone_reports_start_and_completion_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            reference = folder / "reference.m4a"
            reference.write_bytes(b"reference audio")
            candidate = folder / "candidate.wav"
            candidate.write_bytes(b"generated audio" * 20)
            progress = []

            def fake_run(command, timeout=240):
                output_path = Path(command[-1])
                output_path.write_bytes(b"normalized audio" * 20)
                return b""

            def fake_provider(*args, **kwargs):
                return candidate, "test-space"

            with patch.object(video_app, "VOICE_CLONE_ENABLED", True), \
                 patch.object(video_app, "run", side_effect=fake_run), \
                 patch.object(video_app, "_clone_with_provider_fallback", side_effect=fake_provider):
                output = video_app.synthesize_cloned_voice(
                    "আজকের পরীক্ষামূলক বাংলা বক্তব্য।",
                    reference,
                    folder,
                    progress_callback=lambda percent, message: progress.append((percent, message))
                )

            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 100)
            self.assertEqual([item[0] for item in progress], [12, 30])
            self.assertIn("অংশ 1/1", progress[0][1])
            self.assertIn("1/1 অংশ সম্পন্ন", progress[1][1])


if __name__ == "__main__":
    unittest.main()
