from __future__ import annotations

import logging
import time
from typing import Any

from pulse.agents.base import BaseAgent
from pulse.contracts import EventEnvelope, Finding, FindingStatus, Interpretation, Subject
from pulse.topics import AGENT_TOPICS

logger = logging.getLogger("pulse.agent.tyre_strategy")


class TyreStrategyAgent(BaseAgent):
    """Agent 4: Tyre & Strategy Intelligence.
    
    Models tyre stint degradation, calculates neutralised pit loss deltas under VSC and Safety Car,
    generates deterministic pit window alternatives, and exposes input lineage and calculation versions.
    """

    def __init__(self, bus: Any = None) -> None:
        super().__init__(
            agent_id="agent-04-tyre-strategy",
            name="Tyre & Strategy Intelligence",
            output_topic=AGENT_TOPICS["tyre_strategy"],
            bus=bus,
            model_version="1.2.0",
        )
        # Compound baseline degradation rates (seconds per lap)
        self.deg_slopes = {
            "S": 0.12,
            "M": 0.08,
            "H": 0.04,
            "I": 0.15,
            "W": 0.20,
        }
        self.driver_stints: dict[int, dict[str, Any]] = {
            16: {"compound": "M", "stint_age": 23, "gap_to_p2": 2.481, "position": 1},
            4: {"compound": "H", "stint_age": 23, "gap_to_p2": 1.586, "position": 2},
            1: {"compound": "H", "stint_age": 23, "gap_to_p2": 4.675, "position": 3},
            44: {"compound": "M", "stint_age": 23, "gap_to_p2": 1.294, "position": 4},
        }
        self.active_neutralisation: str | None = None

    async def on_event(self, topic: str, key: str, event: Any) -> None:
        t0 = time.perf_counter()
        if isinstance(event, dict):
            event = EventEnvelope.model_validate(event)

        self.record_input(event.event_id, eligible=True, run_id=event.run.run_id)

        try:
            event_type = event.event_type.upper()
            payload = event.payload or {}
            dn = event.subject.driver_number or 16
            provenance = {
                "provider": event.source.provider,
                "adapter": event.source.adapter,
                "source_record_id": event.source.source_record_id,
                "capture_id": event.source.capture_id,
                "data_mode": event.run.mode if isinstance(event.run.mode, str) else event.run.mode.value,
            }

            # Update neutralisation context
            if event_type == "VSC_DEPLOYED":
                self.active_neutralisation = "VSC"
            elif event_type == "SAFETY_CAR_DEPLOYED":
                self.active_neutralisation = "SC"
            elif event_type in {"VSC_ENDED", "SAFETY_CAR_ENDED", "SESSION_STARTED"}:
                self.active_neutralisation = None

            # Update stint info from tyre events
            if event_type in {"TYRE_FITTED", "PIT_STOP"}:
                compound = payload.get("compound", "H")
                stint_age = payload.get("stint_age", 0)
                self.driver_stints[dn] = {
                    "compound": compound,
                    "stint_age": stint_age,
                    "gap_to_p2": self.driver_stints.get(dn, {}).get("gap_to_p2", 2.0),
                    "position": self.driver_stints.get(dn, {}).get("position", 1),
                }

            # Strategy triggers: VSC deployment, pit entry, or driver position update
            should_emit = (
                event_type in {"VSC_DEPLOYED", "SAFETY_CAR_DEPLOYED", "PIT_ENTRY"}
                or (event_type == "POSITION_UPDATE" and (payload.get("pit_lane_entry_distance_m") is not None or self.active_neutralisation))
            )

            if should_emit:
                # Benchmark pit stop losses (seconds)
                green_pit_loss = 21.5
                if self.active_neutralisation == "VSC":
                    pit_loss = 11.0
                    saving = green_pit_loss - pit_loss  # 10.5s saving
                    strategy_score = 88
                elif self.active_neutralisation == "SC":
                    pit_loss = 13.5
                    saving = green_pit_loss - pit_loss  # 8.0s saving
                    strategy_score = 82
                else:
                    pit_loss = green_pit_loss
                    saving = 0.0
                    strategy_score = 50

                stint_data = self.driver_stints.get(dn, {"compound": "M", "stint_age": 23, "gap_to_p2": 2.481, "position": 1})
                current_compound = stint_data["compound"]
                stint_age = stint_data["stint_age"]
                target_compound = "H" if current_compound in {"S", "M"} else "M"
                deg_rate = self.deg_slopes.get(current_compound, 0.08)
                accumulated_deg_sec = round(stint_age * deg_rate, 2)

                assumptions = {
                    "green_pit_loss_sec": green_pit_loss,
                    "neutralised_pit_loss_sec": pit_loss,
                    "net_time_saving_sec": saving,
                    "compound_deg_rate_sec_lap": deg_rate,
                    "accumulated_degradation_sec": accumulated_deg_sec,
                    "calculation_version": self.model_version,
                }

                scenarios = [
                    {
                        "label": "Box this lap",
                        "action": f"Switch to {target_compound} compound",
                        "score": strategy_score,
                        "delta": f"+{saving:.1f}s neutralisation saving",
                        "tone": "positive" if saving > 5.0 else "neutral",
                        "note": f"Capitalises on {saving:.1f}s pit-loss compression under {self.active_neutralisation or 'green flag'}.",
                    },
                    {
                        "label": "Hold 1 lap",
                        "action": "Maintain track position",
                        "score": 58,
                        "delta": "+0.4s projected",
                        "tone": "neutral",
                        "note": "Risk of neutralisation concluding before next lap pit entry window.",
                    },
                    {
                        "label": "Stay out",
                        "action": "Deep stint extension",
                        "score": 32,
                        "delta": "−1.3s projected",
                        "tone": "negative",
                        "note": f"Accumulated tyre degradation ({accumulated_deg_sec}s) exposes car to severe undercut.",
                    },
                ]

                finding_strat = Finding(
                    finding_id=f"finding-strat-{event.event_id}-{dn}",
                    agent_id=self.agent_id,
                    finding_type="PIT_WINDOW_OPPORTUNITY",
                    session_id=event.session.session_id,
                    run_id=event.run.run_id,
                    subject=Subject(driver_number=dn),
                    trigger_event_id=event.event_id,
                    as_of_event_time=event.time.event_time_utc,
                    interpretation=Interpretation.DERIVED,
                    result={
                        "driver_number": dn,
                        "target_compound": target_compound,
                        "current_compound": current_compound,
                        "stint_age_current": stint_age,
                        "green_pit_loss_sec": green_pit_loss,
                        "vsc_pit_loss_sec": pit_loss,
                        "net_time_saving_sec": saving,
                        "gap_to_p2_sec": stint_data.get("gap_to_p2", 2.481),
                        "rejoin_position_projected": stint_data.get("position", 1),
                        "strategy_score": strategy_score,
                        "assumptions": assumptions,
                        "scenarios": scenarios,
                        "source_provenance": provenance,
                    },
                    evidence_refs=[event.event_id, f"stint-{current_compound}-{stint_age}-laps"],
                    assessment_status=FindingStatus.PROVISIONAL,
                    reason_codes=["VSC_COMPRESSED_PIT_LOSS" if saving > 0 else "STRATEGY_WINDOW_EVALUATED"],
                    model_version=self.model_version,
                )
                await self.emit_finding(finding_strat)
                latency = (time.perf_counter() - t0) * 1000.0
                self.record_outcome("FINDING_EMITTED", latency_ms=latency)
                return

            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("NO_FINDING", latency_ms=latency)

        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000.0
            self.record_outcome("FAILED", latency_ms=latency)
            logger.error("TyreStrategyAgent error: %s", e, exc_info=True)
            raise
