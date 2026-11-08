import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import app as video_app


class SceneIntervalDiagnosticsTests(unittest.TestCase):
    def test_warns_when_generated_images_cannot_meet_selected_interval(self):
        result = video_app._scene_interval_diagnostics(113.6, 17, 3)
        self.assertEqual(result["expected_images"], 38)
        self.assertEqual(result["average_seconds_per_image"], 6.7)
        self.assertTrue(result["warning"])

    def test_does_not_warn_when_image_count_covers_interval(self):
        result = video_app._scene_interval_diagnostics(30.0, 10, 3)
        self.assertEqual(result["expected_images"], 10)
        self.assertEqual(result["average_seconds_per_image"], 3.0)
        self.assertFalse(result["warning"])


    def test_visual_scene_count_tracks_selected_interval_for_short_video(self):
        scenes = ["আসসালামু আলাইকুম এটি বাংলা ভিডিও তৈরির পরীক্ষা"]
        result = video_app._visual_scenes_for_interval(scenes, 5.1, 3, 32)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(item == scenes[0] for item in result))

    def test_visual_scene_count_expands_long_sentence_without_fragmenting_it(self):
        words = [f"শব্দ{i}" for i in range(170)]
        sentence = " ".join(words) + "।"
        result = video_app._visual_scenes_for_interval([sentence], 113.6, 3, 48)
        self.assertEqual(len(result), 38)
        self.assertTrue(all(item == sentence for item in result))

    def test_multiple_sentences_keep_complete_meaning_and_order(self):
        scenes = [
            "একজন শিক্ষার্থী ব্রেইল বই পড়ছে।",
            "একজন শিক্ষক তাকে পড়তে সাহায্য করছেন।",
            "শিক্ষার্থীটি নতুন দক্ষতা শিখছে।",
        ]
        result = video_app._visual_scenes_for_interval(scenes, 30, 3, 48)
        self.assertEqual(len(result), 10)
        self.assertEqual(result[0], scenes[0])
        self.assertEqual(result[-1], scenes[-1])
        self.assertTrue(all(item in scenes for item in result))
        self.assertEqual([result.count(scene) for scene in scenes], [3, 4, 3])

    def test_repeated_visual_slots_keep_subject_but_change_composition(self):
        subject = "A Bangladeshi student reading a Braille book in a classroom."
        first = video_app._vary_visual_prompt(subject, 0)
        second = video_app._vary_visual_prompt(subject, 1)
        third = video_app._vary_visual_prompt(subject, 2)
        self.assertIn(subject, first)
        self.assertIn(subject, second)
        self.assertIn(subject, third)
        self.assertNotEqual(first, second)
        self.assertNotEqual(second, third)
        self.assertIn("wide establishing", first)
        self.assertIn("medium eye-level", second)
        self.assertIn("over-the-shoulder", third)

    def test_visual_composition_variation_cycles_after_eight_slots(self):
        subject = "A farmer working in a rice field."
        self.assertEqual(
            video_app._vary_visual_prompt(subject, 0),
            video_app._vary_visual_prompt(subject, 8),
        )

    def test_visual_scene_count_can_exceed_legacy_48_image_ceiling(self):
        scenes = ["একজন শিক্ষার্থী ব্রেইল বই পড়ছে।"]
        result = video_app._visual_scenes_for_interval(scenes, 153.1, 3, None)
        self.assertEqual(len(result), 52)
        self.assertTrue(all(item == scenes[0] for item in result))

    def test_zero_visual_limit_means_duration_based_unlimited_planning(self):
        scenes = ["একজন কৃষক ধানক্ষেতে কাজ করছেন।"]
        result = video_app._visual_scenes_for_interval(scenes, 150.1, 3, 0)
        self.assertEqual(len(result), 51)

    def test_whisper_transcript_parser_normalizes_bangla_and_english_speech(self):
        result = video_app._parse_cloudflare_transcription_response({
            "success": True,
            "result": {"text": "  আজ   একটি   ভিডিও।  Make it clear.  "}
        })
        self.assertEqual(result, "আজ একটি ভিডিও। Make it clear.")

    def test_whisper_transcript_parser_rejects_empty_audio_result(self):
        with self.assertRaises(RuntimeError):
            video_app._parse_cloudflare_transcription_response({
                "success": True,
                "result": {"text": "   "}
            })


    def test_whisper_parser_extracts_explicit_word_timestamps(self):
        result = video_app._parse_cloudflare_transcription_response({
            "success": True,
            "result": {
                "text": "আমি ভালো আছি",
                "segments": [{
                    "words": [
                        {"word": "আমি", "start": 0.1, "end": 0.4},
                        {"word": "ভালো", "start": 0.5, "end": 0.9},
                        {"word": "আছি", "start": 1.0, "end": 1.3},
                    ]
                }]
            }
        }, return_details=True, offset_seconds=120.0)
        self.assertEqual(result["text"], "আমি ভালো আছি")
        self.assertEqual(len(result["word_timestamps"]), 3)
        self.assertEqual(result["word_timestamps"][0]["start"], 120.1)
        self.assertEqual(result["word_timestamps"][-1]["end"], 121.3)

    def test_whisper_parser_keeps_empty_word_timestamps_when_not_provided(self):
        result = video_app._parse_cloudflare_transcription_response({
            "success": True,
            "result": {"text": "কথার প্রতিলিপি"}
        }, return_details=True)
        self.assertEqual(result["text"], "কথার প্রতিলিপি")
        self.assertEqual(result["word_timestamps"], [])

    def test_uploaded_audio_transcription_returns_word_timestamps_when_requested(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            audio_path = folder / "input.mp3"
            audio_path.write_bytes(b"fake audio")
            response_data = {
                "success": True,
                "result": {
                    "text": "আমি ভালো আছি",
                    "segments": [{
                        "words": [
                            {"word": "আমি", "start": 0.1, "end": 0.4},
                            {"word": "ভালো", "start": 0.5, "end": 0.9},
                            {"word": "আছি", "start": 1.0, "end": 1.3},
                        ]
                    }]
                }
            }

            def fake_run(command, timeout=240):
                if "-segment" in command:
                    pattern = Path(command[-1])
                    chunk_path = Path(str(pattern).replace("%04d", "0000"))
                    chunk_path.parent.mkdir(parents=True, exist_ok=True)
                    chunk_path.write_bytes(b"fake chunk")
                return b""

            response = contextlib.nullcontext(
                io.BytesIO(json.dumps(response_data, ensure_ascii=False).encode("utf-8"))
            )
            with patch.object(video_app, "run", side_effect=fake_run), \
                 patch.object(video_app.urllib.request, "urlopen", return_value=response):
                result = video_app.transcribe_uploaded_audio(
                    audio_path, folder, return_details=True
                )

            self.assertEqual(result["text"], "আমি ভালো আছি")
            self.assertEqual(len(result["word_timestamps"]), 3)
            self.assertEqual(result["word_timestamps"][0]["start"], 0.1)
            self.assertEqual(result["word_timestamps"][-1]["end"], 1.3)

    def test_caption_alignment_uses_asr_word_times_only_with_strong_text_match(self):
        script = "আমি ভালো আছি"
        timestamps = [
            {"word": "আমি", "start": 0.1, "end": 0.4},
            {"word": "ভালো", "start": 0.5, "end": 0.9},
            {"word": "আছি", "start": 1.0, "end": 1.3},
        ]
        script_tokens = video_app._normalize_transcript_tokens(script)
        timed_tokens = [video_app._normalize_transcript_tokens(item["word"])[0] for item in timestamps]
        matcher = video_app.difflib.SequenceMatcher(None, script_tokens, timed_tokens, autojunk=False)
        self.assertEqual(matcher.ratio(), 1.0)
        self.assertEqual(len(timestamps), len(script_tokens))

    def test_handles_missing_image_count(self):
        result = video_app._scene_interval_diagnostics(30.0, 0, 3)
        self.assertEqual(result["expected_images"], 10)
        self.assertIsNone(result["average_seconds_per_image"])
        self.assertTrue(result["warning"])


if __name__ == "__main__":
    unittest.main()
