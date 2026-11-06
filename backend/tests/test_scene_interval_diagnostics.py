import unittest

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

    def test_handles_missing_image_count(self):
        result = video_app._scene_interval_diagnostics(30.0, 0, 3)
        self.assertEqual(result["expected_images"], 10)
        self.assertIsNone(result["average_seconds_per_image"])
        self.assertTrue(result["warning"])


if __name__ == "__main__":
    unittest.main()
