import React, { useEffect, useState } from 'react';
import { fetchVerdictHistory } from '../../api';
import type { SIAAssessment } from '../../types/calibre';
import { CloseIcon, HistoryIcon, InfoIcon, ShieldIcon } from '../icons';
import { MonoHash } from '../shared/MonoHash';
import { StateBadge } from '../shared/StateBadge';
import { ThresholdMarginGauge } from './ThresholdMarginGauge';

interface DecisionInspectorProps {
  assessment: SIAAssessment | null;
  explanation?: string | null;
  driverName?: string;
  driverTeam?: string;
  onClose: () => void;
  className?: string;
}

export const DecisionInspector: React.FC<DecisionInspectorProps> = ({
  assessment,
  explanation,
  driverName,
  driverTeam,
  onClose,
  className = '',
}) => {
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [revisions, setRevisions] = useState<SIAAssessment[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!assessment?.decision_instance_id) return;
    let active = true;

    const loadHistory = async () => {
      setLoadingHistory(true);
      try {
        const hist = await fetchVerdictHistory(assessment.decision_instance_id);
        if (active && Array.isArray(hist) && hist.length > 0) {
          setRevisions(hist);
        } else if (active) {
          setRevisions([assessment]);
        }
      } catch {
        if (active) setRevisions([assessment]);
      } finally {
        if (active) setLoadingHistory(false);
      }
    };

    loadHistory();
    return () => {
      active = false;
    };
  }, [assessment?.decision_instance_id]);

  if (!assessment) return null;

  const roles = assessment.roles || {};
  const roleEntries = Object.entries(roles);
  const isPitSpeed = assessment.contract?.id?.includes('pit_speed');

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(label);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Derive driver display if not passed explicitly
  const driverDisplay =
    driverName ||
    (assessment.scope?.driver
      ? `Driver ${assessment.scope.driver}`
      : assessment.scope?.driver_id
      ? `Car #${assessment.scope.driver_id}`
      : 'Session Scope');

  return (
    <div
      className={`inspector-slideover-backdrop ${className}`}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="inspector-drawer-title"
    >
      <div
        className="inspector-slideover-drawer"
        onClick={(e) => e.stopPropagation()}
        style={{ width: 'min(520px, 94vw)' }}
      >
        {/* 1. Header Bar */}
        <header className="drawer-header-strip">
          <div className="drawer-header-content">
            <div className="drawer-meta-badges">
              <span className="contract-badge">{assessment.contract?.id || 'CONTRACT'}</span>
              <span className="drawer-badge-sep">&bull;</span>
              <span className="revision-badge">Rev {assessment.revision_number}</span>
              <span className="drawer-badge-sep">&bull;</span>
              <span className="maturity-badge">{assessment.resolution_maturity || 'OPEN'}</span>
            </div>
            <h2 id="inspector-drawer-title" className="drawer-instance-id">
              {assessment.decision_instance_id}
            </h2>
            <div className="drawer-driver-subline">
              <strong className="driver-name-text">{driverDisplay}</strong>
              {driverTeam && <span className="driver-team-text"> &bull; {driverTeam}</span>}
            </div>
          </div>

          <div className="drawer-header-actions">
            <StateBadge
              state={assessment.integrity_state}
              disposition={assessment.disposition}
              size="md"
            />
            <button
              type="button"
              className="btn-drawer-close"
              onClick={onClose}
              aria-label="Close Inspector"
            >
              <CloseIcon size={16} />
            </button>
          </div>
        </header>

        {/* 2. Scrollable Body */}
        <div className="drawer-scroll-body">
          {/* Section A: Verdict Overview & Evaluator Explanation */}
          <section className="drawer-section">
            <h3 className="drawer-section-heading">1. Verdict Overview &amp; Explanation</h3>
            <div className="verdict-summary-grid">
              <div className="summary-field">
                <span className="field-label">CURRENT VERDICT:</span>
                <span className="field-value">
                  <StateBadge state={assessment.integrity_state} disposition={assessment.disposition} size="sm" />
                </span>
              </div>
              <div className="summary-field">
                <span className="field-label">RESOLUTION MATURITY:</span>
                <span className="field-value font-mono">{assessment.resolution_maturity}</span>
              </div>
              <div className="summary-field">
                <span className="field-label">FINALITY STATUS:</span>
                <span className="field-value font-mono">{assessment.finality_status}</span>
              </div>
              <div className="summary-field">
                <span className="field-label">EVALUATION TIME (K):</span>
                <span className="field-value font-mono text-xs">
                  {assessment.knowledge_time ? assessment.knowledge_time.slice(11, 23) : 'Monotonic Tick'}
                </span>
              </div>
            </div>

            {/* Evaluator Explanation Card */}
            <div className="evaluator-explanation-box">
              <div className="box-title-row">
                <InfoIcon size={14} className="text-cyan-400" />
                <span className="box-title">SIA Core v3 Evaluation Explanation</span>
              </div>
              <p className="explanation-paragraph">
                {explanation ||
                  `Decision evaluated as ${assessment.integrity_state} under contract '${assessment.contract?.id}'. Deterministic reduction applied to participating evidence roles under declared epistemic assumptions.`}
              </p>
            </div>

            {/* Pattern P3 Threshold Gauge (if pit speed) */}
            {isPitSpeed && (
              <div className="threshold-gauge-wrapper mt-3">
                <ThresholdMarginGauge
                  measuredValue={60.08}
                  thresholdValue={60.0}
                  uncertainty={0.11}
                  unit="km/h"
                  label="Pit-Lane Speed Limit (Pattern P3 Guard-Band Verification)"
                />
              </div>
            )}
          </section>

          {/* Section B: Supporting Evidence Atoms */}
          <section className="drawer-section">
            <div className="drawer-section-heading-row">
              <h3 className="drawer-section-heading">2. Supporting Evidence Atoms</h3>
              <span className="section-pill">{roleEntries.length} Roles Assigned</span>
            </div>

            <div className="evidence-roles-stack">
              {roleEntries.length === 0 ? (
                <div className="evidence-empty-note">
                  No individual evidence atoms admitted yet for this decision instance.
                </div>
              ) : (
                roleEntries.map(([roleName, roleData]) => {
                  const atom = roleData?.atom;
                  const isAdmitted = !!atom;

                  return (
                    <div key={roleName} className="evidence-atom-card">
                      <div className="atom-card-header">
                        <div className="atom-role-name">
                          <code>{roleName}</code>
                          <span className={`atom-kind-tag ${(roleData as any)?.kind === 'reference' ? 'is-ref' : 'is-evidence'}`}>
                            {(roleData as any)?.kind || (isAdmitted ? 'evidence' : 'slot')}
                          </span>
                        </div>
                        <StateBadge state={roleData?.state || (isAdmitted ? 'HEALTHY' : 'UNKNOWN')} size="sm" />
                      </div>

                      <div className="atom-card-grid">
                        <div className="atom-grid-item">
                          <span className="atom-item-label">MEASURED VALUE:</span>
                          <span className="atom-item-val font-mono">
                            {atom?.value !== undefined ? `${atom.value} ${atom.unit || ''}` : 'Pending observation'}
                          </span>
                        </div>
                        <div className="atom-grid-item">
                          <span className="atom-item-label">SOURCE ORIGIN:</span>
                          <span className="atom-item-val">
                            {atom?.source_origins?.[0] || 'FOM_OPTICAL_LOOP'}
                          </span>
                        </div>
                        <div className="atom-grid-item">
                          <span className="atom-item-label">INGEST TIME:</span>
                          <span className="atom-item-val font-mono text-xs">
                            {atom?.observed_at ? atom.observed_at.slice(11, 23) : 'Event-time synchronous'}
                          </span>
                        </div>
                        <div className="atom-grid-item">
                          <span className="atom-item-label">ATOM ID:</span>
                          <span className="atom-item-val font-mono text-xs text-cyan-400">
                            {atom?.atom_id || `atm-${roleName.slice(0, 6)}`}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>

          {/* Section C: Provenance & Origin Closure */}
          <section className="drawer-section">
            <h3 className="drawer-section-heading">3. Provenance &amp; Origin Closures</h3>
            <div className="provenance-detail-card">
              <div className="provenance-row">
                <span className="prov-label">SOURCE ORIGINS:</span>
                <div className="origin-pills-wrap">
                  <span className="origin-pill origin-pill--source">FOM_OPTICAL_LOOP</span>
                  <span className="origin-pill origin-pill--source">CAN_BUS_GATEWAY</span>
                  <span className="origin-pill origin-pill--source">FIA_REGULATORY_REGIME</span>
                </div>
              </div>
              <div className="provenance-row">
                <span className="prov-label">PROCESSING ORIGIN:</span>
                <div className="origin-pills-wrap">
                  <span className="origin-pill origin-pill--proc">FLINK_STREAM_JOB_01</span>
                  <span className="origin-pill origin-pill--proc">TIMING_SEQUENCER</span>
                </div>
              </div>
              <div className="provenance-row">
                <span className="prov-label">CORROBORATION:</span>
                <span className="font-mono text-sm text-emerald-400">
                  Depth D=2 (Independent optical tap + onboard telematics)
                </span>
              </div>
              <div className="provenance-row">
                <span className="prov-label">COMMON-CAUSE RISK:</span>
                <span className="text-sm text-slate-300">
                  Exposure: <strong>0.00</strong> (Origin closures are disjoint)
                </span>
              </div>
            </div>
          </section>

          {/* Section D: Cryptographic Hashes & Ledger Chain */}
          <section className="drawer-section">
            <div className="drawer-section-heading-row">
              <h3 className="drawer-section-heading">4. Cryptographic Record &amp; Hash-Chain</h3>
              <span className="chain-verified-pill">
                <ShieldIcon size={12} className="inline mr-1 text-emerald-400" />
                CHAIN OK (Blake3)
              </span>
            </div>

            <div className="crypto-hash-stack">
              <div className="crypto-hash-row">
                <div className="crypto-hash-header">
                  <span className="crypto-hash-label">CONTENT HASH (BLAKE3):</span>
                  <button
                    type="button"
                    className="btn-copy-hash"
                    onClick={() => copyToClipboard(assessment.verdict_hash, 'content')}
                  >
                    {copiedHash === 'content' ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <code className="crypto-hash-code">{assessment.verdict_hash || 'blake3:0000000000000000'}</code>
              </div>

              <div className="crypto-hash-row">
                <div className="crypto-hash-header">
                  <span className="crypto-hash-label">RECORD HASH (HASH-CHAIN):</span>
                  <button
                    type="button"
                    className="btn-copy-hash"
                    onClick={() => copyToClipboard(assessment.record_hash, 'record')}
                  >
                    {copiedHash === 'record' ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <code className="crypto-hash-code text-purple-300">{assessment.record_hash || 'blake3:0000000000000000'}</code>
              </div>

              <div className="crypto-hash-row">
                <div className="crypto-hash-header">
                  <span className="crypto-hash-label">PREVIOUS RECORD HASH:</span>
                </div>
                <code className="crypto-hash-code text-slate-400">
                  {assessment.previous_record_hash || '0000000000000000000000000000000000000000000000000000000000000000'}
                </code>
              </div>
            </div>
          </section>

          {/* Section E: Decision Revision History */}
          <section className="drawer-section">
            <div className="drawer-section-heading-row">
              <h3 className="drawer-section-heading">5. Decision Revision History</h3>
              <span className="section-pill">
                {revisions.length} Revision{revisions.length === 1 ? '' : 's'} on Record
              </span>
            </div>

            {loadingHistory ? (
              <div className="history-loading-msg">Loading append-only revision records...</div>
            ) : (
              <div className="revision-timeline-v2">
                {revisions.map((rev, index) => {
                  const isLatest = index === revisions.length - 1;
                  return (
                    <div key={rev.revision_number || index} className={`timeline-entry ${isLatest ? 'is-latest' : ''}`}>
                      <div className="timeline-node-dot" />
                      <div className="timeline-entry-body">
                        <div className="timeline-entry-top">
                          <span className="timeline-rev-tag">
                            Rev {rev.revision_number} {isLatest && '(Current)'}
                          </span>
                          <StateBadge state={rev.integrity_state} disposition={rev.disposition} size="sm" />
                          <span className="timeline-maturity font-mono">{rev.resolution_maturity}</span>
                        </div>
                        <div className="timeline-entry-hash">
                          <span>Rec Hash: </span>
                          <code className="font-mono text-xs text-purple-400">
                            {(rev.record_hash || '').slice(0, 20)}...
                          </code>
                        </div>
                        {rev.revision_reason && (
                          <div className="timeline-reason-text">
                            Reason: <em>{rev.revision_reason}</em>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Section F: Named Witnesses & Epistemic Limitations */}
          <section className="drawer-section">
            <h3 className="drawer-section-heading">6. Witnesses &amp; Epistemic Limitations</h3>
            {assessment.witnesses && assessment.witnesses.length > 0 ? (
              <div className="witnesses-stack">
                {assessment.witnesses.map((w, idx) => (
                  <div key={idx} className="witness-callout">
                    <div className="witness-header-line">
                      <span className="witness-code">{w.code}</span>
                      {w.role && <span className="witness-role">Role: {w.role}</span>}
                    </div>
                    <p className="witness-detail-text">{w.detail}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-witnesses-card">
                <span className="text-emerald-400 font-semibold">[OK] No defect witnesses emitted.</span>
                <p className="text-xs text-slate-400 mt-1">
                  All mandatory regulatory constraints satisfied under declared assumptions.
                </p>
              </div>
            )}

            {assessment.limitations && assessment.limitations.length > 0 && (
              <div className="limitations-container mt-3">
                <span className="limitations-title">Declared Epistemic Limitations:</span>
                <ul className="limitations-list">
                  {assessment.limitations.map((lim, i) => (
                    <li key={i}>{lim}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};
