import React, { useState } from 'react';
import type { SIAAssessment } from '../../types/calibre';
import { CloseIcon, InfoIcon } from '../icons';
import { MonoHash } from '../shared/MonoHash';
import { StateBadge } from '../shared/StateBadge';
import { AtomViewer } from './AtomViewer';
import { RequirementsTree } from './RequirementsTree';
import { ThresholdMarginGauge } from './ThresholdMarginGauge';

interface DecisionInspectorProps {
  assessment: SIAAssessment | null;
  explanation?: string | null;
  onClose: () => void;
  className?: string;
}

export const DecisionInspector: React.FC<DecisionInspectorProps> = ({
  assessment,
  explanation,
  onClose,
  className = '',
}) => {
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);

  if (!assessment) return null;

  const roles = assessment.roles || {};
  const activeRole = selectedRoleId ? roles[selectedRoleId] : Object.values(roles)[0];
  const activeAtom = activeRole?.atom;

  // Check if contract is a threshold contract (e.g. pit speed)
  const isPitSpeed = assessment.contract?.id?.includes('pit_speed');

  return (
    <div className={`decision-inspector-overlay ${className}`} onClick={onClose} role="dialog" aria-modal="true">
      <div className="decision-inspector-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Header Bar */}
        <div className="inspector-header">
          <div>
            <div className="inspector-meta-row">
              <span className="contract-tag">{assessment.contract?.id || 'Contract'}</span>
              <span className="dot-sep">•</span>
              <span className="scope-tag">
                Scope: {Object.entries(assessment.scope || {}).map(([k, v]) => `${k}=${v}`).join(', ')}
              </span>
              <span className="dot-sep">•</span>
              <span className="revision-tag">Rev {assessment.revision_number}</span>
            </div>
            <h2 className="inspector-title">{assessment.decision_instance_id}</h2>
          </div>

          <button
            type="button"
            className="inspector-close-btn"
            onClick={onClose}
            aria-label="Close Decision Inspector"
          >
            <CloseIcon size={16} />
          </button>
        </div>

        {/* Status Strip: State, Maturity, Finality, Hashes */}
        <div className="inspector-status-strip">
          <div className="status-item">
            <span className="s-label">VERDICT STATE:</span>
            <StateBadge state={assessment.integrity_state} disposition={assessment.disposition} size="md" />
          </div>

          <div className="status-item">
            <span className="s-label">RESOLUTION:</span>
            <span className={`maturity-tag maturity--${assessment.resolution_maturity.toLowerCase()}`}>
              {assessment.resolution_maturity}
            </span>
          </div>

          <div className="status-item">
            <span className="s-label">FINALITY:</span>
            <span className={`finality-tag finality--${assessment.finality_status.toLowerCase()}`}>
              {assessment.finality_status}
            </span>
          </div>

          <div className="status-item">
            <MonoHash hash={assessment.verdict_hash} label="Content Hash" truncateLength={10} />
          </div>

          <div className="status-item">
            <MonoHash hash={assessment.record_hash} label="Record Hash" truncateLength={10} />
          </div>
        </div>

        {/* Drawer Body Scroll */}
        <div className="inspector-body">
          {/* Explanation Banner */}
          {explanation && (
            <div className="explanation-card">
              <span className="exp-label">
                <InfoIcon size={12} className="inline mr-1" />
                DETERMINISTIC EVALUATOR EXPLANATION:
              </span>
              <p className="exp-text">{explanation}</p>
            </div>
          )}

          {/* Section 1: Named Witnesses & Epistemic Limitations */}
          <section className="inspector-section witnesses-section">
            <h4 className="section-title">Named Epistemic Witnesses & Limitations</h4>
            <div className="witnesses-list">
              {assessment.witnesses && assessment.witnesses.length > 0 ? (
                assessment.witnesses.map((w, idx) => (
                  <div key={idx} className={`witness-item witness-severity--${w.severity?.toLowerCase() || 'info'}`}>
                    <div className="witness-header">
                      <span className={`w-severity-tag severity--${w.severity?.toLowerCase() || 'info'}`}>
                        {w.severity || 'INFO'}
                      </span>
                      <strong className="w-code">{w.code}</strong>
                      {w.role && <span className="w-role">[{w.role}]</span>}
                    </div>
                    <p className="w-detail">{w.detail}</p>
                    {w.remedial_action && (
                      <p className="w-remedial">
                        <strong>Remedial:</strong> {w.remedial_action}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <div className="no-witnesses-item">
                  <span>No defect witnesses emitted. Requirements satisfied under declared assumptions.</span>
                </div>
              )}

              {/* Limitations */}
              {assessment.limitations && assessment.limitations.length > 0 && (
                <div className="limitations-box">
                  <span className="lim-title">Declared Epistemic Limitations:</span>
                  <ul className="lim-list">
                    {assessment.limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>

          {/* Section 2: Pattern P3 Threshold Margin (if applicable) */}
          {isPitSpeed && (
            <section className="inspector-section threshold-section">
              <h4 className="section-title">Threshold Margin Analysis (Pattern P3)</h4>
              <ThresholdMarginGauge
                measuredValue={60.08}
                thresholdValue={60.0}
                uncertainty={0.11}
                unit="km/h"
                label="Pit-Lane Speed Limit (Illustrative Incident Scenario)"
              />
            </section>
          )}

          {/* Section 3: Requirements Logic Tree */}
          <section className="inspector-section tree-section">
            <h4 className="section-title">Formula Evaluation AST</h4>
            <RequirementsTree
              formula={assessment.contract?.formula || 'AND(roles...)'}
              rootState={assessment.integrity_state}
              roles={roles}
              limitingChildren={assessment.limiting_children}
              selectedRoleId={selectedRoleId || Object.keys(roles)[0]}
              onSelectRole={(rId) => setSelectedRoleId(rId)}
            />
          </section>

          {/* Section 4: Evidence Atom & Raw Span Viewer */}
          <section className="inspector-section atom-section">
            <h4 className="section-title">Supporting Evidence Atom & Provenance</h4>
            <AtomViewer
              atom={activeAtom}
              rawSpanAvailable={true}
              rawSpanOffset="0x004A2F"
            />
          </section>
        </div>
      </div>
    </div>
  );
};

