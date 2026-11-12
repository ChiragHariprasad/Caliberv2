# CALIBRE Kafka Architecture Decision Record (ADR)

## Decision 1: 11 Partitions for Driver-Scoped Topics
- **Context:** Formula 1 grid consists of 20 to 22 cars (10-11 teams).
- **Decision:** Use 11 partitions as the primary driver tier (`CALIBRE_DRIVER_PARTITIONS=11`), with an override option for 22 partitions (`--driver-partitions 22`).
- **Rationale:** With dense driver slot assignment, 22 drivers map to 11 partitions with exactly 2 drivers per partition (e.g. 2 drivers per team), preventing skew while avoiding hash-partitioner collision hotspots.

## Decision 2: Multi-Broker KRaft Cluster Topology
- **Context:** Previous environment ran a single Confluent broker (7.7.0) with ZooKeeper.
- **Decision:** Migrate to a 3-broker KRaft cluster (`kafka-1`, `kafka-2`, `kafka-3`) with `CLUSTER_ID="MkU3OEVBNTcwNTJENDM2Qk"`, `replication.factor=3`, `min.insync.replicas=2`, and `unclean.leader.election.enable=false`.
- **Ports:**
  - Host access: `localhost:19092`, `localhost:19093`, `localhost:19094`
  - Container network: `kafka-1:29092`, `kafka-2:29092`, `kafka-3:29092`
  - Kafka UI: `http://localhost:8080`

## Decision 3: Centralized Kafka IO Architecture
- **Context:** scattered producer/consumer instantiations prevent unified configuration and transactional guarantees.
- **Decision:** Centralize all Kafka client construction, configuration, publishing, DLQ management, and consumer lifecycle inside `backend/pulse/stream/kafka_io.py`.

## Decision 4: Topic Catalogue and Backward Compatibility
- **Context:** The prompt specifies `calibre.*` topic catalogue, while existing integration tests utilize `pulse.*`.
- **Decision:** The topic management catalogue in `kafka_io.py` and `topics.py` declares the full `calibre.*` catalogue with explicit tiers (`DRIVER` = 11, `OPS` = 3, `SINGLE` = 1), while maintaining `pulse.*` aliases so existing test suites and streaming dashboards run without regression.

## Decision 5: Client Migration to `confluent-kafka`
- **Context:** `aiokafka` does not support Kafka transactional producers (`init_transactions`, `begin_transaction`, `send_offsets_to_transaction`, `commit_transaction`) or idempotence fencing required for EOS.
- **Decision:** Standardize on `confluent-kafka>=2.5.0` with asynchronous/threaded wrappers for FastAPI and pytest integration.

