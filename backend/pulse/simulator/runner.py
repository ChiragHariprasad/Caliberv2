from __future__ import annotations

import asyncio
import logging
from typing import Any

from pulse.contracts import EventEnvelope, RunMode, RunRecord, RunStatus, utc_now
from pulse.simulator.scenarios import build_vsc_scenario
from pulse.stream.bus import PulseEventBus, get_event_bus
from pulse.topics import raw_topic_for_event, routing_key

logger = logging.getLogger("pulse.simulator")


class ScenarioRunner:
    """Controls the deterministic replay/simulation loop."""

    def __init__(self, bus: PulseEventBus | None = None) -> None:
        self.bus = bus or get_event_bus()
        self.scenario_name = "vsc_pit_window"
        self.events: list[EventEnvelope] = build_vsc_scenario()
        self.current_index = 0
        self.speed: float = 1.0
        self.status: RunStatus = RunStatus.CREATED
        self._task: asyncio.Task[None] | None = None
        self.run_record = RunRecord(
            run_id="pulse-sim-vsc-001",
            session_instance_id="sim-2026-monaco",
            mode=RunMode.SIMULATED,
            status=RunStatus.CREATED,
            replay_speed=1.0,
            scenario="vsc_pit_window",
            source_summary={
                "capture_id": "pulse-sim-v1",
                "provider": "PULSE_SIMULATOR",
                "provenance_status": "APPROVED",
            },
        )

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self.status = RunStatus.RUNNING
        self.run_record.status = RunStatus.RUNNING
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Simulator runner started scenario '%s'", self.scenario_name)

    async def _run_loop(self) -> None:
        try:
            while self.current_index < len(self.events):
                if self.status == RunStatus.PAUSED:
                    await asyncio.sleep(0.3)
                    continue
                if self.status in {RunStatus.STOPPED, RunStatus.COMPLETED}:
                    break

                event = self.events[self.current_index]
                topic = raw_topic_for_event(event.event_type)
                key = routing_key(
                    event.session.session_id,
                    event.subject.driver_number,
                    event.subject.segment_id,
                )

                logger.debug("Simulator emitting event %s (%s) to %s", event.event_id, event.event_type, topic)
                await self.bus.publish(topic, key, event)
                self.run_record.last_event_time_utc = event.time.event_time_utc

                self.current_index += 1

                # Calculate delay to next event
                if self.current_index < len(self.events):
                    next_event = self.events[self.current_index]
                    cur_ms = event.time.session_elapsed_ms or 0
                    nxt_ms = next_event.time.session_elapsed_ms or (cur_ms + 1000)
                    delay_ms = max(500, nxt_ms - cur_ms)
                    delay_sec = (delay_ms / 1000.0) / max(0.2, self.speed)
                    await asyncio.sleep(delay_sec)
                else:
                    await asyncio.sleep(1.0)

            self.status = RunStatus.COMPLETED
            self.run_record.status = RunStatus.COMPLETED
            logger.info("Simulator scenario completed.")
        except asyncio.CancelledError:
            self.status = RunStatus.STOPPED
            self.run_record.status = RunStatus.STOPPED
            logger.info("Simulator runner loop cancelled.")
        except Exception as e:
            self.status = RunStatus.FAILED
            self.run_record.status = RunStatus.FAILED
            logger.error("Simulator runner error: %s", e)

    def pause(self) -> None:
        self.status = RunStatus.PAUSED
        self.run_record.status = RunStatus.PAUSED
        logger.info("Simulator paused.")

    def resume(self) -> None:
        self.status = RunStatus.RUNNING
        self.run_record.status = RunStatus.RUNNING
        logger.info("Simulator resumed.")

    async def restart(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.current_index = 0
        self.status = RunStatus.CREATED
        self.run_record.status = RunStatus.CREATED
        await self.start()
        logger.info("Simulator restarted.")

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.2, min(speed, 16.0))
        self.run_record.replay_speed = self.speed
        logger.info("Simulator replay speed set to %.1fx", self.speed)


_runner: ScenarioRunner | None = None


def get_scenario_runner() -> ScenarioRunner:
    global _runner
    if _runner is None:
        _runner = ScenarioRunner()
    return _runner

