from __future__ import annotations

import logging
import time
from pathlib import Path

from pulse.stream.flink.client import FlinkClient, FlinkJobMetrics, get_flink_client

logger = logging.getLogger("pulse.flink.manager")

SQL_JOB_PATH = Path(__file__).parent / "jobs" / "normalizer_job.sql"


class FlinkStreamManager:
    """Orchestrates Flink jobs, lifecycle checks, and runtime verification."""

    def __init__(self, client: FlinkClient | None = None) -> None:
        self.client = client or get_flink_client()
        self.active_job_id: str | None = None

    def ensure_normalizer_job_running(self) -> str:
        """Verifies or deploys the primary Race Control Normalizer Flink job.
        
        Returns the verified RUNNING Job ID.
        """
        if not self.client.is_cluster_online():
            raise RuntimeError("Cannot start Flink normalizer job: Flink cluster is offline or has no available task slots.")

        # Check existing jobs
        existing_jobs = self.client.list_jobs()
        for j in existing_jobs:
            name = j.get("name", "")
            if ("pulse-canonical-normalizer" in name or "pulse-race-control-normalizer" in name) and j.get("state") == "RUNNING":
                self.active_job_id = j["jid"]
                logger.info("Reusing existing RUNNING Flink job [%s] (%s)", self.active_job_id, name)
                return self.active_job_id

        # Submit new job
        logger.info("Deploying Flink Normalizer job from %s", SQL_JOB_PATH)
        sql_content = SQL_JOB_PATH.read_text(encoding="utf-8")
        job_id = self.client.submit_sql_job(sql_content, job_name="pulse-canonical-normalizer-v2")
        self.active_job_id = job_id

        # Poll until RUNNING
        start_time = time.time()
        while time.time() - start_time < 15.0:
            status = self.client.get_job_status(job_id)
            if status:
                state = status.get("state", "UNKNOWN")
                if state == "RUNNING":
                    logger.info("Flink job [%s] confirmed in RUNNING state.", job_id)
                    return job_id
                if state in {"FAILED", "CANCELED"}:
                    raise RuntimeError(f"Flink job [{job_id}] entered terminal error state: {state}")
            time.sleep(1.0)

        raise TimeoutError(f"Flink job [{job_id}] failed to reach RUNNING state within 15 seconds.")

    def get_metrics(self) -> FlinkJobMetrics | None:
        """Retrieves metrics for the active job."""
        if not self.active_job_id:
            # Try to discover active job
            jobs = self.client.list_jobs()
            for j in jobs:
                name = j.get("name", "")
                if ("pulse-canonical-normalizer" in name or "pulse-race-control-normalizer" in name) and j.get("state") == "RUNNING":
                    self.active_job_id = j["jid"]
                    break

        if self.active_job_id:
            return self.client.get_job_metrics(self.active_job_id)
        return None

    def stop_job(self) -> bool:
        """Stops the active job."""
        if self.active_job_id:
            success = self.client.cancel_job(self.active_job_id)
            if success:
                self.active_job_id = None
            return success
        return True


_manager: FlinkStreamManager | None = None


def get_flink_manager() -> FlinkStreamManager:
    global _manager
    if _manager is None:
        _manager = FlinkStreamManager()
    return _manager

