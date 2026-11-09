import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import app as video_app


class VoiceCloneUnitTests(unittest.TestCase):
    def test_gradio_remote_filedata_downloads_url_when_path_is_remote(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            payload = b"RIFF" + (b"generated-audio-data" * 12)
            result = {
                "path": "/tmp/gradio/remote-space-output.wav",
                "url": "https://space.example/gradio_api/file=output.wav",
            }
            with patch.object(video_app.urllib.request, "urlopen", return_value=io.BytesIO(payload)):
                output = video_app._write_gradio_audio_result(result, folder, "remote-test")
            self.assertIsNotNone(output)
            self.assertTrue(output.exists())
            self.assertEqual(output.read_bytes(), payload)

    def test_gradio_local_filedata_path_is_used_without_download(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            local_audio = folder / "local.wav"
            local_audio.write_bytes(b"local-audio" * 20)
            result = {
                "path": str(local_audio),
                "url": "https://space.example/gradio_api/file=unused.wav",
            }
            with patch.object(video_app.urllib.request, "urlopen") as download:
                output = video_app._write_gradio_audio_result(result, folder, "local-test")
            self.assertEqual(output, local_audio)
            download.assert_not_called()

    def test_gradio_filedata_object_supports_relative_url(self):
        class FileData:
            path = "/tmp/remote-space/audio.wav"
            url = "/gradio_api/file=audio.wav"

        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            payload = b"RIFF" + (b"audio-content" * 20)
            with patch.object(video_app.urllib.request, "urlopen", return_value=io.BytesIO(payload)) as download:
                output = video_app._write_gradio_audio_result(
                    FileData(), folder, "typed-filedata", base_url="https://owner-space.hf.space"
                )
            self.assertIsNotNone(output)
            self.assertEqual(output.read_bytes(), payload)
            self.assertTrue(download.call_args.args[0].full_url.startswith("https://owner-space.hf.space/gradio_api/"))

    def test_gradio_dict_relative_url_uses_space_host(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            payload = b"RIFF" + (b"audio-content" * 20)
            with patch.object(video_app.urllib.request, "urlopen", return_value=io.BytesIO(payload)) as download:
                output = video_app._write_gradio_audio_result(
                    {"path": "/tmp/remote/audio.wav", "url": "/file=audio.wav"},
                    folder, "relative-filedata", base_url="https://owner-space.hf.space"
                )
            self.assertIsNotNone(output)
            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual(download.call_args.args[0].full_url, "https://owner-space.hf.space/file=audio.wav")

    def test_split_voice_clone_text_respects_limit_and_preserves_text(self):
        script = ("বাংলাদেশের উন্নয়ন মানুষের সম্মিলিত প্রচেষ্টার ওপর নির্ভর করে। " * 12).strip()
        chunks = video_app._split_voice_clone_text(script, max_chars=80)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 80 for chunk in chunks))
        self.assertEqual(" ".join(chunks), script)

    def test_mixed_script_is_split_into_language_matched_chunks(self):
        chunks = video_app._split_voice_clone_text_by_language(
            "বাংলা কথা। This is English. আবার বাংলা।"
        )
        self.assertEqual([language for language, _ in chunks], ["bn", "en", "bn"])
        self.assertIn("This is English.", chunks[1][1])

    def test_inline_english_term_stays_with_bengali_sentence(self):
        chunks = video_app._split_voice_clone_text_by_language(
            "আজকের AI প্রযুক্তি আমাদের জীবন বদলে দিচ্ছে।"
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], "bn")
        self.assertEqual(chunks[0][1], "আজকের AI প্রযুক্তি আমাদের জীবন বদলে দিচ্ছে।")

    def test_standalone_english_sentence_uses_english_provider(self):
        chunks = video_app._split_voice_clone_text_by_language(
            "আজকের খবর। Artificial intelligence is changing our lives."
        )
        self.assertEqual([language for language, _ in chunks], ["bn", "en"])
        self.assertEqual(chunks[1][1], "Artificial intelligence is changing our lives.")

    def test_mixed_script_routes_english_chunks_to_english_clone_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            reference = folder / "reference.m4a"
            reference.write_bytes(b"reference audio")
            candidate = folder / "candidate.wav"
            candidate.write_bytes(b"generated audio" * 20)
            calls = []
            ffmpeg_commands = []

            def fake_run(command, timeout=240):
                ffmpeg_commands.append(command)
                Path(command[-1]).write_bytes(b"normalized audio" * 20)
                return b""

            def fake_provider(script, normalized, spaces, clone_function, language, *args, **kwargs):
                calls.append((script, list(spaces), clone_function, language))
                return candidate, f"{language}-test-space"

            with (
                patch.object(video_app, "VOICE_CLONE_ENABLED", True),
                patch.object(video_app, "VOICE_CLONE_EN_SPACES", ["english-space"]),
                patch.object(video_app, "VOICE_CLONE_BN_SPACES", ["bengali-space"]),
                patch.object(video_app, "VOICE_CLONE_BN_VAKYA_SPACES", ["vakya-space"]),
                patch.object(video_app, "run", side_effect=fake_run),
                patch.object(video_app, "_clone_with_provider_fallback", side_effect=fake_provider),
            ):
                output = video_app.synthesize_cloned_voice(
                    "বাংলা কথা। This is English. আবার বাংলা।", reference, folder
                )

            self.assertTrue(output.exists())
            self.assertEqual([call[3] for call in calls], ["bn", "en", "bn"])
            self.assertEqual(calls[0][1], ["bengali-space"])
            self.assertIs(calls[0][2], video_app._clone_with_cosyvoice)
            self.assertEqual(calls[1][1], ["english-space"])
            self.assertIs(calls[1][2], video_app._clone_with_chatterbox)
            self.assertEqual(calls[2][1], ["bengali-space"])
            self.assertIs(calls[2][2], video_app._clone_with_cosyvoice)
            chunk_conversions = [command for command in ffmpeg_commands if str(folder / "clone-part-") in str(command[-1])]
            self.assertEqual(len(chunk_conversions), 3)
            self.assertTrue(all("-af" in command and "apad=pad_dur=0.12" in command for command in chunk_conversions))

    def test_english_provider_failure_never_falls_back_to_bengali_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            reference = folder / "reference.m4a"
            reference.write_bytes(b"reference audio")
            candidate = folder / "candidate.wav"
            candidate.write_bytes(b"generated audio" * 20)
            calls = []

            def fake_run(command, timeout=240):
                Path(command[-1]).write_bytes(b"normalized audio" * 20)
                return b""

            def fake_provider(script, normalized, spaces, clone_function, language, *args, **kwargs):
                calls.append((list(spaces), language, clone_function))
                if language == "en":
                    raise RuntimeError("English provider unavailable")
                return candidate, "bengali-test-space"

            with (
                patch.object(video_app, "VOICE_CLONE_ENABLED", True),
                patch.object(video_app, "VOICE_CLONE_EN_SPACES", ["english-space"]),
                patch.object(video_app, "VOICE_CLONE_BN_SPACES", ["bengali-space"]),
                patch.object(video_app, "VOICE_CLONE_BN_VAKYA_SPACES", ["vakya-space"]),
                patch.object(video_app, "run", side_effect=fake_run),
                patch.object(video_app, "_clone_with_provider_fallback", side_effect=fake_provider),
            ):
                with self.assertRaisesRegex(RuntimeError, "নিজের কণ্ঠে অডিও তৈরি করা যায়নি"):
                    video_app.synthesize_cloned_voice(
                        "বাংলা কথা। This is English.", reference, folder
                    )

            self.assertEqual([call[1] for call in calls], ["bn", "en"])
            self.assertEqual(calls[0][0], ["bengali-space"])
            self.assertEqual(calls[1][0], ["english-space"])
            self.assertIs(calls[1][2], video_app._clone_with_chatterbox)

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

            progress = []
            result, selected = video_app._clone_with_provider_fallback(
                "পরীক্ষা", folder / "reference.wav",
                ["first-space", "second-space"], fake_clone,
                "bn", folder, "unit-test",
                progress_callback=lambda percent, message: progress.append((percent, message))
            )

            self.assertEqual(calls, ["first-space", "first-space", "second-space"])
            self.assertEqual(selected, "second-space")
            self.assertEqual(result, good_audio)
            self.assertEqual([item[0] for item in progress], [14, 14, 21])
            self.assertIn("কণ্ঠসেবা 1/2", progress[0][1])
            self.assertIn("আরেকবার চেষ্টা", progress[1][1])
            self.assertIn("কণ্ঠসেবা 2/2", progress[2][1])

    def test_provider_retries_once_after_transient_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            good_audio = folder / "recovered.wav"
            good_audio.write_bytes(b"valid recovered audio" * 20)
            calls = []

            def flaky_clone(script, normalized, space):
                calls.append(space)
                if len(calls) == 1:
                    raise TimeoutError("provider request timed out")
                return str(good_audio)

            progress = []
            with patch.object(video_app.time, "sleep") as sleep:
                result, selected = video_app._clone_with_provider_fallback(
                    "পরীক্ষা", folder / "reference.wav",
                    ["temporary-space"], flaky_clone,
                    "bn", folder, "retry-test",
                    progress_callback=lambda percent, message: progress.append((percent, message))
                )

            self.assertEqual(calls, ["temporary-space", "temporary-space"])
            self.assertEqual(selected, "temporary-space")
            self.assertEqual(result, good_audio)
            sleep.assert_called_once_with(2)
            self.assertTrue(any("আরেকবার চেষ্টা" in message for _, message in progress))

    def test_provider_retries_once_when_space_returns_no_audio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            good_audio = folder / "recovered.wav"
            good_audio.write_bytes(b"valid recovered audio" * 20)
            calls = []

            def empty_then_success(script, normalized, space):
                calls.append(space)
                if len(calls) == 1:
                    return None
                return str(good_audio)

            progress = []
            with patch.object(video_app.time, "sleep") as sleep:
                result, selected = video_app._clone_with_provider_fallback(
                    "পরীক্ষা", folder / "reference.wav",
                    ["bengali-space"], empty_then_success,
                    "bn", folder, "empty-audio-retry",
                    progress_callback=lambda percent, message: progress.append((percent, message))
                )

            self.assertEqual(calls, ["bengali-space", "bengali-space"])
            self.assertEqual(selected, "bengali-space")
            self.assertEqual(result, good_audio)
            sleep.assert_called_once_with(2)
            self.assertTrue(any("আরেকবার চেষ্টা" in message for _, message in progress))

    def test_cosyvoice_uses_clear_bengali_narrator_instruction(self):
        calls = []

        class FakeClient:
            src = "https://example-space.hf.space"

            def __init__(self, *args, **kwargs):
                pass

            def predict(self, *args, **kwargs):
                calls.append((args, kwargs))
                return ("audio-result", "done")

        with patch.dict("sys.modules", {
            "gradio_client": type("FakeGradioClient", (), {
                "Client": FakeClient,
                "handle_file": staticmethod(lambda path: f"FILE:{path}"),
            })
        }):
            result = video_app._clone_with_cosyvoice(
                "আজকের খবর আপনাদের জানাচ্ছি।",
                Path("/tmp/reference.wav"),
                "bengali-space",
            )

        self.assertEqual(result, ("audio-result", "https://example-space.hf.space"))
        args, kwargs = calls[0]
        self.assertTrue(args[0].startswith(
            "You are a professional Bengali narrator. Speak calmly and clearly.<|endofprompt|>"
        ))
        self.assertTrue(args[0].endswith("আজকের খবর আপনাদের জানাচ্ছি।"))
        self.assertEqual(args[1], "FILE:/tmp/reference.wav")
        self.assertEqual(args[2:], (0, 1.0))
        self.assertEqual(kwargs["api_name"], "/generate_cross_lingual_audio")

    def test_indicf5_adapter_transcribes_reference_then_generates_audio(self):
        calls = []

        class FakeClient:
            def __init__(self, *args, **kwargs):
                calls.append(("client", args[0]))

            def predict(self, *args, **kwargs):
                calls.append((kwargs.get("api_name"), args))
                return (24000, [0.0, 0.1, -0.1] * 1000)

        with (
            patch.dict("sys.modules", {
                "gradio_client": type("FakeGradioClient", (), {
                    "Client": FakeClient,
                    "handle_file": staticmethod(lambda path: f"FILE:{path}"),
                })
            }),
            patch.object(video_app, "transcribe_uploaded_audio", return_value="আমি আজ বাংলা বলছি।") as transcribe,
        ):
            result = video_app._clone_with_vakya(
                "বাংলা পরীক্ষা", Path("/tmp/reference.wav"), "ai4bharat/IndicF5"
            )

        self.assertEqual(result[0], 24000)
        self.assertEqual(calls[0], ("client", "ai4bharat/IndicF5"))
        self.assertEqual(calls[1][0], "/synthesize_speech")
        self.assertEqual(calls[1][1][0], "বাংলা পরীক্ষা")
        self.assertEqual(calls[1][1][1], "FILE:/tmp/reference.wav")
        self.assertEqual(calls[1][1][2], "আমি আজ বাংলা বলছি।")
        transcribe.assert_called_once_with(Path("/tmp/reference.wav"), Path("/tmp"))

    def test_bengali_clone_uses_vakya_pool_after_primary_pool_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            reference = folder / "reference.m4a"
            reference.write_bytes(b"reference audio")
            candidate = folder / "candidate.wav"
            candidate.write_bytes(b"generated audio" * 20)
            calls = []

            def fake_run(command, timeout=240):
                Path(command[-1]).write_bytes(b"normalized audio" * 20)
                return b""

            def fake_provider(script, normalized, spaces, clone_function, language, *args, **kwargs):
                calls.append((list(spaces), clone_function, language))
                if len(calls) == 1:
                    raise RuntimeError("primary Bengali provider pool unavailable")
                return candidate, "vakya-test-space"

            progress = []
            with (
                patch.object(video_app, "VOICE_CLONE_ENABLED", True),
                patch.object(video_app, "VOICE_CLONE_BN_SPACES", ["primary-space"]),
                patch.object(video_app, "VOICE_CLONE_BN_VAKYA_SPACES", ["vakya-space"]),
                patch.object(video_app, "run", side_effect=fake_run),
                patch.object(video_app, "_clone_with_provider_fallback", side_effect=fake_provider),
            ):
                output = video_app.synthesize_cloned_voice(
                    "বাংলা পরীক্ষামূলক বক্তব্য।", reference, folder,
                    progress_callback=lambda percent, message: progress.append((percent, message))
                )

            self.assertTrue(output.exists())
            self.assertEqual(calls[0][0], ["primary-space"])
            self.assertIs(calls[0][1], video_app._clone_with_cosyvoice)
            self.assertEqual(calls[1][0], ["vakya-space"])
            self.assertIs(calls[1][1], video_app._clone_with_vakya)
            self.assertEqual(calls[1][2], "bn_vakya_fallback")

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
                callback = kwargs.get("progress_callback")
                if callback:
                    callback(kwargs.get("progress_base", 15), "ফ্রি কণ্ঠসেবা 1/1 চেষ্টা করা হচ্ছে।")
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
            self.assertEqual([item[0] for item in progress], [12, 13, 14, 15, 30])
            self.assertIn("নমুনা অডিও প্রস্তুত", progress[0][1])
            self.assertIn("অংশ 1/1", progress[2][1])
            self.assertIn("কণ্ঠসেবা 1/1", progress[3][1])
            self.assertIn("1/1 অংশ সম্পন্ন", progress[4][1])


if __name__ == "__main__":
    unittest.main()
