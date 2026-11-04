SET 'execution.runtime-mode' = 'streaming';
SET 'pipeline.name' = 'pulse-canonical-normalizer-v2';
SET 'execution.checkpointing.interval' = '5000';

-- ============================================================
-- 1. RACE CONTROL & SESSION STATUS -> pulse.norm.race_events.v1
-- ============================================================
CREATE TABLE kafka_raw_race_control (
    raw_payload STRING,
    event_id AS JSON_VALUE(raw_payload, '$.event_id'),
    event_type AS JSON_VALUE(raw_payload, '$.event_type'),
    session_id AS JSON_VALUE(raw_payload, '$.session.session_id'),
    event_time_ts AS COALESCE(TRY_CAST(REPLACE(SUBSTRING(JSON_VALUE(raw_payload, '$.time.event_time_utc'), 1, 19), 'T', ' ') AS TIMESTAMP(3)), CURRENT_TIMESTAMP),
    WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '2' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'pulse.raw.race_control.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'pulse-flink-race-control-v2',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'raw'
);

CREATE TABLE kafka_norm_race_events (
    event_id STRING,
    raw_payload STRING,
    PRIMARY KEY (event_id) NOT ENFORCED
) WITH (
    'connector' = 'upsert-kafka',
    'topic' = 'pulse.norm.race_events.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'key.format' = 'raw',
    'value.format' = 'raw',
    'value.fields-include' = 'EXCEPT_KEY'
);

-- ============================================================
-- 2. TRACK STATUS & WEATHER -> pulse.norm.track_segments.v1
-- ============================================================
CREATE TABLE kafka_raw_track_status (
    raw_payload STRING,
    event_id AS JSON_VALUE(raw_payload, '$.event_id'),
    event_type AS JSON_VALUE(raw_payload, '$.event_type'),
    session_id AS JSON_VALUE(raw_payload, '$.session.session_id'),
    event_time_ts AS COALESCE(TRY_CAST(REPLACE(SUBSTRING(JSON_VALUE(raw_payload, '$.time.event_time_utc'), 1, 19), 'T', ' ') AS TIMESTAMP(3)), CURRENT_TIMESTAMP),
    WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '2' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'pulse.raw.track_status.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'pulse-flink-track-status-v2',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'raw'
);

CREATE TABLE kafka_raw_weather (
    raw_payload STRING,
    event_id AS JSON_VALUE(raw_payload, '$.event_id'),
    event_type AS JSON_VALUE(raw_payload, '$.event_type'),
    session_id AS JSON_VALUE(raw_payload, '$.session.session_id'),
    event_time_ts AS COALESCE(TRY_CAST(REPLACE(SUBSTRING(JSON_VALUE(raw_payload, '$.time.event_time_utc'), 1, 19), 'T', ' ') AS TIMESTAMP(3)), CURRENT_TIMESTAMP),
    WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '2' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'pulse.raw.weather.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'pulse-flink-weather-v2',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'raw'
);

CREATE TABLE kafka_norm_track_segments (
    event_id STRING,
    raw_payload STRING,
    PRIMARY KEY (event_id) NOT ENFORCED
) WITH (
    'connector' = 'upsert-kafka',
    'topic' = 'pulse.norm.track_segments.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'key.format' = 'raw',
    'value.format' = 'raw',
    'value.fields-include' = 'EXCEPT_KEY'
);

-- ============================================================
-- 3. TIMING LAPS -> pulse.norm.driver_laps.v1
-- ============================================================
CREATE TABLE kafka_raw_timing_laps (
    raw_payload STRING,
    event_id AS JSON_VALUE(raw_payload, '$.event_id'),
    event_type AS JSON_VALUE(raw_payload, '$.event_type'),
    session_id AS JSON_VALUE(raw_payload, '$.session.session_id'),
    event_time_ts AS COALESCE(TRY_CAST(REPLACE(SUBSTRING(JSON_VALUE(raw_payload, '$.time.event_time_utc'), 1, 19), 'T', ' ') AS TIMESTAMP(3)), CURRENT_TIMESTAMP),
    WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '2' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'pulse.raw.timing.laps.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'pulse-flink-timing-laps-v2',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'raw'
);

CREATE TABLE kafka_norm_driver_laps (
    event_id STRING,
    raw_payload STRING,
    PRIMARY KEY (event_id) NOT ENFORCED
) WITH (
    'connector' = 'upsert-kafka',
    'topic' = 'pulse.norm.driver_laps.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'key.format' = 'raw',
    'value.format' = 'raw',
    'value.fields-include' = 'EXCEPT_KEY'
);

-- ============================================================
-- 4. POSITIONS & TELEMETRY -> pulse.norm.driver_state.v1
-- ============================================================
CREATE TABLE kafka_raw_timing_positions (
    raw_payload STRING,
    event_id AS JSON_VALUE(raw_payload, '$.event_id'),
    event_type AS JSON_VALUE(raw_payload, '$.event_type'),
    session_id AS JSON_VALUE(raw_payload, '$.session.session_id'),
    event_time_ts AS COALESCE(TRY_CAST(REPLACE(SUBSTRING(JSON_VALUE(raw_payload, '$.time.event_time_utc'), 1, 19), 'T', ' ') AS TIMESTAMP(3)), CURRENT_TIMESTAMP),
    WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '2' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'pulse.raw.timing.positions.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'pulse-flink-positions-v2',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'raw'
);

CREATE TABLE kafka_norm_driver_state (
    event_id STRING,
    raw_payload STRING,
    PRIMARY KEY (event_id) NOT ENFORCED
) WITH (
    'connector' = 'upsert-kafka',
    'topic' = 'pulse.norm.driver_state.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'key.format' = 'raw',
    'value.format' = 'raw',
    'value.fields-include' = 'EXCEPT_KEY'
);

-- ============================================================
-- 5. TYRES & PIT EVENTS -> pulse.norm.tyre_stints.v1
-- ============================================================
CREATE TABLE kafka_raw_tyres_stints (
    raw_payload STRING,
    event_id AS JSON_VALUE(raw_payload, '$.event_id'),
    event_type AS JSON_VALUE(raw_payload, '$.event_type'),
    session_id AS JSON_VALUE(raw_payload, '$.session.session_id'),
    event_time_ts AS COALESCE(TRY_CAST(REPLACE(SUBSTRING(JSON_VALUE(raw_payload, '$.time.event_time_utc'), 1, 19), 'T', ' ') AS TIMESTAMP(3)), CURRENT_TIMESTAMP),
    WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '2' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'pulse.raw.tyres.stints.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'pulse-flink-tyres-v2',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'raw'
);

CREATE TABLE kafka_raw_pit_events (
    raw_payload STRING,
    event_id AS JSON_VALUE(raw_payload, '$.event_id'),
    event_type AS JSON_VALUE(raw_payload, '$.event_type'),
    session_id AS JSON_VALUE(raw_payload, '$.session.session_id'),
    event_time_ts AS COALESCE(TRY_CAST(REPLACE(SUBSTRING(JSON_VALUE(raw_payload, '$.time.event_time_utc'), 1, 19), 'T', ' ') AS TIMESTAMP(3)), CURRENT_TIMESTAMP),
    WATERMARK FOR event_time_ts AS event_time_ts - INTERVAL '2' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'pulse.raw.pit.events.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'pulse-flink-pit-events-v2',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'raw'
);

CREATE TABLE kafka_norm_tyre_stints (
    event_id STRING,
    raw_payload STRING,
    PRIMARY KEY (event_id) NOT ENFORCED
) WITH (
    'connector' = 'upsert-kafka',
    'topic' = 'pulse.norm.tyre_stints.v1',
    'properties.bootstrap.servers' = 'kafka:29092',
    'key.format' = 'raw',
    'value.format' = 'raw',
    'value.fields-include' = 'EXCEPT_KEY'
);

-- ============================================================
-- UNIFIED EXECUTION STATEMENT SET
-- Deduplicates each stream statefully by event_id with event-time ordering
-- ============================================================
EXECUTE STATEMENT SET
BEGIN
    INSERT INTO kafka_norm_race_events
    SELECT event_id, raw_payload
    FROM (
        SELECT event_id, raw_payload,
               ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time_ts ASC) AS row_num
        FROM kafka_raw_race_control
        WHERE event_id IS NOT NULL AND event_type IS NOT NULL
    ) WHERE row_num = 1;

    INSERT INTO kafka_norm_track_segments
    SELECT event_id, raw_payload
    FROM (
        SELECT event_id, raw_payload,
               ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time_ts ASC) AS row_num
        FROM kafka_raw_track_status
        WHERE event_id IS NOT NULL AND event_type IS NOT NULL
    ) WHERE row_num = 1;

    INSERT INTO kafka_norm_track_segments
    SELECT event_id, raw_payload
    FROM (
        SELECT event_id, raw_payload,
               ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time_ts ASC) AS row_num
        FROM kafka_raw_weather
        WHERE event_id IS NOT NULL AND event_type IS NOT NULL
    ) WHERE row_num = 1;

    INSERT INTO kafka_norm_driver_laps
    SELECT event_id, raw_payload
    FROM (
        SELECT event_id, raw_payload,
               ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time_ts ASC) AS row_num
        FROM kafka_raw_timing_laps
        WHERE event_id IS NOT NULL AND event_type IS NOT NULL
    ) WHERE row_num = 1;

    INSERT INTO kafka_norm_driver_state
    SELECT event_id, raw_payload
    FROM (
        SELECT event_id, raw_payload,
               ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time_ts ASC) AS row_num
        FROM kafka_raw_timing_positions
        WHERE event_id IS NOT NULL AND event_type IS NOT NULL
    ) WHERE row_num = 1;

    INSERT INTO kafka_norm_tyre_stints
    SELECT event_id, raw_payload
    FROM (
        SELECT event_id, raw_payload,
               ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time_ts ASC) AS row_num
        FROM kafka_raw_tyres_stints
        WHERE event_id IS NOT NULL AND event_type IS NOT NULL
    ) WHERE row_num = 1;

    INSERT INTO kafka_norm_tyre_stints
    SELECT event_id, raw_payload
    FROM (
        SELECT event_id, raw_payload,
               ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY event_time_ts ASC) AS row_num
        FROM kafka_raw_pit_events
        WHERE event_id IS NOT NULL AND event_type IS NOT NULL
    ) WHERE row_num = 1;
END;
