from __future__ import annotations

import logging
import subprocess
import time
from typing import Any

import httpx
from pydantic import BaseModel

from pulse.config import get_settings

logger = logging.getLogger("pulse.flink")


class FlinkJobMetrics(BaseModel):
    job_id: str
    name: str
    state: str
    duration_ms: int
    read_records: int = 0
    write_records: int = 0
    checkpoints_completed: int = 0
    checkpoints_failed: int = 0
    last_checkpoint_timestamp: int | None = None


class FlinkClient:
    """Production-grade client for Apache Flink JobManager REST API & SQL Job Deployment."""

    def __init__(self, rest_url: str | None = None, container_name: str = "calibre-flink-jobmanager") -> None:
        settings = get_settings()
        self.rest_url = (rest_url or settings.flink_rest_url).rstrip("/")
        self.container_name = container_name

    def is_cluster_online(self) -> bool:
        """Verifies Flink JobManager is reachable and has active task slots."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.rest_url}/overview")
                if res.status_code == 200:
                    data = res.json()
                    slots_total = data.get("slots-total", 0)
                    taskmanagers = data.get("taskmanagers", 0)
                    return slots_total > 0 and taskmanagers > 0
                return False
        except Exception as e:
            logger.debug("Flink cluster check failed: %s", e)
            return False

    def list_jobs(self) -> list[dict[str, Any]]:
        """Lists all submitted jobs and their states."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.rest_url}/jobs/overview")
                if res.status_code == 200:
                    return res.json().get("jobs", [])
                return []
        except Exception as e:
            logger.error("Failed to list Flink jobs: %s", e)
            return []

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Retrieves real-time status and vertex metrics for a specific job."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.rest_url}/jobs/{job_id}")
                if res.status_code == 200:
                    return res.json()
                return None
        except Exception as e:
            logger.error("Error querying Flink job %s: %s", job_id, e)
            return None

    def get_job_metrics(self, job_id: str) -> FlinkJobMetrics | None:
        """Extracts normalized records in/out and checkpoint metrics for verification."""
        status = self.get_job_status(job_id)
        if not status:
            return None

        name = status.get("name", "unknown")
        state = status.get("state", "UNKNOWN")
        duration = status.get("duration", 0)

        read_records = 0
        write_records = 0
        for vertex in status.get("vertices", []):
            metrics = vertex.get("metrics", {})
            read_records += metrics.get("read-records", 0)
            write_records += metrics.get("write-records", 0)

        # Checkpoints
        checkpoints_completed = 0
        checkpoints_failed = 0
        try:
            with httpx.Client(timeout=2.0) as client:
                cp_res = client.get(f"{self.rest_url}/jobs/{job_id}/checkpoints")
                if cp_res.status_code == 200:
                    cp_data = cp_res.json()
                    counts = cp_data.get("counts", {})
                    checkpoints_completed = counts.get("completed", 0)
                    checkpoints_failed = counts.get("failed", 0)
        except Exception:
            pass

        return FlinkJobMetrics(
            job_id=job_id,
            name=name,
            state=state,
            duration_ms=duration,
            read_records=read_records,
            write_records=write_records,
            checkpoints_completed=checkpoints_completed,
            checkpoints_failed=checkpoints_failed,
        )

    def cancel_job(self, job_id: str) -> bool:
        """Cancels a running Flink job."""
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.patch(f"{self.rest_url}/jobs/{job_id}?mode=cancel")
                return res.status_code in {200, 202}
        except Exception as e:
            logger.error("Failed to cancel Flink job %s: %s", job_id, e)
            return False

    def submit_sql_job(self, sql_script_content: str, job_name: str | None = None) -> str:
        """Deploys a streaming SQL job directly into the Flink cluster.
        
        Returns the confirmed Job ID.
        """
        import tempfile
        import os
        from pathlib import Path

        # 1. Write SQL to local temporary file
        with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
            f.write(sql_script_content)
            tmp_local_path = f.name

        try:
            # 2. Copy into Flink container
            container_path = "/tmp/pulse_active_job.sql"
            cp_cmd = ["docker", "cp", tmp_local_path, f"{self.container_name}:{container_path}"]
            subprocess.run(cp_cmd, check=True, capture_output=True)

            # 3. Snapshot running jobs before submission
            existing_job_ids = {j["jid"] for j in self.list_jobs()}

            # 4. Execute sql-client.sh inside container
            exec_cmd = [
                "docker", "exec", self.container_name,
                "/opt/flink/bin/sql-client.sh", "-f", container_path
            ]
            res = subprocess.run(exec_cmd, check=True, capture_output=True, text=True)
            output = res.stdout + res.stderr

            # 5. Extract Job ID from output or by diffing active jobs
            job_id = None
            for line in output.splitlines():
                if "Job ID:" in line:
                    job_id = line.split("Job ID:")[1].strip()
                    break

            if not job_id:
                # Diff jobs list to find newly created job
                time.sleep(1.0)
                new_jobs = self.list_jobs()
                for j in new_jobs:
                    if j["jid"] not in existing_job_ids:
                        job_id = j["jid"]
                        break

            if not job_id:
                raise RuntimeError(f"Flink SQL submission completed but failed to capture Job ID. Output: {output}")

            logger.info("Successfully deployed Flink Job [%s] (Name: %s)", job_id, job_name or "pulse-sql-job")
            return job_id

        finally:
            if os.path.exists(tmp_local_path):
                try:
                    os.remove(tmp_local_path)
                except Exception:
                    pass


_client: FlinkClient | None = None


def get_flink_client() -> FlinkClient:
    global _client
    if _client is None:
        _client = FlinkClient()
    return _client

