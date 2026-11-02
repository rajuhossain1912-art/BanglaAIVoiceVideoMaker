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


if __name__ == "__main__":
    unittest.main()
