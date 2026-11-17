import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from backend import app as video_app


class SubtitleOcrLanguageFallbackTests(unittest.TestCase):
    def test_ascii_only_active_word_tries_english_before_bilingual(self):
        self.assertEqual(
            video_app._tesseract_language_candidates(["Hello"]),
            ("eng", "ben+eng"),
        )

    def test_bengali_active_word_keeps_bilingual_ocr(self):
        self.assertEqual(
            video_app._tesseract_language_candidates(["বাংলা"]),
            ("ben+eng",),
        )

    def test_mixed_active_word_keeps_bilingual_ocr(self):
        self.assertEqual(
            video_app._tesseract_language_candidates(["AI", "বাংলা"]),
            ("ben+eng",),
        )

    def test_punctuation_normalized_ascii_token_still_uses_english(self):
        tokens = video_app._normalize_transcript_tokens("Hello,")
        self.assertEqual(
            video_app._tesseract_language_candidates(tokens),
            ("eng", "ben+eng"),
        )

    def test_real_tesseract_reads_english_word_from_rendered_caption_crop(self):
        """Exercise the same panel geometry, font, highlight, and crop as video rendering."""
        try:
            available = subprocess.run(
                ["tesseract", "--list-langs"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.skipTest("Tesseract is not installed in this test environment")
        self.assertEqual(available.returncode, 0, available.stderr)
        self.assertIn("eng", (available.stdout or "").splitlines())

        words = ["Hello", "This", "English", "video", "generation", "test"]
        detected = []
        with tempfile.TemporaryDirectory() as temporary:
            for index, word in enumerate(words):
                frame = Image.new("RGB", (360, 640), (80, 90, 100))
                overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                panel = ImageDraw.Draw(overlay)
                panel.rounded_rectangle(
                    (14, 440, 346, 622),
                    radius=18,
                    fill=(0, 0, 0, 205),
                    outline=(95, 170, 230, 220),
                    width=2,
                )
                frame = Image.alpha_composite(frame.convert("RGBA"), overlay)
                draw = ImageDraw.Draw(frame)
                font = video_app.load_font(25, True)
                draw.text(
                    (14, 464),
                    word,
                    font=font,
                    fill=(255, 224, 65),
                    stroke_width=1,
                    stroke_fill=(0, 0, 0),
                )
                crop, bounds = video_app._extract_highlighted_word_crop(frame.convert("RGB"))
                self.assertIsNotNone(bounds, f"Yellow highlight was not found for {word}")
                self.assertIsNotNone(crop, f"Crop was not created for {word}")
                crop_path = Path(temporary) / f"word-{index}.png"
                crop.resize((1200, 480), Image.Resampling.LANCZOS).save(crop_path)
                recognized = ""
                for psm in ("7", "8", "10", "11", "13"):
                    result = subprocess.run(
                        ["tesseract", str(crop_path), "stdout", "-l", "eng", "--psm", psm],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if video_app._tesseract_crop_matches_expected_tokens(
                        result.stdout, video_app._normalize_transcript_tokens(word)
                    ):
                        recognized = result.stdout.strip()
                        break
                if recognized:
                    detected.append(word)
        print(f"Rendered English caption OCR diagnostic: {len(detected)}/{len(words)} words detected: {detected}")
        self.assertGreater(
            len(detected),
            0,
            "Tesseract did not recognize any English word from the actual rendered-caption crop",
        )


if __name__ == "__main__":
    unittest.main()
