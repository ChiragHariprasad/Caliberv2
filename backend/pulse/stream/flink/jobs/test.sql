SET 'execution.runtime-mode' = 'streaming';
SET 'pipeline.name' = 'pulse-json-test';

CREATE TABLE raw_test (
    raw_payload STRING
) WITH (
    'connector' = 'datagen',
    'rows-per-second' = '1',
    'fields.raw_payload.kind' = 'sequence',
    'fields.raw_payload.start' = '1',
    'fields.raw_payload.end' = '10'
);

CREATE TABLE sink_test (
    val STRING
) WITH (
    'connector' = 'blackhole'
);

INSERT INTO sink_test
SELECT raw_payload FROM raw_test;

