"""Versioned Kafka topic names and routing helpers."""

RAW_TOPICS = {
    "race_control": "pulse.raw.race_control.v1",
    "track_status": "pulse.raw.track_status.v1",
    "timing_laps": "pulse.raw.timing.laps.v1",
    "timing_positions": "pulse.raw.timing.positions.v1",
    "telemetry_car": "pulse.raw.telemetry.car.v1",
    "weather": "pulse.raw.weather.v1",
    "tyres_stints": "pulse.raw.tyres.stints.v1",
    "pit_events": "pulse.raw.pit.events.v1",
    "session_status": "pulse.raw.session_status.v1",
}

NORMALISED_TOPICS = {
    "race_events": "pulse.norm.race_events.v1",
    "driver_laps": "pulse.norm.driver_laps.v1",
    "driver_state": "pulse.norm.driver_state.v1",
    "track_segments": "pulse.norm.track_segments.v1",
    "tyre_stints": "pulse.norm.tyre_stints.v1",
}

FEATURE_TOPICS = {
    "vehicle_response": "pulse.features.vehicle_response.v1",
    "tyre_stints": "pulse.features.tyre_stints.v1",
    "race_context": "pulse.features.race_context.v1",
}

AGENT_TOPICS = {
    "event_context": "pulse.agent.event_context.findings.v1",
    "track_state": "pulse.agent.track_state.findings.v1",
    "vehicle_response": "pulse.agent.vehicle_response.findings.v1",
    "tyre_strategy": "pulse.agent.tyre_strategy.findings.v1",
    "race_impact": "pulse.agent.race_impact.findings.v1",
}

INTELLIGENCE_TOPICS = {
    "driver_impact": "pulse.intelligence.driver_impact.v1",
    "track_alerts": "pulse.intelligence.track_alerts.v1",
    "strategy_alerts": "pulse.intelligence.strategy_alerts.v1",
    "race_timeline": "pulse.intelligence.race_timeline.v1",
}

OPS_TOPICS = {
    "agent_health": "pulse.ops.agent_health.v1",
    "pipeline_metrics": "pulse.ops.pipeline_metrics.v1",
}


def raw_topic_for_event(event_type: str) -> str:
    event_type = event_type.upper()
    if event_type in {
        "VSC_DEPLOYED", "VSC_ENDING", "VSC_ENDED",
        "SAFETY_CAR_DEPLOYED", "SAFETY_CAR_ENDING", "SAFETY_CAR_ENDED",
        "RED_FLAG", "YELLOW_FLAG", "INCIDENT_NOTICE", "TRACK_STATUS_GREEN",
        "RACE_CONTROL_NOTICE", "RACE_CONTROL_MESSAGE", "CHEQUERED_FLAG",
        "GREEN_FLAG", "STEWARD_DECISION", "DRIVER_RETIRED", "DRIVER_DNS",
        "SESSION_STARTED", "SESSION_ENTRY_LIST"
    }:
        return RAW_TOPICS["race_control"]
    if event_type in {"TRACK_STATUS_UPDATE", "SEGMENT_STATUS_UPDATE"}:
        return RAW_TOPICS["track_status"]
    if event_type in {"LAP_COMPLETED", "SECTOR_COMPLETED"}:
        return RAW_TOPICS["timing_laps"]
    if event_type in {"POSITION_UPDATE", "INTERVAL_UPDATE"}:
        return RAW_TOPICS["timing_positions"]
    if event_type in {"CAR_TELEMETRY", "CAR_TELEMETRY_SAMPLE"}:
        return RAW_TOPICS["telemetry_car"]
    if event_type == "WEATHER_OBSERVATION":
        return RAW_TOPICS["weather"]
    if event_type in {"TYRE_FITTED", "STINT_UPDATE"}:
        return RAW_TOPICS["tyres_stints"]
    if event_type in {"PIT_ENTRY", "PIT_STOP", "PIT_EXIT"}:
        return RAW_TOPICS["pit_events"]
    return RAW_TOPICS["race_control"]


def routing_key(session_instance_id: str, driver_number: int | None = None, segment_id: str | None = None) -> str:
    if driver_number is not None:
        return f"{session_instance_id}:{driver_number}"
    if segment_id:
        return f"{session_instance_id}:{segment_id}"
    return session_instance_id


ALL_TOPICS = [*RAW_TOPICS.values(), *NORMALISED_TOPICS.values(), *FEATURE_TOPICS.values(), *AGENT_TOPICS.values(), *INTELLIGENCE_TOPICS.values(), *OPS_TOPICS.values()]
