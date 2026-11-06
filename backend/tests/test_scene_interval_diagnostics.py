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

    def test_handles_missing_image_count(self):
        result = video_app._scene_interval_diagnostics(30.0, 0, 3)
        self.assertEqual(result["expected_images"], 10)
        self.assertIsNone(result["average_seconds_per_image"])
        self.assertTrue(result["warning"])


if __name__ == "__main__":
    unittest.main()
