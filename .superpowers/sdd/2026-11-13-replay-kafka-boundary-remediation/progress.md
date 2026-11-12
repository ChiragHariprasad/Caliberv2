# SDD ledger — plan: docs/superpowers/plans/2026-11-13-replay-kafka-boundary-remediation.md

Ruling: The packaged SDD shell helpers cannot execute in this Windows sandbox (`E_ACCESSDENIED`), so this equivalent workspace and ledger are maintained manually — cost if wrong: task bookkeeping is less automated, not implementation behavior.
Pre-flight: Task 1 produces `ReplayEventProcessor.process`; Task 2 consumes it through `ReplayController.set_event_processor`; no incompatible interface found.
