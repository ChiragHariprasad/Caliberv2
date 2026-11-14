/**
 * CALIBRE & SIA Core v3 Formal Type System
 * 
 * Defines TypeScript interfaces matching the formal CALIBRE specifications:
 * - Evidence Event Specification (EE v1.0)
 * - Decision Evidence Contract Specification (DEC v1.0)
 * - Integrity Assessment Specification (IA v1.0)
 * - Admission Log Specification (LOG v1.0)
 */

// ---------------------------------------------------------------------------
// 1. Scoped Integrity Algebra (SIA) Lattice States & Dispositions
// ---------------------------------------------------------------------------

/**
 * Five primary operational views in PULSE.
 */
export type PulseView = 'TRACKSIDE' | 'INTEGRITY_BOARD' | 'SIA_LOGIC_LAB' | 'AGENTS_PIPELINE' | 'REPLAY_AUDIT';

/**
 * The strict 4-state algebraic lattice ordered:
 * DEGRADED < UNKNOWN < SUSPECT < HEALTHY
 */
export type IntegrityState = 'DEGRADED' | 'UNKNOWN' | 'SUSPECT' | 'HEALTHY';

/**
 * Administrative decision disposition.
 * VOIDED is not a fifth lattice state; it is an administrative disposition
 * resulting in an UNKNOWN state with a VOIDED witness, sealed as FINAL.
 */
export type DecisionDisposition = 'NORMAL' | 'VOIDED';

/**
 * Resolution maturity of an integrity decision.
 * - OPEN: Pending evidence slots exist, bounds have not converged.
 * - STATE_RESOLVED: Lower and upper bounds in possible-world envelope converge.
 * - TUPLE_RESOLVED: All roles in contract have received admitted atoms/facts.
 */
export type ResolutionMaturity = 'OPEN' | 'STATE_RESOLVED' | 'TUPLE_RESOLVED';

/**
 * Finality status of a decision revision.
 * - PROVISIONAL: Subject to late evidence, reference updates, or revisions.
 * - FINAL: Sealed into the append-only ledger; further evidence quarantined.
 */
export type FinalityStatus = 'PROVISIONAL' | 'FINAL';

export type DecisionMaturity = 'PROVISIONAL' | 'REVISED' | 'FINAL';

// ---------------------------------------------------------------------------
// 2. Typed Time, Scopes & Origins
// ---------------------------------------------------------------------------

export type TimeClass = 'ABSOLUTE_UTC' | 'SESSION_ELAPSED' | 'LAP_RELATIVE';

export interface TypedTime {
  class: TimeClass;
  value: number; // integer microseconds
  unc: number;   // uncertainty in microseconds
}

export type ScopeClass = 'SESSION' | 'DRIVER_SESSION' | 'DRIVER_LAP' | 'SECTOR' | 'ZONE';

export type Scope = Record<string, string | number>;

export interface OriginClosure {
  provider: string;
  source_origins: string[];
  processing_origins: string[];
  closure: string[];
}

// ---------------------------------------------------------------------------
// 3. Evidence Atoms (EE v1.0)
// ---------------------------------------------------------------------------

export interface EvidenceAtom {
  atom_id: string;
  role_id: string;
  value: number | string | boolean | null;
  unit: string;
  observed_at: string; // ISO-8601 string
  time: TypedTime;
  scope: Scope;
  source_origins: string[];
  processing_origins: string[];
  processor_family_id: string;
  transform_version: string;
  raw_event_ids: string[];
  quality_grade: IntegrityState;
  supersedes?: string | null;
  reference_atom_ids?: string[];
  format_version?: string;
  content_hash?: string;
}

// ---------------------------------------------------------------------------
// 4. Witnesses & Limitations (CR-6)
// ---------------------------------------------------------------------------

export type WitnessSeverity = 'INFO' | 'WARNING' | 'DEFECT';

export interface SIAWitness {
  code: string;
  severity?: WitnessSeverity;
  category?: string;
  role?: string | null;
  detail: string;
  remedial_action?: string | null;
}

// ---------------------------------------------------------------------------
// 5. Decision Contracts (DEC v1.0)
// ---------------------------------------------------------------------------

export interface ContractRoleSpec {
  kind: 'evidence' | 'reference';
  scope_class: ScopeClass;
  time_class_required: TimeClass;
  value_time_class?: string;
  admissible_source_origins?: string[];
  agreement?: {
    metric: string;
    unit?: string;
    tolerance?: number;
  };
  freshness?: {
    soft_age_s?: number;
    hard_age_s?: number;
  };
  slot?: {
    deadline_s?: number;
    allowed_lateness_s?: number;
  };
  corroboration?: {
    mode: 'MANDATORY' | 'INFORMATIONAL';
    min_source_depth?: number;
    min_processing_depth?: number;
  };
}

export interface ContractConstraintSpec {
  id: string;
  kind: 'bounds' | 'diff' | 'ratio' | 'linear' | 'interval' | 'monotonic';
  operands: string[];
  lo?: number;
  hi?: number;
  unit?: string;
  tolerance?: number;
  uncertainty_guard_band?: number;
  description?: string;
}

export interface ContractDefinition {
  contract_id: string;
  version: string;
  epoch: number;
  decision_type: string;
  scope_class: string;
  formula: string;
  role_count: number;
  constraint_count: number;
  definition_hash: string;
  roles?: Record<string, ContractRoleSpec>;
  constraints?: ContractConstraintSpec[];
  fault_model?: {
    diagnosis_budget: number;
    resilience_requirement: number;
    report_k: number;
  };
  limitations?: string[];
}

export interface ContractSummary {
  id: string;
  version?: string;
  epoch?: number;
  decision_type?: string;
  formula?: string;
  scope_class?: string;
}

// ---------------------------------------------------------------------------
// 6. Evaluations, Constraints & Envelopes
// ---------------------------------------------------------------------------

export interface RoleEvaluation {
  role_id?: string;
  atom?: EvidenceAtom;
  atoms?: EvidenceAtom[];
  timeline?: Array<[number, string]>; // [instant, state]
  state?: IntegrityState;
  freshness_status?: string;
  corroboration_depth?: number;
  origin_closure?: string[];
}

export interface ConstraintEvaluation {
  id: string;
  kind?: string;
  operands?: string[];
  satisfied: boolean;
  state?: IntegrityState;
  margin?: number;
  uncertainty?: number;
  within_uncertainty?: boolean;
  detail?: string;
}

export interface SuperpositionEnvelope {
  lower: IntegrityState;
  upper: IntegrityState;
  current_state: IntegrityState;
  resolution_maturity: ResolutionMaturity;
  is_punctual?: boolean;
}

// ---------------------------------------------------------------------------
// 7. Integrity Assessments (IA v1.0)
// ---------------------------------------------------------------------------

export interface SIAAssessment {
  decision_instance_id: string;
  contract: ContractSummary;
  scope: Scope;
  integrity_state: IntegrityState;
  disposition?: DecisionDisposition;
  validity_timeline?: Array<[number, string]>;
  resolution_maturity: ResolutionMaturity;
  finality_status: FinalityStatus;
  decision_maturity?: DecisionMaturity;
  envelope?: SuperpositionEnvelope;
  roles: Record<string, RoleEvaluation>;
  constraints?: Record<string, ConstraintEvaluation> | ConstraintEvaluation[];
  diagnosis?: {
    fault_hypotheses?: string[][];
    budget?: number;
    ambiguous?: boolean;
  };
  resilience?: {
    k_values?: Record<number, boolean>;
    critical_origins?: string[];
  };
  witnesses: SIAWitness[];
  witness_set?: string[];
  primary_binding_witness?: string;
  limitations: string[];
  evaluated_at?: string;
  next_transition_at?: string | null;
  lease_until?: string | null;
  limiting_children?: string[];
  revision_number: number;
  revision_reason?: string;
  knowledge_time?: string;
  verdict_hash: string;
  record_hash: string;
  previous_record_hash?: string;
  evidence_frontier?: string;
}

// ---------------------------------------------------------------------------
// 8. Decision Instances & Registry Metadata
// ---------------------------------------------------------------------------

export interface DecisionInstance {
  instance_id: string;
  contract_id: string;
  scope: Scope;
  opens_at: string;
  auto: boolean;
  sealed: boolean;
  revision_count: number;
  latest_state: IntegrityState | null;
  disposition?: DecisionDisposition;
}

export interface LedgerStats {
  atoms: number;
  facts: number;
  guards: number;
  rejected: number;
  clock: string | null;
  finality_violations: any[];
  contract_history: Record<string, any>;
  [key: string]: any;
}

export interface IntegritySummary {
  overall_state: IntegrityState;
  decision_count: number;
  state_distribution: Record<IntegrityState, number>;
  contract_count: number;
  ledger: Record<string, number>;
  finality_violations: number;
  chain_verified: boolean;
}

export interface HashChainVerificationResult {
  verified: boolean;
  chain_count: number;
  results: Record<string, string>; // instance_id -> "OK" | "FAIL:..."
}

export interface QuarantinedEvidence {
  atom_id?: string;
  event_id?: string;
  decision_instance_id: string;
  quarantined_at?: string;
  reason: string;
  payload?: Record<string, any>;
}

// ---------------------------------------------------------------------------
// 9. Algorithm-Tagged Hash Utilities
// ---------------------------------------------------------------------------

export type HashAlgorithm = 'blake3' | 'sha256' | 'hex';

export interface TaggedHash {
  algorithm: HashAlgorithm;
  hash: string;
  raw: string;
  short: string;
}

export function parseTaggedHash(raw: string | null | undefined): TaggedHash {
  if (!raw) {
    return { algorithm: 'hex', hash: '', raw: '', short: '—' };
  }
  let algorithm: HashAlgorithm = 'hex';
  let hash = raw;

  if (raw.startsWith('blake3:')) {
    algorithm = 'blake3';
    hash = raw.slice(7);
  } else if (raw.startsWith('sha256:')) {
    algorithm = 'sha256';
    hash = raw.slice(7);
  }

  const short = hash.length > 12 ? `${hash.slice(0, 6)}…${hash.slice(-6)}` : hash;
  return { algorithm, hash, raw, short };
}
