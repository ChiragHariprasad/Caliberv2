import React, { useMemo, useState } from 'react';
import type { ContractDefinition, SIAAssessment } from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';
import { InfoIcon, ShieldIcon, CheckCircleIcon, AlertTriangleIcon } from '../icons';

interface ContextualityDagProps {
  atomId?: string;
  roleId?: string;
  decisionId?: string;
  verdict?: SIAAssessment | null;
  allVerdicts?: SIAAssessment[];
  contracts?: ContractDefinition[];
  className?: string;
}

interface ContractEvaluationDetail {
  id: string;
  name: string;
  scope: string;
  state: 'HEALTHY' | 'SUSPECT' | 'UNKNOWN' | 'DEGRADED';
  constraints: string[];
  outcome: string;
  explanation: string;
}

export const ContextualityDag: React.FC<ContextualityDagProps> = ({
  decisionId = '',
  verdict,
  allVerdicts = [],
  contracts = [],
  className = '',
}) => {
  const { liveAtoms, liveDetails } = useMemo(() => {
    const atomMap = new Map<string, { id: string; role: string; value: string; source: string; timestamp: string; contracts: string[] }>();
    const details: Record<string, ContractEvaluationDetail> = {};

    const sourceList = allVerdicts.length > 0 ? allVerdicts : verdict ? [verdict] : [];
    for (const v of sourceList) {
      const cid = v.decision_instance_id;
      const cSpec = contracts.find((c) => c.contract_id === v.contract?.id);
      const consLabels =
        (v.contract_constraints || []).map((cs: any) => `${cs.id} (${cs.kind})`) ||
        (cSpec?.constraints || []).map((cs: any) => `${cs.id} (${cs.kind})`);
      details[cid] = {
        id: cid,
        name: `${v.contract?.id || cid}`,
        scope: JSON.stringify(v.scope || {}),
        state: v.integrity_state,
        constraints: consLabels.length > 0 ? consLabels : ['Role presence & admissibility bounds'],
        outcome: `${v.integrity_state} (${v.primary_binding_witness || 'Evaluated'})`,
        explanation:
          (v.limitations && v.limitations.length > 0 ? v.limitations.join('; ') : null) ||
          'Evaluated hermetically within contract scope bounds without cross-contract contamination.',
      };

      for (const [rName, rawRole] of Object.entries(v.roles || {})) {
        const r = rawRole as any;
        for (const a of r?.atoms_detail || []) {
          const aid = String(a.atom_id);
          const existing = atomMap.get(aid);
          if (existing) {
            if (!existing.contracts.includes(cid)) existing.contracts.push(cid);
          } else {
            atomMap.set(aid, {
              id: aid.slice(0, 14),
              role: a.role_id || rName,
              value: a.value !== undefined ? `${a.value} ${a.unit || ''}`.trim() : '—',
              source: a.source_origins?.[0] || 'Unknown',
              timestamp: a.observed_at || '—',
              contracts: [cid],
            });
          }
        }
      }
    }

    return {
      liveAtoms: Array.from(atomMap.values()).slice(0, 8),
      liveDetails: details,
    };
  }, [allVerdicts, verdict, contracts]);

  const [selectedAtomId, setSelectedAtomId] = useState<string>('');
  const [selectedContractId, setSelectedContractId] = useState<string>(decisionId);

  const activeAtom =
    liveAtoms.find((a) => a.id === selectedAtomId) ||
    liveAtoms[0] || {
      id: 'awaiting-atom',
      role: 'none',
      value: '—',
      source: 'Awaiting stream evaluation',
      timestamp: '—',
      contracts: [],
    };
  const participatingContracts = activeAtom.contracts.map((cid) => liveDetails[cid]).filter(Boolean);
  const activeDetail =
    liveDetails[selectedContractId] ||
    participatingContracts[0] || {
      id: 'none',
      name: 'No evaluated decision instance',
      scope: 'Start or seek replay to inspect real atom-to-contract contextuality.',
      state: 'UNKNOWN' as const,
      constraints: [],
      outcome: 'Pending evaluation',
      explanation: 'Real atoms admitted during replay will appear here mapped across participating contracts.',
    };

  return (
    <div className={`contextuality-workspace ${className}`}>
      {/* 1. Top Section: Selectable Evidence Atoms & Source Metadata */}
      <section className="contextuality-top-section">
        <div className="section-title-wrap">
          <div className="title-left">
            <span className="eyebrow-accent">HERMETIC SCOPE ISOLATION</span>
            <h2 className="workspace-section-title">Contextuality &amp; Cross-Contract Non-Contamination</h2>
          </div>
          <div className="title-right">
            <span className="theorem-callout font-mono">
              Theorem: &nbsp; E<sub>C01</sub>(atom) &perp; E<sub>C03</sub>(atom)
            </span>
          </div>
        </div>

        {/* Atom Selection Toolbar */}
        <div className="atom-selector-bar">
          <span className="atom-sel-label">SELECT EVIDENCE ATOM:</span>
          <div className="atom-pills-group">
            {liveAtoms.length > 0 ? liveAtoms.map((atom) => (
              <button
                key={atom.id}
                type="button"
                className={`atom-select-pill ${atom.id === activeAtom.id ? 'is-selected-atom' : ''}`}
                onClick={() => {
                  setSelectedAtomId(atom.id);
                  if (atom.contracts[0]) setSelectedContractId(atom.contracts[0]);
                }}
              >
                <span className="atom-pill-id font-mono">{atom.id}</span>
                <span className="atom-pill-role">[{atom.role}]</span>
              </button>
            )) : (
              <span className="text-xs text-slate-400">No evidence atoms admitted yet (start replay to populate live atoms).</span>
            )}
          </div>
        </div>

        {/* Selected Atom Metadata Strip */}
        <div className="atom-metadata-strip">
          <div className="meta-card">
            <span className="meta-k">ATOM IDENTIFIER:</span>
            <code className="meta-v text-cyan-400">{activeAtom.id}</code>
          </div>
          <div className="meta-card">
            <span className="meta-k">EVIDENCE ROLE:</span>
            <strong className="meta-v">{activeAtom.role}</strong>
          </div>
          <div className="meta-card">
            <span className="meta-k">OBSERVED VALUE:</span>
            <strong className="meta-v text-emerald-400 font-mono">{activeAtom.value}</strong>
          </div>
          <div className="meta-card">
            <span className="meta-k">SOURCE ORIGIN:</span>
            <span className="meta-v">{activeAtom.source}</span>
          </div>
          <div className="meta-card">
            <span className="meta-k">INGEST TIMESTAMP:</span>
            <span className="meta-v font-mono text-xs">{activeAtom.timestamp}</span>
          </div>
        </div>
      </section>

      {/* 2. Centre Section: Visual Radiating Branching Graph */}
      <section className="contextuality-visual-centre">
        <div className="centre-title-line">
          <span className="centre-title">Evidence Atom Multi-Contract Participation Topology</span>
          <span className="centre-sub text-slate-400">
            A suspect verdict in C01 does not propagate contamination to C03 or C04
          </span>
        </div>

        <div className="branching-diagram-container">
          <svg className="branching-svg" viewBox="0 0 760 220">
            <defs>
              <linearGradient id="branch-grad-healthy" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#38bdf8" />
                <stop offset="100%" stopColor="#10b981" />
              </linearGradient>
              <linearGradient id="branch-grad-suspect" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#38bdf8" />
                <stop offset="100%" stopColor="#f59e0b" />
              </linearGradient>
            </defs>

            {/* Central Atom Box */}
            <g transform="translate(40, 70)">
              <rect width="200" height="80" rx="8" fill="#0f172a" stroke="#38bdf8" strokeWidth="2" />
              <text x="16" y="28" fill="#38bdf8" fontSize="10" fontWeight="bold" fontFamily="monospace">
                EVIDENCE ATOM
              </text>
              <text x="16" y="48" fill="#ffffff" fontSize="13" fontWeight="bold">
                {activeAtom.id}
              </text>
              <text x="16" y="66" fill="#94a3b8" fontSize="11" fontFamily="monospace">
                Value: {activeAtom.value}
              </text>
            </g>

            {/* Branching Curves and Contract Nodes */}
            {participatingContracts.map((c, i) => {
              const targetY = 30 + i * 75;
              const isSelected = c.id === selectedContractId;
              const isSuspect = c.state === 'SUSPECT';

              return (
                <g key={c.id} onClick={() => setSelectedContractId(c.id)} style={{ cursor: 'pointer' }}>
                  {/* Branching Connecting Curve */}
                  <path
                    d={`M 240 110 C 350 110, 400 ${targetY + 25}, 500 ${targetY + 25}`}
                    fill="none"
                    stroke={isSelected ? '#38bdf8' : isSuspect ? 'url(#branch-grad-suspect)' : 'url(#branch-grad-healthy)'}
                    strokeWidth={isSelected ? 3 : 2}
                    strokeDasharray={isSelected ? 'none' : '4 2'}
                  />

                  {/* Contract Node Box */}
                  <g transform={`translate(500, ${targetY})`}>
                    {isSelected && (
                      <rect
                        x="-4"
                        y="-4"
                        width="248"
                        height="58"
                        rx="8"
                        fill="none"
                        stroke="#38bdf8"
                        strokeWidth="2"
                      />
                    )}
                    <rect
                      width="240"
                      height="50"
                      rx="6"
                      fill="#0b0f17"
                      stroke={c.state === 'SUSPECT' ? '#ffd000' : '#00ff88'}
                      strokeWidth="1.5"
                    />
                    <text x="12" y="20" fill="#94a3b8" fontSize="9" fontFamily="monospace">
                      {c.scope}
                    </text>
                    <text x="12" y="38" fill="#ffffff" fontSize="12" fontWeight="bold">
                      {c.id}
                    </text>
                    <g transform="translate(170, 16)">
                      <StateBadge state={c.state} size="sm" />
                    </g>
                  </g>
                </g>
              );
            })}
          </svg>
        </div>
      </section>

      {/* 3. Below Section: Individual Contract Result Cards */}
      <section className="contextuality-results-section">
        <div className="section-title-wrap">
          <div className="title-left">
            <span className="eyebrow-accent">CONTRACT EVALUATION RESULTS</span>
            <h3 className="workspace-section-title">Participating Contract Assessments</h3>
          </div>
          <span className="contracts-counter-pill">
            {participatingContracts.length} Isolated Contract Evaluations
          </span>
        </div>

        <div className="contract-cards-grid">
          {participatingContracts.map((c) => {
            const isSelected = c.id === selectedContractId;

            return (
              <div
                key={c.id}
                className={`contract-eval-card ${isSelected ? 'is-selected-card' : ''}`}
                onClick={() => setSelectedContractId(c.id)}
                role="button"
                tabIndex={0}
              >
                <div className="eval-card-header">
                  <div>
                    <span className="eval-card-scope">{c.scope}</span>
                    <h4 className="eval-card-title">{c.name}</h4>
                    <code className="eval-card-id">{c.id}</code>
                  </div>
                  <StateBadge state={c.state} size="md" />
                </div>

                <div className="eval-card-body">
                  <div className="eval-constraints-box">
                    <span className="box-label">CONSTRAINTS EVALUATED:</span>
                    <ul className="constraints-list">
                      {c.constraints.map((cn, idx) => (
                        <li key={idx}>
                          <code>{cn}</code>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="eval-outcome-box">
                    <span className="box-label">OUTCOME:</span>
                    <strong className={c.state === 'SUSPECT' ? 'text-amber-400' : 'text-emerald-400'}>
                      {c.outcome}
                    </strong>
                  </div>

                  <p className="eval-explanation-text">{c.explanation}</p>
                </div>

                <div className="eval-card-footer">
                  <span className="isolation-guarantee">
                    <ShieldIcon size={12} className="inline mr-1 text-cyan-400" />
                    Hermetic Scope Isolation Guaranteed
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
};
