import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.job_storage import R2JobStorage


class FakeR2Client:
    def __init__(self, clock):
        self.clock = clock
        self.objects = {}
        self.modified = {}

    def upload_file(self, filename, bucket, key, ExtraArgs=None, Config=None):
        self.objects[key] = Path(filename).read_bytes()
        self.modified[key] = datetime.fromtimestamp(self.clock(), timezone.utc)

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[Key] = bytes(Body)
        self.modified[Key] = datetime.fromtimestamp(self.clock(), timezone.utc)

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            error = RuntimeError("missing key")
            error.response = {"Error": {"Code": "NoSuchKey"}}
            raise error
        return {"Body": io.BytesIO(self.objects[Key])}

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[key])

    def list_objects_v2(self, Bucket, Prefix, MaxKeys):
        return {
            "Contents": [
                {"Key": key, "LastModified": self.modified[key]}
                for key in self.objects if key.startswith(Prefix)
            ]
        }

    def delete_objects(self, Bucket, Delete):
        for item in Delete["Objects"]:
            self.objects.pop(item["Key"], None)
            self.modified.pop(item["Key"], None)


class R2JobStorageTests(unittest.TestCase):
    def setUp(self):
        self.now = [1_800_000_000.0]
        self.client = FakeR2Client(lambda: self.now[0])
        self.storage = R2JobStorage(
            account_id="account",
            bucket_name="private-videos",
            access_key_id="access",
            secret_access_key="secret",
            max_jobs=3,
            max_video_bytes=1024 * 1024,
            retention_seconds=3600,
            client_factory=lambda: self.client,
            clock=lambda: self.now[0],
        )

    def _job(self, job_id):
        return {
            "id": job_id,
            "status": "completed",
            "progress": 100,
            "share_allowed": False,
            "source_audio_path": "/tmp/private-input.wav",
        }

    def test_disabled_storage_is_ephemeral_and_does_not_connect(self):
        storage = R2JobStorage()
        result = storage.save_job(
            self._job("a" * 32), Path("/missing/video.mp4"), Path("/missing/audit.json")
        )
        self.assertEqual(result["storage_backend"], "ephemeral")
        self.assertFalse(result["video_stored"])
        self.assertIsNone(storage.load_job("a" * 32))

    def test_save_and_restore_job_video_and_scene_audit(self):
        job_id = "a" * 32
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video = root / "video.mp4"
            audit = root / "scene-audit.json"
            video.write_bytes(b"test-mp4-bytes")
            audit.write_text('[{"scene":1}]', encoding="utf-8")

            saved = self.storage.save_job(self._job(job_id), video, audit)
            self.assertEqual(saved["storage_backend"], "cloudflare_r2")
            self.assertTrue(saved["video_stored"])
            self.assertTrue(saved["scene_audit_stored"])
            stored_metadata = json.loads(self.client.objects[f"jobs/{job_id}/job.json"])
            self.assertNotIn("source_audio_path", stored_metadata)

            restored = self.storage.load_job(job_id)
            self.assertEqual(restored["id"], job_id)
            self.assertFalse((root / "restored" / "video.mp4").exists())
            destination = root / "restored"
            self.assertTrue(self.storage.restore_files(job_id, destination, restored))
            self.assertEqual((destination / "video.mp4").read_bytes(), b"test-mp4-bytes")
            self.assertEqual(
                (destination / "scene-audit.json").read_text(encoding="utf-8"),
                '[{"scene":1}]',
            )

    def test_oversized_video_keeps_metadata_but_does_not_upload_video(self):
        job_id = "b" * 32
        storage = R2JobStorage(
            account_id="account", bucket_name="private-videos",
            access_key_id="access", secret_access_key="secret",
            max_video_bytes=4, client_factory=lambda: self.client,
            clock=lambda: self.now[0],
        )
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "video.mp4"
            video.write_bytes(b"12345")
            saved = storage.save_job(self._job(job_id), video, Path(temp) / "missing.json")
        self.assertFalse(saved["video_stored"])
        self.assertIn(f"jobs/{job_id}/job.json", self.client.objects)
        self.assertNotIn(f"jobs/{job_id}/video.mp4", self.client.objects)

    def test_storage_keeps_only_the_configured_number_of_jobs(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "video.mp4"
            video.write_bytes(b"small")
            for job_id in ("1" * 32, "2" * 32, "3" * 32):
                self.storage.save_job(self._job(job_id), video, Path(temp) / "missing.json")
                self.now[0] += 1
            self.storage.save_job(self._job("4" * 32), video, Path(temp) / "missing.json")
        remaining = {
            key.split("/")[1] for key in self.client.objects if key.startswith("jobs/")
        }
        self.assertEqual(len(remaining), 3)
        self.assertNotIn("1" * 32, remaining)
        self.assertIn("4" * 32, remaining)

    def test_expired_jobs_are_deleted(self):
        with tempfile.TemporaryDirectory() as temp:
            video = Path(temp) / "video.mp4"
            video.write_bytes(b"small")
            self.storage.save_job(self._job("5" * 32), video, Path(temp) / "missing.json")
            self.now[0] += 3601
            removed = self.storage.cleanup()
        self.assertEqual(removed, 1)
        self.assertFalse(any(key.startswith("jobs/") for key in self.client.objects))

    def test_invalid_job_id_is_rejected_before_object_access(self):
        with self.assertRaises(ValueError):
            self.storage.load_job("../private")


if __name__ == "__main__":
    unittest.main()
