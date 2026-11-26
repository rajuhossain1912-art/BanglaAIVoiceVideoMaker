import unittest

from backend import app as video_app


class PublicationGateTests(unittest.TestCase):
    def _valid_inputs(self):
        return {
            "image_count": 1,
            "semantic_review": {"reviewed": 1, "unavailable": 0},
            "audio_verification": {
                "status": "matched",
                "missing_tokens": 0,
                "extra_tokens": 0,
            },
            "caption_alignment": {
                "status": "asr_word_timestamps",
                "matched_word_timestamps": 5,
                "script_word_count": 5,
                "timing_integrity_passed": True,
            },
            "subtitle_ocr": {"status": "passed"},
            "scene_audit": [{"final_visual_status": "matched"}],
            "technical_ok": True,
        }

    def _decision(self, **overrides):
        inputs = self._valid_inputs()
        inputs.update(overrides)
        return video_app._publication_gate_decision(**inputs)

    def test_complete_verified_video_is_allowed(self):
        decision = self._decision()
        self.assertTrue(decision["share_allowed"])
        self.assertEqual(decision["publication_status"], "ready")
        self.assertEqual(decision["reasons"], [])

    def test_unreviewed_topic_graphic_blocks_publication(self):
        decision = self._decision(
            scene_audit=[{"final_visual_status": "topic_graphic_unreviewed"}]
        )
        self.assertFalse(decision["share_allowed"])
        self.assertEqual(decision["publication_status"], "blocked")

    def test_topic_graphic_without_vision_review_blocks_publication(self):
        decision = self._decision(
            scene_audit=[{"final_visual_status": "topic_graphic_unavailable"}]
        )
        self.assertFalse(decision["share_allowed"])
        self.assertEqual(decision["publication_status"], "blocked")

    def test_topic_graphic_mismatch_blocks_publication(self):
        decision = self._decision(
            scene_audit=[{"final_visual_status": "topic_graphic_mismatched"}]
        )
        self.assertFalse(decision["share_allowed"])

    def test_topic_graphic_passes_only_after_explicit_vision_match(self):
        decision = self._decision(
            scene_audit=[{
                "image_source": "topic_graphic",
                "final_visual_status": "matched",
                "final_visual_description": "A person climbing steps toward a goal",
            }]
        )
        self.assertTrue(decision["share_allowed"])

    def test_missing_scene_audit_blocks_publication(self):
        decision = self._decision(scene_audit=[])
        self.assertFalse(decision["share_allowed"])

    def test_audio_word_mismatch_blocks_publication(self):
        decision = self._decision(
            audio_verification={
                "status": "matched",
                "missing_tokens": 1,
                "extra_tokens": 0,
            }
        )
        self.assertFalse(decision["share_allowed"])

    def test_incomplete_word_timestamps_block_publication(self):
        alignment = self._valid_inputs()["caption_alignment"]
        alignment["matched_word_timestamps"] = 4
        decision = self._decision(caption_alignment=alignment)
        self.assertFalse(decision["share_allowed"])

    def test_subtitle_ocr_failure_blocks_publication(self):
        decision = self._decision(subtitle_ocr={"status": "unavailable"})
        self.assertFalse(decision["share_allowed"])

    def test_remaining_duplicate_image_blocks_publication(self):
        decision = self._decision(
            scene_audit=[{
                "final_visual_status": "matched",
                "duplicate_remaining": True,
            }]
        )
        self.assertFalse(decision["share_allowed"])


    def test_subtitle_report_does_not_claim_failure_after_all_checks_pass(self):
        reason = video_app._subtitle_publication_diagnostic_reason(
            {"status": "asr_word_timestamps", "timing_integrity_passed": True},
            {"status": "passed"},
        )
        self.assertIn("সক্রিয় শব্দ OCR-এ শনাক্ত হয়েছে", reason)
        self.assertNotIn("যাচাই হয়নি", reason)

    def test_subtitle_report_names_missing_ocr_and_word_timing(self):
        reason = video_app._subtitle_publication_diagnostic_reason(
            {"status": "estimated", "timing_integrity_passed": False},
            {"status": "unavailable"},
        )
        self.assertIn("OCR দিয়ে নিশ্চিত করা যায়নি", reason)
        self.assertIn("স্পষ্ট শব্দ-সময়", reason)

    def test_technical_failure_blocks_publication(self):
        decision = self._decision(technical_ok=False)
        self.assertFalse(decision["share_allowed"])


if __name__ == "__main__":
    unittest.main()
