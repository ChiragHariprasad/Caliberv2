import React, { useEffect, useState } from 'react';
import {
  fetchVerdictAsOf,
  verifyHashChains,
  seekReplay,
  startReplay,
  pauseReplay,
  resetReplay,
  setReplaySpeed,
} from '../../api';
import type { HashChainVerificationResult, ReplayStatusData, SIAAssessment } from '../../types';
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  PauseIcon,
  PlayIcon,
  ResetIcon,
  ShieldIcon,
  SpeedIcon,
} from '../icons';
import { MonoHash } from '../shared/MonoHash';
import { StateBadge } from '../shared/StateBadge';

interface ReplayAuditViewProps {
  replayStatus: ReplayStatusData | null;
  onControlAction?: (action: 'START' | 'PAUSE' | 'RESUME' | 'RESET' | 'SEEK' | 'SPEED', val?: any) => void;
  className?: string;
}

export const ReplayAuditView: React.FC<ReplayAuditViewProps> = ({
  replayStatus,
  onControlAction,
  className = '',
}) => {
  const [activeTab, setActiveTab] = useState<'VERIFIER' | 'AS_OF_QUERY' | 'LAB_SCENARIOS'>('VERIFIER');
  const [verificationResult, setVerificationResult] = useState<HashChainVerificationResult | null>(null);
  const [verifying, setVerifying] = useState<boolean>(false);

  // As-Of Knowledge Time Query State
  const [queryInstanceId, setQueryInstanceId] = useState<string>('dec-pit_speed-d16');
  const [knowledgeTimeIso, setKnowledgeTimeIso] = useState<string>('2026-05-24T14:32:05.120Z');
  const [asOfVerdict, setAsOfVerdict] = useState<SIAAssessment | null>(null);
  const [queryingAsOf, setQueryingAsOf] = useState<boolean>(false);

  // Load hash chain verification status
  const runVerification = async () => {
    setVerifying(true);
    const res = await verifyHashChains();
    setVerificationResult(res);
    setVerifying(false);
  };

  useEffect(() => {
    runVerification();
  }, []);

  const handleExecuteAsOf = async () => {
    setQueryingAsOf(true);
    const res = await fetchVerdictAsOf(queryInstanceId, knowledgeTimeIso);
    setAsOfVerdict(res);
    setQueryingAsOf(false);
  };

  const isRunning = replayStatus?.status === 'RUNNING';
  const speed = replayStatus?.speed ?? 1.0;
  const currentLap = replayStatus?.currentLap ?? 1;
  const totalLaps = replayStatus?.totalLaps ?? 78;

  return (
    <div className={`replay-audit-view ${className}`}>
      {/* View Intro Bar */}
      <div className="view-intro-bar">
        <div>
          <span className="eyebrow">Deterministic Time-Travel & Cryptographic Verification</span>
          <h2>Global Replay Engine, Bitemporal History & Hash Chain Audit</h2>
        </div>

        <div className="domain-tabs">
          <button
            type="button"
            className={`domain-tab ${activeTab === 'VERIFIER' ? 'active' : ''}`}
            onClick={() => setActiveTab('VERIFIER')}
          >
            Hash-Chain Ledger Verifier
          </button>
          <button
            type="button"
            className={`domain-tab ${activeTab === 'AS_OF_QUERY' ? 'active' : ''}`}
            onClick={() => setActiveTab('AS_OF_QUERY')}
          >
            Bitemporal "As-Of" Knowledge Query
          </button>
          <button
            type="button"
            className={`domain-tab ${activeTab === 'LAB_SCENARIOS' ? 'active' : ''}`}
            onClick={() => setActiveTab('LAB_SCENARIOS')}
          >
            LAB Scenario Fault Injector
          </button>
        </div>
      </div>

      {/* Stream Playback Controller (Valid-Time Advancement) */}
      <section className="panel replay-playback-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Physical Stream Controller (Valid-Time)</p>
            <h3>Clean Reconstruction Playback Cursor</h3>
          </div>
          <span className="subtle-chip">Deterministic Seek · Zero Sinks Duplication</span>
        </div>

        <div className="playback-controls-row">
          <div className="btn-group">
            <button
              type="button"
              className={`ctrl-btn ${isRunning ? 'is-running' : ''}`}
              onClick={() => onControlAction?.(isRunning ? 'PAUSE' : 'START')}
            >
              {isRunning ? <PauseIcon size={14} className="inline mr-1" /> : <PlayIcon size={14} className="inline mr-1" />}
              {isRunning ? 'Pause Stream' : 'Play Stream'}
            </button>

            <button
              type="button"
              className="ctrl-btn"
              onClick={() => onControlAction?.('RESET')}
              title="Reset state to Lap 1"
            >
              <ResetIcon size={14} className="inline mr-1" />
              Reset State
            </button>
          </div>

          {/* Speed Selector */}
          <div className="speed-pills">
            <span className="speed-label"><SpeedIcon size={14} className="inline mr-1" /> Speed:</span>
            {[0.5, 1.0, 2.0, 5.0].map((s) => (
              <button
                key={s}
                type="button"
                className={`speed-pill ${speed === s ? 'is-active' : ''}`}
                onClick={() => onControlAction?.('SPEED', s)}
              >
                {s}x
              </button>
            ))}
          </div>

          <div className="playback-cursor-readout">
            <span className="readout-label">TRACK VALID TIME:</span>
            <strong className="readout-val">Lap {currentLap}/{totalLaps} · {replayStatus?.elapsed || '00:00:00'}</strong>
          </div>
        </div>
      </section>

      {/* TAB 1: HASH-CHAIN LEDGER VERIFIER */}
      {activeTab === 'VERIFIER' && (
        <section className="panel hash-verifier-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Cryptographic Integrity Audit</p>
              <h3>Hash-Chained Verdict Ledger (Append-Only Verification)</h3>
            </div>
            <button
              type="button"
              className="ctrl-btn verify-btn"
              onClick={runVerification}
              disabled={verifying}
            >
              <ShieldIcon size={14} className="inline mr-1" />
              {verifying ? 'Verifying Chains...' : 'Re-verify All Chains'}
            </button>
          </div>

          <div className="verifier-summary-card">
            <div className="v-status-badge">
              {verificationResult?.verified ? (
                <div className="v-banner is-ok">
                  <CheckCircleIcon size={20} className="text-emerald-400" />
                  <div>
                    <strong>ALL DECISION CHAINS CRYPTOGRAPHICALLY VERIFIED</strong>
                    <p>{verificationResult.chain_count} decision instance chains inspected · Zero tampering detected.</p>
                  </div>
                </div>
              ) : (
                <div className="v-banner is-pending">
                  <ShieldIcon size={20} className="text-amber-400" />
                  <div>
                    <strong>VERIFICATION ENGINE READY</strong>
                    <p>Click Re-verify All Chains to validate content_hash and record_hash links.</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Sample Ledger Revisions Table */}
          <div className="ledger-table-container">
            <table className="ledger-revisions-table">
              <thead>
                <tr>
                  <th>REV</th>
                  <th>DECISION INSTANCE ID</th>
                  <th>STATE</th>
                  <th>KNOWLEDGE TIME</th>
                  <th>CONTENT HASH (VERDICT)</th>
                  <th>RECORD HASH (CHAIN LINK)</th>
                  <th>STATUS</th>
                </tr>
              </thead>
              <tbody>
                <tr className="ledger-row">
                  <td><code>v1</code></td>
                  <td><code>dec-pit_speed-d16-l24</code></td>
                  <td><StateBadge state="UNKNOWN" size="sm" /></td>
                  <td>14:32:04.980 UTC</td>
                  <td><MonoHash hash="blake3:88a1f290d4e3cb12" truncateLength={8} /></td>
                  <td><MonoHash hash="blake3:1a2b3c4d5e6f7a8b" truncateLength={8} /></td>
                  <td><span className="chain-ok-tag">CHAIN OK</span></td>
                </tr>
                <tr className="ledger-row">
                  <td><code>v2</code></td>
                  <td><code>dec-pit_speed-d16-l24</code></td>
                  <td><StateBadge state="SUSPECT" size="sm" /></td>
                  <td>14:32:05.120 UTC</td>
                  <td><MonoHash hash="blake3:7f8a9b0c1d2e3f4a" truncateLength={8} /></td>
                  <td><MonoHash hash="blake3:3c2e1a9f8d7b6c5a" truncateLength={8} /></td>
                  <td><span className="chain-ok-tag">CHAIN OK</span></td>
                </tr>
                <tr className="ledger-row">
                  <td><code>v3</code></td>
                  <td><code>dec-pit_speed-d16-l24</code></td>
                  <td><StateBadge state="HEALTHY" size="sm" /></td>
                  <td>14:32:05.450 UTC</td>
                  <td><MonoHash hash="blake3:4d5e6f7a8b9c0d1e" truncateLength={8} /></td>
                  <td><MonoHash hash="blake3:9f8e7d6c5b4a3a2b" truncateLength={8} /></td>
                  <td><span className="chain-ok-tag">CHAIN OK</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB 2: BITEMPORAL AS-OF QUERY */}
      {activeTab === 'AS_OF_QUERY' && (
        <section className="panel as-of-query-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Bitemporal Epistemic Inspection</p>
              <h3>Historical As-Of Knowledge-Time Query (as_of(K))</h3>
            </div>
            <span className="subtle-chip">Read-Only Query · Does Not Mutate Playback</span>
          </div>

          <div className="as-of-form-row">
            <div className="input-group">
              <label htmlFor="inst-id-input">Decision Instance ID:</label>
              <input
                id="inst-id-input"
                type="text"
                className="query-input"
                value={queryInstanceId}
                onChange={(e) => setQueryInstanceId(e.target.value)}
              />
            </div>

            <div className="input-group">
              <label htmlFor="kt-input">Knowledge Time Instant (K):</label>
              <input
                id="kt-input"
                type="text"
                className="query-input"
                value={knowledgeTimeIso}
                onChange={(e) => setKnowledgeTimeIso(e.target.value)}
              />
            </div>

            <button
              type="button"
              className="ctrl-btn query-submit-btn"
              onClick={handleExecuteAsOf}
              disabled={queryingAsOf}
            >
              <ClockIcon size={14} className="inline mr-1" />
              {queryingAsOf ? 'Querying Index...' : 'Execute As-Of Query'}
            </button>
          </div>

          {/* Query Result Card */}
          {asOfVerdict ? (
            <div className="as-of-result-card">
              <h4>Historical Verdict as Known at K:</h4>
              <div className="result-details-grid">
                <div><span>State:</span> <StateBadge state={asOfVerdict.integrity_state} size="sm" /></div>
                <div><span>Revision:</span> <strong>v{asOfVerdict.revision_number}</strong></div>
                <div><span>Maturity:</span> <strong>{asOfVerdict.resolution_maturity}</strong></div>
                <div><span>Knowledge Time:</span> <code>{asOfVerdict.knowledge_time}</code></div>
                <div><span>Content Hash:</span> <MonoHash hash={asOfVerdict.verdict_hash} /></div>
              </div>
            </div>
          ) : (
            <div className="as-of-placeholder">
              <p>Enter an instance ID and knowledge timestamp above to inspect what CALIBRE concluded at that historical instant.</p>
            </div>
          )}
        </section>
      )}

      {/* TAB 3: LAB SCENARIOS */}
      {activeTab === 'LAB_SCENARIOS' && (
        <section className="panel lab-scenarios-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Synthetic Evaluation Bench</p>
              <h3>LAB Scenario Fault Injector (calibre_core/tests)</h3>
            </div>
            <span className="lab-watermark-pill">LAB / SYNTHETIC WATERMARK ACTIVE</span>
          </div>

          <div className="scenarios-grid">
            <div className="scenario-card">
              <h4>Monaco 2026 Geometry Model Fault (Motivating Incident)</h4>
              <p>
                Simulates 2.9% survey distance overstatement in pit lane timing loops.
                Verifies Pattern P3 guard-band margin detection against vehicle telemetry.
              </p>
              <button type="button" className="scenario-run-btn">
                Run Monaco Reference Scenario
              </button>
            </div>

            <div className="scenario-card">
              <h4>Late Reference Fact Injection</h4>
              <p>
                Reference fact admitted after soft deadline. Verifies that evaluator emits
                <code>LATE_REFERENCE_FACT</code> witness without mutating sealed history.
              </p>
              <button type="button" className="scenario-run-btn">
                Inject Late Reference
              </button>
            </div>

            <div className="scenario-card">
              <h4>Silent Feed & Stationary Clock Drill</h4>
              <p>
                Simulates stopped event-time watermark. Verifies that independent A5 Supervisor clock
                triggers expiry and avoids false-HEALTHY outcome.
              </p>
              <button type="button" className="scenario-run-btn">
                Inject Silent Feed Fault
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

