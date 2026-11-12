import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend import app as video_app


class VoiceCloneUnitTests(unittest.TestCase):
    def test_transcription_reports_cloudflare_rate_limit_without_hiding_root_cause(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            audio = folder / "rendered.mp4"
            audio.write_bytes(b"video")
            def fake_run(command, timeout=240):
                chunk_pattern = Path(command[-1])
                chunk_path = Path(str(chunk_pattern).replace("%04d", "0000"))
                chunk_path.write_bytes(b"audio chunk")
                return b""
            rate_limit = video_app.urllib.error.HTTPError(
                "https://api.cloudflare.com/", 429, "Too Many Requests", {}, None
            )
            with (
                patch.dict("os.environ", {
                    "CLOUDFLARE_ACCOUNT_ID": "test-account",
                    "CLOUDFLARE_AI_API_TOKEN": "test-token",
                }),
                patch.object(video_app, "run", side_effect=fake_run),
                patch.object(video_app.urllib.request, "urlopen", side_effect=rate_limit),
            ):
                with self.assertRaisesRegex(RuntimeError, "বিনামূল্যের সীমা বা অনুরোধের হার"):
                    video_app.transcribe_uploaded_audio(audio, folder)

    def test_voice_gradio_client_uses_optional_huggingface_token(self):
        from types import SimpleNamespace
        fake_client = Mock()
        fake_module = SimpleNamespace(Client=fake_client)
        with (
            patch.dict("sys.modules", {"gradio_client": fake_module}),
            patch.dict("os.environ", {"HF_TOKEN": "hf-test-token"}, clear=False),
        ):
            video_app._make_voice_gradio_client("owner/space", 90.0)
        fake_client.assert_called_once_with(
            "owner/space",
            verbose=False,
            httpx_kwargs={"timeout": 90.0},
            token="hf-test-token",
        )

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

    def test_consecutive_bengali_sentences_share_one_clone_chunk_for_natural_flow(self):
        chunks = video_app._split_voice_clone_text_by_language(
            "আসসালামু আলাইকুম। আজ আমরা বাংলাদেশের প্রকৃতি নিয়ে কথা বলব।"
        )
        self.assertEqual([language for language, _ in chunks], ["bn"])
        self.assertEqual(
            [text for _, text in chunks],
            ["আসসালামু আলাইকুম। আজ আমরা বাংলাদেশের প্রকৃতি নিয়ে কথা বলব।"],
        )

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
            self.assertTrue(all("-af" in command and "apad=pad_dur=0.25" in command for command in chunk_conversions))

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

    def test_provider_stops_immediately_when_free_zerogpu_quota_is_exhausted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            calls = []

            def quota_exhausted(script, normalized, space):
                calls.append(space)
                raise RuntimeError(
                    "You have exceeded your ZeroGPU runs limit. "
                    "Authenticate with a Hugging Face token."
                )

            with self.assertRaisesRegex(RuntimeError, "ZeroGPU quota exhausted"):
                video_app._clone_with_provider_fallback(
                    "পরীক্ষা", folder / "reference.wav",
                    ["first-space", "second-space"], quota_exhausted,
                    "bn", folder, "quota-test",
                )

            self.assertEqual(calls, ["first-space"])

    def test_bengali_quota_exhaustion_does_not_try_vakya_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            reference = folder / "reference.m4a"
            reference.write_bytes(b"reference audio")
            primary_calls = []
            fallback_calls = []

            def fake_run(command, timeout=240):
                Path(command[-1]).write_bytes(b"normalized audio" * 20)
                return b""

            def primary(*args, **kwargs):
                primary_calls.append(args[2])
                raise RuntimeError("Hugging Face free ZeroGPU quota exhausted; stop retrying")

            def fallback(*args, **kwargs):
                fallback_calls.append(args[2])
                raise AssertionError("Quota exhaustion must not call another HF provider")

            with (
                patch.object(video_app, "VOICE_CLONE_ENABLED", True),
                patch.object(video_app, "VOICE_CLONE_BN_SPACES", ["cosyvoice-space"]),
                patch.object(video_app, "VOICE_CLONE_BN_VAKYA_SPACES", ["vakya-space"]),
                patch.object(video_app, "run", side_effect=fake_run),
                patch.object(
                    video_app,
                    "_clone_with_provider_fallback",
                    side_effect=RuntimeError("Hugging Face free ZeroGPU quota exhausted; stop retrying"),
                ) as provider_call,
            ):
                with self.assertRaisesRegex(RuntimeError, "বিনামূল্যের GPU সীমা শেষ হয়েছে"):
                    video_app.synthesize_cloned_voice("বাংলা পরীক্ষা।", reference, folder)

            self.assertEqual(provider_call.call_count, 1)

    def test_provider_retries_once_when_server_reports_busy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            good_audio = folder / "recovered.wav"
            good_audio.write_bytes(b"valid recovered audio" * 20)
            calls = []

            def busy_then_success(script, normalized, space):
                calls.append(space)
                if len(calls) == 1:
                    raise RuntimeError("The upstream server is busy; please try again")
                return str(good_audio)

            progress = []
            with patch.object(video_app.time, "sleep") as sleep:
                result, selected = video_app._clone_with_provider_fallback(
                    "পরীক্ষা", folder / "reference.wav",
                    ["busy-space"], busy_then_success,
                    "bn", folder, "busy-retry-test",
                    progress_callback=lambda percent, message: progress.append((percent, message))
                )

            self.assertEqual(calls, ["busy-space", "busy-space"])
            self.assertEqual(selected, "busy-space")
            self.assertEqual(result, good_audio)
            sleep.assert_called_once_with(2)
            self.assertTrue(any("আরেকবার চেষ্টা" in message for _, message in progress))

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
            "Speak clearly and naturally in Bengali and English, at a steady pace.<|endofprompt|>"
        ))
        self.assertLessEqual(len(args[0]), 500)
        self.assertTrue(args[0].endswith("আজকের খবর আপনাদের জানাচ্ছি।"))
        self.assertEqual(args[1], "FILE:/tmp/reference.wav")
        self.assertEqual(args[2:], (0, 0.95))
        self.assertEqual(kwargs["api_name"], "/generate_cross_lingual_audio")

    def test_chatterbox_uses_gentler_pacing_settings(self):
        calls = []

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def predict(self, *args, **kwargs):
                calls.append((args, kwargs))
                return "audio-result"

        with patch.dict("sys.modules", {
            "gradio_client": type("FakeGradioClient", (), {
                "Client": FakeClient,
                "handle_file": staticmethod(lambda path: f"FILE:{path}"),
            })
        }):
            result = video_app._clone_with_chatterbox(
                "This is a clear English test.",
                Path("/tmp/reference.wav"),
                "english-space",
            )

        self.assertEqual(result, "audio-result")
        args, kwargs = calls[0]
        self.assertEqual(args, ("This is a clear English test.", "FILE:/tmp/reference.wav", 0.5, 0.8, 0, 0.4))
        self.assertEqual(kwargs["api_name"], "/generate_tts_audio")

    def test_multilingual_chatterbox_uses_full_text_reference_and_cross_language_cfg(self):
        calls = []

        class FakeClient:
            def __init__(self, *args, **kwargs):
                calls.append(("client", args[0]))

            def predict(self, *args, **kwargs):
                calls.append(("predict", args, kwargs))
                return "audio-result"

        with patch.dict("sys.modules", {
            "gradio_client": type("FakeGradioClient", (), {
                "Client": FakeClient,
                "handle_file": staticmethod(lambda path: f"FILE:{path}"),
            })
        }):
            result = video_app._clone_with_chatterbox(
                "This is the complete English sentence.",
                Path("/tmp/reference.wav"),
                "ResembleAI/Chatterbox-Multilingual-TTS",
            )

        self.assertEqual(result, "audio-result")
        _, args, kwargs = calls[1]
        self.assertEqual(args, ())
        self.assertEqual(kwargs["text_input"], "This is the complete English sentence.")
        self.assertEqual(kwargs["language_id"], "en")
        self.assertEqual(kwargs["audio_prompt_path_input"], "FILE:/tmp/reference.wav")
        self.assertEqual(kwargs["cfgw_input"], 0.0)
        self.assertEqual(kwargs["api_name"], "/generate_tts_audio")

    def test_multilingual_fallback_chunk_limit_is_250_characters(self):
        script = ("This is a complete English sentence for testing. " * 20).strip()
        chunks = video_app._split_voice_clone_text_by_language(script, max_chars=250)
        self.assertTrue(all(len(text) <= 250 for _, text in chunks))
        self.assertEqual(" ".join(text for _, text in chunks), script)

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

 
    def test_voice_wait_heartbeat_updates_message_and_stops_for_finished_job(self):
        job_id = "heartbeat-test"
        with video_app.LOCK:
            video_app.JOBS[job_id] = {
                "status": "processing",
                "progress": 12,
                "message": "নিজের কণ্ঠ তৈরি হচ্ছে",
            }
        try:
            stop = video_app._start_job_wait_heartbeat(job_id, interval=0.01)
            try:
                deadline = video_app.time.monotonic() + 1.0
                while video_app.time.monotonic() < deadline:
                    with video_app.LOCK:
                        message = video_app.JOBS[job_id]["message"]
                    if "অপেক্ষার সময়" in message:
                        break
                    video_app.time.sleep(0.01)
                self.assertIn("অপেক্ষার সময়", message)
                self.assertEqual(video_app.JOBS[job_id]["progress"], 12)
            finally:
                stop()
            with video_app.LOCK:
                video_app.JOBS[job_id]["status"] = "completed"
                before = video_app.JOBS[job_id]["message"]
            video_app.time.sleep(0.03)
            with video_app.LOCK:
                self.assertEqual(video_app.JOBS[job_id]["message"], before)
        finally:
            with video_app.LOCK:
                video_app.JOBS.pop(job_id, None)


    def test_audio_token_diagnostics_are_included_in_bangla_report(self):
        report = video_app._audio_token_diagnostics_report({
            "matched_tokens": 17,
            "missing_tokens": 2,
            "extra_tokens": 1,
        })
        self.assertIn("2টি শব্দ অনুপস্থিত", report)
        self.assertIn("1টি অতিরিক্ত শব্দ", report)
        self.assertIn("17টি শব্দ মিলে গেছে", report)

    def test_unavailable_audio_diagnostics_do_not_invent_word_counts(self):
        report = video_app._audio_token_diagnostics_report({
            "status": "unavailable",
            "matched_tokens": None,
            "missing_tokens": None,
            "extra_tokens": None,
        })
        self.assertEqual(report, "")



class NarrationTranscriptionReuseTests(unittest.TestCase):
    def test_single_narration_transcription_can_drive_audio_qc(self):
        transcription = {
            "text": "আমি আজ বাংলা বলছি today is sunny",
            "word_timestamps": [
                {"word": "আমি", "start": 0.0, "end": 0.3},
                {"word": "আজ", "start": 0.3, "end": 0.5},
                {"word": "বাংলা", "start": 0.5, "end": 0.9},
                {"word": "বলছি", "start": 0.9, "end": 1.2},
                {"word": "today", "start": 1.2, "end": 1.5},
                {"word": "is", "start": 1.5, "end": 1.6},
                {"word": "sunny", "start": 1.6, "end": 2.0},
            ],
        }
        result = video_app._audio_verification_from_transcription(
            "আমি আজ বাংলা বলছি today is sunny", transcription
        )
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["matched_tokens"], 7)
        self.assertEqual(result["missing_tokens"], 0)
        self.assertEqual(result["extra_tokens"], 0)
        self.assertEqual(result["transcript_characters"], len(transcription["text"]))
        self.assertEqual(result["source"], "source_narration_audio_before_mux")
        # The same returned object still carries the provider's explicit times for captions.
        self.assertEqual(len(transcription["word_timestamps"]), 7)
        self.assertEqual(transcription["word_timestamps"][0]["start"], 0.0)

    def test_unavailable_narration_transcription_is_not_treated_as_verified(self):
        with self.assertRaises(RuntimeError):
            video_app._audio_verification_from_transcription(
                "আমি আজ বলছি", None
            )

    def test_transcription_failure_reason_is_accessible_and_specific(self):
        self.assertIn(
            "বিনামূল্যের সীমা",
            video_app._transcription_failure_reason(
                RuntimeError("Whisper-এর বিনামূল্যের সীমা শেষ")
            ),
        )
        self.assertIn(
            "TimeoutError",
            video_app._transcription_failure_reason(TimeoutError("timeout")),
        )



class PublicationReleaseGateTests(unittest.TestCase):
    def _good_checks(self):
        return {
            "image_count": 2,
            "semantic_review": {"reviewed": 2, "matched": 2, "unavailable": 0},
            "audio_verification": {"status": "matched", "missing_tokens": 0, "extra_tokens": 0},
            "caption_alignment": {"status": "asr_word_timestamps", "matched_word_timestamps": 8, "script_word_count": 8},
            "subtitle_ocr": {"status": "passed"},
            "scene_audit": [
                {"final_visual_status": "matched"},
                {"final_visual_status": "retry_matched"},
            ],
            "technical_ok": True,
        }

    def test_share_allowed_only_when_every_required_check_passes(self):
        result = video_app._publication_gate_decision(**self._good_checks())
        self.assertTrue(result["share_allowed"])
        self.assertEqual(result["publication_status"], "ready")
        self.assertEqual(result["reasons"], [])

    def test_missing_image_review_blocks_sharing(self):
        checks = self._good_checks()
        checks["semantic_review"] = {"reviewed": 1, "matched": 1, "unavailable": 0}
        result = video_app._publication_gate_decision(**checks)
        self.assertFalse(result["share_allowed"])
        self.assertEqual(result["publication_status"], "blocked")
        self.assertTrue(any("সব পটভূমির ছবি" in reason for reason in result["reasons"]))

    def test_estimated_caption_timing_blocks_sharing(self):
        checks = self._good_checks()
        checks["caption_alignment"] = {"status": "estimated"}
        result = video_app._publication_gate_decision(**checks)
        self.assertFalse(result["share_allowed"])
        self.assertTrue(any("অনুমানভিত্তিক সময়" in reason for reason in result["reasons"]))

    def test_missing_subtitle_ocr_blocks_sharing_even_with_word_timestamps(self):
        checks = self._good_checks()
        checks["subtitle_ocr"] = {}
        result = video_app._publication_gate_decision(**checks)
        self.assertFalse(result["share_allowed"])
        self.assertTrue(any("OCR দিয়ে যাচাই হয়নি" in reason for reason in result["reasons"]))

    def test_audio_mismatch_or_unavailable_blocks_sharing(self):
        for status in ("mismatch", "unavailable", "review_required"):
            checks = self._good_checks()
            checks["audio_verification"] = {"status": status}
            result = video_app._publication_gate_decision(**checks)
            self.assertFalse(result["share_allowed"])


    def test_every_final_scene_must_have_a_verified_match(self):
        checks = self._good_checks()
        checks["scene_audit"][1]["final_visual_status"] = "not_reviewed"
        result = video_app._publication_gate_decision(**checks)
        self.assertFalse(result["share_allowed"])
        checks = self._good_checks()
        checks["scene_audit"] = checks["scene_audit"][:1]
        result = video_app._publication_gate_decision(**checks)
        self.assertFalse(result["share_allowed"])

    def test_missing_or_extra_spoken_words_blocks_sharing_even_when_similarity_passes(self):
        for field in ("missing_tokens", "extra_tokens"):
            checks = self._good_checks()
            checks["audio_verification"][field] = 1
            result = video_app._publication_gate_decision(**checks)
            self.assertFalse(result["share_allowed"])

    def test_partial_asr_word_alignment_blocks_sharing(self):
        checks = self._good_checks()
        checks["caption_alignment"]["matched_word_timestamps"] = 7
        result = video_app._publication_gate_decision(**checks)
        self.assertFalse(result["share_allowed"])


    def test_unverified_technical_audio_or_video_blocks_sharing(self):
        checks = self._good_checks()
        checks["technical_ok"] = False
        result = video_app._publication_gate_decision(**checks)
        self.assertFalse(result["share_allowed"])
        self.assertEqual(result["publication_status"], "blocked")



class SubtitleOCRVerificationTests(unittest.TestCase):
    def test_tesseract_tsv_words_are_assigned_to_the_correct_panel(self):
        tsv = (
            "level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n"
            "5\\t1\\t1\\t1\\t1\\t1\\t10\\t40\\t80\\t25\\t95\\tবাংলা\\n"
            "5\\t1\\t1\\t1\\t1\\t2\\t10\\t400\\t60\\t25\\t92\\ttest\\n"
        )
        panels = video_app._parse_tesseract_tsv_panels(tsv, 364, 388, 2)
        self.assertIn("বাংলা", panels[0])
        self.assertNotIn("test", panels[0])
        self.assertIn("test", panels[1])

    def test_every_caption_frame_active_word_must_be_detected(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frames = root / "caption-frames"
            frames.mkdir()
            first = frames / "frame-000000.png"
            second = frames / "frame-000001.png"
            video_app.Image.new("RGB", (360, 640), "black").save(first)
            video_app.Image.new("RGB", (360, 640), "black").save(second)
            listing = root / "caption-frames.txt"
            listing.write_text(
                f"file '{first.as_posix()}'\\nduration 1.0\\n"
                f"file '{second.as_posix()}'\\nduration 1.0\\n",
                encoding="utf-8",
            )
            tsv = (
                "level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n"
                "5\\t1\\t1\\t1\\t1\\t1\\t10\\t40\\t80\\t25\\t95\\tবাংলা\\n"
                "5\\t1\\t1\\t1\\t1\\t2\\t10\\t400\\t60\\t25\\t92\\ttest\\n"
            )
            fake = SimpleNamespace(returncode=0, stdout="List of available languages (2):\\nben\\neng\\n", stderr="")
            ocr = SimpleNamespace(returncode=0, stdout=tsv, stderr="")
            with patch.object(video_app.subprocess, "run", side_effect=[fake, ocr]):
                result = video_app._verify_subtitle_frames_with_ocr(listing, "বাংলা test", root)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["frames_checked"], 2)
            self.assertEqual(result["words_detected"], 2)

    def test_missing_active_caption_word_fails_ocr_verification(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frames = root / "caption-frames"
            frames.mkdir()
            first = frames / "frame-000000.png"
            second = frames / "frame-000001.png"
            video_app.Image.new("RGB", (360, 640), "black").save(first)
            video_app.Image.new("RGB", (360, 640), "black").save(second)
            listing = root / "caption-frames.txt"
            listing.write_text(
                f"file '{first.as_posix()}'\\nduration 1.0\\n"
                f"file '{second.as_posix()}'\\nduration 1.0\\n",
                encoding="utf-8",
            )
            tsv = (
                "level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n"
                "5\\t1\\t1\\t1\\t1\\t1\\t10\\t40\\t80\\t25\\t95\\tবাংলা\\n"
            )
            fake = SimpleNamespace(returncode=0, stdout="List of available languages (2):\\nben\\neng\\n", stderr="")
            ocr = SimpleNamespace(returncode=0, stdout=tsv, stderr="")
            with patch.object(video_app.subprocess, "run", side_effect=[fake, ocr]):
                result = video_app._verify_subtitle_frames_with_ocr(listing, "বাংলা test", root)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["words_missing"], 1)


if __name__ == "__main__":
    unittest.main()


class TranscriptComparisonDiagnosticsTests(unittest.TestCase):
    def test_exact_bilingual_transcript_has_no_missing_or_extra_tokens(self):
        result = video_app._compare_script_transcript(
            "আমি ভালো আছি today is sunny", "আমি ভালো আছি today is sunny"
        )
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["matched_tokens"], 6)
        self.assertEqual(result["missing_tokens"], 0)
        self.assertEqual(result["extra_tokens"], 0)

    def test_omitted_and_added_words_are_reported_separately(self):
        result = video_app._compare_script_transcript(
            "আমি আজ বাজারে যাব", "আমি বাজারে যাব কাল"
        )
        self.assertEqual(result["matched_tokens"], 3)
        self.assertEqual(result["missing_tokens"], 1)
        self.assertEqual(result["extra_tokens"], 1)
        self.assertNotEqual(result["status"], "matched")

    def test_empty_transcript_does_not_claim_missing_word_count(self):
        result = video_app._compare_script_transcript("আমি যাব", "")
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["missing_tokens"])
        self.assertIsNone(result["extra_tokens"])

    def test_punctuation_and_case_do_not_create_false_mismatches(self):
        result = video_app._compare_script_transcript(
            "Hello, বাংলাদেশ!", "hello বাংলাদেশ"
        )
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["missing_tokens"], 0)
        self.assertEqual(result["extra_tokens"], 0)
