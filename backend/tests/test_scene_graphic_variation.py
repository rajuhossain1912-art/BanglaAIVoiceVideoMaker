import contextlib
import io
import tempfile
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


if __name__ == "__main__":
    unittest.main()
