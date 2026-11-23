import unittest

from backend import app as video_app


class FinalSceneMismatchReportTests(unittest.TestCase):
    def test_recovered_first_attempt_mismatch_is_not_reported_as_final_mismatch(self):
        audit = [{
            "semantic_status": "mismatched",
            "final_visual_status": "retry_matched",
        }]
        self.assertEqual(video_app._unresolved_final_scene_mismatches(audit), 0)

    def test_unresolved_final_mismatch_is_reported(self):
        audit = [{
            "semantic_status": "mismatched",
            "final_visual_status": "retry_mismatched",
        }]
        self.assertEqual(video_app._unresolved_final_scene_mismatches(audit), 1)

    def test_final_topic_graphic_mismatch_is_reported(self):
        audit = [{"final_visual_status": "topic_graphic_mismatched"}]
        self.assertEqual(video_app._unresolved_final_scene_mismatches(audit), 1)

    def test_successful_final_image_is_not_reported_as_mismatch(self):
        audit = [{"semantic_status": "retry_matched", "final_visual_status": "matched"}]
        self.assertEqual(video_app._unresolved_final_scene_mismatches(audit), 0)


if __name__ == "__main__":
    unittest.main()
