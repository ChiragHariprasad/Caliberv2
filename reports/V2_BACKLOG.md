# PULSE V2 — Architectural Roadmap & Feature Backlog

**Document Version:** 2.0-DRAFT  
**Date:** 2026-11-05  
**Scope:** Post-V1 Architecture Expansions, Advanced Modeling, and Enterprise Features  

---

## 1. High-Frequency Real-Time Telemetry & GPS Ingest

### EPIC-1: Direct Telemetry Ingestion Pipeline
- **CAN-bus Stream Connector**: Ingest high-frequency (10Hz–50Hz) CAN-bus telemetry packets (throttle, brake pressure, RPM, gear, steering angle, DRS activation) via gRPC/Kafka bridge when authorized live data feeds are active.
- **Micro-Sector Delta Smoothing**: Implement Kalman filtering and cubic spline interpolation over micro-sector times to project continuous car movement along track centerlines rather than discrete sector updates.
- **Millimeter-Accurate Geodetic Track Mapping**: Upgrade circuit vector representation from 2D normalized planar coordinate systems (`LOCAL_NORMALIZED_1000`) to geodetically referenced WGS-84 UTM coordinates with elevation profiles for camber and elevation-change physics models.

---

## 2. Distributed Stream Processing & Fault-Tolerance Scale-Out

### EPIC-2: Enterprise Flink & Kafka Scaling
- **RocksDB State Backend**: Transition Apache Flink normalizer from in-memory state backend to incremental RocksDB checkpoints on distributed storage (S3/MinIO/Ceph) for long-duration multi-day endurance racing.
- **Dynamic Partition Key Rebalancing**: Implement session-aware dynamic partitioning on Kafka topics to distribute 20+ car streams across multi-partition brokers with zero out-of-order latency.
- **Automated Replay Resumption Checkpoints**: Store ReplayController cursor checkpoints in Redis/PostgreSQL so replaying long historical sessions can be resumed across backend server restarts.

---

## 3. Advanced Predictive Intelligence & Machine Learning

### EPIC-3: Deep Learning Consequence Modeling
- **Non-Linear Tyre Degradation Forecaster**: Replace parametric degradation slopes with LSTM/Transformer models trained on multi-season historical track temperatures, track evolution, and compound wear curves.
- **Pit Window Undercut/Overcut Probability Matrix**: Multi-driver Monte Carlo simulation predicting probability of clean air re-entry across all 20 cars upon pit exit under green, VSC, and Safety Car regimes.
- **Driver Radio NLP & Sentiment Synthesis**: Ingest team radio audio transcripts via Whisper/Groq LLM to detect driver frustration, tyre complaints, or tactical intentions and feed into the Vehicle Response agent.

---

## 4. Frontend & User Experience Enhancements

### EPIC-4: Immersive Race Operations UI
- **3D WebGL Circuit Viewer**: Optional 3D track visualization using Three.js/deck.gl with camera chase modes, sector elevation contours, and dynamic weather particle effects.
- **Custom Strategy Sandbox**: Interactive strategy builder allowing strategists to simulate hypothetical "What-if" pit stops and overlay projected gap evolution against live competitors.
- **Voice-Activated Race Engineer Assistant**: Conversational audio interface allowing race engineers to verbally ask "What is our pit delta to Hamilton if VSC ends now?" and receive instant synthesized tactical briefings.
- **Multi-Monitor Broadcast Layouts**: Pop-out panels and multi-window dashboard configurations tailored for dual- and triple-monitor engineering workstations.

---

## 5. Enterprise Security & Integration

### EPIC-5: Multi-Tenant Enterprise Operations
- **Role-Based Access Control (RBAC)**: Team-specific strategy views with cryptographically isolated tenant workspaces ensuring Team A cannot access Team B's private telemetry or predictive forecasts.
- **FIA Stewards Regulatory Archive**: Searchable vector database indexing 10+ years of FIA International Sporting Code precedents and steward decisions for automated incident assessment comparison.
- **OpenTelemetry & Distributed Tracing**: Native OpenTelemetry instrumentation exporting traces to Grafana Tempo/Jaeger for sub-millisecond pipeline latency profiling.

