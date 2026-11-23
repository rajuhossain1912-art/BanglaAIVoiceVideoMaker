import tempfile
import unittest
from pathlib import Path

from PIL import Image

from backend import app as video_app


class SceneImageSimilarityTests(unittest.TestCase):
    def _image(self, folder: Path, name: str, color):
        path = folder / name
        Image.new("RGB", (120, 180), color).save(path)
        return path

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

    def test_rejects_satellite_view_for_abstract_motivational_narration(self):
        self.assertTrue(video_app._is_unrelated_map_image(
            "প্রতিদিন একটু একটু করে এগিয়ে যান এবং নিজের ওপর বিশ্বাস রাখুন",
            "Satellite view of Barisal city",
        ))

    def test_allows_map_when_narration_explicitly_discusses_geography(self):
        self.assertFalse(video_app._is_unrelated_map_image(
            "বাংলাদেশের মানচিত্রে বিভিন্ন জেলার অবস্থান দেখানো হয়েছে",
            "Satellite view of Barisal city",
        ))


if __name__ == "__main__":
    unittest.main()
