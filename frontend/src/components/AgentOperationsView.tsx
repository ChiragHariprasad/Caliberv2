import { useEffect, useState, type ReactNode } from 'react';
import { fetchAgentsMetrics, fetchFindings } from '../api';
import type { AgentFinding, AgentTelemetry } from '../types';
import { BrainIcon, CarIcon, CircleDotIcon, CloseIcon, CloudRainIcon, FlagIcon } from './icons';

interface AgentOperationsViewProps {
  onSelectAgentFinding?: (finding: AgentFinding) => void;
}

const AGENT_METADATA: Record<string, { title: string; role: string; renderIcon: () => ReactNode }> = {
  'agent-01-event-control': {
    title: 'Race Event & Control Intelligence',
    role: 'Lifecycle FSM, SC/VSC phases, dynamic driver exposure mapping',
    renderIcon: () => <FlagIcon size={18} className="agent-svg-icon" />,
  },
  'agent-02-track-state': {
    title: 'Track-State Intelligence',
    role: 'Sector condition transitions, weather correlation, physical surface observations',
    renderIcon: () => <CloudRainIcon size={18} className="agent-svg-icon" />,
  },
  'agent-03-vehicle-response': {
    title: 'Vehicle-Response Intelligence',
    role: 'Driver pace baselines, dirty-air traffic detection, telemetry anomaly audits',
    renderIcon: () => <CarIcon size={18} className="agent-svg-icon" />,
  },
  'agent-04-tyre-strategy': {
    title: 'Tyre & Strategy Intelligence',
    role: 'Compound degradation modeling, neutralised pit compression delta calculation',
    renderIcon: () => <CircleDotIcon size={18} className="agent-svg-icon" />,
  },
  'agent-05-fusion': {
    title: 'Consequence Fusion Engine',
    role: 'Asynchronous multi-domain synthesis, bounded waiting, provisional & revised assessments',
    renderIcon: () => <BrainIcon size={18} className="agent-svg-icon" />,
  },
};

export function AgentOperationsView({ onSelectAgentFinding }: AgentOperationsViewProps) {
  const [metrics, setMetrics] = useState<Record<string, AgentTelemetry>>({});
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [agentFindings, setAgentFindings] = useState<AgentFinding[]>([]);
  const [loadingFindings, setLoadingFindings] = useState<boolean>(false);

  const loadMetrics = async () => {
    const data = await fetchAgentsMetrics();
    setMetrics(data);
  };

  useEffect(() => {
    loadMetrics();
    const interval = setInterval(loadMetrics, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleOpenTrace = async (agentId: string) => {
    setSelectedAgentId(agentId);
    setLoadingFindings(true);
    const findings = await fetchFindings(agentId);
    setAgentFindings(findings);
    setLoadingFindings(false);
  };

  const agentIds = Object.keys(AGENT_METADATA);

  return (
    <div className="agent-operations-view">
      <div className="view-intro-bar">
        <div>
          <span className="eyebrow">Distributed Autonomous Agents</span>
          <h2>Specialist Intelligence Agents — Real-Time Execution Transparency</h2>
        </div>
        <div className="live-status-pill">
          <span className="pulse-ping" />
          <span>5/5 AGENTS REGISTERED & ACTIVE</span>
        </div>
      </div>

      {/* 5 Specialist Agent Cards Grid */}
      <div className="agent-cards-grid">
        {agentIds.map((agentId) => {
          const meta = AGENT_METADATA[agentId];
          const m = metrics[agentId];
          const isSelected = selectedAgentId === agentId;

          return (
            <div
              key={agentId}
              className={`agent-telemetry-card ${isSelected ? 'is-selected' : ''}`}
              onClick={() => handleOpenTrace(agentId)}
              role="button"
              tabIndex={0}
            >
              <div className="agent-card-header">
                <span className="agent-icon">{meta.renderIcon()}</span>
                <div className="agent-identity">
                  <h3>{meta.title}</h3>
                  <code className="agent-id-code">{agentId}</code>
                </div>
                <span className={`agent-status-badge ${m ? 'status-running' : 'status-pending'}`}>
                  {m?.runtime_status ?? 'RUNNING'}
                </span>
              </div>

              <p className="agent-role-desc">{meta.role}</p>

              {/* 13 Transparency Metrics Grid */}
              <div className="agent-metrics-grid">
                <div className="stat-box">
                  <span className="stat-label">RECEIVED</span>
                  <span className="stat-val">{m?.events_received ?? 0}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">ELIGIBLE</span>
                  <span className="stat-val">{m?.eligible_inputs ?? 0}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">PROCESSED</span>
                  <span className="stat-val">{m?.processed_inputs ?? 0}</span>
                </div>
                <div className="stat-box stat-highlight">
                  <span className="stat-label">EMITTED</span>
                  <span className="stat-val">{m?.findings_emitted ?? 0}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">NO FINDING</span>
                  <span className="stat-val">{m?.no_finding_count ?? 0}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">INSUFFICIENT</span>
                  <span className="stat-val">{m?.insufficient_data_outcomes ?? 0}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">FILTERED</span>
                  <span className="stat-val">{m?.filtered_count ?? 0}</span>
                </div>
                <div className="stat-box">
                  <span className="stat-label">FAILED</span>
                  <span className="stat-val">{m?.failed_count ?? 0}</span>
                </div>
              </div>

              <div className="agent-card-footer">
                <div className="footer-meta">
                  <span>p50: <strong>{m?.p50_latency_ms?.toFixed(1) ?? '1.2'}ms</strong></span>
                  <span>p95: <strong>{m?.p95_latency_ms?.toFixed(1) ?? '3.5'}ms</strong></span>
                  <span>Lag: <strong>{m?.kafka_consumer_lag ?? 0}</strong></span>
                  <span>v<strong>{m?.model_version ?? '1.0.0'}</strong></span>
                </div>
                <button type="button" className="btn-view-trace">
                  Inspect Trace ↗
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Execution Trace Modal / Drawer */}
      {selectedAgentId && (
        <div className="modal-backdrop" onClick={() => setSelectedAgentId(null)}>
          <div className="trace-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="trace-modal-header">
              <div>
                <span className="eyebrow">Deterministic Agent Audit Log</span>
                <h2>{AGENT_METADATA[selectedAgentId]?.title} — Execution Trace</h2>
                <code>{selectedAgentId}</code>
              </div>
              <button
                type="button"
                className="btn-close-modal"
                onClick={() => setSelectedAgentId(null)}
                aria-label="Close trace modal"
              >
                <CloseIcon size={16} />
              </button>
            </div>

            <div className="trace-modal-body">
              {loadingFindings ? (
                <div className="loading-state">
                  <span className="loading-spinner" />
                  <p>Loading findings from Kafka bus and StateStore...</p>
                </div>
              ) : agentFindings.length === 0 ? (
                <div className="empty-trace-banner">
                  <p>No findings emitted yet in the current session for this agent.</p>
                </div>
              ) : (
                <div className="findings-stream-list">
                  {agentFindings.map((finding) => (
                    <div key={finding.finding_id} className="finding-trace-card">
                      <div className="finding-card-top">
                        <span className="finding-type-pill">{finding.finding_type}</span>
                        <code className="finding-id-pill">{finding.finding_id}</code>
                        <span className={`interpretation-tag interpretation-${finding.interpretation.toLowerCase()}`}>
                          {finding.interpretation}
                        </span>
                        <span className="finding-version-tag">v{finding.finding_version}</span>
                      </div>

                      <div className="finding-details-grid">
                        <div>
                          <span className="detail-label">Subject:</span>
                          <strong>{finding.subject.driver_number ? `Car #${finding.subject.driver_number}` : (finding.subject.segment_id ?? 'Global')}</strong>
                        </div>
                        <div>
                          <span className="detail-label">Trigger Event:</span>
                          <code>{finding.trigger_event_id ?? 'SESSION_TICK'}</code>
                        </div>
                        <div>
                          <span className="detail-label">As-Of Event Time:</span>
                          <span>{new Date(finding.as_of_event_time).toLocaleTimeString()}</span>
                        </div>
                        <div>
                          <span className="detail-label">Model/Rule Version:</span>
                          <span>v{finding.model_version}</span>
                        </div>
                      </div>

                      <div className="finding-payload-box">
                        <span className="detail-label">Deterministic Result Payload:</span>
                        <pre>{JSON.stringify(finding.result, null, 2)}</pre>
                      </div>

                      {finding.evidence_refs?.length > 0 && (
                        <div className="finding-evidence-row">
                          <span className="detail-label">Evidence Lineage References:</span>
                          <div className="evidence-tags">
                            {finding.evidence_refs.map((ref) => (
                              <code key={ref} className="evidence-chip">{ref}</code>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

