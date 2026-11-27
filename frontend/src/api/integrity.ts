/**
 * CALIBRE & SIA Core v3 Integrity API Client
 * 
 * Provides typed access to all 11 /api/integrity/* endpoints exposed by
 * pulse.integrity.router in the backend.
 */

import type {
  ContractDefinition,
  DecisionInstance,
  HashChainVerificationResult,
  IntegritySummary,
  LedgerStats,
  QuarantinedEvidence,
  SIAAssessment,
} from '../types/calibre';

const API_ROOT = '/api/integrity';

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_ROOT}${path}`, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/**
 * High-level integrity summary across all tracked decision instances.
 * Endpoint: GET /api/integrity/summary
 */
export async function fetchIntegritySummary(): Promise<IntegritySummary | null> {
  return await fetchJson<IntegritySummary>('/summary');
}

/**
 * Ledger admission statistics: counts of atoms, facts, guards, clock instant.
 * Endpoint: GET /api/integrity/ledger
 */
export async function fetchLedgerStats(): Promise<LedgerStats | null> {
  return await fetchJson<LedgerStats>('/ledger');
}

/**
 * List all registered Decision Evidence Contracts with formula AST and constraints.
 * Endpoint: GET /api/integrity/contracts
 */
export async function fetchContracts(): Promise<ContractDefinition[]> {
  const res = await fetchJson<ContractDefinition[]>('/contracts');
  return res ?? [];
}

/**
 * List all tracked decision instances with latest state, scope, and revision count.
 * Endpoint: GET /api/integrity/decisions
 */
export async function fetchDecisions(): Promise<DecisionInstance[]> {
  const res = await fetchJson<DecisionInstance[]>('/decisions');
  return res ?? [];
}

/**
 * Latest verdict for every tracked decision instance.
 * Endpoint: GET /api/integrity/verdicts
 */
export async function fetchAllVerdicts(): Promise<SIAAssessment[]> {
  const res = await fetchJson<SIAAssessment[]>('/verdicts');
  return res ?? [];
}

/**
 * Latest verdict for a specific decision instance.
 * Endpoint: GET /api/integrity/verdicts/{instance_id}
 */
export async function fetchVerdict(instanceId: string): Promise<SIAAssessment | null> {
  if (!instanceId) return null;
  return await fetchJson<SIAAssessment>(`/verdicts/${encodeURIComponent(instanceId)}`);
}

/**
 * Full append-only revision history (hash-chain) for a decision instance.
 * Endpoint: GET /api/integrity/verdicts/{instance_id}/history
 */
export async function fetchVerdictHistory(instanceId: string): Promise<SIAAssessment[]> {
  if (!instanceId) return [];
  const res = await fetchJson<SIAAssessment[]>(`/verdicts/${encodeURIComponent(instanceId)}/history`);
  return res ?? [];
}

/**
 * Deterministic template-based natural language explanation of the latest verdict.
 * Endpoint: GET /api/integrity/verdicts/{instance_id}/explain
 */
export async function fetchVerdictExplanation(instanceId: string): Promise<string | null> {
  if (!instanceId) return null;
  const res = await fetchJson<{ instance_id: string; explanation: string }>(
    `/verdicts/${encodeURIComponent(instanceId)}/explain`,
  );
  return res?.explanation ?? null;
}

/**
 * Bitemporal "As-Of" query: what was concluded about this decision as known at knowledge instant K?
 * Endpoint: GET /api/integrity/verdicts/{instance_id}/as-of?knowledge_time=...
 */
export async function fetchVerdictAsOf(
  instanceId: string,
  knowledgeTimeIso: string,
): Promise<SIAAssessment | null> {
  if (!instanceId || !knowledgeTimeIso) return null;
  return await fetchJson<SIAAssessment>(
    `/verdicts/${encodeURIComponent(instanceId)}/as-of?knowledge_time=${encodeURIComponent(knowledgeTimeIso)}`,
  );
}

/**
 * Cryptographic hash-chain verification for all active decision instances.
 * Returns verified status and per-instance results ('OK' or failure detail).
 * Endpoint: GET /api/integrity/verify
 */
export async function verifyHashChains(): Promise<HashChainVerificationResult | null> {
  return await fetchJson<HashChainVerificationResult>('/verify');
}

/**
 * Retrieve evidence items that arrived after a decision was sealed FINAL (quarantined).
 * Endpoint: GET /api/integrity/quarantine
 */
export async function fetchQuarantinedEvidence(): Promise<QuarantinedEvidence[]> {
  const res = await fetchJson<QuarantinedEvidence[]>('/quarantine');
  return res ?? [];
}

export interface LabScenarioResponse {
  scenario_id: string;
  regime: string;
  verdict: SIAAssessment;
  explanation: string;
}

export async function runLabScenario(scenarioId: string): Promise<LabScenarioResponse | null> {
  try {
    const response = await fetch(`${API_ROOT}/lab-scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId }),
    });
    if (!response.ok) return null;
    return (await response.json()) as LabScenarioResponse;
  } catch {
    return null;
  }
}

