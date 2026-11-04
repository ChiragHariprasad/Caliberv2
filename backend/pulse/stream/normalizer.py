from __future__ import annotations

import logging
from typing import Any

from pulse.contracts import Completeness, EventEnvelope, Interpretation, Quality, UnitValidation, utc_now
from pulse.topics import NORMALISED_TOPICS

logger = logging.getLogger("pulse.normalizer")


class StreamNormalizer:
    """Validates, deduplicates, and normalises raw F1 events into canonical streams."""

    def __init__(self) -> None:
        self._seen_events: set[str] = set()
        self.processed_count = 0
        self.duplicate_count = 0
        self.invalid_count = 0

    def process(self, raw_data: dict[str, Any] | EventEnvelope) -> tuple[EventEnvelope | None, str | None]:
        """Validates envelope and returns (canonical_envelope, target_topic).

        Returns (None, reason) if invalid or duplicate.
        """
        try:
            if isinstance(raw_data, EventEnvelope):
                envelope = raw_data
            else:
                envelope = EventEnvelope.model_validate(raw_data)
        except Exception as e:
            self.invalid_count += 1
            logger.warning("Normalizer rejected invalid event payload: %s", e)
            return None, f"INVALID_SCHEMA: {e}"

        # Deduplication
        if envelope.event_id in self._seen_events:
            self.duplicate_count += 1
            logger.debug("Deduplicated event %s", envelope.event_id)
            return None, "DUPLICATE_EVENT"

        self._seen_events.add(envelope.event_id)
        self.processed_count += 1

        # Determine target canonical topic
        event_type = envelope.event_type.upper()
        if event_type in {
            "VSC_DEPLOYED", "VSC_ENDING", "VSC_ENDED",
            "SAFETY_CAR_DEPLOYED", "SAFETY_CAR_ENDING", "SAFETY_CAR_ENDED",
            "RED_FLAG", "YELLOW_FLAG", "INCIDENT_NOTICE", "SESSION_STARTED"
        }:
            target_topic = NORMALISED_TOPICS["race_events"]
        elif event_type in {"LAP_COMPLETED", "SECTOR_COMPLETED"}:
            target_topic = NORMALISED_TOPICS["driver_laps"]
        elif event_type in {"POSITION_UPDATE", "INTERVAL_UPDATE", "TYRE_FITTED", "PIT_STOP"}:
            target_topic = NORMALISED_TOPICS["driver_state"]
        elif event_type in {"TRACK_STATUS_UPDATE", "WEATHER_OBSERVATION"}:
            target_topic = NORMALISED_TOPICS["track_segments"]
        else:
            target_topic = NORMALISED_TOPICS["race_events"]

        return envelope, target_topic

