import unittest

from backend import app as video_app


class AudioPreflightTests(unittest.TestCase):
    def test_exactly_matched_narration_can_continue_to_render(self):
        self.assertIsNone(video_app._audio_preflight_failure_reason({
            "status": "matched",
            "similarity": 1.0,
            "missing_tokens": 0,
            "extra_tokens": 0,
        }))

    def test_mismatched_narration_stops_before_expensive_render(self):
        reason = video_app._audio_preflight_failure_reason({
            "status": "mismatch",
            "similarity": 0.24,
            "missing_tokens": 69,
            "extra_tokens": 30,
        })
        self.assertIsInstance(reason, str)
        self.assertIn("২৪ শতাংশ", reason)
        self.assertIn("69টি", reason)
        self.assertIn("30টি", reason)

    def test_incomplete_but_nonzero_token_diagnostics_still_stop(self):
        reason = video_app._audio_preflight_failure_reason({
            "status": "matched",
            "similarity": 0.95,
            "missing_tokens": 1,
            "extra_tokens": 0,
        })
        self.assertIsInstance(reason, str)

    def test_unavailable_transcription_stops_before_expensive_render(self):
        reason = video_app._audio_preflight_failure_reason({
            "status": "unavailable",
            "similarity": None,
            "missing_tokens": None,
            "extra_tokens": None,
        })
        self.assertIsInstance(reason, str)
        self.assertIn("যাচাই করা যায়নি", reason)


if __name__ == "__main__":
    unittest.main()
