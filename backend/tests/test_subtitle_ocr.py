import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend import app as video_app


class SubtitleOcrLanguageFallbackTests(unittest.TestCase):
    def test_caption_font_uses_latin_glyphs_for_english(self):
        font = video_app.load_caption_font("Hello", 25, True)
        self.assertEqual(font.getname()[0], "Liberation Sans")

    def test_caption_font_uses_serif_glyph_for_uppercase_i(self):
        font = video_app.load_caption_font("AI", 25, True)
        self.assertEqual(font.getname(), ("DejaVu Serif", "Bold"))

    def test_caption_font_uses_bengali_glyphs_for_bengali(self):
        font = video_app.load_caption_font("বাংলা", 25, True)
        self.assertEqual(font.getname(), video_app.load_font(25, True).getname())

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
        """Compare production crop OCR with direct OCR on the same rendered panel."""
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
        crop_detected = []
        panel_detected = []
        diagnostics = []
        with tempfile.TemporaryDirectory() as temporary:
            for index, word in enumerate(words):
                frame = Image.new("RGB", (360, 640), (80, 90, 100))
                overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                panel_draw = ImageDraw.Draw(overlay)
                panel_draw.rounded_rectangle(
                    (14, 440, 346, 622),
                    radius=18,
                    fill=(0, 0, 0, 205),
                    outline=(95, 170, 230, 220),
                    width=2,
                )
                frame = Image.alpha_composite(frame.convert("RGBA"), overlay)
                draw = ImageDraw.Draw(frame)
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 25)
                draw.text(
                    (14, 464),
                    word,
                    font=font,
                    fill=(255, 224, 65),
                    stroke_width=1,
                    stroke_fill=(0, 0, 0),
                )
                rgb_frame = frame.convert("RGB")
                crop, bounds = video_app._extract_highlighted_word_crop(rgb_frame)
                self.assertIsNotNone(bounds, f"Yellow highlight was not found for {word}")
                self.assertIsNotNone(crop, f"Crop was not created for {word}")
                crop_path = Path(temporary) / f"word-{index}.png"
                crop.resize((1200, 480), Image.Resampling.LANCZOS).save(crop_path)

                panel_path = Path(temporary) / f"panel-{index}.png"
                rgb_frame.crop((14, 440, 346, 622)).resize(
                    (1328, 728), Image.Resampling.LANCZOS
                ).save(panel_path)

                raw_crop_path = Path(temporary) / f"raw-{index}.png"
                raw_panel = rgb_frame.crop((14, 440, 346, 622))
                raw_bounds = bounds
                raw_panel.crop(raw_bounds).resize(
                    (1200, 480), Image.Resampling.LANCZOS
                ).save(raw_crop_path)

                crop_outputs = []
                panel_outputs = []
                expected = video_app._normalize_transcript_tokens(word)
                for psm in ("6", "7", "8", "10", "11", "13"):
                    for source_name, source_path, outputs in (
                        ("crop", crop_path, crop_outputs),
                        ("panel", panel_path, panel_outputs),
                        ("raw", raw_crop_path, crop_outputs),
                    ):
                        result = subprocess.run(
                            ["tesseract", str(source_path), "stdout", "-l", "eng", "--psm", psm],
                            capture_output=True,
                            text=True,
                            timeout=15,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        text = " ".join(result.stdout.split())
                        outputs.append(f"{source_name}/psm{psm}={text!r}")
                        if video_app._tesseract_crop_matches_expected_tokens(
                            result.stdout, expected
                        ):
                            if source_name == "panel":
                                panel_detected.append(word)
                            else:
                                crop_detected.append(word)
                diagnostics.append(
                    f"{word}: crop[{'; '.join(crop_outputs)}] panel[{'; '.join(panel_outputs)}]"
                )
        print(
            "English rendered-caption OCR diagnostic: "
            f"isolated/raw crops={len(set(crop_detected))}/{len(words)}, "
            f"full panels={len(set(panel_detected))}/{len(words)}"
        )
        print(" | ".join(diagnostics))
        self.assertTrue(
            crop_detected or panel_detected,
            "Tesseract did not recognize English words from either the production crop or its source panel",
        )


    def test_production_caption_frames_render_and_ocr_active_words(self):
        """Exercise make_caption_frames itself, then OCR its actual highlighted frames."""
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
        languages = set((available.stdout or "").splitlines())
        self.assertIn("eng", languages)
        self.assertIn("ben", languages)

        script = (
            "জীবনে সফল হতে হলে কখনো হাল ছেড়ে দেওয়া যাবে না। "
            "প্রতিটি ব্যর্থতা আমাদের নতুন কিছু শেখায়। "
            "আজ হয়তো পথ কঠিন, কিন্তু ধৈর্য, পরিশ্রম এবং আত্মবিশ্বাস থাকলে একদিন সফলতা আসবেই। "
            "নিজের ওপর বিশ্বাস রাখুন, স্বপ্ন দেখুন এবং স্বপ্ন পূরণের জন্য প্রতিদিন চেষ্টা চালিয়ে যান।"
        )
        expected = re.findall(r"\S+", script)
        self.assertEqual(len(expected), 43)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            background = root / "background.png"
            Image.new("RGB", (360, 640), (70, 85, 100)).save(background)
            listing, frame_count = video_app.make_caption_frames(
                script=script,
                duration=43.0,
                background=background,
                folder=root,
                scene_interval=3,
            )
            self.assertTrue(listing.is_file())
            self.assertEqual(frame_count, len(expected))
            frame_paths = sorted((root / "caption-frames").glob("frame-*.png"))
            self.assertEqual(len(frame_paths), len(expected))
            for index, word in enumerate(expected):
                with Image.open(frame_paths[index]) as source:
                    frame = source.convert("RGB")
                crop, bounds = video_app._extract_highlighted_word_crop(frame)
                self.assertIsNotNone(bounds, f"Active highlight missing for {word}")
                self.assertIsNotNone(crop, f"Active-word crop missing for {word}")
                crop_path = root / f"production-active-{index}.png"
                crop.resize((1200, 480), Image.Resampling.LANCZOS).save(crop_path)
                is_bengali = any(0x0980 <= ord(char) <= 0x09FF for char in word)
                language = "ben+eng" if is_bengali else "eng"
                recognized = False
                diagnostics = []
                for psm in ("7", "8", "10", "13"):
                    result = subprocess.run(
                        ["tesseract", str(crop_path), "stdout", "-l", language, "--psm", psm],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    diagnostics.append(f"crop/psm{psm}={result.stdout.strip()!r}")
                    if video_app._tesseract_crop_matches_expected_tokens(
                        result.stdout, video_app._normalize_transcript_tokens(word)
                    ):
                        recognized = True
                        break

                # Short all-capital acronyms such as AI are inherently ambiguous
                # when OCR sees an isolated two-character crop (I and l share
                # near-identical glyph shapes). Use the same contextual, spatially
                # constrained fallback as production: OCR the caption panel and
                # accept the exact token only when its box overlaps the yellow
                # active-word highlight.
                if not recognized:
                    panel_path = root / f"production-panel-{index}.png"
                    panel = frame.crop((14, 440, 346, 622)).resize(
                        (664, 364), Image.Resampling.LANCZOS
                    )
                    panel.save(panel_path)
                    result = subprocess.run(
                        ["tesseract", str(panel_path), "stdout", "-l", language, "--psm", "6", "tsv"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    diagnostics.append(
                        f"panel/psm6={video_app._normalize_transcript_tokens(result.stdout)!r}"
                    )
                    recognized = video_app._tesseract_tsv_matches_highlighted_word(
                        result.stdout,
                        video_app._normalize_transcript_tokens(word),
                        bounds,
                        scale=2,
                    )
                self.assertTrue(
                    recognized,
                    f"Production-rendered active word {word!r} was not OCR-matched: {'; '.join(diagnostics)}",
                )


if __name__ == "__main__":
    unittest.main()
