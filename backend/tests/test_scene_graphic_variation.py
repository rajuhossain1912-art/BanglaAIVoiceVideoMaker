import contextlib
import io
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from backend import app as video_app


class SceneImageSimilarityTests(unittest.TestCase):
    def _image(self, folder: Path, name: str, color):
        path = folder / name
        Image.new("RGB", (120, 180), color).save(path)
        return path

    def test_bengali_bus_keyword_does_not_match_inside_biswas(self):
        self.assertFalse(video_app._contains_visual_term("নিজের ওপর বিশ্বাস রাখুন", "বাস"))
        self.assertTrue(video_app._contains_visual_term("বাসস্ট্যান্ডে একটি বাস দাঁড়িয়ে আছে", "বাস"))

    def test_bengali_inflections_match_their_visual_subjects(self):
        self.assertTrue(video_app._contains_visual_term("কৃষকেরা ধানক্ষেতে কাজ করছেন", "কৃষক"))
        self.assertTrue(video_app._contains_visual_term("বাসের যাত্রীরা অপেক্ষা করছেন", "বাস"))
        self.assertTrue(video_app._contains_visual_term("ডাক্তারের সঙ্গে রোগীর কথা হচ্ছে", "ডাক্তার"))

    def test_bengali_prefix_matching_does_not_match_unrelated_words(self):
        self.assertFalse(video_app._contains_visual_term("বাস্তব জীবনের গল্প", "বাস"))
        self.assertFalse(video_app._contains_visual_term("বিশ্বাস ধরে রাখুন", "বাস"))

    def test_motivation_text_selects_motivation_visual_not_bus(self):
        concepts = video_app._matched_visual_concepts("নিজের ওপর বিশ্বাস রাখুন এবং চেষ্টা চালিয়ে যান")
        self.assertTrue(any("determined Bangladeshi person" in item for item in concepts))
        self.assertFalse(any("passenger bus" in item for item in concepts))

    def test_success_and_forward_progress_select_motivation_visual(self):
        for text in (
            "জীবনে সফল হতে হলে সামনে এগিয়ে যেতে হবে",
            "বাধা এলেও নিজের লক্ষ্যের পথে থেমে যাবেন না",
        ):
            concepts = video_app._matched_visual_concepts(text)
            self.assertTrue(any("determined Bangladeshi person" in item for item in concepts))

    def test_motivation_fallback_has_three_distinct_scene_variants(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outputs = []
            with patch.object(video_app, "find_generated_image", return_value=(None, "")), \
                 patch.object(video_app, "ALLOW_LICENSED_IMAGE_FALLBACK", False):
                for index in range(3):
                    folder = root / str(index)
                    folder.mkdir()
                    outputs.append(video_app.make_background(
                        "জীবনে সফল হতে হলে সামনে এগিয়ে যেতে হবে",
                        folder, variation_seed=index, scene_index=index
                    ))
            self.assertEqual(len({path.read_bytes() for path in outputs}), 3)

    def test_detects_identical_scene_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            first = self._image(folder, "first.png", (80, 110, 140))
            second = self._image(folder, "second.png", (80, 110, 140))
            self.assertTrue(video_app._scene_images_too_similar(first, second))

    def test_detects_near_identical_scene_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            first = self._image(folder, "first.png", (80, 110, 140))
            second = self._image(folder, "second.png", (88, 118, 148))
            self.assertTrue(video_app._scene_images_too_similar(first, second))

    def test_keeps_visually_distinct_scene_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            first = self._image(folder, "first.png", (40, 70, 100))
            second = self._image(folder, "second.png", (180, 190, 200))
            self.assertFalse(video_app._scene_images_too_similar(first, second))

    def test_same_topic_graphics_vary_between_scene_indices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_dir = root / "first"
            second_dir = root / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            first = video_app.make_background(
                "বাংলাদেশের ট্রেন ও রেলস্টেশন", first_dir,
                force_topic_graphic=True, variation_seed=0, scene_index=1
            )
            second = video_app.make_background(
                "বাংলাদেশের ট্রেন ও রেলস্টেশন", second_dir,
                force_topic_graphic=True, variation_seed=1, scene_index=2
            )
            self.assertFalse(video_app._scene_images_too_similar(first, second))

    def test_topic_graphic_is_deterministic_for_same_scene_seed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_dir = root / "first"
            second_dir = root / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            first = video_app.make_background(
                "বাংলাদেশের ট্রেন ও রেলস্টেশন", first_dir,
                force_topic_graphic=True, variation_seed=4
            )
            second = video_app.make_background(
                "বাংলাদেশের ট্রেন ও রেলস্টেশন", second_dir,
                force_topic_graphic=True, variation_seed=4
            )
            self.assertTrue(video_app._scene_images_too_similar(first, second))

    def test_scene_generation_reports_monotonic_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            progress = []
            generated = []

            def fake_background(script, folder, model_visual_prompt=None, **kwargs):
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / "background.png"
                index = len(generated)
                Image.new("RGB", (120, 180), (20 + index * 30, 30 + index * 20, 40 + index * 15)).save(path)
                generated.append(path)
                return path

            script = (
                "প্রথম দৃশ্যের জন্য একটি আলাদা বিষয় এখানে বিস্তারিতভাবে বলা হয়েছে।  "
                "দ্বিতীয় দৃশ্যে সম্পূর্ণ নতুন আরেকটি বিষয় নিয়ে আলোচনা করা হয়েছে।  "
                "তৃতীয় দৃশ্যে আরেকটি গুরুত্বপূর্ণ বিষয় তুলে ধরা হয়েছে।"
            )
            with patch.object(video_app, "_plan_scene_visual_prompts", return_value=None) as _planner, patch.object(video_app, "make_background", side_effect=fake_background):
                backgrounds, scenes, semantic_review = video_app.make_scene_backgrounds(
                    script, root,
                    progress_callback=lambda percent, message: progress.append((percent, message))
                )

            self.assertGreaterEqual(len(scenes), 2)
            self.assertIsInstance(semantic_review, dict)
            self.assertEqual(len(backgrounds), len(generated))
            values = [item[0] for item in progress]
            self.assertEqual(values, sorted(values))
            self.assertEqual(values[-1], 40)
            self.assertIn("দৃশ্যের ছবি তৈরি হচ্ছে", " ".join(item[1] for item in progress))

    def test_capabilities_match_android_defaults_and_free_service_limits(self):
        capabilities = video_app.capabilities()
        self.assertEqual(capabilities["scene_interval_default_seconds"], 3)
        self.assertEqual(capabilities["max_concurrent_jobs"], 1)
        self.assertGreaterEqual(capabilities["job_retention_hours"], 1)

    def test_expired_terminal_job_and_folder_are_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expired_id = "expired-job"
            expired_folder = root / expired_id
            expired_folder.mkdir()
            (expired_folder / "video.mp4").write_bytes(b"old video")
            now = time.time()
            previous_jobs = dict(video_app.JOBS)
            try:
                with patch.object(video_app, "WORK_DIR", root), patch.object(video_app, "JOB_RETENTION_SECONDS", 3600):
                    with video_app.LOCK:
                        video_app.JOBS.clear()
                        video_app.JOBS[expired_id] = {
                            "id": expired_id,
                            "status": "completed",
                            "created_at": now - 7200,
                            "completed_at": now - 7200,
                        }
                    video_app._cleanup_expired_jobs(now=now)
                    self.assertNotIn(expired_id, video_app.JOBS)
                    self.assertFalse(expired_folder.exists())
            finally:
                with video_app.LOCK:
                    video_app.JOBS.clear()
                    video_app.JOBS.update(previous_jobs)

    def test_logs_ai_generated_source_and_provider_for_scene(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            generated = self._image(folder, "generated.png", (120, 150, 180))
            output = io.StringIO()
            with patch.object(video_app, "find_generated_image", return_value=(
                generated, "AI-generated with test-provider"
            )), contextlib.redirect_stdout(output):
                video_app.make_background(
                    "বাংলাদেশের ট্রেন", folder, scene_index=3
                )
            self.assertIn(
                "IMAGE_SCENE_SOURCE index=3 source=ai_generated provider=test-provider",
                output.getvalue()
            )

    def test_logs_licensed_contextual_source_when_ai_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            licensed = self._image(folder, "licensed.png", (130, 160, 190))
            output = io.StringIO()
            with patch.object(video_app, "find_generated_image", return_value=(None, "")), \
                 patch.object(video_app, "ALLOW_LICENSED_IMAGE_FALLBACK", True), \
                 patch.object(video_app, "find_contextual_image", return_value=(
                     licensed, "CC BY contextual image"
                 )), contextlib.redirect_stdout(output):
                video_app.make_background(
                    "বাংলাদেশের ট্রেন", folder, scene_index=4
                )
            self.assertIn(
                "IMAGE_SCENE_SOURCE index=4 source=licensed_contextual provider=openverse_or_wikimedia",
                output.getvalue()
            )

    def test_logs_topic_graphic_source_for_duplicate_scene(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                video_app.make_background(
                    "বাংলাদেশের ট্রেন", folder,
                    force_topic_graphic=True, scene_index=5
                )
            self.assertIn(
                "IMAGE_SCENE_SOURCE index=5 source=topic_graphic reason=duplicate_image",
                output.getvalue()
            )

    def test_scene_splitter_keeps_short_sentences_intact(self):
        first = "একজন কৃষক সবুজ ধানক্ষেতে কাজ করছেন।"
        second = "তিনি জমির পরিচর্যা করছেন।"
        scenes = video_app._split_script_into_scenes(
            first + " " + second, target_words=4
        )
        self.assertEqual(scenes, [first, second])

    def test_scene_splitter_preserves_all_words_in_long_sentences(self):
        script = (
            "বাংলাদেশের একজন পরিশ্রমী কৃষক সকালে মাঠে গিয়ে "
            "ধানের চারা রোপণ করেন এবং যত্ন নিয়ে ফসলের পরিচর্যা করেন।"
        )
        scenes = video_app._split_script_into_scenes(script, target_words=4)
        self.assertEqual(
            " ".join(" ".join(scenes).split()),
            " ".join(script.split())
        )
        self.assertTrue(all(len(scene.split()) <= 8 for scene in scenes))


    def test_image_keywords_preserve_important_scene_descriptors(self):
        keywords = video_app._image_keywords(
            "বাংলাদেশের সবুজ গ্রাম ও গাছপালা",
            "green rural village with plants beside a river"
        )
        self.assertIn("green", keywords)
        self.assertIn("rural", keywords)
        self.assertIn("plants", keywords)

    def test_image_keywords_remove_generic_generation_prompt_terms(self):
        keywords = video_app._image_keywords(
            "একজন কৃষক ধানক্ষেতে কাজ করছেন",
            "One coherent documentary photograph, vertical 9:16, for a Bangladeshi educational video. "
            "Depict the exact real-world subject and physical action stated in this scene: "
            "farmer harvesting rice in a field. Show the actual named object, believable authentic "
            "materials, environmental details, natural light, and a clear camera viewpoint."
        )
        self.assertIn("farmer", keywords)
        self.assertIn("harvesting", keywords)
        self.assertIn("rice", keywords)
        self.assertNotIn("documentary", keywords)
        self.assertNotIn("educational", keywords)
        self.assertNotIn("world", keywords)
        self.assertNotIn("materials", keywords)
        self.assertNotIn("viewpoint", keywords)


    def test_image_search_cache_reuses_successful_empty_results(self):
        with patch.object(video_app, "_IMAGE_SEARCH_CACHE", {}), \
             patch.object(video_app.time, "monotonic", return_value=100.0):
            video_app._image_search_cache_set("openverse", "train railway", [])
            self.assertEqual(
                video_app._image_search_cache_get("openverse", "train railway"),
                []
            )
            self.assertIsNone(
                video_app._image_search_cache_get("wikimedia", "train railway")
            )

    def test_image_search_cache_expires_old_provider_results(self):
        with patch.object(video_app, "_IMAGE_SEARCH_CACHE", {}):
            with patch.object(video_app.time, "monotonic", return_value=100.0):
                video_app._image_search_cache_set("wikimedia", "farmer rice", [{"id": 1}])
            with patch.object(
                video_app.time, "monotonic",
                return_value=100.0 + video_app.IMAGE_SEARCH_CACHE_TTL_SECONDS + 1
            ):
                self.assertIsNone(
                    video_app._image_search_cache_get("wikimedia", "farmer rice")
                )

    def test_image_search_cache_stays_within_configured_limit(self):
        with patch.object(video_app, "_IMAGE_SEARCH_CACHE", {}):
            for index in range(video_app.IMAGE_SEARCH_CACHE_MAX_ENTRIES + 5):
                video_app._image_search_cache_set("openverse", str(index), [])
            self.assertEqual(
                len(video_app._IMAGE_SEARCH_CACHE),
                video_app.IMAGE_SEARCH_CACHE_MAX_ENTRIES
            )
            self.assertIsNone(video_app._image_search_cache_get("openverse", "0"))

    def test_specific_bangla_subject_terms_win_over_broad_country_concept(self):
        concepts = video_app._matched_visual_concepts("বাংলাদেশের ট্রেন ও রেলস্টেশন")
        self.assertTrue(any("passenger train" in item for item in concepts))
        keywords = video_app._image_keywords("বাংলাদেশের ট্রেন ও রেলস্টেশন")
        self.assertIn("train", keywords)
        self.assertIn("railway", keywords)
        self.assertNotIn("community", keywords)


    def test_openverse_provider_success_is_reused_across_scene_requests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            calls = []

            def fake_urlopen(request, timeout=6):
                calls.append(request.full_url)
                return contextlib.nullcontext(io.BytesIO(b'{"results": []}'))

            with patch.object(video_app, "_IMAGE_SEARCH_CACHE", {}), \
                 patch.object(video_app.urllib.request, "urlopen", side_effect=fake_urlopen):
                first = video_app.find_openverse_image(
                    "একজন কৃষক ধানক্ষেতে কাজ করছেন",
                    folder,
                    "farmer rice field harvesting",
                )
                first_call_count = len(calls)
                second = video_app.find_openverse_image(
                    "একজন কৃষক ধানক্ষেতে কাজ করছেন",
                    folder,
                    "farmer rice field harvesting",
                )

            self.assertEqual(first, (None, ""))
            self.assertEqual(second, (None, ""))
            self.assertGreater(first_call_count, 0)
            self.assertEqual(
                len(calls),
                first_call_count,
                "A successful empty Openverse response should be reused, not requested again",
            )


    def test_duplicate_retry_review_counters_include_licensed_photo(self):
        semantic_review = {
            "duplicate_retry_reviewed": 0,
            "duplicate_retry_matched": 0,
            "duplicate_retry_mismatched": 0,
            "duplicate_retry_unavailable": 0,
        }
        self.assertEqual(
            video_app._record_duplicate_retry_review(
                {"match": True, "description": "Farmer in rice field"}, semantic_review
            ),
            "matched",
        )
        self.assertEqual(
            video_app._record_duplicate_retry_review({"match": False}, semantic_review),
            "mismatched",
        )
        self.assertEqual(
            video_app._record_duplicate_retry_review(None, semantic_review),
            "unavailable",
        )
        self.assertEqual(semantic_review, {
            "duplicate_retry_reviewed": 3,
            "duplicate_retry_matched": 1,
            "duplicate_retry_mismatched": 1,
            "duplicate_retry_unavailable": 1,
        })


    def test_storyboard_prompt_cannot_override_narration_subject(self):
        prompt = video_app._english_visual_prompt(
            "একজন কৃষক ধানক্ষেতে কাজ করছেন।",
            "A generic city skyline with tall buildings and traffic."
        )
        self.assertIn("Bangladeshi farmer working in a green rice field", prompt)
        self.assertNotIn("additional scene detail", prompt)
        self.assertNotIn("generic city skyline", prompt)
        self.assertTrue(prompt.startswith("Main subject and action"))
        self.assertLess(prompt.index("Bangladeshi farmer working in a green rice field"), 220)


    def test_rejected_image_retry_uses_narration_as_source_of_truth(self):
        prompt = video_app._scene_mismatch_retry_prompt(
            "একজন কৃষক ধানক্ষেতে ধান কাটছেন",
            "A city bus driving through a crowded market street",
            "A city bus on a busy road",
        )
        self.assertIn("farmer", prompt.lower())
        self.assertIn("rice field", prompt.lower())
        self.assertNotIn("crowded market street", prompt.lower())
        self.assertNotIn("additional scene detail", prompt.lower())
        self.assertIn("rejected visual content", prompt.lower())


    def test_rejected_image_recovery_prompt_survives_provider_adapter(self):
        retry = video_app._scene_mismatch_retry_prompt(
            "একজন কৃষক ধানক্ষেতে ধান কাটছেন",
            "A city bus driving through a crowded market street",
            "A city bus on a busy road",
        )
        provider_prompt = video_app._english_visual_prompt(
            "একজন কৃষক ধানক্ষেতে ধান কাটছেন", retry
        )
        self.assertIn("farmer", provider_prompt.lower())
        self.assertIn("rice field", provider_prompt.lower())
        self.assertIn("avoid this rejected visual content", provider_prompt.lower())
        self.assertIn("city bus on a busy road", provider_prompt.lower())
        self.assertNotIn("crowded market street", provider_prompt.lower())
        varied_prompt = video_app._vary_visual_prompt(provider_prompt, variation_seed=3)
        self.assertEqual(varied_prompt, provider_prompt)
        self.assertIn("avoid this rejected visual content", varied_prompt.lower())
        self.assertIn("city bus", varied_prompt.lower())


    def test_vision_review_stops_repeating_requests_after_http_429(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image = self._image(Path(temp_dir), "review.png", (80, 110, 140))
            error = __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
                "https://api.cloudflare.com", 429, "Too Many Requests", {}, io.BytesIO(b"quota exhausted")
            )
            with (
                patch.object(video_app, "_IMAGE_REVIEW_QUOTA_EXHAUSTED", False),
                patch.dict("os.environ", {"CLOUDFLARE_ACCOUNT_ID": "test", "CLOUDFLARE_AI_API_TOKEN": "test"}),
                patch.object(video_app.urllib.request, "urlopen", side_effect=error) as mocked,
            ):
                first = video_app._review_generated_image_against_scene(image, "একজন কৃষক ধান কাটছেন")
                second = video_app._review_generated_image_against_scene(image, "একজন কৃষক ধান কাটছেন")
            self.assertIsNone(first)
            self.assertIsNone(second)
            self.assertEqual(mocked.call_count, 1)

    def test_vision_review_label_without_description_is_unavailable(self):
        parsed = video_app._parse_scene_match_response("MISMATCH")
        self.assertIsNotNone(parsed)
        self.assertFalse(parsed["match"])
        self.assertEqual(parsed["description"], "")
        with tempfile.TemporaryDirectory() as temp_dir:
            image = self._image(Path(temp_dir), "label-only.png", (80, 110, 140))
            with (
                patch.object(video_app, "_IMAGE_REVIEW_QUOTA_EXHAUSTED", False),
                patch.dict("os.environ", {"CLOUDFLARE_ACCOUNT_ID": "test", "CLOUDFLARE_AI_API_TOKEN": "test"}),
                patch.object(
                    video_app.urllib.request, "urlopen",
                    side_effect=lambda *args, **kwargs: contextlib.nullcontext(
                        io.BytesIO(b'{"result":{"response":"MISMATCH"}}')
                    ),
                ) as mocked,
            ):
                review = video_app._review_generated_image_against_scene(
                    image, "একজন কৃষক ধান কাটছেন"
                )
            self.assertIsNone(review)
            self.assertEqual(mocked.call_count, 1)

    def test_openverse_timeout_activates_provider_cooldown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            with patch.object(video_app, "IMAGE_PROVIDER_COOLDOWN_UNTIL", {}), \
                 patch.object(video_app.urllib.request, "urlopen", side_effect=TimeoutError("timed out")):
                result = video_app.find_openverse_image(
                    "একজন কৃষক ধান কাটছেন", folder, "farmer harvesting rice"
                )
                self.assertEqual(result, (None, ""))
                self.assertGreater(
                    video_app.IMAGE_PROVIDER_COOLDOWN_UNTIL.get("Openverse-Search", 0),
                    video_app.time.time(),
                )

    def test_vision_review_parser_keeps_rejected_image_description(self):
        review = video_app._parse_scene_match_response(
            '{"match":false,"confidence":0.94,'
            '"description":"A city bus on a crowded road",'
            '"reason":"The narration is about a farmer harvesting rice."}'
        )
        self.assertIsNotNone(review)
        self.assertFalse(review["match"])
        self.assertEqual(review["confidence"], 0.94)
        self.assertIn("city bus", review["description"])
        self.assertIn("farmer", review["reason"])



    def test_cloudflare_fallback_stops_for_account_limits_and_timeouts(self):
        self.assertTrue(video_app._cloudflare_should_stop_fallback(
            __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
                "https://example.com", 429, "rate limited", {}, None
            )
        ))
        self.assertTrue(video_app._cloudflare_should_stop_fallback(TimeoutError("timed out")))
        self.assertFalse(video_app._cloudflare_should_stop_fallback(
            __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
                "https://example.com", 500, "server error", {}, None
            )
        ))

    def test_video_brain_parser_validates_language_and_research_queries(self):
        parsed = video_app._parse_video_brain_response(
            '{"language":"mixed","topic":"কৃষি ও প্রযুক্তি","content_type":"educational",'
            '"tone":"informative","audience":"general","visual_style":"documentary",'
            '"research_needed":true,"research_queries":["Bangladesh agriculture","Bangladesh agriculture",""]}',
            "কৃষি ও technology",
        )
        self.assertEqual(parsed["language"], "mixed")
        self.assertEqual(parsed["content_type"], "educational")
        self.assertEqual(parsed["research_queries"], ["Bangladesh agriculture"])
        self.assertTrue(parsed["research_needed"])

    def test_video_brain_treats_string_false_as_false(self):
        parsed = video_app._parse_video_brain_response(
            '{"language":"bn","research_needed":"false",'
            '"research_queries":["Bangladesh agriculture"]}',
            "বাংলা লেখা",
        )
        self.assertFalse(parsed["research_needed"])

    def test_video_brain_rejects_malformed_response_and_uses_no_research(self):
        self.assertIsNone(video_app._parse_video_brain_response("not json", "বাংলা লেখা"))
        parsed = video_app._parse_video_brain_response(
            '{"language":"unknown","research_needed":true,"research_queries":[]}', "বাংলা লেখা"
        )
        self.assertFalse(parsed["research_needed"])
        self.assertEqual(parsed["research_queries"], [])

    def test_video_brain_context_uses_research_as_context_not_scene_override(self):
        context = video_app._video_brain_visual_context({
            "topic": "বাংলাদেশের কৃষি", "content_type": "educational",
            "tone": "informative", "audience": "students",
            "visual_style": "documentary",
            "research_sources": [{"source": "Wikipedia", "title": "Rice",
                                  "snippet": "Rice is a staple crop.", "url": "https://en.wikipedia.org/?curid=1"}],
        })
        self.assertIn("Overall topic", context)
        self.assertIn("Rice", context)
        self.assertIn("Rice is a staple crop", context)


if __name__ == "__main__":
    unittest.main()
