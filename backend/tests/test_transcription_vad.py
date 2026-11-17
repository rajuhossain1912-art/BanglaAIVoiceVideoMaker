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

    def test_whisper_response_preserves_detected_language_and_probability(self):
        parsed = video_app._parse_cloudflare_transcription_response({
            "result": {
                "text": "আমি আজ কথা বলছি",
                "transcription_info": {
                    "language": "bn",
                    "language_probability": 0.97,
                    "duration": 12.5,
                    "duration_after_vad": 12.5,
                },
                "word_count": 5,
            }
        }, return_details=True)
        self.assertEqual(parsed["transcription_info"]["language"], "bn")
        self.assertAlmostEqual(parsed["transcription_info"]["language_probability"], 0.97)
        self.assertEqual(parsed["transcription_info"]["duration"], 12.5)
        self.assertEqual(parsed["transcription_info"]["duration_after_vad"], 12.5)
        self.assertEqual(parsed["transcription_info"]["word_count"], 5)

    def test_whisper_language_metadata_appears_in_accessible_audio_report(self):
        report = video_app._audio_token_diagnostics_report({
            "matched_tokens": 4,
            "missing_tokens": 0,
            "extra_tokens": 0,
            "transcript_preview": "আমি আজ কথা বলছি",
            "transcription_info": [{
                "language": "bn",
                "language_probability": 0.97,
            }],
        })
        self.assertIn("Whisper শনাক্ত ভাষা: bn", report)
        self.assertIn("97.0 শতাংশ", report)
        report = video_app._audio_token_diagnostics_report({
            "matched_tokens": 4, "missing_tokens": 0, "extra_tokens": 0,
            "transcription_info": [{
                "language": "bn", "language_probability": 0.97,
                "duration": 12.5, "duration_after_vad": 12.5, "word_count": 5,
            }],
        })
        self.assertIn("অডিও দৈর্ঘ্য 12.50 সেকেন্ড", report)
        self.assertIn("Whisper-এর শব্দ গণনা 5", report)

    def test_invalid_whisper_language_probability_is_ignored(self):
        parsed = video_app._parse_cloudflare_transcription_response({
            "result": {
                "text": "hello",
                "transcription_info": {
                    "language": "en",
                    "language_probability": 2.5,
                },
            }
        }, return_details=True)
        self.assertEqual(parsed["transcription_info"]["language"], "en")
        self.assertIsNone(parsed["transcription_info"]["language_probability"])

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



    def test_daily_free_allocation_is_detected_from_provider_body_even_on_http_400(self):
        detail = video_app._cloudflare_whisper_http_error_detail(
            400,
            '{"success":false,"errors":[{"message":"you have used up your daily free allocation of 10,000 neurons"}]}',
        )
        self.assertIn("দৈনিক বিনামূল্যের বরাদ্দ শেষ", detail)

    def test_whisper_http_error_keeps_auth_rate_and_server_categories(self):
        self.assertIn("অনুমতি দেয়নি", video_app._cloudflare_whisper_http_error_detail(403, ""))
        self.assertIn("বিনামূল্যের সীমা", video_app._cloudflare_whisper_http_error_detail(429, ""))
        self.assertIn("সাময়িকভাবে ব্যস্ত", video_app._cloudflare_whisper_http_error_detail(503, ""))

    def test_daily_quota_failure_is_reported_in_plain_bangla(self):
        message = video_app._transcription_failure_reason(
            RuntimeError("Cloudflare Workers AI-এর দৈনিক বিনামূল্যের বরাদ্দ শেষ হয়েছে।")
        )
        self.assertIn("দৈনিক বিনামূল্যের বরাদ্দ শেষ", message)
        self.assertIn("নতুন দৈনিক বরাদ্দ", message)


class AudioTranscriptReportTests(unittest.TestCase):
    def test_audio_verification_exposes_short_whisper_transcript_preview(self):
        transcript = "আমি আজ নতুন কিছু শিখছি"
        result = video_app._audio_verification_from_transcription(
            "আমি আজ নতুন কিছু শিখছি",
            {"text": transcript, "word_timestamps": []},
        )
        self.assertEqual(result["transcript_preview"], transcript)
        self.assertEqual(result["transcript_characters"], len(transcript))

    def test_audio_report_includes_whisper_heard_text_for_diagnosis(self):
        report = video_app._audio_token_diagnostics_report({
            "matched_tokens": 4,
            "missing_tokens": 2,
            "extra_tokens": 1,
            "transcript_preview": "আমি আজ নতুন কিছু শিখছি",
        })
        self.assertIn("Whisper অডিওতে যা শুনেছে: আমি আজ নতুন কিছু শিখছি", report)

    def test_audio_transcript_preview_is_limited_to_1200_characters(self):
        result = video_app._audio_verification_from_transcription(
            "বাংলা",
            {"text": "ক" * 1400, "word_timestamps": []},
        )
        self.assertEqual(len(result["transcript_preview"]), 1200)


if __name__ == "__main__":
    unittest.main()
