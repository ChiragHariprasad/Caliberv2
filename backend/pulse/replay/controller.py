from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pulse.contracts import EventEnvelope, RunMode, utc_now
from pulse.sessions.registry import get_session_by_id
from pulse.state.store import get_state_store
from pulse.stream.bus import PulseEventBus, get_event_bus
from pulse.topics import raw_topic_for_event, routing_key

logger = logging.getLogger("pulse.replay.controller")


class ReplayStatus(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    RESETTING = "RESETTING"
    FAILED = "FAILED"


class ReplayController:
    """Backend-driven Formula 1 race replay controller.
    
    Owns replay cursor, run identity, scheduling, and publication to the streaming backbone.
    """

    ALLOWED_SPEEDS: list[float] = [0.25, 0.5, 1.0, 2.0, 5.0]

    def __init__(self, bus: PulseEventBus | None = None) -> None:
        self.bus = bus or get_event_bus()
        self.session_id: str = "f1-2026-monaco-sim"
        self.capture_id: str = "pulse-sim-monaco-v1"
        self.run_id: str = f"run-sim-{uuid4().hex[:8]}"
        self.mode: str = "SIMULATED"
        self.status: ReplayStatus = ReplayStatus.READY
        self.speed: float = 1.0
        self.current_index: int = 0
        self.published_count: int = 0
        self.drop_count: int = 0
        self.elapsed_ms: int = 0
        self.last_event_time_utc: datetime | None = None
        self.envelopes: list[EventEnvelope] = []
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

        # Load initial default session envelopes
        self._load_session_envelopes(self.session_id)

    def _load_session_envelopes(self, session_id: str) -> bool:
        """Loads canonical envelopes for the chosen session into memory."""
        meta = get_session_by_id(session_id)
        self.envelopes.clear()
        self.current_index = 0
        self.published_count = 0

        if not meta or meta.availability_status == "NO_SESSION_DATA":
            self.session_id = session_id
            self.capture_id = ""
            self.status = ReplayStatus.READY
            return False

        self.session_id = session_id
        self.capture_id = meta.capture_id or ""
        self.mode = "REPLAY" if meta.availability_status == "AVAILABLE_HISTORICAL" else "SIMULATED"

        if meta.availability_status == "AVAILABLE_HISTORICAL":
            capture_dir = Path("captures/f1-2023-silverstone-race")
            if not capture_dir.exists():
                capture_dir = Path("captures") / self.capture_id
            env_file = capture_dir / "envelopes.jsonl"
            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            self.envelopes.append(EventEnvelope.model_validate(json.loads(line)))

        elif meta.availability_status == "AVAILABLE_SIMULATION":
            from pulse.simulator.scenarios import build_vsc_scenario
            self.envelopes = build_vsc_scenario()

        self.status = ReplayStatus.READY
        logger.info(
            "ReplayController loaded %d envelopes for session [%s] (mode: %s)",
            len(self.envelopes),
            self.session_id,
            self.mode,
        )
        return True

    def get_status(self) -> dict[str, Any]:
        """Provides current playback state and progress metrics."""
        store = get_state_store()
        sess = store.get_session()
        cur_lap = sess.get("lap", 1)
        tot_laps = sess.get("totalLaps", 52)
        elapsed_str = sess.get("elapsed", "00:00:00")

        return {
            "sessionId": self.session_id,
            "captureId": self.capture_id,
            "runId": self.run_id,
            "status": self.status.value,
            "runner_status": self.status.value,
            "mode": self.mode,
            "speed": self.speed,
            "allowedSpeeds": self.ALLOWED_SPEEDS,
            "currentIndex": self.current_index,
            "totalEvents": len(self.envelopes),
            "publishedCount": self.published_count,
            "dropCount": self.drop_count,
            "currentLap": cur_lap,
            "totalLaps": tot_laps,
            "elapsed": elapsed_str,
            "elapsedMs": self.elapsed_ms,
            "lastEventTimeUtc": self.last_event_time_utc.isoformat() if self.last_event_time_utc else None,
            "progressPercent": round((self.current_index / max(1, len(self.envelopes))) * 100, 1),
        }

    async def switch_session(self, session_id: str) -> dict[str, Any]:
        """Switches active playback session and reinitializes state."""
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

            self.status = ReplayStatus.RESETTING
            store = get_state_store()
            store.switch_session(session_id)
            self._load_session_envelopes(session_id)
            self.run_id = f"run-{session_id}-{uuid4().hex[:6]}"
            self.status = ReplayStatus.READY

            status_payload = self.get_status()
            store.notify_replay_status(status_payload)
            return status_payload

    async def start(self, session_id: str | None = None, speed: float | None = None) -> dict[str, Any]:
        """Starts or unpauses replay playback."""
        async with self._lock:
            if session_id and session_id != self.session_id:
                await self.switch_session(session_id)

            if speed is not None:
                self.set_speed(speed)

            if self.status == ReplayStatus.PAUSED:
                return self.resume()

            if self.status == ReplayStatus.COMPLETED or self.current_index >= len(self.envelopes):
                await self.reset()

            self.status = ReplayStatus.RUNNING
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._replay_loop())

            status_payload = self.get_status()
            get_state_store().notify_replay_status(status_payload)
            logger.info("Replay started: session=%s, run=%s, speed=%.2fx", self.session_id, self.run_id, self.speed)
            return status_payload

    def pause(self) -> dict[str, Any]:
        """Pauses replay event scheduling while preserving cursor."""
        self.status = ReplayStatus.PAUSED
        status_payload = self.get_status()
        get_state_store().notify_replay_status(status_payload)
        logger.info("Replay paused at index %d / %d", self.current_index, len(self.envelopes))
        return status_payload

    def resume(self) -> dict[str, Any]:
        """Resumes playback from the current cursor."""
        if self.status in {ReplayStatus.PAUSED, ReplayStatus.READY}:
            self.status = ReplayStatus.RUNNING
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._replay_loop())
            status_payload = self.get_status()
            get_state_store().notify_replay_status(status_payload)
            logger.info("Replay resumed from index %d", self.current_index)
            return status_payload
        return self.get_status()

    async def reset(self) -> dict[str, Any]:
        """Resets replay cursor to beginning under a fresh run ID."""
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

            self.status = ReplayStatus.RESETTING
            self.current_index = 0
            self.published_count = 0
            self.elapsed_ms = 0
            self.run_id = f"run-{uuid4().hex[:8]}"

            store = get_state_store()
            store.switch_session(self.session_id)
            self.status = ReplayStatus.READY

            status_payload = self.get_status()
            store.notify_replay_status(status_payload)
            logger.info("Replay reset completed: new run_id=%s", self.run_id)
            return status_payload

    def set_speed(self, speed: float) -> dict[str, Any]:
        """Adjusts playback acceleration factor."""
        if speed in self.ALLOWED_SPEEDS or 0.1 <= speed <= 20.0:
            self.speed = speed
        else:
            self.speed = 1.0
        status_payload = self.get_status()
        get_state_store().notify_replay_status(status_payload)
        logger.info("Replay speed set to %.2fx", self.speed)
        return status_payload

    async def seek(
        self,
        target_lap: int | None = None,
        target_index: int | None = None,
        target_elapsed_ms: int | None = None,
    ) -> dict[str, Any]:
        """Fast-forwards or rewinds state to exact seek target by fast-replaying history."""
        async with self._lock:
            was_running = (self.status == ReplayStatus.RUNNING)
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

            # Determine target index
            target_idx = 0
            if target_index is not None:
                target_idx = max(0, min(len(self.envelopes), target_index))
            elif target_lap is not None:
                # Find index where lap completes or starts
                for idx, env in enumerate(self.envelopes):
                    if env.payload.get("lap", 1) >= target_lap:
                        target_idx = idx
                        break
                else:
                    target_idx = len(self.envelopes)
            elif target_elapsed_ms is not None:
                for idx, env in enumerate(self.envelopes):
                    if (env.time.session_elapsed_ms or 0) >= target_elapsed_ms:
                        target_idx = idx
                        break
                else:
                    target_idx = len(self.envelopes)

            # Rebuild state from index 0 up to target_idx
            store = get_state_store()
            store.switch_session(self.session_id)

            for i in range(target_idx):
                env = self.envelopes[i]
                store.record_canonical_event(env)

            self.current_index = target_idx
            self.published_count = target_idx
            if target_idx > 0:
                last_env = self.envelopes[target_idx - 1]
                self.last_event_time_utc = last_env.time.event_time_utc
                self.elapsed_ms = last_env.time.session_elapsed_ms or 0

            self.status = ReplayStatus.RUNNING if was_running else ReplayStatus.PAUSED
            if was_running:
                self._task = asyncio.create_task(self._replay_loop())

            status_payload = self.get_status()
            store.notify_replay_status(status_payload)
            logger.info("Replay seek completed: target_index=%d / %d", self.current_index, len(self.envelopes))
            return status_payload

    async def _replay_loop(self) -> None:
        """Asynchronous playback loop publishing timestamped events."""
        store = get_state_store()
        logger.info("Entering replay loop for session [%s] at index %d", self.session_id, self.current_index)

        try:
            while self.current_index < len(self.envelopes):
                if self.status == ReplayStatus.PAUSED:
                    await asyncio.sleep(0.1)
                    continue

                if self.status in {ReplayStatus.RESETTING, ReplayStatus.FAILED, ReplayStatus.COMPLETED}:
                    break

                env = self.envelopes[self.current_index]
                env.run.run_id = self.run_id
                env.run.session_instance_id = self.session_id
                env.run.mode = RunMode.REPLAY if self.mode == "REPLAY" else RunMode.SIMULATED

                topic = raw_topic_for_event(env.event_type)
                key = routing_key(self.session_id, env.subject.driver_number, env.subject.segment_id)

                # Publish event to event bus & Kafka broker
                try:
                    await self.bus.publish(topic, key, env)
                    self.published_count += 1
                except Exception as e:
                    self.drop_count += 1
                    logger.warning("Replay failed to publish event %s: %s", env.event_id, e)

                self.last_event_time_utc = env.time.event_time_utc
                self.elapsed_ms = env.time.session_elapsed_ms or 0

                self.current_index += 1

                # Every 5 events or on significant events, broadcast replay status
                if self.current_index % 5 == 0 or env.event_type in {"VSC_DEPLOYED", "SAFETY_CAR_DEPLOYED", "PIT_STOP", "DRIVER_RETIRED"}:
                    store.notify_replay_status(self.get_status())

                # Event-time scheduling: wall_clock_delay = delta / speed
                if self.current_index < len(self.envelopes):
                    next_env = self.envelopes[self.current_index]
                    t_cur = env.time.session_elapsed_ms or 0
                    t_nxt = next_env.time.session_elapsed_ms or t_cur
                    delta_ms = min(2500, max(0, t_nxt - t_cur))
                    if delta_ms > 0:
                        wall_clock_sec = (delta_ms / 1000.0) / max(0.1, self.speed)
                        # Chunked responsive sleep to allow immediate pause/reset/seek reaction
                        end_sleep = asyncio.get_running_loop().time() + wall_clock_sec
                        while asyncio.get_running_loop().time() < end_sleep:
                            if self.status != ReplayStatus.RUNNING:
                                break
                            rem = end_sleep - asyncio.get_running_loop().time()
                            await asyncio.sleep(min(0.05, max(0.001, rem)))
                    else:
                        await asyncio.sleep(0.001)

            self.status = ReplayStatus.COMPLETED
            store.notify_replay_status(self.get_status())
            logger.info("Replay completed for session [%s] (published: %d events)", self.session_id, self.published_count)

        except asyncio.CancelledError:
            logger.info("Replay loop task cancelled.")
        except Exception as e:
            self.status = ReplayStatus.FAILED
            store.notify_replay_status(self.get_status())
            logger.error("Replay loop error: %s", e, exc_info=True)


_controller: ReplayController | None = None


def get_replay_controller() -> ReplayController:
    """Singleton provider for backend ReplayController."""
    global _controller
    if _controller is None:
        _controller = ReplayController()
    return _controller
