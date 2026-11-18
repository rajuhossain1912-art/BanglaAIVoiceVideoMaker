"""Optional private Cloudflare R2 storage for completed video jobs.

The application remains fully usable without R2 credentials. When configured,
only terminal job metadata, the rendered MP4 (within a strict size limit), and
the scene audit are persisted. Uploaded source audio is never copied here.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable


_JOB_ID = re.compile(r"^[a-f0-9]{32}$")


class R2JobStorage:
    def __init__(
        self,
        account_id: str = "",
        bucket_name: str = "",
        access_key_id: str = "",
        secret_access_key: str = "",
        max_jobs: int = 100,
        max_video_bytes: int = 80 * 1024 * 1024,
        retention_seconds: int = 86400,
        client_factory: Callable[[], Any] | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.account_id = str(account_id or "").strip()
        self.bucket_name = str(bucket_name or "").strip()
        self.access_key_id = str(access_key_id or "").strip()
        self.secret_access_key = str(secret_access_key or "").strip()
        self.max_jobs = max(1, min(100, int(max_jobs)))
        self.max_video_bytes = max(1, min(80, int(max_video_bytes // (1024 * 1024)))) * 1024 * 1024
        self.retention_seconds = max(3600, int(retention_seconds))
        self.client_factory = client_factory
        self.clock = clock
        self._client_instance = None

    @classmethod
    def from_env(cls):
        import os

        def bounded_int(name: str, default: int, minimum: int, maximum: int):
            try:
                return max(minimum, min(maximum, int(os.getenv(name, str(default)))))
            except (TypeError, ValueError):
                return default

        return cls(
            account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
            bucket_name=os.getenv("R2_BUCKET_NAME", ""),
            access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
            secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
            max_jobs=bounded_int("R2_MAX_STORED_JOBS", 100, 1, 100),
            max_video_bytes=bounded_int("R2_MAX_VIDEO_MB", 80, 1, 80) * 1024 * 1024,
            retention_seconds=bounded_int("R2_RETENTION_SECONDS", 86400, 3600, 604800),
        )

    @property
    def enabled(self) -> bool:
        return bool(
            self.account_id and self.bucket_name
            and self.access_key_id and self.secret_access_key
        )

    def _client(self):
        if not self.enabled:
            return None
        if self._client_instance is not None:
            return self._client_instance
        if self.client_factory is not None:
            self._client_instance = self.client_factory()
            return self._client_instance
        import boto3
        from botocore.config import Config

        self._client_instance = boto3.client(
            "s3",
            endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 2, "mode": "standard"},
                connect_timeout=10,
                read_timeout=60,
            ),
        )
        return self._client_instance

    @staticmethod
    def _prefix(job_id: str) -> str:
        if not _JOB_ID.fullmatch(str(job_id or "")):
            raise ValueError("Invalid video job identifier")
        return f"jobs/{job_id}/"

    def _delete_keys(self, client, keys):
        values = [{"Key": key} for key in keys if key]
        for start in range(0, len(values), 1000):
            batch = values[start:start + 1000]
            if batch:
                client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={"Objects": batch, "Quiet": True},
                )

    def cleanup(self, reserve_slot: bool = False):
        """Prune expired jobs and enforce a hard per-app object-count ceiling."""
        client = self._client()
        if client is None:
            return 0
        response = client.list_objects_v2(
            Bucket=self.bucket_name, Prefix="jobs/", MaxKeys=1000
        )
        groups = {}
        for item in response.get("Contents", []):
            key = str(item.get("Key") or "")
            parts = key.split("/")
            if len(parts) != 3 or not _JOB_ID.fullmatch(parts[1]):
                continue
            group = groups.setdefault(parts[1], {"keys": [], "modified": 0.0})
            group["keys"].append(key)
            modified = item.get("LastModified")
            try:
                group["modified"] = max(group["modified"], float(modified.timestamp()))
            except Exception:
                pass

        now = self.clock()
        expired = [
            job_id for job_id, group in groups.items()
            if group["modified"] and now - group["modified"] > self.retention_seconds
        ]
        for job_id in expired:
            self._delete_keys(client, groups[job_id]["keys"])
            groups.pop(job_id, None)

        job_limit = max(0, self.max_jobs - (1 if reserve_slot else 0))
        excess = max(0, len(groups) - job_limit)
        oldest = sorted(groups, key=lambda key: groups[key]["modified"])
        removed = 0
        for job_id in oldest[:excess]:
            self._delete_keys(client, groups[job_id]["keys"])
            removed += 1
        return len(expired) + removed

    def save_job(self, job: dict, video_path: Path, audit_path: Path) -> dict:
        """Persist a terminal job and its small set of output artifacts."""
        result = dict(job or {})
        job_id = str(result.get("id") or "")
        if not self.enabled:
            result.update(storage_backend="ephemeral", video_stored=False)
            return result
        prefix = self._prefix(job_id)
        client = self._client()
        self.cleanup(reserve_slot=True)

        video = Path(video_path)
        audit = Path(audit_path)
        video_stored = False
        audit_stored = False
        if video.is_file() and video.stat().st_size > 0:
            if video.stat().st_size <= self.max_video_bytes:
                client.upload_file(
                    str(video), self.bucket_name, prefix + "video.mp4",
                    ExtraArgs={"ContentType": "video/mp4"},
                )
                video_stored = True
        if audit.is_file():
            client.upload_file(
                str(audit), self.bucket_name, prefix + "scene-audit.json",
                ExtraArgs={"ContentType": "application/json; charset=utf-8"},
            )
            audit_stored = True

        result.update(
            storage_backend="cloudflare_r2",
            video_stored=video_stored,
            scene_audit_stored=audit_stored,
        )
        safe_metadata = {
            key: value for key, value in result.items()
            if key not in {"raw_audio", "uploaded_audio_path", "source_audio_path"}
        }
        client.put_object(
            Bucket=self.bucket_name,
            Key=prefix + "job.json",
            Body=json.dumps(safe_metadata, ensure_ascii=False, default=str).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        return result

    def load_job(self, job_id: str) -> dict | None:
        """Load terminal metadata without downloading the video."""
        client = self._client()
        if client is None:
            return None
        prefix = self._prefix(job_id)
        try:
            response = client.get_object(
                Bucket=self.bucket_name, Key=prefix + "job.json"
            )
            raw = response["Body"].read(1_000_000)
            job = json.loads(raw.decode("utf-8"))
            if not isinstance(job, dict) or job.get("id") != job_id:
                return None
            if job.get("status") not in ("completed", "failed"):
                return None
            return job
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404", "NotFound"):
                return None
            raise

    def restore_files(self, job_id: str, destination: Path, job: dict) -> bool:
        """Restore the private MP4 and scene audit only when the report/download needs them."""
        client = self._client()
        if client is None:
            return False
        prefix = self._prefix(job_id)
        folder = Path(destination)
        folder.mkdir(parents=True, exist_ok=True)
        restored_any = False
        if job.get("video_stored"):
            target = folder / "video.mp4"
            if not target.is_file() or target.stat().st_size <= 0:
                client.download_file(self.bucket_name, prefix + "video.mp4", str(target))
            restored_any = target.is_file() and target.stat().st_size > 0
        if job.get("scene_audit_stored"):
            target = folder / "scene-audit.json"
            if not target.is_file():
                client.download_file(self.bucket_name, prefix + "scene-audit.json", str(target))
        return restored_any
