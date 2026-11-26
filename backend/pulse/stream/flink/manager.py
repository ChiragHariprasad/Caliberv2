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

        # Check existing jobs: require exact v3 pipeline covering all 9 RAW_TOPICS
        active_states = {"RUNNING", "RESTARTING", "RECONCILING", "CREATED", "INITIALIZING"}
        existing_jobs = self.client.list_jobs()
        for j in existing_jobs:
            name = j.get("name", "")
            state = j.get("state", "")
            if name == "pulse-canonical-normalizer-v3" and state in active_states:
                jid = j["jid"]
                self.active_job_id = jid
                if state == "RUNNING":
                    logger.info("Reusing existing RUNNING Flink job [%s] (%s)", jid, name)
                    return jid
                # Wait briefly for transient RESTARTING/INITIALIZING job to recover rather than stacking duplicates
                logger.info("Found Flink v3 job [%s] in transient state %s; waiting up to 20s...", jid, state)
                wait_start = time.time()
                while time.time() - wait_start < 20.0:
                    st = self.client.get_job_status(jid)
                    if st and st.get("state") == "RUNNING":
                        logger.info("Flink v3 job [%s] recovered to RUNNING state.", jid)
                        return jid
                    if st and st.get("state") in {"FAILED", "CANCELED", "FINISHED"}:
                        break
                    time.sleep(1.0)
                logger.warning("Cancelling stalled Flink v3 job [%s] before clean redeploy", jid)
                self.client.cancel_job(jid)
                time.sleep(2.0)
                existing_jobs = self.client.list_jobs()
                break

        # Cancel any legacy or leftover active normalizer version so v3 owns slot resources cleanly
        cancelled_any = False
        for j in existing_jobs:
            name = j.get("name", "")
            state = j.get("state", "")
            if ("pulse-canonical-normalizer" in name or "pulse-race-control-normalizer" in name) and state in active_states:
                logger.info("Cancelling superseded/duplicate Flink job [%s] (%s, %s) before v3 deploy", j["jid"], name, state)
                self.client.cancel_job(j["jid"])
                cancelled_any = True
        if cancelled_any:
            time.sleep(2.0)

        # Submit new job
        logger.info("Deploying Flink Normalizer job from %s", SQL_JOB_PATH)
        sql_content = SQL_JOB_PATH.read_text(encoding="utf-8")
        job_id = self.client.submit_sql_job(sql_content, job_name="pulse-canonical-normalizer-v3")
        self.active_job_id = job_id

        # Poll until RUNNING
        start_time = time.time()
        while time.time() - start_time < 25.0:
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
            # Prefer active v3 job if running, else fall back to any active normalizer job
            jobs = self.client.list_jobs()
            for j in jobs:
                if j.get("name") == "pulse-canonical-normalizer-v3" and j.get("state") == "RUNNING":
                    self.active_job_id = j["jid"]
                    break
            if not self.active_job_id:
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

