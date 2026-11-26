import React, { useEffect, useMemo, useState } from 'react';
import type { IntegrityState, SIAAssessment } from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';
import { CheckCircleIcon, ShieldIcon, AlertTriangleIcon, InfoIcon } from '../icons';

interface StateAlgebraTreeProps {
  decisionId?: string;
  contractId?: string;
  verdict?: SIAAssessment | null;
  className?: string;
}

const ORDERED_STATES: Array<{ state: IntegrityState; rank: number; color: string; label: string }> = [
  { state: 'DEGRADED', rank: 0, color: '#ff4d4f', label: '0 — DEGRADED (Breach / Corrupted Witness)' },
  { state: 'UNKNOWN', rank: 1, color: '#64748b', label: '1 — UNKNOWN (Unobserved / Pending Tick)' },
  { state: 'SUSPECT', rank: 2, color: '#ffd000', label: '2 — SUSPECT (Anomaly / Uncorroborated)' },
  { state: 'HEALTHY', rank: 3, color: '#00ff88', label: '3 — HEALTHY (All Constraints Verified)' },
];

const DEFAULT_ROLE_LABELS: Record<string, { roleA: [string, string]; roleB: [string, string]; roleC: [string, string]; roleD: [string, string] }> = {
  pit_speed: {
    roleA: ['timing_speed', 'Timing transponder pit-lane speed measurement'],
    roleB: ['vehicle_speed', 'ECU CAN-bus wheelspeed and engine RPM sensor'],
    roleC: ['configured_distance', 'Calibrated physical distance between timing loops'],
    roleD: ['calibration_bias', 'Master telemetry clock drift and bias reference'],
  },
  lap_time: {
    roleA: ['lap_record', 'Official lap completion timing passage'],
    roleB: ['lap_start', 'Session elapsed lap start reference fact'],
    roleC: ['session_t0', 'Session genesis anchor timestamp'],
    roleD: ['feed_guard', 'Upstream origin liveliness and stall monitor'],
  },
  sector_time: {
    roleA: ['sector_record', 'Sector boundary crossing elapsed interval'],
    roleB: ['sector_gate', 'Circuit timing gate reference geometry'],
    roleC: ['session_t0', 'Session genesis anchor timestamp'],
    roleD: ['feed_guard', 'Upstream origin liveliness and stall monitor'],
  },
  driver_position: {
    roleA: ['position_report', 'Per-car race classification and gap observation'],
    roleB: ['lap_anchor', 'Current driver lap counter alignment'],
    roleC: ['session_t0', 'Session genesis anchor timestamp'],
    roleD: ['feed_guard', 'Upstream origin liveliness and stall monitor'],
  },
  weather_observation: {
    roleA: ['weather_reading', 'Track and ambient temperature observation'],
    roleB: ['precipitation_sensor', 'Surface moisture and rain risk channel'],
    roleC: ['session_t0', 'Session genesis anchor timestamp'],
    roleD: ['feed_guard', 'Upstream origin liveliness and stall monitor'],
  },
};

export const StateAlgebraTree: React.FC<StateAlgebraTreeProps> = ({
  decisionId = '',
  contractId = 'lap_time',
  verdict,
  className = '',
}) => {
  const [operator, setOperator] = useState<'MEET' | 'JOIN' | 'K_OF_N'>('MEET');
  const [kThreshold, setKThreshold] = useState<number>(2);

  const roleLabels = useMemo(() => {
    const defaults = DEFAULT_ROLE_LABELS[contractId] || DEFAULT_ROLE_LABELS.lap_time;
    const roleKeys = verdict?.roles ? Object.keys(verdict.roles) : [];
    return {
      roleA: [roleKeys[0] || defaults.roleA[0], defaults.roleA[1]],
      roleB: [roleKeys[1] || defaults.roleB[0], defaults.roleB[1]],
      roleC: [roleKeys[2] || defaults.roleC[0], defaults.roleC[1]],
      roleD: [roleKeys[3] || defaults.roleD[0], defaults.roleD[1]],
    };
  }, [contractId, verdict?.roles]);

  const [inputStates, setInputStates] = useState<{
    roleA: IntegrityState;
    roleB: IntegrityState;
    roleC: IntegrityState;
    roleD: IntegrityState;
  }>({
    roleA: 'UNKNOWN',
    roleB: 'UNKNOWN',
    roleC: 'UNKNOWN',
    roleD: 'UNKNOWN',
  });

  useEffect(() => {
    if (!verdict?.roles) return;
    const roleVals = Object.values(verdict.roles).map((r: any) => {
      const tl = Array.isArray(r?.timeline) ? r.timeline : [];
      const last = tl[tl.length - 1];
      return (Array.isArray(last) ? last[1] : last?.state || (r?.has_evidence ? verdict.integrity_state : 'UNKNOWN')) as IntegrityState;
    });
    setInputStates({
      roleA: roleVals[0] || verdict.integrity_state || 'UNKNOWN',
      roleB: roleVals[1] || verdict.integrity_state || 'UNKNOWN',
      roleC: roleVals[2] || 'HEALTHY',
      roleD: roleVals[3] || 'HEALTHY',
    });
  }, [verdict?.decision_instance_id, verdict?.revision_number]);

  const getRank = (st: IntegrityState): number => {
    switch (st) {
      case 'DEGRADED':
        return 0;
      case 'UNKNOWN':
        return 1;
      case 'SUSPECT':
        return 2;
      case 'HEALTHY':
        return 3;
      default:
        return 1;
    }
  };

  const getStateFromRank = (rank: number): IntegrityState => {
    if (rank <= 0) return 'DEGRADED';
    if (rank === 1) return 'UNKNOWN';
    if (rank === 2) return 'SUSPECT';
    return 'HEALTHY';
  };

  // Compute evaluation result deterministically
  const evaluationResult = useMemo(() => {
    const ranks = [
      getRank(inputStates.roleA),
      getRank(inputStates.roleB),
      getRank(inputStates.roleC),
      getRank(inputStates.roleD),
    ];

    if (operator === 'MEET') {
      const minRank = Math.min(...ranks);
      const verdictState = getStateFromRank(minRank);
      return {
        verdictState,
        verdictRank: minRank,
        operationName: 'AND / Meet (∧)',
        ruleApplied: 'Lattice Meet: min(Rank(A), Rank(B), Rank(C), Rank(D))',
        trace: `min(${ranks.join(', ')}) = ${minRank} → ${verdictState}`,
        explanation:
          'In a Meet / AND evaluation, the weakest integrity evidence limits the whole contract. The presence of lower-rank evidence immediately caps the verdict.',
      };
    }

    if (operator === 'JOIN') {
      const maxRank = Math.max(...ranks);
      const verdictState = getStateFromRank(maxRank);
      return {
        verdictState,
        verdictRank: maxRank,
        operationName: 'OR / Join (∨)',
        ruleApplied: 'Lattice Join: max(Rank(A), Rank(B), Rank(C), Rank(D))',
        trace: `max(${ranks.join(', ')}) = ${maxRank} → ${verdictState}`,
        explanation:
          'In a Join / OR evaluation, any high-integrity corroborating witness promotes the decision to the highest observed evidence tier.',
      };
    }

    // K-OF-N (Order statistic)
    const sortedRanks = [...ranks].sort((a, b) => b - a);
    const selectedRank = sortedRanks[Math.min(sortedRanks.length - 1, Math.max(0, kThreshold - 1))];
    const verdictState = getStateFromRank(selectedRank);
    return {
      verdictState,
      verdictRank: selectedRank,
      operationName: `${kThreshold}-of-4 Order Statistic`,
      ruleApplied: `${kThreshold}-of-4 resilient consensus threshold`,
      trace: `sorted(${sortedRanks.join(', ')}) → Rank[${kThreshold - 1}] = ${selectedRank} → ${verdictState}`,
      explanation: `Requires at least ${kThreshold} independent inputs to agree on or exceed this integrity rank to promote the evaluation.`,
    };
  }, [operator, inputStates, kThreshold]);

  const updateRoleState = (roleKey: 'roleA' | 'roleB' | 'roleC' | 'roleD', newState: IntegrityState) => {
    setInputStates((prev) => ({ ...prev, [roleKey]: newState }));
  };

  return (
    <div className={`evaluator-workspace ${className}`}>
      {/* 1. Top Section: Four-State Total Order Hierarchy */}
      <section className="evaluator-top-section">
        <div className="section-title-wrap">
          <div className="title-left">
            <span className="eyebrow-accent">TOTAL ORDER HIERARCHY</span>
            <h2 className="workspace-section-title">Deterministic SIA State Algebra</h2>
          </div>
          <div className="title-right">
            <span className="order-rule-badge font-mono">
              0 — DEGRADED &lt; 1 — UNKNOWN &lt; 2 — SUSPECT &lt; 3 — HEALTHY
            </span>
          </div>
        </div>

        {/* 4 Distinct Rank Progression Cards */}
        <div className="algebra-ranks-grid">
          {ORDERED_STATES.map((item) => (
            <div key={item.state} className="rank-hierarchy-card" style={{ borderTopColor: item.color }}>
              <div className="rank-num-badge">RANK {item.rank}</div>
              <strong className="rank-title" style={{ color: item.color }}>
                {item.state}
              </strong>
              <p className="rank-desc">{item.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 2. Middle Section: Operator Selector Bar */}
      <section className="evaluator-operator-section">
        <div className="operator-bar">
          <span className="operator-bar-label">SELECT ALGEBRAIC OPERATION:</span>
          <div className="operator-buttons-group">
            <button
              type="button"
              className={`op-btn ${operator === 'MEET' ? 'is-active-op' : ''}`}
              onClick={() => setOperator('MEET')}
            >
              <strong>AND / Meet (&and;)</strong>
              <span className="op-sub">Weakest link limits &bull; min(ranks)</span>
            </button>
            <button
              type="button"
              className={`op-btn ${operator === 'JOIN' ? 'is-active-op' : ''}`}
              onClick={() => setOperator('JOIN')}
            >
              <strong>OR / Join (&or;)</strong>
              <span className="op-sub">Strongest corroborator &bull; max(ranks)</span>
            </button>
            <button
              type="button"
              className={`op-btn ${operator === 'K_OF_N' ? 'is-active-op' : ''}`}
              onClick={() => setOperator('K_OF_N')}
            >
              <strong>k-of-n Consensus</strong>
              <span className="op-sub">Order statistic voting</span>
            </button>
          </div>

          {operator === 'K_OF_N' && (
            <div className="k-threshold-picker">
              <span className="k-picker-label">k THRESHOLD:</span>
              {[1, 2, 3, 4].map((k) => (
                <button
                  key={k}
                  type="button"
                  className={`k-btn ${kThreshold === k ? 'is-selected-k' : ''}`}
                  onClick={() => setKThreshold(k)}
                >
                  {k}-of-4
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* 3. Input Roles Section: 4 Equal Sized Panels */}
      <section className="evaluator-inputs-section">
        <div className="section-title-wrap">
          <div className="title-left">
            <span className="eyebrow-accent">INPUT EVIDENCE ROLES</span>
            <h3 className="workspace-section-title">Participating Evidence Role States</h3>
          </div>
          <span className="text-xs text-slate-400">Click any rank button to change input state</span>
        </div>

        <div className="input-roles-grid">
          {/* Role A */}
          <div className="input-role-panel">
            <div className="role-panel-header">
              <div className="role-header-left">
                <span className="role-id font-mono">ROLE A</span>
                <strong className="role-name">{roleLabels.roleA[0]}</strong>
              </div>
              <StateBadge state={inputStates.roleA} size="sm" />
            </div>
            <p className="role-desc">{roleLabels.roleA[1]}</p>
            <div className="role-rank-indicator">
              <span>Current Rank: </span>
              <strong className="font-mono text-cyan-400">Rank {getRank(inputStates.roleA)}</strong>
            </div>
            <div className="role-selectors-row">
              {(['DEGRADED', 'UNKNOWN', 'SUSPECT', 'HEALTHY'] as IntegrityState[]).map((st) => (
                <button
                  key={st}
                  type="button"
                  className={`role-select-chip chip--${st.toLowerCase()} ${inputStates.roleA === st ? 'is-active' : ''}`}
                  onClick={() => updateRoleState('roleA', st)}
                >
                  {st.slice(0, 3)}
                </button>
              ))}
            </div>
          </div>

          {/* Role B */}
          <div className="input-role-panel">
            <div className="role-panel-header">
              <div className="role-header-left">
                <span className="role-id font-mono">ROLE B</span>
                <strong className="role-name">{roleLabels.roleB[0]}</strong>
              </div>
              <StateBadge state={inputStates.roleB} size="sm" />
            </div>
            <p className="role-desc">{roleLabels.roleB[1]}</p>
            <div className="role-rank-indicator">
              <span>Current Rank: </span>
              <strong className="font-mono text-cyan-400">Rank {getRank(inputStates.roleB)}</strong>
            </div>
            <div className="role-selectors-row">
              {(['DEGRADED', 'UNKNOWN', 'SUSPECT', 'HEALTHY'] as IntegrityState[]).map((st) => (
                <button
                  key={st}
                  type="button"
                  className={`role-select-chip chip--${st.toLowerCase()} ${inputStates.roleB === st ? 'is-active' : ''}`}
                  onClick={() => updateRoleState('roleB', st)}
                >
                  {st.slice(0, 3)}
                </button>
              ))}
            </div>
          </div>

          {/* Role C */}
          <div className="input-role-panel">
            <div className="role-panel-header">
              <div className="role-header-left">
                <span className="role-id font-mono">ROLE C</span>
                <strong className="role-name">{roleLabels.roleC[0]}</strong>
              </div>
              <StateBadge state={inputStates.roleC} size="sm" />
            </div>
            <p className="role-desc">{roleLabels.roleC[1]}</p>
            <div className="role-rank-indicator">
              <span>Current Rank: </span>
              <strong className="font-mono text-cyan-400">Rank {getRank(inputStates.roleC)}</strong>
            </div>
            <div className="role-selectors-row">
              {(['DEGRADED', 'UNKNOWN', 'SUSPECT', 'HEALTHY'] as IntegrityState[]).map((st) => (
                <button
                  key={st}
                  type="button"
                  className={`role-select-chip chip--${st.toLowerCase()} ${inputStates.roleC === st ? 'is-active' : ''}`}
                  onClick={() => updateRoleState('roleC', st)}
                >
                  {st.slice(0, 3)}
                </button>
              ))}
            </div>
          </div>

          {/* Role D */}
          <div className="input-role-panel">
            <div className="role-panel-header">
              <div className="role-header-left">
                <span className="role-id font-mono">ROLE D</span>
                <strong className="role-name">{roleLabels.roleD[0]}</strong>
              </div>
              <StateBadge state={inputStates.roleD} size="sm" />
            </div>
            <p className="role-desc">{roleLabels.roleD[1]}</p>
            <div className="role-rank-indicator">
              <span>Current Rank: </span>
              <strong className="font-mono text-cyan-400">Rank {getRank(inputStates.roleD)}</strong>
            </div>
            <div className="role-selectors-row">
              {(['DEGRADED', 'UNKNOWN', 'SUSPECT', 'HEALTHY'] as IntegrityState[]).map((st) => (
                <button
                  key={st}
                  type="button"
                  className={`role-select-chip chip--${st.toLowerCase()} ${inputStates.roleD === st ? 'is-active' : ''}`}
                  onClick={() => updateRoleState('roleD', st)}
                >
                  {st.slice(0, 3)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* 4. Bottom Section: Prominent Evaluation Result */}
      <section className="evaluator-result-section">
        <div className="result-container-card">
          <div className="result-card-header">
            <div className="result-header-left">
              <span className="result-label">DETERMINISTIC EVALUATION OUTCOME</span>
              <h3 className="result-operation-name">{evaluationResult.operationName}</h3>
            </div>
            <div className="result-verdict-large">
              <span className="result-verdict-label">FINAL VERDICT:</span>
              <StateBadge state={evaluationResult.verdictState} size="lg" />
            </div>
          </div>

          <div className="result-card-body">
            <div className="trace-box">
              <span className="trace-label">EVALUATION REDUCTION TRACE:</span>
              <code className="trace-code font-mono">{evaluationResult.trace}</code>
            </div>

            <div className="rule-box">
              <span className="rule-label">APPLIED ALGEBRAIC RULE:</span>
              <strong className="rule-name">{evaluationResult.ruleApplied}</strong>
              <p className="rule-explanation">{evaluationResult.explanation}</p>
            </div>
          </div>

          <div className="result-card-footer">
            <span className="formal-soundness-badge">
              <ShieldIcon size={13} className="inline mr-1 text-emerald-400" />
              SIA Core v3 Deterministic Theorem 1 (Monotonic Lattice Soundness Guaranteed)
            </span>
          </div>
        </div>
      </section>
    </div>
  );
};
