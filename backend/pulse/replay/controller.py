from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from collections.abc import Awaitable, Callable
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
        self._event_processor: Callable[..., Awaitable[None]] | None = None
        self._reset_hook: Callable[[], None] | None = None

        # Load initial default session envelopes
        self._load_session_envelopes(self.session_id)

    def set_event_processor(self, processor: Callable[..., Awaitable[None]] | None) -> None:
        """Install the canonical processing path used by playback and seek rebuilds.

        A processor receives an envelope and a ``publish`` keyword.  Normal
        playback uses ``publish=True``; seek reconstruction uses
        ``publish=False`` so rebuilding a run cannot duplicate source events
        on the transport.
        """
        self._event_processor = processor

    def set_reset_hook(self, hook: Callable[[], None] | None) -> None:
        """Register a callback to be invoked whenever replay state is reset or seeked."""
        self._reset_hook = hook

    def _for_current_run(self, envelope: EventEnvelope) -> EventEnvelope:
        """Copy a source envelope into the active replay-run namespace."""
        replayed = envelope.model_copy(deep=True)
        replayed.run.run_id = self.run_id
        replayed.run.session_instance_id = self.session_id
        replayed.run.mode = RunMode.REPLAY if self.mode == "REPLAY" else RunMode.SIMULATED
        replayed.event_id = f"{envelope.event_id}-{self.run_id}"
        return replayed

    async def _process(self, envelope: EventEnvelope, *, publish: bool) -> None:
        # Guarantee state store projection is immediately updated on every event
        get_state_store().record_canonical_event(envelope)

        if self._event_processor is not None:
            await self._event_processor(envelope, publish=publish)
            return

        if publish:
            topic = raw_topic_for_event(envelope.event_type)
            key = routing_key(self.session_id, envelope.subject.driver_number, envelope.subject.segment_id)
            await self.bus.publish(topic, key, envelope)

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
        self.capture_id = meta.capture_id or session_id
        self.mode = "REPLAY" if meta.availability_status == "AVAILABLE_HISTORICAL" else "SIMULATED"

        # Search multiple candidate locations for the captures directory to support
        # running from repo root, backend subdirectory, WSL mounts, or test runners.
        repo_root = Path(__file__).resolve().parents[3]
        candidate_dirs = [
            repo_root / "captures" / self.capture_id,
            repo_root / "captures" / self.session_id,
            Path("captures") / self.capture_id,
            Path("captures") / self.session_id,
            Path("../captures") / self.capture_id,
            Path("../captures") / self.session_id,
            Path("../../captures") / self.capture_id,
            Path("../../captures") / self.session_id,
        ]

        env_file: Path | None = None
        for cdir in candidate_dirs:
            candidate_file = cdir / "envelopes.jsonl"
            if candidate_file.exists():
                env_file = candidate_file
                break

        if env_file is not None and env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.envelopes.append(EventEnvelope.model_validate(json.loads(line)))
        elif meta.availability_status == "AVAILABLE_SIMULATION":
            from pulse.simulator.scenarios import build_vsc_scenario
            self.envelopes = build_vsc_scenario()

        self.status = ReplayStatus.READY
        logger.info(
            "ReplayController loaded %d envelopes for session [%s] (mode: %s, file: %s)",
            len(self.envelopes),
            self.session_id,
            self.mode,
            str(env_file) if env_file else "none",
        )
        return len(self.envelopes) > 0

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

    async def _switch_session_internal(self, session_id: str) -> dict[str, Any]:
        """Internal session switch helper without acquiring lock (caller must hold lock or be un-locked)."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self.status = ReplayStatus.RESETTING
        if self._reset_hook is not None:
            self._reset_hook()
        store = get_state_store()
        store.switch_session(session_id)
        self._load_session_envelopes(session_id)
        self.run_id = f"run-{session_id}-{uuid4().hex[:6]}"
        store.begin_run(self.run_id)
        self.status = ReplayStatus.READY

        status_payload = self.get_status()
        store.notify_replay_status(status_payload)
        return status_payload

    async def switch_session(self, session_id: str) -> dict[str, Any]:
        """Switches active playback session and reinitializes state."""
        async with self._lock:
            return await self._switch_session_internal(session_id)

    async def _reset_internal(self) -> dict[str, Any]:
        """Internal reset helper without acquiring lock (caller must hold lock or be un-locked)."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self.status = ReplayStatus.RESETTING
        if self._reset_hook is not None:
            self._reset_hook()
        self.current_index = 0
        self.published_count = 0
        self.elapsed_ms = 0
        self.last_event_time_utc = None
        self.drop_count = 0
        self.run_id = f"run-{uuid4().hex[:8]}"

        store = get_state_store()
        store.switch_session(self.session_id)
        store.begin_run(self.run_id)
        self.status = ReplayStatus.READY

        status_payload = self.get_status()
        store.notify_replay_status(status_payload)
        logger.info("Replay reset completed: new run_id=%s", self.run_id)
        return status_payload

    async def reset(self) -> dict[str, Any]:
        """Resets replay cursor to beginning under a fresh run ID."""
        async with self._lock:
            return await self._reset_internal()

    async def start(self, session_id: str | None = None, speed: float | None = None) -> dict[str, Any]:
        """Starts or unpauses replay playback."""
        async with self._lock:
            if session_id and session_id != self.session_id:
                await self._switch_session_internal(session_id)

            if speed is not None:
                self.set_speed(speed)

            if self.status == ReplayStatus.PAUSED:
                return self.resume()

            if self.status == ReplayStatus.COMPLETED or (len(self.envelopes) > 0 and self.current_index >= len(self.envelopes)):
                await self._reset_internal()

            if len(self.envelopes) == 0:
                logger.warning("Replay start requested but 0 envelopes available for session [%s]", self.session_id)
                self.status = ReplayStatus.READY
                status_payload = self.get_status()
                get_state_store().notify_replay_status(status_payload)
                return status_payload

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
                    cur_lap = env.payload.get("lap") or env.payload.get("lap_number") or 1
                    if cur_lap >= target_lap:
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

            # A seek creates a new execution lineage. Any delayed Kafka
            # records from the abandoned cursor can therefore be identified
            # and ignored by the active-run consumer instead of mutating the
            # reconstructed state.
            if self._reset_hook is not None:
                self._reset_hook()
            self.run_id = f"run-{self.session_id}-{uuid4().hex[:6]}"

            # Rebuild state from index 0 up to target_idx through the exact
            # same canonical processor as normal playback. This deliberately
            # avoids republishing raw source records while reconstructing.
            store = get_state_store()
            store.switch_session(self.session_id)
            store.begin_run(self.run_id)
            self.last_event_time_utc = None
            self.elapsed_ms = 0
            self.drop_count = 0
            try:
                for i in range(target_idx):
                    await self._process(self._for_current_run(self.envelopes[i]), publish=False)
            except Exception:
                self.status = ReplayStatus.FAILED
                store.notify_replay_status(self.get_status())
                logger.exception("Replay seek reconstruction failed at index %d", self.current_index)
                raise

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
            store.notify_session_state()
            store.notify_driver_state()
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

                env = self._for_current_run(self.envelopes[self.current_index])

                # Send normal playback through the shared processor. A
                # processing failure is terminal for this run: advancing the
                # cursor would silently skip evidence and corrupt replay
                # state.
                try:
                    await self._process(env, publish=True)
                    self.published_count += 1
                except Exception as e:
                    self.drop_count += 1
                    raise RuntimeError(f"Replay failed to process event {env.event_id}") from e

                self.last_event_time_utc = env.time.event_time_utc
                self.elapsed_ms = env.time.session_elapsed_ms or 0

                self.current_index += 1

                # Every 10 events (~0.5s at 20Hz) or on significant events, broadcast replay status
                if self.current_index % 10 == 0 or env.event_type in {"VSC_DEPLOYED", "SAFETY_CAR_DEPLOYED", "PIT_STOP", "DRIVER_RETIRED"}:
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
                            await asyncio.sleep(min(0.025, max(0.001, rem)))
                    else:
                        # Prevent microsecond bursts if two events share the same millisecond timestamp
                        min_paced = max(0.002, 0.010 / max(0.1, self.speed))
                        await asyncio.sleep(min_paced)

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
