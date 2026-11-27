"""Integrity API routes: /api/integrity/*

Exposes the SIA Core v3 integrity engine through RESTful endpoints for
querying verdicts, decision history, bitemporal queries, chain verification,
and contract inspection.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from pulse.api.security import require_control_api_key

logger = logging.getLogger("pulse.integrity.router")

integrity_router = APIRouter(prefix="/api/integrity", tags=["SIA Integrity Engine"])


def _get_agent():
    """Lazy import to avoid circular dependencies."""
    from pulse.integrity.agent import IntegrityAgent
    from pulse.state.store import get_state_store
    store = get_state_store()
    agent = store.agents.get("agent-06-integrity")
    if agent is None or not isinstance(agent, IntegrityAgent):
        agent = IntegrityAgent()
        store.register_agent(agent)
    return agent


# ---------------------------------------------------------------------------
# Summary / health
# ---------------------------------------------------------------------------

@integrity_router.get("/summary")
async def get_integrity_summary() -> dict[str, Any]:
    """High-level integrity summary across all tracked decisions."""
    agent = _get_agent()
    return agent.get_summary()


@integrity_router.get("/ledger")
async def get_ledger_stats() -> dict[str, Any]:
    """Ledger admission statistics: atoms, facts, guards, rejections."""
    agent = _get_agent()
    return agent.get_ledger_stats()


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

@integrity_router.get("/contracts")
async def get_contracts() -> list[dict[str, Any]]:
    """List all registered Decision Evidence Contracts."""
    agent = _get_agent()
    return agent.get_contracts()


# ---------------------------------------------------------------------------
# Decisions (instances)
# ---------------------------------------------------------------------------

@integrity_router.get("/decisions")
async def get_decisions() -> list[dict[str, Any]]:
    """List all tracked decision instances with latest state."""
    agent = _get_agent()
    return agent.get_decisions()


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------

@integrity_router.get("/verdicts")
async def get_all_verdicts() -> list[dict[str, Any]]:
    """Latest verdict for every tracked decision instance."""
    agent = _get_agent()
    return agent.get_all_verdicts()


@integrity_router.get("/verdicts/{instance_id}")
async def get_verdict(instance_id: str) -> dict[str, Any]:
    """Latest verdict for a specific decision instance."""
    agent = _get_agent()
    result = agent.get_verdict(instance_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Decision instance not found: {instance_id}")
    return result


@integrity_router.get("/verdicts/{instance_id}/history")
async def get_verdict_history(instance_id: str) -> list[dict[str, Any]]:
    """Full revision chain for a decision instance (hash-chained, append-only)."""
    agent = _get_agent()
    history = agent.get_verdict_history(instance_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"No history for decision: {instance_id}")
    return history


@integrity_router.get("/verdicts/{instance_id}/explain")
async def explain_verdict(instance_id: str) -> dict[str, str]:
    """Template-based deterministic explanation of the latest verdict."""
    agent = _get_agent()
    text = agent.explain_verdict(instance_id)
    if text is None:
        raise HTTPException(status_code=404, detail=f"Decision instance not found: {instance_id}")
    return {"instance_id": instance_id, "explanation": text}


@integrity_router.get("/verdicts/{instance_id}/as-of")
async def get_verdict_as_of(
    instance_id: str,
    knowledge_time: str = Query(..., description="ISO-8601 timestamp: what did we know at this time?"),
) -> dict[str, Any]:
    """Bitemporal query: what was concluded about this decision as known at the given time?"""
    agent = _get_agent()
    result = agent.get_verdict_as_of(instance_id, knowledge_time)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No verdict for {instance_id} as of {knowledge_time}",
        )
    return result


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------

@integrity_router.get("/verify")
async def verify_chains() -> dict[str, Any]:
    """Verify hash-chain integrity for all decision instances.

    Returns OK for each chain if no tampering is detected.
    """
    agent = _get_agent()
    results = agent.verify_chains()
    all_ok = all(v == "OK" for v in results.values())
    return {
        "verified": all_ok,
        "chain_count": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Finality violations (post-finality evidence quarantine)
# ---------------------------------------------------------------------------

@integrity_router.get("/quarantine")
async def get_quarantined() -> list[dict[str, Any]]:
    """Evidence quarantined pre-admission or flagged post-finality."""
    agent = _get_agent()
    return agent.engine.quarantined_items or agent.engine.finality_violations


class LabScenarioRequest(BaseModel):
    scenario_id: str


@integrity_router.post("/lab-scenario", dependencies=[Depends(require_control_api_key)])
async def execute_lab_scenario(req: LabScenarioRequest) -> dict[str, Any]:
    """Run an isolated LAB fault-injection drill inside SIA Core v3 without mutating active session state."""
    agent = _get_agent()
    return agent.run_lab_scenario(req.scenario_id)

