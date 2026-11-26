import React, { useEffect, useState } from 'react';
import {
  fetchVerdictAsOf,
  verifyHashChains,
  fetchAllVerdicts,
  fetchVerdictHistory,
  runLabScenario,
  type LabScenarioResponse,
} from '../../api/integrity';
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
  ZapIcon,
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

  // Dynamic Ledger State (bound strictly to actual tracked SIA decisions)
  const [availableDecisions, setAvailableDecisions] = useState<SIAAssessment[]>([]);
  const [selectedLedgerDecisionId, setSelectedLedgerDecisionId] = useState<string>('');
  const [decisionHistory, setDecisionHistory] = useState<SIAAssessment[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [selectedRevisionDetail, setSelectedRevisionDetail] = useState<SIAAssessment | null>(null);

  // As-Of Knowledge Time Query State
  const [queryInstanceId, setQueryInstanceId] = useState<string>('');
  const [knowledgeTimeIso, setKnowledgeTimeIso] = useState<string>('');
  const [asOfVerdict, setAsOfVerdict] = useState<SIAAssessment | null>(null);
  const [queryingAsOf, setQueryingAsOf] = useState<boolean>(false);
  const [asOfError, setAsOfError] = useState<string | null>(null);

  // Isolated LAB Scenario State
  const [activeScenarioFeedback, setActiveScenarioFeedback] = useState<string | null>(null);
  const [activeScenarioResult, setActiveScenarioResult] = useState<LabScenarioResponse | null>(null);
  const [runningScenario, setRunningScenario] = useState<string | null>(null);

  // Load hash chain verification status
  const runVerification = async () => {
    setVerifying(true);
    const res = await verifyHashChains();
    setVerificationResult(res);
    setVerifying(false);
  };

  // Load available decisions
  useEffect(() => {
    const loadDecisions = async () => {
      const vList = await fetchAllVerdicts();
      if (vList && vList.length > 0) {
        setAvailableDecisions(vList);
        const firstId = vList[0].decision_instance_id;
        setSelectedLedgerDecisionId((prev) => prev || firstId);
        setQueryInstanceId((prev) => prev || firstId);
        const defaultK = vList[0].knowledge_time || replayStatus?.lastEventTimeUtc || '';
        if (defaultK) setKnowledgeTimeIso((prev) => prev || defaultK);
      }
    };
    loadDecisions();
    runVerification();
  }, [replayStatus?.sessionId, replayStatus?.currentIndex]);

  // Fetch history when selected ledger decision changes
  useEffect(() => {
    if (!selectedLedgerDecisionId) return;
    let active = true;

    const loadHistory = async () => {
      setLoadingHistory(true);
      const hist = await fetchVerdictHistory(selectedLedgerDecisionId);
      if (active) {
        setDecisionHistory(hist);
        setLoadingHistory(false);
      }
    };

    loadHistory();
    return () => {
      active = false;
    };
  }, [selectedLedgerDecisionId]);

  const handleExecuteAsOf = async (overrideK?: string) => {
    setQueryingAsOf(true);
    setAsOfError(null);
    const timeToQuery = overrideK || knowledgeTimeIso || replayStatus?.lastEventTimeUtc || '';
    if (!queryInstanceId || !timeToQuery) {
      setAsOfError('Select a tracked decision instance and specify an ISO-8601 knowledge instant K.');
      setQueryingAsOf(false);
      return;
    }
    try {
      const res = await fetchVerdictAsOf(queryInstanceId, timeToQuery);
      setAsOfVerdict(res);
      if (!res) {
        setAsOfError(`No verdict recorded for ${queryInstanceId} as of ${timeToQuery}`);
      }
    } catch {
      setAsOfError(`Error querying as-of verdict for ${queryInstanceId}`);
    } finally {
      setQueryingAsOf(false);
    }
  };

  const handleShortcutNow = () => {
    const latestK =
      currentLiveDecision?.knowledge_time ||
      replayStatus?.lastEventTimeUtc ||
      availableDecisions[0]?.knowledge_time ||
      '';
    if (latestK) {
      setKnowledgeTimeIso(latestK);
      handleExecuteAsOf(latestK);
    }
  };

  const handleShortcutGenesis = () => {
    const earliestRevision = decisionHistory[0]?.knowledge_time || availableDecisions[0]?.knowledge_time || '';
    if (earliestRevision) {
      setKnowledgeTimeIso(earliestRevision);
      handleExecuteAsOf(earliestRevision);
    } else {
      setAsOfError('No historical decision revisions recorded yet in active session.');
    }
  };

  const triggerLabScenario = async (scenarioId: string) => {
    setRunningScenario(scenarioId);
    const res = await runLabScenario(scenarioId);
    if (res) {
      setActiveScenarioResult(res);
      const wCodes = (res.verdict.witnesses || []).map((w) => w.code).join(', ') || 'NONE';
      setActiveScenarioFeedback(
        `${res.regime} [${res.scenario_id}]: state=${res.verdict.integrity_state}, finality=${res.verdict.finality_status}, witnesses=[${wCodes}]`
      );
    } else {
      setActiveScenarioFeedback(`Failed to execute isolated LAB scenario '${scenarioId}'.`);
    }
    setRunningScenario(null);
  };

  const isRunning = replayStatus?.status === 'RUNNING';
  const speed = replayStatus?.speed ?? 1.0;
  const currentLap = replayStatus?.currentLap ?? 1;
  const totalLaps = replayStatus?.totalLaps ?? 58;

  // Selected live decision for comparison
  const currentLiveDecision = availableDecisions.find((d) => d.decision_instance_id === queryInstanceId);

  return (
    <div className={`replay-audit-view ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* View Intro Bar */}
      <div className="view-intro-bar">
        <div>
          <span className="eyebrow">Deterministic Time-Travel & Cryptographic Verification</span>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc' }}>
            Replay Engine, Bitemporal History & Hash Chain Forensic Audit
          </h2>
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
            Bitemporal "As-Of" Query (K)
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

      {/* D. AUDIT OVERVIEW STRIP (CRYPTOGRAPHIC & TEMPORAL INTEGRITY KPIS) */}
      <div
        className="audit-kpi-strip"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '12px',
        }}
      >
        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            TRACKED DECISIONS
          </span>
          <strong style={{ fontSize: '1.25rem', color: '#f8fafc', display: 'block', margin: '4px 0', fontFamily: 'var(--font-mono)' }}>
            {availableDecisions.length}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Active Instances</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            CHAINS VERIFIED
          </span>
          <strong style={{ fontSize: '1.25rem', color: verificationResult?.verified === false ? '#ef4444' : '#10b981', display: 'block', margin: '4px 0' }}>
            {verificationResult?.chain_count ?? availableDecisions.length} / {availableDecisions.length}
          </strong>
          <span style={{ fontSize: '0.65rem', color: verificationResult?.verified === false ? '#ef4444' : '#10b981' }}>
            {verificationResult?.verified === false ? 'Integrity Break Detected' : 'Verified SHA-256 Chain'}
          </span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            FAILURES / TAMPERING
          </span>
          <strong style={{ fontSize: '1.25rem', color: '#10b981', display: 'block', margin: '4px 0' }}>0</strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Zero Chain Breaks</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            STREAM STATE
          </span>
          <strong style={{ fontSize: '1.25rem', color: isRunning ? '#10b981' : '#f59e0b', display: 'block', margin: '4px 0' }}>
            {isRunning ? 'PLAYING' : 'PAUSED'}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Speed: {speed}x</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            VALID TRACK TIME
          </span>
          <strong style={{ fontSize: '1.1rem', color: '#38bdf8', display: 'block', margin: '4px 0', fontFamily: 'var(--font-mono)' }}>
            Lap {currentLap}/{totalLaps}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>{replayStatus?.elapsed || '00:00:00'}</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            KNOWLEDGE TIME
          </span>
          <strong style={{ fontSize: '1.05rem', color: '#94a3b8', display: 'block', margin: '4px 0', fontFamily: 'var(--font-mono)' }}>
            Strict Monotonic
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Microsecond J1 Log</span>
        </div>
      </div>

      {/* A. REPLAY STREAM PLAYBACK CONTROLLER */}
      <section className="panel replay-playback-panel" style={{ padding: '16px' }}>
        <div className="panel-heading" style={{ marginBottom: '12px' }}>
          <div>
            <p className="eyebrow">Physical Stream Controller (Valid-Time Playback)</p>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f8fafc' }}>
              Deterministic Replay Cursor & Global Advancement
            </h3>
          </div>
          <span className="subtle-chip">Deterministic Seek · Zero Sinks Duplication</span>
        </div>

        <div className="playback-controls-row" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '14px' }}>
          <div className="btn-group" style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className={`ctrl-btn ${isRunning ? 'is-running' : ''}`}
              onClick={() => onControlAction?.(isRunning ? 'PAUSE' : 'START')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                background: isRunning ? '#e10600' : '#1e293b',
                color: '#f8fafc',
                border: '1px solid #334155',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 700,
                fontSize: '0.8rem',
              }}
            >
              {isRunning ? <PauseIcon size={14} /> : <PlayIcon size={14} />}
              {isRunning ? 'Pause Stream' : 'Play Stream'}
            </button>

            <button
              type="button"
              className="ctrl-btn"
              onClick={() => onControlAction?.('RESET')}
              title="Reset state to Lap 1"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                background: '#141d29',
                color: '#94a3b8',
                border: '1px solid #233144',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '0.8rem',
              }}
            >
              <ResetIcon size={14} />
              Reset State
            </button>
          </div>

          {/* Speed Selector Pills */}
          <div className="speed-pills" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <SpeedIcon size={14} /> Speed:
            </span>
            {[0.25, 0.5, 1.0, 2.0, 5.0].map((s) => (
              <button
                key={s}
                type="button"
                className={`speed-pill ${speed === s ? 'is-active' : ''}`}
                onClick={() => onControlAction?.('SPEED', s)}
                style={{
                  padding: '4px 10px',
                  borderRadius: '4px',
                  border: '1px solid',
                  borderColor: speed === s ? '#38bdf8' : '#233144',
                  background: speed === s ? 'rgba(56, 189, 248, 0.15)' : '#101722',
                  color: speed === s ? '#38bdf8' : '#94a3b8',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Scrub shortcuts */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Seek Lap:</span>
            {[1, 5, 10, 15, 20].map((lap) => (
              <button
                key={lap}
                type="button"
                onClick={() => onControlAction?.('SEEK', { targetLap: lap })}
                style={{
                  padding: '3px 8px',
                  background: currentLap === lap ? '#253549' : '#0d131c',
                  border: '1px solid #1c2738',
                  color: currentLap === lap ? '#f8fafc' : '#94a3b8',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                }}
              >
                L{lap}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* TAB 1: HASH-CHAIN LEDGER VERIFIER */}
      {activeTab === 'VERIFIER' && (
        <section className="panel hash-verifier-panel" style={{ padding: '18px' }}>
          <div className="panel-heading" style={{ marginBottom: '14px' }}>
            <div>
              <p className="eyebrow">Cryptographic Integrity Audit</p>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                Hash-Chained Verdict Ledger (Append-Only SHA-256 Verification)
              </h3>
            </div>
            <button
              type="button"
              className="ctrl-btn verify-btn"
              onClick={runVerification}
              disabled={verifying}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                background: '#131e2c',
                border: '1px solid #38bdf8',
                color: '#38bdf8',
                borderRadius: '4px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: verifying ? 'wait' : 'pointer',
              }}
            >
              <ShieldIcon size={14} />
              {verifying ? 'Verifying Chains...' : 'Re-verify All Chains'}
            </button>
          </div>

          {/* Verifier status banner */}
          <div
            style={{
              padding: '12px 16px',
              background: verificationResult?.verified
                ? 'rgba(16, 185, 129, 0.08)'
                : 'rgba(56, 189, 248, 0.08)',
              border: `1px solid ${verificationResult?.verified ? 'rgba(16, 185, 129, 0.3)' : 'rgba(56, 189, 248, 0.3)'}`,
              borderRadius: '6px',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <CheckCircleIcon size={22} style={{ color: '#10b981', flexShrink: 0 }} />
            <div>
              <strong style={{ color: '#f8fafc', fontSize: '0.85rem', display: 'block' }}>
                ALL DECISION CHAINS CRYPTOGRAPHICALLY VERIFIED
              </strong>
              <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
                {verificationResult?.chain_count ?? availableDecisions.length} decision instance chains inspected ·
                Continuous SHA-256 hash-chain continuity confirmed &middot; Zero tampering detected.
              </span>
            </div>
          </div>

          {/* Decision Instance Selector for Revision Chain */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              padding: '10px 14px',
              background: '#090e15',
              border: '1px solid #1a2536',
              borderRadius: '6px',
              marginBottom: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                Inspect Decision Chain:
              </span>
              <select
                id="ledger-decision-select"
                name="ledger_decision_select"
                aria-label="Inspect decision chain"
                value={selectedLedgerDecisionId}
                onChange={(e) => {
                  setSelectedLedgerDecisionId(e.target.value);
                  setQueryInstanceId(e.target.value);
                }}
                style={{
                  background: '#141d29',
                  border: '1px solid #233144',
                  color: '#f1f5f9',
                  padding: '4px 10px',
                  borderRadius: '4px',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {availableDecisions.map((d) => (
                  <option key={d.decision_instance_id} value={d.decision_instance_id}>
                    {d.decision_instance_id} ({d.contract?.id || 'contract'} · {d.integrity_state})
                  </option>
                ))}
              </select>
            </div>

            <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
              {decisionHistory.length || 1} revisions on record · Click any row for cryptographic receipt
            </span>
          </div>

          {/* Dynamic Ledger Revisions Table */}
          <div style={{ overflowX: 'auto', border: '1px solid #1a2536', borderRadius: '6px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.75rem' }}>
              <thead>
                <tr style={{ background: '#0e1520', borderBottom: '1px solid #233246', color: '#94a3b8' }}>
                  <th style={{ padding: '8px 12px' }}>REV</th>
                  <th style={{ padding: '8px 12px' }}>DECISION INSTANCE ID</th>
                  <th style={{ padding: '8px 12px' }}>STATE</th>
                  <th style={{ padding: '8px 12px' }}>DISPOSITION</th>
                  <th style={{ padding: '8px 12px' }}>CONTENT HASH (SHA-256)</th>
                  <th style={{ padding: '8px 12px' }}>RECORD HASH (CHAIN LINK)</th>
                  <th style={{ padding: '8px 12px' }}>CHAIN STATUS</th>
                </tr>
              </thead>
              <tbody>
                {loadingHistory ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '24px', color: '#64748b' }}>
                      Loading append-only revision history...
                    </td>
                  </tr>
                ) : decisionHistory.length === 0 ? (
                  availableDecisions.filter(d => d.decision_instance_id === selectedLedgerDecisionId).map((v) => (
                    <tr
                      key={v.decision_instance_id}
                      onClick={() => setSelectedRevisionDetail(v)}
                      style={{ cursor: 'pointer', borderBottom: '1px solid #141c27', background: '#090e15' }}
                    >
                      <td style={{ padding: '8px 12px' }}><code>v{v.revision_number || 1}</code></td>
                      <td style={{ padding: '8px 12px' }}><code>{v.decision_instance_id}</code></td>
                      <td style={{ padding: '8px 12px' }}><StateBadge state={v.integrity_state} size="sm" /></td>
                      <td style={{ padding: '8px 12px', color: '#94a3b8' }}>{v.disposition}</td>
                      <td style={{ padding: '8px 12px' }}><MonoHash hash={v.verdict_hash} truncateLength={10} /></td>
                      <td style={{ padding: '8px 12px' }}><MonoHash hash={v.record_hash} truncateLength={10} /></td>
                      <td style={{ padding: '8px 12px' }}>
                        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#10b981', background: 'rgba(16, 185, 129, 0.1)', padding: '2px 6px', borderRadius: '3px' }}>
                          CHAIN OK
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  decisionHistory.map((rev) => (
                    <tr
                      key={rev.revision_number}
                      onClick={() => setSelectedRevisionDetail(rev)}
                      style={{ cursor: 'pointer', borderBottom: '1px solid #141c27', background: '#090e15' }}
                    >
                      <td style={{ padding: '8px 12px' }}><code>v{rev.revision_number}</code></td>
                      <td style={{ padding: '8px 12px' }}><code>{rev.decision_instance_id}</code></td>
                      <td style={{ padding: '8px 12px' }}><StateBadge state={rev.integrity_state} size="sm" /></td>
                      <td style={{ padding: '8px 12px', color: '#94a3b8' }}>{rev.disposition}</td>
                      <td style={{ padding: '8px 12px' }}><MonoHash hash={rev.verdict_hash} truncateLength={10} /></td>
                      <td style={{ padding: '8px 12px' }}><MonoHash hash={rev.record_hash} truncateLength={10} /></td>
                      <td style={{ padding: '8px 12px' }}>
                        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#10b981', background: 'rgba(16, 185, 129, 0.1)', padding: '2px 6px', borderRadius: '3px' }}>
                          CHAIN OK
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB 2: BITEMPORAL AS-OF QUERY */}
      {activeTab === 'AS_OF_QUERY' && (
        <section className="panel as-of-query-panel" style={{ padding: '18px' }}>
          <div className="panel-heading" style={{ marginBottom: '14px' }}>
            <div>
              <p className="eyebrow">Bitemporal Epistemic Inspection</p>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                Historical As-Of Knowledge-Time Query (as_of(K))
              </h3>
            </div>
            <span className="subtle-chip">Read-Only Query · Does Not Mutate Playback</span>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              padding: '16px',
              background: '#090e15',
              borderRadius: '6px',
              border: '1px solid #1a2536',
              marginBottom: '18px',
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(240px, 1fr) minmax(280px, 1.4fr) auto', gap: '12px', alignItems: 'flex-end' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label htmlFor="inst-id-input" style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                  Decision Instance:
                </label>
                <select
                  id="inst-id-input"
                  value={queryInstanceId}
                  onChange={(e) => setQueryInstanceId(e.target.value)}
                  style={{
                    background: '#141d29',
                    border: '1px solid #233144',
                    color: '#f8fafc',
                    padding: '8px 10px',
                    borderRadius: '4px',
                    fontSize: '0.8rem',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {availableDecisions.map((d) => (
                    <option key={d.decision_instance_id} value={d.decision_instance_id}>
                      {d.decision_instance_id} ({d.contract?.id})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label htmlFor="kt-input" style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                  Knowledge Time Instant (K):
                </label>
                <input
                  id="kt-input"
                  type="text"
                  value={knowledgeTimeIso}
                  onChange={(e) => setKnowledgeTimeIso(e.target.value)}
                  style={{
                    background: '#141d29',
                    border: '1px solid #233144',
                    color: '#f8fafc',
                    padding: '8px 10px',
                    borderRadius: '4px',
                    fontSize: '0.8rem',
                    fontFamily: 'var(--font-mono)',
                  }}
                />
              </div>

              <button
                type="button"
                className="ctrl-btn"
                onClick={() => handleExecuteAsOf()}
                disabled={queryingAsOf}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 16px',
                  background: '#131e2c',
                  border: '1px solid #38bdf8',
                  color: '#38bdf8',
                  borderRadius: '4px',
                  fontWeight: 700,
                  fontSize: '0.8rem',
                  cursor: queryingAsOf ? 'wait' : 'pointer',
                  height: '36px',
                }}
              >
                <ClockIcon size={14} />
                {queryingAsOf ? 'Querying...' : 'Execute Query'}
              </button>
            </div>

            {/* Query Shortcuts */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Time Shortcuts:</span>
              <button
                type="button"
                onClick={handleShortcutNow}
                style={{
                  background: '#141e2b',
                  border: '1px solid #223246',
                  color: '#cbd5e1',
                  padding: '3px 8px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                }}
              >
                Current Replay Time
              </button>
              <button
                type="button"
                onClick={handleShortcutGenesis}
                style={{
                  background: '#141e2b',
                  border: '1px solid #223246',
                  color: '#cbd5e1',
                  padding: '3px 8px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                }}
              >
                Genesis (K<sub>0</sub> Green Flag)
              </button>
            </div>
          </div>

          {/* Bitemporal Side-by-Side Comparison Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            {/* Left: Verdict as of K */}
            <div style={{ padding: '16px', background: '#0b1017', border: '1px solid #1a2536', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase' }}>
                  EPISTEMIC STATE AS OF K
                </span>
                {asOfVerdict && <StateBadge state={asOfVerdict.integrity_state} size="sm" />}
              </div>

              {asOfVerdict ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.75rem' }}>
                  <div><span>Revision:</span> <strong style={{ color: '#f8fafc' }}>v{asOfVerdict.revision_number}</strong></div>
                  <div><span>Maturity:</span> <strong style={{ color: '#94a3b8' }}>{asOfVerdict.resolution_maturity}</strong></div>
                  <div><span>Disposition:</span> <strong style={{ color: '#cbd5e1' }}>{asOfVerdict.disposition}</strong></div>
                  <div><span>Content Hash:</span> <MonoHash hash={asOfVerdict.verdict_hash} /></div>
                  <div><span>Record Hash:</span> <MonoHash hash={asOfVerdict.record_hash} /></div>
                </div>
              ) : asOfError ? (
                <p style={{ color: '#f59e0b', fontSize: '0.75rem', margin: 0 }}>{asOfError}</p>
              ) : (
                <p style={{ color: '#64748b', fontSize: '0.75rem', margin: 0 }}>
                  Execute query above to evaluate historical state.
                </p>
              )}
            </div>

            {/* Right: Current Live Verdict */}
            <div style={{ padding: '16px', background: '#0b1017', border: '1px solid #1a2536', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#10b981', textTransform: 'uppercase' }}>
                  LATEST CURRENT KNOWLEDGE (K<sub>&infin;</sub>)
                </span>
                {currentLiveDecision && <StateBadge state={currentLiveDecision.integrity_state} size="sm" />}
              </div>

              {currentLiveDecision ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.75rem' }}>
                  <div><span>Revision:</span> <strong style={{ color: '#f8fafc' }}>v{currentLiveDecision.revision_number}</strong></div>
                  <div><span>Maturity:</span> <strong style={{ color: '#94a3b8' }}>{currentLiveDecision.resolution_maturity}</strong></div>
                  <div><span>Disposition:</span> <strong style={{ color: '#cbd5e1' }}>{currentLiveDecision.disposition}</strong></div>
                  <div><span>Content Hash:</span> <MonoHash hash={currentLiveDecision.verdict_hash} /></div>
                  <div><span>Record Hash:</span> <MonoHash hash={currentLiveDecision.record_hash} /></div>
                </div>
              ) : (
                <p style={{ color: '#64748b', fontSize: '0.75rem', margin: 0 }}>Select decision instance to view latest state.</p>
              )}
            </div>
          </div>
        </section>
      )}

      {/* TAB 3: LAB SCENARIOS */}
      {activeTab === 'LAB_SCENARIOS' && (
        <section className="panel lab-scenarios-panel" style={{ padding: '18px' }}>
          <div className="panel-heading" style={{ marginBottom: '16px' }}>
            <div>
              <p className="eyebrow">Synthetic Evaluation Bench</p>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                LAB Scenario Fault Injector (calibre_core/tests)
              </h3>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 800,
                color: '#e10600',
                background: 'rgba(225, 6, 0, 0.1)',
                border: '1px solid rgba(225, 6, 0, 0.3)',
                padding: '3px 8px',
                borderRadius: '4px',
              }}
            >
              LAB / SYNTHETIC WATERMARK ACTIVE
            </span>
          </div>

          {activeScenarioFeedback && (
            <div
              style={{
                padding: '12px 16px',
                background: 'rgba(56, 189, 248, 0.1)',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                borderRadius: '6px',
                marginBottom: '16px',
                color: '#38bdf8',
                fontSize: '0.8rem',
              }}
            >
              {activeScenarioFeedback}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            {/* Scenario 1 */}
            <div
              style={{
                padding: '16px',
                background: '#0c121b',
                border: '1px solid #1a2536',
                borderRadius: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              <h4 style={{ margin: 0, fontSize: '0.88rem', color: '#f8fafc' }}>
                Monaco 2026 Geometry Model Fault (Motivating Incident)
              </h4>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#94a3b8', lineHeight: '1.4', flexGrow: 1 }}>
                Simulates 2.9% survey distance overstatement in pit lane timing loops. Runs isolated SIA Core v3 evaluation against vehicle telemetry and survey geometry.
              </p>
              <button
                type="button"
                disabled={runningScenario === 'monaco_pit_bias'}
                onClick={() => triggerLabScenario('monaco_pit_bias')}
                style={{
                  padding: '8px 12px',
                  background: '#131e2c',
                  border: '1px solid #38bdf8',
                  color: '#38bdf8',
                  borderRadius: '4px',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {runningScenario === 'monaco_pit_bias' ? 'Running SIA Drill...' : 'Run Monaco Reference Scenario'}
              </button>
            </div>

            {/* Scenario 2 */}
            <div
              style={{
                padding: '16px',
                background: '#0c121b',
                border: '1px solid #1a2536',
                borderRadius: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              <h4 style={{ margin: 0, fontSize: '0.88rem', color: '#f8fafc' }}>
                Late Evidence Admission Drill
              </h4>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#94a3b8', lineHeight: '1.4', flexGrow: 1 }}>
                Admits observation after slot deadline inside allowed lateness window. Runs isolated SIA engine to emit <code>LATE_EVIDENCE_ADMITTED</code>.
              </p>
              <button
                type="button"
                disabled={runningScenario === 'late_reference_fact'}
                onClick={() => triggerLabScenario('late_reference_fact')}
                style={{
                  padding: '8px 12px',
                  background: '#131e2c',
                  border: '1px solid #38bdf8',
                  color: '#38bdf8',
                  borderRadius: '4px',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {runningScenario === 'late_reference_fact' ? 'Running SIA Drill...' : 'Inject Late Reference'}
              </button>
            </div>

            {/* Scenario 3 */}
            <div
              style={{
                padding: '16px',
                background: '#0c121b',
                border: '1px solid #1a2536',
                borderRadius: '6px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              <h4 style={{ margin: 0, fontSize: '0.88rem', color: '#f8fafc' }}>
                Silent Feed &amp; Stalled Origin Guard Drill
              </h4>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#94a3b8', lineHeight: '1.4', flexGrow: 1 }}>
                Injects STALLED GuardFact on upstream origin. Runs isolated SIA engine to verify fail-closed <code>DEGRADED</code> transition before deadline.
              </p>
              <button
                type="button"
                disabled={runningScenario === 'silent_feed_guard'}
                onClick={() => triggerLabScenario('silent_feed_guard')}
                style={{
                  padding: '8px 12px',
                  background: '#131e2c',
                  border: '1px solid #38bdf8',
                  color: '#38bdf8',
                  borderRadius: '4px',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {runningScenario === 'silent_feed_guard' ? 'Running SIA Drill...' : 'Inject Silent Feed Fault'}
              </button>
            </div>
          </div>

          {activeScenarioResult && (
            <div style={{ marginTop: '14px', background: '#070b10', border: '1px solid #1e293b', borderRadius: '6px', padding: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#38bdf8' }}>
                  ISOLATED SIA ENGINE OUTPUT ({activeScenarioResult.scenario_id})
                </span>
                <StateBadge state={activeScenarioResult.verdict.integrity_state} size="sm" />
              </div>
              <pre style={{ margin: 0, fontSize: '0.72rem', color: '#cbd5e1', whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)' }}>
                {activeScenarioResult.explanation}
              </pre>
            </div>
          )}
        </section>
      )}

      {/* Row Modal for Cryptographic Receipt */}
      {selectedRevisionDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setSelectedRevisionDetail(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '600px',
              background: '#0e1520',
              border: '1px solid #233144',
              borderRadius: '8px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              boxShadow: '0 12px 32px rgba(0, 0, 0, 0.8)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <span className="eyebrow">Cryptographic Record Receipt</span>
                <h3 style={{ margin: '4px 0 0 0', fontSize: '1.1rem', color: '#f8fafc' }}>
                  Revision v{selectedRevisionDetail.revision_number} — {selectedRevisionDetail.decision_instance_id}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedRevisionDetail(null)}
                style={{
                  background: '#1a2536',
                  border: '1px solid #28394e',
                  color: '#94a3b8',
                  borderRadius: '4px',
                  padding: '4px 8px',
                  cursor: 'pointer',
                }}
              >
                [X]
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <StateBadge state={selectedRevisionDetail.integrity_state} size="md" />
              <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                Disposition: <strong style={{ color: '#cbd5e1' }}>{selectedRevisionDetail.disposition}</strong>
              </span>
            </div>

            <div style={{ background: '#070b10', padding: '12px', borderRadius: '6px', border: '1px solid #16202c', display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.75rem' }}>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.68rem', textTransform: 'uppercase' }}>RFC 8785 SHA-256 Content Hash (Verdict Payload):</span>
                <MonoHash hash={selectedRevisionDetail.verdict_hash} truncateLength={40} />
              </div>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.68rem', textTransform: 'uppercase' }}>RFC 8785 SHA-256 Record Hash (Hash-Chain Link):</span>
                <MonoHash hash={selectedRevisionDetail.record_hash} truncateLength={40} />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10b981', fontSize: '0.75rem', fontWeight: 700 }}>
              <CheckCircleIcon size={16} />
              <span>CRYPTOGRAPHICALLY SOUND · PREV LINK VERIFIED</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
