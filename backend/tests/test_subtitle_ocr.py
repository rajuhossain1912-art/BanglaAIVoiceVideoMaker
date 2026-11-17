import unittest

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


if __name__ == "__main__":
    unittest.main()
