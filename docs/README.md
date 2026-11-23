# CALIBRE / PULSE documentation

## Authority and status

This directory is organised around the static engineering audit completed on 22 November 2026. Source code is authoritative for current behaviour. Claims in reports, screenshots, or test output are historical evidence only; they are not a substitute for a fresh runtime verification.

Start here:

1. [Current-system architecture](ARCHITECTURE.md) — the implementation as statically inspected, including known boundaries and non-guarantees.
2. [Engineering audit and findings register](AUDIT.md) — evidence, scores, risks, state machine, and inspection coverage.
3. [Proposed remediation roadmap](ROADMAP.md) — dependency-ordered target architecture and implementation plan. It is not implemented.

Supporting material:

- [Top 10 Report Screenshots](TOP10_REPORT_SCREENSHOTS.md) — curated selection of the 10 must-add UI screens for executive and technical reports.
- [UI Visual Reference & Screenshots (Full 22)](UI_SCREENSHOTS.md) — comprehensive visual catalogue of all 22 operational cockpits, forensic inspection drawers, and epistemic workbenches.
- [Data sourcing assessment](DATA_SOURCING_ASSESSMENT.md) — source capability and governance assumptions; coverage claims require runtime/data validation.
- [Controversy corpus research](F1_CONTROVERSY_CORPUS.md) — research backlog and candidate scenarios, not an implementation conformance record.
- [Decision log](DECISION_LOG.md) and [history](HISTORY.md) — retained historical records. Where they conflict with the three documents above or current source, they are superseded.

## Current terminology

- **SIA Core v3**: `sia_core_v3/sia_core`, the deterministic in-process integrity kernel.
- **CALIBRE core**: `calibre_core`, reusable contracts, evidence archetypes, admission-log and archive utilities.
- **PULSE**: `backend/pulse` and `frontend`, the reference F1 tactical application.
- **Archetypes A1–A5** and **PULSE Agents 01–06** are different systems. The former are intended evidence producers; the latter produce tactical findings and an SIA bridge. They are not interchangeable.
