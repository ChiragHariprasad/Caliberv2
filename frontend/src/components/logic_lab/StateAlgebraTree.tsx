import React, { useState } from 'react';
import type { IntegrityState } from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';

const LATTICE_VALUES: Record<IntegrityState, number> = {
  DEGRADED: 0,
  UNKNOWN: 1,
  SUSPECT: 2,
  HEALTHY: 3,
};

const VALUE_TO_STATE: IntegrityState[] = ['DEGRADED', 'UNKNOWN', 'SUSPECT', 'HEALTHY'];

export const StateAlgebraTree: React.FC = () => {
  const [operator, setOperator] = useState<'MEET_AND' | 'JOIN_OR' | 'K_OF_N'>('MEET_AND');
  const [inputA, setInputA] = useState<IntegrityState>('HEALTHY');
  const [inputB, setInputB] = useState<IntegrityState>('SUSPECT');
  const [inputC, setInputC] = useState<IntegrityState>('HEALTHY');
  const [kThreshold, setKThreshold] = useState<number>(2);

  // Calculate deterministic outcome
  const computeResult = (): { state: IntegrityState; rule: string } => {
    const valA = LATTICE_VALUES[inputA];
    const valB = LATTICE_VALUES[inputB];
    const valC = LATTICE_VALUES[inputC];

    if (operator === 'MEET_AND') {
      const minVal = Math.min(valA, valB, valC);
      return {
        state: VALUE_TO_STATE[minVal],
        rule: `min(${inputA}, ${inputB}, ${inputC}) = ${VALUE_TO_STATE[minVal]} (Weakest input wins AND)`,
      };
    }

    if (operator === 'JOIN_OR') {
      const maxVal = Math.max(valA, valB, valC);
      return {
        state: VALUE_TO_STATE[maxVal],
        rule: `max(${inputA}, ${inputB}, ${inputC}) = ${VALUE_TO_STATE[maxVal]} (Strongest input wins OR)`,
      };
    }

    // k-of-n: k-th largest value
    const sorted = [valA, valB, valC].sort((a, b) => b - a);
    const kIdx = Math.min(sorted.length - 1, Math.max(0, kThreshold - 1));
    const kVal = sorted[kIdx];
    return {
      state: VALUE_TO_STATE[kVal],
      rule: `${kThreshold}-of-3 order statistic: ${VALUE_TO_STATE[kVal]}`,
    };
  };

  const result = computeResult();

  return (
    <div className="state-algebra-card panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Pure Mathematical Evaluation</p>
          <h3>Deterministic Scoped Integrity Algebra (SIA) Explorer</h3>
        </div>

        <div className="algebra-mode-toggle">
          <button
            type="button"
            className={`mode-btn ${operator === 'MEET_AND' ? 'is-active' : ''}`}
            onClick={() => setOperator('MEET_AND')}
          >
            Meet (AND)
          </button>
          <button
            type="button"
            className={`mode-btn ${operator === 'JOIN_OR' ? 'is-active' : ''}`}
            onClick={() => setOperator('JOIN_OR')}
          >
            Join (OR)
          </button>
          <button
            type="button"
            className={`mode-btn ${operator === 'K_OF_N' ? 'is-active' : ''}`}
            onClick={() => setOperator('K_OF_N')}
          >
            k-of-n
          </button>
        </div>
      </div>

      <div className="state-algebra-body">
        <p className="algebra-lead">
          Test deterministic state propagation across the 4-state total order:{' '}
          <code>DEGRADED &lt; UNKNOWN &lt; SUSPECT &lt; HEALTHY</code>.
        </p>

        {/* Inputs Selection Controls */}
        <div className="inputs-selection-row">
          <div className="input-picker-box">
            <span className="p-label">Input Role A:</span>
            <select
              value={inputA}
              onChange={(e) => setInputA(e.target.value as IntegrityState)}
              className="state-select"
            >
              {(['HEALTHY', 'SUSPECT', 'UNKNOWN', 'DEGRADED'] as const).map((st) => (
                <option key={st} value={st}>{st}</option>
              ))}
            </select>
            <StateBadge state={inputA} size="sm" />
          </div>

          <div className="input-picker-box">
            <span className="p-label">Input Role B:</span>
            <select
              value={inputB}
              onChange={(e) => setInputB(e.target.value as IntegrityState)}
              className="state-select"
            >
              {(['HEALTHY', 'SUSPECT', 'UNKNOWN', 'DEGRADED'] as const).map((st) => (
                <option key={st} value={st}>{st}</option>
              ))}
            </select>
            <StateBadge state={inputB} size="sm" />
          </div>

          <div className="input-picker-box">
            <span className="p-label">Input Role C:</span>
            <select
              value={inputC}
              onChange={(e) => setInputC(e.target.value as IntegrityState)}
              className="state-select"
            >
              {(['HEALTHY', 'SUSPECT', 'UNKNOWN', 'DEGRADED'] as const).map((st) => (
                <option key={st} value={st}>{st}</option>
              ))}
            </select>
            <StateBadge state={inputC} size="sm" />
          </div>

          {operator === 'K_OF_N' && (
            <div className="input-picker-box k-box">
              <span className="p-label">Threshold k:</span>
              <select
                value={kThreshold}
                onChange={(e) => setKThreshold(Number(e.target.value))}
                className="state-select"
              >
                <option value={1}>1 of 3 (Weakest Join)</option>
                <option value={2}>2 of 3 (Majority)</option>
                <option value={3}>3 of 3 (Strict Meet)</option>
              </select>
            </div>
          )}
        </div>

        {/* Evaluation Output Result */}
        <div className="algebra-result-box">
          <div className="result-main-col">
            <span className="res-tag">EVALUATOR RESULT:</span>
            <StateBadge state={result.state} size="lg" />
          </div>
          <div className="result-rule-col">
            <span className="rule-label">Algebraic Evaluation Rule:</span>
            <code className="rule-code">{result.rule}</code>
          </div>
        </div>
      </div>
    </div>
  );
};

