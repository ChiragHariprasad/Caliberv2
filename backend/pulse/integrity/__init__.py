"""PULSE Integrity Layer: SIA Core v3 integration.

Bridges the PULSE streaming pipeline (EventEnvelopes, Findings, Assessments)
with the deterministic SIA Core v3 integrity engine (atoms, facts, contracts,
hash-chained verdicts).

Architecture:
  - bridge.py      : translates PULSE Pydantic models <-> SIA content-addressed domain objects
  - contracts.py   : default F1 Decision Evidence Contracts for each decision type
  - agent.py       : IntegrityAgent (Agent 6) - subscribes to normalised topics, feeds the engine
  - router.py      : /api/integrity/* API endpoints for querying verdicts, history, chain verification
"""
