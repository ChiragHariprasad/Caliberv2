# Replay and Kafka Boundary Design

## Intent

Make the operational PULSE replay path truthful about its execution profile: each replayed event must traverse one canonical processing path, replay state must be rebuilt from data rather than a UI cursor, and Kafka failures must not be silently treated as successful publication.

## Findings informing the design

- `pulse.stream.kafka_io` supplies the desired Confluent Kafka configuration but is not used by the live app, which still instantiates `aiokafka` clients.
- In `KAFKA` mode the app publishes raw events but registers no raw normalizer handler; it relies on a separately deployed Flink job that the lifespan does not start or verify.
- `ReplayController.seek()` resets the `StateStore` and calls only `record_canonical_event`. It bypasses normalization, agents, finding fusion, and integrity evaluation.
- The historical acquisition script combines downloaded data with hard-coded event/weather records described as official. Those derived records must not obtain an unqualified production evidence claim.

## Approaches considered

1. Keep Flink as the only raw-to-normalized execution path. This would require reliable Flink deployment, checkpoint/offset reset coordination, and a per-seek run namespace before a seek can be correct. That infrastructure is not currently connected.
2. Add a dedicated replay-only local path alongside Kafka. It risks two competing event semantics and Kafka replay duplicates.
3. Define a single in-process processing callback used by MEMORY/SIMULATOR replay and replay reconstruction, while retaining Kafka as a transport adapter. Kafka mode must explicitly verify its downstream normalizer rather than pretending the local replay path has run. This is the selected incremental repair because it fixes the currently broken execution path without claiming end-to-end Kafka semantics that have not been wired.

## Design

- `ReplayController` owns a `process_event` callback. Normal playback and seeking both invoke it for each envelope. The callback is responsible for normalization and downstream processing; the controller no longer reconstructs only the display store.
- The callback supports `publish=False` reconstruction. Rebuilding state may run all deterministic handlers but must not emit another raw/Kafka record.
- The application builds one callback from its normalizer, agents, fusion, integrity agent, and store and supplies it to the controller. In non-Kafka modes it is also the raw-bus subscriber. In Kafka mode the local callback is used only for explicit reconstruction; the app reports a failure if its independently required streaming normalizer is absent rather than falling back silently.
- The existing Kafka layers are not both made authoritative. The live `KafkaBroker` remains the active adapter until the Confluent client is integrated end-to-end. Its delivery failures must propagate to callers instead of being logged and ignored. The unconnected `kafka_io` implementation is retained as a future adapter and marked as such in the audit rather than falsely advertised as live.
- Historic generated records are explicitly labelled `LAB` unless a captured source artifact and provenance metadata justify a higher data regime.

## Constraints

- Preserve PULSE topic names and API contracts.
- Do not manufacture data or use a new dependency.
- A seek is successful only after the deterministic callback has processed every prior record and the store and agents have been reset for the replay run.
