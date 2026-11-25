import React, { useState } from 'react';
import { StateBadge } from '../shared/StateBadge';
import { InfoIcon, ShieldIcon, CheckCircleIcon, AlertTriangleIcon } from '../icons';

interface ContextualityDagProps {
  atomId?: string;
  roleId?: string;
  decisionId?: string;
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

const SAMPLE_ATOMS = [
  {
    id: 'atm-spd-88f2',
    role: 'timing_speed',
    value: '79.2 km/h',
    source: 'FOM_OPTICAL_LOOP',
    timestamp: '2026-05-24T14:15:32.420Z',
    contracts: ['C03_pit_speed', 'C01_lap_time', 'C04_kinematics'],
  },
  {
    id: 'atm-pos-44a1',
    role: 'track_coordinate',
    value: 'Sector 1 Pit In (s=142.4m)',
    source: 'GPS_HIGH_FREQUENCY',
    timestamp: '2026-05-24T14:15:32.418Z',
    contracts: ['C06_position', 'C03_pit_speed', 'C08_incident_timing'],
  },
  {
    id: 'atm-temp-09a',
    role: 'track_temperature',
    value: '35.4 °C',
    source: 'TRACK_METEOROLOGY_STATION',
    timestamp: '2026-05-24T14:15:00.000Z',
    contracts: ['C09_weather', 'C10_weather_advisory'],
  },
];

const CONTRACT_DETAILS: Record<string, ContractEvaluationDetail> = {
  C03_pit_speed: {
    id: 'C03_pit_speed',
    name: 'Pit-Lane Speed Limit Verification',
    scope: 'SECTOR (Sector 1 Pit Lane)',
    state: 'HEALTHY',
    constraints: ['measured_speed <= 80.0 km/h', 'guard_band_margin >= 0.5 km/h'],
    outcome: 'SATISFIED (79.2 km/h within 80.0 km/h limit with 0.8 km/h margin)',
    explanation:
      'The speed reading of 79.2 km/h was verified against the pit lane speed limiter threshold under declared optical loop tolerances.',
  },
  C01_lap_time: {
    id: 'C01_lap_time',
    name: 'Lap-Time Sum Consistency',
    scope: 'DRIVER_LAP (Lap 24)',
    state: 'SUSPECT',
    constraints: ['sector_sum_delta <= 15ms', 'microsector_monotonicity == true'],
    outcome: 'DISCREPANCY (Loop delta of 22ms exceeds 15ms consistency guard-band)',
    explanation:
      'In this contract, the exact same optical reading participates as an entry milestone. It is flagged as SUSPECT here because a companion loop exhibited clock drift, demonstrating that contextuality isolates the verdict to this contract alone.',
  },
  C04_kinematics: {
    id: 'C04_kinematics',
    name: 'Vehicle Acceleration & Kinematics',
    scope: 'DRIVER_LAP (Lap 24)',
    state: 'HEALTHY',
    constraints: ['longitudinal_g <= 5.5G', 'lateral_g <= 5.8G'],
    outcome: 'SATISFIED (Deceleration profile conforms to physical tire-grip bounds)',
    explanation:
      'The deceleration into the speed trap was within kinematic feasibility limits of the Brembo carbon-carbon braking assembly.',
  },
  C06_position: {
    id: 'C06_position',
    name: 'Track Position & Marshalling Gate',
    scope: 'DRIVER_LAP (Lap 24)',
    state: 'HEALTHY',
    constraints: ['centerline_offset <= 12.0m', 'pit_entry_flag == true'],
    outcome: 'SATISFIED (Trajectory within pit entry delineation)',
    explanation: 'Position coordinate confirms vehicle was strictly inside the designated pit lane entrance boundary.',
  },
  C08_incident_timing: {
    id: 'C08_incident_timing',
    name: 'Race Incident & Yellow Flag Timing',
    scope: 'SESSION',
    state: 'HEALTHY',
    constraints: ['yellow_flag_speed_reduction >= 20%'],
    outcome: 'SATISFIED (Vehicle was not in an active yellow zone)',
    explanation: 'Pit entry sector was green at the moment of ingress.',
  },
  C09_weather: {
    id: 'C09_weather',
    name: 'Weather Reporting Consistency',
    scope: 'SESSION',
    state: 'HEALTHY',
    constraints: ['track_temp >= air_temp', 'gradient_limit <= 2.0C/min'],
    outcome: 'SATISFIED (Thermal gradient stable at +0.2 C/min)',
    explanation: 'Thermal sensors across the circuit agree with trackside meteorological baseline.',
  },
  C10_weather_advisory: {
    id: 'C10_weather_advisory',
    name: 'Track Surface Grip Advisory',
    scope: 'SESSION',
    state: 'HEALTHY',
    constraints: ['grip_coefficient >= 0.82'],
    outcome: 'SATISFIED (Dry track conditions verified)',
    explanation: 'Rain risk is 0.0% with consistent infrared track reflection.',
  },
};

export const ContextualityDag: React.FC<ContextualityDagProps> = ({
  atomId: initialAtomId = 'atm-spd-88f2',
  className = '',
}) => {
  const [selectedAtomId, setSelectedAtomId] = useState<string>(initialAtomId);
  const [selectedContractId, setSelectedContractId] = useState<string>('C03_pit_speed');

  const activeAtom = SAMPLE_ATOMS.find((a) => a.id === selectedAtomId) || SAMPLE_ATOMS[0];
  const participatingContracts = activeAtom.contracts.map((cid) => CONTRACT_DETAILS[cid]).filter(Boolean);
  const activeDetail = CONTRACT_DETAILS[selectedContractId] || participatingContracts[0];

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
            {SAMPLE_ATOMS.map((atom) => (
              <button
                key={atom.id}
                type="button"
                className={`atom-select-pill ${atom.id === selectedAtomId ? 'is-selected-atom' : ''}`}
                onClick={() => {
                  setSelectedAtomId(atom.id);
                  setSelectedContractId(atom.contracts[0]);
                }}
              >
                <span className="atom-pill-id font-mono">{atom.id}</span>
                <span className="atom-pill-role">[{atom.role}]</span>
              </button>
            ))}
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
