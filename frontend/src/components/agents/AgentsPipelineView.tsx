import React, { useEffect, useState } from 'react';
import { fetchAgentsMetrics, fetchFindings, fetchPipelineStatus } from '../../api';
import type { AgentFinding, AgentTelemetry, PipelineStatusData } from '../../types';
import {
  BrainIcon,
  CarIcon,
  CircleDotIcon,
  ClockIcon,
  CloudRainIcon,
  CpuIcon,
  FlagIcon,
  ScaleIcon,
  ShieldIcon,
  ZapIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  InfoIcon,
} from '../icons';
import { MonoHash } from '../shared/MonoHash';
import { PipelineLabView } from '../PipelineLabView';

interface AgentMeta {
  id: string;
  title: string;
  role: string;
  type: 'TACTICAL' | 'FUSION' | 'EVALUATOR' | 'INGEST' | 'SEQUENCER';
  inputs: string[];
  outputs: string[];
  responsibilities: string[];
  icon: string;
}

const AGENTS_METADATA: Record<string, AgentMeta> = {
  'agent-01-event-control': {
    id: 'agent-01-event-control',
    title: 'Race Event & Control Intelligence',
    role: 'Lifecycle FSM, SC/VSC phases, dynamic driver exposure mapping',
    type: 'TACTICAL',
    inputs: ['pulse.raw.race_control.v1', 'pulse.norm.race_events.v1'],
    outputs: ['pulse.agents.event_control.v1'],
    responsibilities: [
      'Track-wide and sector-local flag state change machine (GREEN, YELLOW, RED, SC, VSC)',
      'Pit lane open/closed condition tracking and speed limit regime mapping',
      'Safety car deployment phase classification and driver delta baseline calculation',
    ],
    icon: 'flag',
  },
  'agent-02-track-state': {
    id: 'agent-02-track-state',
    title: 'Track-State Intelligence',
    role: 'Sector condition transitions, weather correlation, physical surface observations',
    type: 'TACTICAL',
    inputs: ['pulse.raw.weather.v1', 'pulse.raw.track_status.v1', 'pulse.norm.track_segments.v1'],
    outputs: ['pulse.agents.track_state.v1'],
    responsibilities: [
      'Continuous micro-sector grip coefficient and wetness index evaluation',
      'Ambient & track temperature thermal gradients with rainfall intensity',
      'Yellow-flag hazard zone spatial delineation and clear conditions detection',
    ],
    icon: 'rain',
  },
  'agent-03-vehicle-response': {
    id: 'agent-03-vehicle-response',
    title: 'Vehicle-Response Intelligence',
    role: 'Driver pace baselines, dirty-air traffic detection, telemetry anomaly audits',
    type: 'TACTICAL',
    inputs: ['pulse.raw.timing_laps.v1', 'pulse.raw.timing_positions.v1', 'pulse.norm.driver_laps.v1'],
    outputs: ['pulse.agents.vehicle_response.v1'],
    responsibilities: [
      'CAN-bus / telemetry sanity checking (throttle/brake exclusivity, speed vs RPM)',
      'Circuit-adapted clean-air pace baselines and dirty-air gap monitoring',
      'Sector delta pace baseline anomaly audits and outlier exclusion',
    ],
    icon: 'car',
  },
  'agent-04-tyre-strategy': {
    id: 'agent-04-tyre-strategy',
    title: 'Tyre & Strategy Intelligence',
    role: 'Compound degradation modeling, neutralised pit compression delta calculation',
    type: 'TACTICAL',
    inputs: ['pulse.raw.pit_events.v1', 'pulse.raw.tyres_stints.v1', 'pulse.norm.tyre_stints.v1'],
    outputs: ['pulse.agents.tyre_strategy.v1'],
    responsibilities: [
      'Fuel-mass compensated stint regression with explicit uncertainty bands',
      'Pit lane loss time calculation under green vs neutralized delta conditions',
      'Compound crossover timing estimations and undercut / overcut threat forecasting',
    ],
    icon: 'tyre',
  },
  'agent-05-fusion': {
    id: 'agent-05-fusion',
    title: 'Consequence Fusion Engine',
    role: 'Asynchronous multi-domain synthesis, bounded waiting, provisional & revised assessments',
    type: 'FUSION',
    inputs: ['pulse.agents.*', 'pulse.norm.*'],
    outputs: ['pulse.intel.assessments.v1', 'pulse.intel.alerts.v1'],
    responsibilities: [
      'Asynchronous bounded joining of cross-domain findings across tactical agents',
      'Evidence-grounded tactical consequence synthesis with conflict surfacing',
      'Provisional and revised impact assessment versioning',
    ],
    icon: 'brain',
  },
  'agent-06-integrity': {
    id: 'agent-06-integrity',
    title: 'J2 Evaluator Bridge (SIA Core v3)',
    role: 'Scoped Integrity Algebra kernel, bitemporal fact admission, RFC 8785 SHA-256 hash chaining',
    type: 'EVALUATOR',
    inputs: ['pulse.raw.*', 'pulse.norm.*', 'pulse.agents.*'],
    outputs: ['pulse.integrity.verdicts.v1', 'pulse.integrity.audit.v1'],
    responsibilities: [
      'Pure Scoped Integrity Algebra (SIA) evaluation over 4-state lattice (DEGRADED < UNKNOWN < SUSPECT < HEALTHY)',
      'Pattern P3 guard-band margin detection and source-independence depth checks',
      'Append-only bitemporal knowledge ledger updates and RFC 8785 Canonical SHA-256 hash-chain linkage',
    ],
    icon: 'shield',
  },
};

const TARGET_ARCHETYPES = [
  {
    id: 'A1_measurement',
    name: 'A1: Measurement Archetype (Timing Agent)',
    file: 'calibre_core/agents/timing.py',
    emits: 'Lap records, sector times, timing passages, speed traps, numbering regressions',
    rule: 'Rule AR-1: Pure observation; never evaluates integrity',
    scope: 'Session & Car Timing',
    contracts: ['C01_lap_time_consistency', 'C02_speed_trap_plausibility'],
    testRef: 'calibre_core/tests/test_agents_and_contracts.py:test_a1_timing_emits_pure_observations',
  },
  {
    id: 'A2_telemetry',
    name: 'A2: Asset Telemetry Archetype (Vehicle Telemetry Agent)',
    file: 'calibre_core/agents/telemetry.py',
    emits: 'Windowed speed, integrated distance, throttle/brake pedal exclusivity, >2.0g deceleration checks',
    rule: 'Rule AR-1: Pure observation; never evaluates integrity',
    scope: 'ECU CAN-Bus & Sensor Bus',
    contracts: ['C03_pit_speed_integrity', 'C06_drs_activation_validity'],
    testRef: 'calibre_core/tests/test_agents_and_contracts.py:test_a2_telemetry_observation_bounds',
  },
  {
    id: 'A3_spatial',
    name: 'A3: Spatial & Geometry Archetype (Spatial Agent)',
    file: 'calibre_core/agents/spatial.py',
    emits: 'Gate crossing interpolation, trajectory path lengths, effective-dated circuit geometry references',
    rule: 'Rule AR-1: Pure observation; never evaluates integrity',
    scope: 'Circuit Coordinates & Micro-Sectors',
    contracts: ['C03_pit_speed_integrity', 'C07_track_limits_baseline'],
    testRef: 'calibre_core/tests/test_agents_and_contracts.py:test_a3_spatial_spline_interpolation',
  },
  {
    id: 'A4_context',
    name: 'A4: Session Context Archetype (Session Context Agent)',
    file: 'calibre_core/agents/context.py',
    emits: 'Race control message lifecycle, session state intervals, participant status, rule limits',
    rule: 'Rule AR-1: Pure observation; never evaluates integrity',
    scope: 'Stewarding & Race Direction',
    contracts: ['C04_vsc_delta_compliance', 'C08_flag_adherence_check'],
    testRef: 'calibre_core/tests/test_agents_and_contracts.py:test_a4_context_fsm_integrity',
  },
  {
    id: 'A5_supervisor',
    name: 'A5: Independent Feed Supervisor Archetype',
    file: 'calibre_core/agents/supervisor.py',
    emits: 'Monotonic clock ticks, heartbeat cadence, STALLED/RESUMED guards, schema drift',
    rule: 'Independent Failure Domain: Separate hardware tap & unshared clock',
    scope: 'Streaming Pipeline Health',
    contracts: ['C09_ingestion_heartbeat_supervisor'],
    testRef: 'calibre_core/tests/test_agents_and_contracts.py:test_a5_supervisor_stall_detection',
  },
];

export const AgentsPipelineView: React.FC<{ decisionCount?: number }> = ({ decisionCount }) => {
  const [activeTab, setActiveTab] = useState<'RUNTIME' | 'TARGET_ARCHETYPES' | 'TOPOLOGY' | 'PIPELINE_LAB'>('RUNTIME');
  const [metrics, setMetrics] = useState<Record<string, AgentTelemetry>>({});
  const [pipelineData, setPipelineData] = useState<PipelineStatusData | null>(null);
  const [loaded, setLoaded] = useState<boolean>(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('agent-01-event-control');
  const [findings, setFindings] = useState<AgentFinding[]>([]);
  const [loadingFindings, setLoadingFindings] = useState<boolean>(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    let inFlight = false;
    const load = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const [m, p] = await Promise.all([fetchAgentsMetrics(), fetchPipelineStatus()]);
        if (!active) return;
        if (m) setMetrics(m);
        if (p) setPipelineData(p);
        setLoaded(true);
      } finally {
        inFlight = false;
      }
    };
    load();
    const interval = setInterval(load, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const handleSelectAgent = async (agentId: string, openDrawer = true) => {
    setSelectedAgentId(agentId);
    if (openDrawer) setIsDrawerOpen(true);
    setLoadingFindings(true);
    const f = await fetchFindings(agentId);
    setFindings(f);
    setLoadingFindings(false);
  };

  // Initial load of findings for default selected agent
  useEffect(() => {
    if (selectedAgentId) {
      handleSelectAgent(selectedAgentId, false);
    }
  }, []);

  // Compute aggregated runtime KPIs
  const agentEntries = Object.entries(metrics);
  const totalProcessedInputs = agentEntries.reduce((acc, [_, m]) => acc + (m.processed_inputs || 0), 0);
  const totalFindingsEmitted = agentEntries.reduce((acc, [_, m]) => acc + (m.findings_emitted || 0), 0);
  const totalFailures = agentEntries.reduce((acc, [_, m]) => acc + (m.failed_count || 0), 0);
  const errorRatePct = totalProcessedInputs > 0 ? ((totalFailures / totalProcessedInputs) * 100).toFixed(2) : '0.0';
  const activeAgentCount = pipelineData?.agents?.total_registered ?? agentEntries.length;
  const latencies = agentEntries.map(([_, m]) => m.p95_latency_ms).filter(Boolean) as number[];
  const avgP95 = latencies.length > 0 ? latencies.reduce((a, b) => a + b, 0) / latencies.length : null;
  const isKafkaOnline = pipelineData?.kafka?.connected ?? false;
  const transportMode = loaded ? (pipelineData?.kafka?.transport ?? 'MEMORY') : 'CONNECTING...';
  const flinkStatus = loaded ? (pipelineData?.flink?.status ?? 'FALLBACK') : 'CHECKING...';
  const liveDecisionCount = decisionCount ?? 0;

  const selectedAgentMeta = AGENTS_METADATA[selectedAgentId] || AGENTS_METADATA['agent-01-event-control'];
  const selectedAgentMetric = metrics[selectedAgentId];

  return (
    <div className="agents-pipeline-view" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header & Tab Navigation */}
      <div className="view-intro-bar">
        <div>
          <span className="eyebrow">Distributed Autonomous Agents & Streaming Backbone</span>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc' }}>
            System Observability: Active Runtime Agents & SIA Pipeline
          </h2>
        </div>

        <div className="domain-tabs">
          <button
            type="button"
            className={`domain-tab ${activeTab === 'RUNTIME' ? 'active' : ''}`}
            onClick={() => setActiveTab('RUNTIME')}
          >
            Orchestration & Runtime (6 Active)
          </button>
          <button
            type="button"
            className={`domain-tab ${activeTab === 'TARGET_ARCHETYPES' ? 'active' : ''}`}
            onClick={() => setActiveTab('TARGET_ARCHETYPES')}
          >
            Target Archetypes (A1–A5 Specification)
          </button>
          <button
            type="button"
            className={`domain-tab ${activeTab === 'TOPOLOGY' ? 'active' : ''}`}
            onClick={() => setActiveTab('TOPOLOGY')}
          >
            Transport & Normalizer Diagnostics
          </button>
          <button
            type="button"
            className={`domain-tab ${activeTab === 'PIPELINE_LAB' ? 'active' : ''}`}
            onClick={() => setActiveTab('PIPELINE_LAB')}
          >
            Verification & Lineage Lab
          </button>
        </div>
      </div>

      {/* A. RUNTIME KPI SUMMARY STRIP (8 DYNAMIC SYSTEM METRICS) */}
      <div
        className="pipeline-kpi-strip"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '12px',
        }}
      >
        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            REGISTERED AGENTS
          </span>
          <strong style={{ fontSize: '1.25rem', color: '#10b981', display: 'block', margin: '4px 0' }}>
            {loaded ? `${activeAgentCount} Active` : '—'}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Specialists + SIA Engine</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            REASONING BRIDGE
          </span>
          <strong style={{ fontSize: '1.25rem', color: '#38bdf8', display: 'block', margin: '4px 0' }}>SIA Core v3</strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>J2 Evaluator Host</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            PROCESSED INPUTS
          </span>
          <strong style={{ fontSize: '1.25rem', color: '#f8fafc', display: 'block', margin: '4px 0', fontFamily: 'var(--font-mono)' }}>
            {loaded ? totalProcessedInputs.toLocaleString() : '—'}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Events Ingested</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            FINDINGS EMITTED
          </span>
          <strong style={{ fontSize: '1.25rem', color: '#f59e0b', display: 'block', margin: '4px 0', fontFamily: 'var(--font-mono)' }}>
            {loaded ? totalFindingsEmitted.toLocaleString() : '—'}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Synthesized Evidence</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            LATENCY p95
          </span>
          <strong style={{ fontSize: '1.25rem', color: '#38bdf8', display: 'block', margin: '4px 0', fontFamily: 'var(--font-mono)' }}>
            {loaded && avgP95 !== null ? `${avgP95.toFixed(1)}ms` : '—'}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Bounded Response</span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            SYSTEM ERROR RATE
          </span>
          <strong style={{ fontSize: '1.25rem', color: totalFailures === 0 ? '#10b981' : '#ef4444', display: 'block', margin: '4px 0' }}>
            {loaded ? `${errorRatePct}%` : '—'}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>
            {loaded ? `${totalFailures} Pipeline Failures` : 'Evaluating...'}
          </span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            EVENT TRANSPORT
          </span>
          <strong style={{ fontSize: '1.1rem', color: isKafkaOnline ? '#10b981' : '#38bdf8', display: 'block', margin: '4px 0' }}>
            {transportMode}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>
            {!loaded ? 'Probing Cluster...' : (isKafkaOnline ? 'Kafka Clustered' : 'In-Process Bus')}
          </span>
        </div>

        <div className="kpi-mini-card panel" style={{ padding: '12px 14px' }}>
          <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            STREAM NORMALIZER
          </span>
          <strong style={{ fontSize: '1.1rem', color: flinkStatus === 'RUNNING' ? '#10b981' : '#94a3b8', display: 'block', margin: '4px 0' }}>
            {!loaded ? 'CHECKING...' : (flinkStatus === 'RUNNING' ? 'APACHE FLINK' : 'IN-PROCESS J1')}
          </strong>
          <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Monotonic Knowledge Time</span>
        </div>
      </div>

      {/* TAB 1: RUNTIME OBSERVABILITY & INTERACTIVE ORCHESTRATION DIAGRAM */}
      {activeTab === 'RUNTIME' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* B. INTERACTIVE AGENT ORCHESTRATION SVG DIAGRAM */}
          <section className="panel pipeline-orchestration-panel" style={{ padding: '18px' }}>
            <div className="panel-heading" style={{ marginBottom: '16px' }}>
              <div>
                <p className="eyebrow">Dataflow Topology & Stage Coupling</p>
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                  Interactive Agent Orchestration & Reasoning Pipeline
                </h3>
              </div>
              <span className="subtle-chip" style={{ fontSize: '0.7rem' }}>
                Click Any Node to Inspect Diagnostics & Findings
              </span>
            </div>

            {/* SVG Dataflow Diagram */}
            <div
              style={{
                width: '100%',
                background: '#090e15',
                border: '1px solid #1a2636',
                borderRadius: '8px',
                padding: '20px 10px',
                overflowX: 'auto',
              }}
            >
              <svg viewBox="0 0 1000 360" style={{ width: '100%', minWidth: '780px', height: 'auto', display: 'block' }}>
                <defs>
                  <linearGradient id="glowLine" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#e10600" stopOpacity="0.4" />
                    <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.8" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.4" />
                  </linearGradient>
                  <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 8 5 L 0 9 z" fill="#475569" />
                  </marker>
                  <marker id="arrowActive" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1 L 8 5 L 0 9 z" fill="#38bdf8" />
                  </marker>
                </defs>

                {/* Connecting lines */}
                {/* Ingest to Normalizer */}
                <line x1="140" y1="180" x2="210" y2="180" stroke="#334155" strokeWidth="2" markerEnd="url(#arrow)" />

                {/* Normalizer to 5 Tactical Agents */}
                <path d="M 330 180 L 370 180 L 370 60 L 410 60" fill="none" stroke="#334155" strokeWidth="2" markerEnd="url(#arrow)" />
                <path d="M 330 180 L 370 180 L 370 120 L 410 120" fill="none" stroke="#334155" strokeWidth="2" markerEnd="url(#arrow)" />
                <path d="M 330 180 L 410 180" fill="none" stroke="#334155" strokeWidth="2" markerEnd="url(#arrow)" />
                <path d="M 330 180 L 370 180 L 370 240 L 410 240" fill="none" stroke="#334155" strokeWidth="2" markerEnd="url(#arrow)" />
                <path d="M 330 180 L 370 180 L 370 300 L 410 300" fill="none" stroke="#334155" strokeWidth="2" markerEnd="url(#arrow)" />

                {/* Tactical Agents to Consequence Fusion & J2 Evaluator */}
                <path d="M 590 60 L 630 60 L 630 150 L 670 150" fill="none" stroke="#334155" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <path d="M 590 120 L 630 120 L 630 160 L 670 160" fill="none" stroke="#334155" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <path d="M 590 180 L 670 180" fill="none" stroke="#334155" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <path d="M 590 240 L 630 240 L 630 200 L 670 200" fill="none" stroke="#334155" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <path d="M 590 300 L 630 300 L 630 210 L 670 210" fill="none" stroke="#334155" strokeWidth="1.5" markerEnd="url(#arrow)" />

                {/* Evaluator to Sinks */}
                <line x1="850" y1="180" x2="900" y2="180" stroke="#38bdf8" strokeWidth="2" strokeDasharray="4 2" markerEnd="url(#arrowActive)" />

                {/* Node 1: Raw Ingestion */}
                <g transform="translate(10, 140)" style={{ cursor: 'pointer' }}>
                  <rect width="130" height="80" rx="6" fill="#111822" stroke="#253549" strokeWidth="1.5" />
                  <text x="65" y="24" textAnchor="middle" fill="#94a3b8" fontSize="10" fontWeight="700">RAW INGESTION</text>
                  <text x="65" y="44" textAnchor="middle" fill="#f8fafc" fontSize="11" fontWeight="800">{isKafkaOnline ? 'Kafka Streams' : 'Capture & Sim'}</text>
                  <text x="65" y="62" textAnchor="middle" fill="#64748b" fontSize="9">{isKafkaOnline ? '7 Raw Topics' : 'Event Envelope'}</text>
                </g>

                {/* Node 2: Stream Normalizer & Canonical Sequencer */}
                <g transform="translate(210, 140)" style={{ cursor: 'pointer' }}>
                  <rect width="120" height="80" rx="6" fill="#111822" stroke="#253549" strokeWidth="1.5" />
                  <text x="60" y="24" textAnchor="middle" fill="#38bdf8" fontSize="10" fontWeight="700">J1 NORMALIZER</text>
                  <text x="60" y="44" textAnchor="middle" fill="#f8fafc" fontSize="11" fontWeight="800">Stream Sequencer</text>
                  <text x="60" y="62" textAnchor="middle" fill="#10b981" fontSize="9">Monotonic Ticks</text>
                </g>

                {/* Tactical Agents Column (5 Parallel Nodes) */}
                {/* Agent 1 */}
                <g
                  transform="translate(410, 36)"
                  onClick={() => handleSelectAgent('agent-01-event-control')}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    width="180"
                    height="48"
                    rx="6"
                    fill={selectedAgentId === 'agent-01-event-control' ? '#18273d' : '#111822'}
                    stroke={selectedAgentId === 'agent-01-event-control' ? '#38bdf8' : '#253549'}
                    strokeWidth={selectedAgentId === 'agent-01-event-control' ? 2 : 1}
                  />
                  <circle cx="20" cy="24" r="5" fill="#10b981" />
                  <text x="32" y="22" fill="#f8fafc" fontSize="11" fontWeight="700">Race Event Control</text>
                  <text x="32" y="36" fill="#94a3b8" fontSize="9">agent-01 · FSM Flags</text>
                </g>

                {/* Agent 2 */}
                <g
                  transform="translate(410, 96)"
                  onClick={() => handleSelectAgent('agent-02-track-state')}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    width="180"
                    height="48"
                    rx="6"
                    fill={selectedAgentId === 'agent-02-track-state' ? '#18273d' : '#111822'}
                    stroke={selectedAgentId === 'agent-02-track-state' ? '#38bdf8' : '#253549'}
                    strokeWidth={selectedAgentId === 'agent-02-track-state' ? 2 : 1}
                  />
                  <circle cx="20" cy="24" r="5" fill="#10b981" />
                  <text x="32" y="22" fill="#f8fafc" fontSize="11" fontWeight="700">Track State & Weather</text>
                  <text x="32" y="36" fill="#94a3b8" fontSize="9">agent-02 · Grip & Rain</text>
                </g>

                {/* Agent 3 */}
                <g
                  transform="translate(410, 156)"
                  onClick={() => handleSelectAgent('agent-03-vehicle-response')}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    width="180"
                    height="48"
                    rx="6"
                    fill={selectedAgentId === 'agent-03-vehicle-response' ? '#18273d' : '#111822'}
                    stroke={selectedAgentId === 'agent-03-vehicle-response' ? '#38bdf8' : '#253549'}
                    strokeWidth={selectedAgentId === 'agent-03-vehicle-response' ? 2 : 1}
                  />
                  <circle cx="20" cy="24" r="5" fill="#10b981" />
                  <text x="32" y="22" fill="#f8fafc" fontSize="11" fontWeight="700">Vehicle Response</text>
                  <text x="32" y="36" fill="#94a3b8" fontSize="9">agent-03 · Telemetry Pace</text>
                </g>

                {/* Agent 4 */}
                <g
                  transform="translate(410, 216)"
                  onClick={() => handleSelectAgent('agent-04-tyre-strategy')}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    width="180"
                    height="48"
                    rx="6"
                    fill={selectedAgentId === 'agent-04-tyre-strategy' ? '#18273d' : '#111822'}
                    stroke={selectedAgentId === 'agent-04-tyre-strategy' ? '#38bdf8' : '#253549'}
                    strokeWidth={selectedAgentId === 'agent-04-tyre-strategy' ? 2 : 1}
                  />
                  <circle cx="20" cy="24" r="5" fill="#10b981" />
                  <text x="32" y="22" fill="#f8fafc" fontSize="11" fontWeight="700">Tyre & Strategy</text>
                  <text x="32" y="36" fill="#94a3b8" fontSize="9">agent-04 · Degradation</text>
                </g>

                {/* Agent 5 */}
                <g
                  transform="translate(410, 276)"
                  onClick={() => handleSelectAgent('agent-05-fusion')}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    width="180"
                    height="48"
                    rx="6"
                    fill={selectedAgentId === 'agent-05-fusion' ? '#18273d' : '#111822'}
                    stroke={selectedAgentId === 'agent-05-fusion' ? '#38bdf8' : '#253549'}
                    strokeWidth={selectedAgentId === 'agent-05-fusion' ? 2 : 1}
                  />
                  <circle cx="20" cy="24" r="5" fill="#10b981" />
                  <text x="32" y="22" fill="#f8fafc" fontSize="11" fontWeight="700">Consequence Fusion</text>
                  <text x="32" y="36" fill="#94a3b8" fontSize="9">agent-05 · Multi-Domain</text>
                </g>

                {/* Node 6: J2 Evaluator Bridge (SIA Core v3) */}
                <g
                  transform="translate(670, 130)"
                  onClick={() => handleSelectAgent('agent-06-integrity')}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    width="180"
                    height="100"
                    rx="8"
                    fill={selectedAgentId === 'agent-06-integrity' ? '#1a273b' : '#121b27'}
                    stroke={selectedAgentId === 'agent-06-integrity' ? '#e10600' : '#e1060080'}
                    strokeWidth="2"
                  />
                  <text x="90" y="26" textAnchor="middle" fill="#e10600" fontSize="10" fontWeight="800">REASONING KERNEL</text>
                  <text x="90" y="46" textAnchor="middle" fill="#f8fafc" fontSize="12" fontWeight="800">J2 Evaluator Bridge</text>
                  <text x="90" y="66" textAnchor="middle" fill="#38bdf8" fontSize="10" fontWeight="600">SIA Core v3 Evaluator</text>
                  <text x="90" y="84" textAnchor="middle" fill="#10b981" fontSize="9">{liveDecisionCount} Decision Instances</text>
                </g>

                {/* Node 7: Bitemporal Sinks & Downstream Fact Ledger */}
                <g transform="translate(900, 140)">
                  <rect width="90" height="80" rx="6" fill="#0d141e" stroke="#253549" strokeWidth="1.5" />
                  <text x="45" y="24" textAnchor="middle" fill="#94a3b8" fontSize="9" fontWeight="700">SINKS</text>
                  <text x="45" y="42" textAnchor="middle" fill="#f8fafc" fontSize="10" fontWeight="800">Fact Ledger</text>
                  <text x="45" y="58" textAnchor="middle" fill="#38bdf8" fontSize="8">SHA-256 Chain</text>
                  <text x="45" y="72" textAnchor="middle" fill="#64748b" fontSize="8">SSE Stream</text>
                </g>
              </svg>
            </div>
          </section>

          {/* D. AGENT DETAIL INSPECTOR & METRICS WORKBENCH */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 1fr) minmax(360px, 1.4fr)', gap: '16px' }}>
            {/* Left: Active Agent Selector List */}
            <div className="panel" style={{ padding: '16px' }}>
              <div className="panel-heading" style={{ marginBottom: '12px' }}>
                <div>
                  <p className="eyebrow">Operational Status</p>
                  <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
                    Active Runtime Agents
                  </h3>
                </div>
                <span className="subtle-chip">6 Registered</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Object.entries(AGENTS_METADATA).map(([agentId, meta]) => {
                  const m = metrics[agentId];
                  const isSelected = selectedAgentId === agentId;

                  return (
                    <div
                      key={agentId}
                      onClick={() => handleSelectAgent(agentId, false)}
                      style={{
                        padding: '12px 14px',
                        background: isSelected ? '#162232' : '#0d131c',
                        border: `1px solid ${isSelected ? '#38bdf8' : '#1e293b'}`,
                        borderRadius: '6px',
                        cursor: 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ color: isSelected ? '#38bdf8' : '#94a3b8' }}>
                            {meta.icon === 'flag' ? <FlagIcon size={14} /> :
                             meta.icon === 'rain' ? <CloudRainIcon size={14} /> :
                             meta.icon === 'car' ? <CarIcon size={14} /> :
                             meta.icon === 'tyre' ? <CircleDotIcon size={14} /> :
                             meta.icon === 'shield' ? <ShieldIcon size={14} /> :
                             <BrainIcon size={14} />}
                          </span>
                          <strong style={{ fontSize: '0.82rem', color: isSelected ? '#f8fafc' : '#cbd5e1' }}>
                            {meta.title}
                          </strong>
                        </div>
                        <span style={{ fontSize: '0.65rem', fontWeight: 700, color: '#10b981', background: 'rgba(16, 185, 129, 0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                          OPERATIONAL
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.72rem', color: '#64748b' }}>
                        <code>{agentId}</code>
                        <span>{m?.processed_inputs ?? 0} inputs · {m?.findings_emitted ?? 0} findings</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right: Selected Agent Detail Inspector */}
            <div className="panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="panel-heading" style={{ margin: 0 }}>
                <div>
                  <p className="eyebrow">Inspector & Live Diagnostics</p>
                  <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
                    {selectedAgentMeta.title}
                  </h3>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="subtle-chip" style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
                    {selectedAgentId}
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsDrawerOpen(true)}
                    style={{
                      background: '#1e293b',
                      color: '#f8fafc',
                      border: '1px solid #334155',
                      padding: '4px 8px',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      cursor: 'pointer',
                    }}
                  >
                    Open Drawer View
                  </button>
                </div>
              </div>

              <p style={{ margin: 0, fontSize: '0.78rem', color: '#94a3b8', lineHeight: '1.4' }}>
                {selectedAgentMeta.role}
              </p>

              {/* Responsibilities list */}
              <div style={{ background: '#0a0f17', padding: '10px 12px', borderRadius: '6px', border: '1px solid #1a2536' }}>
                <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>
                  Core Responsibilities:
                </span>
                <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '0.73rem', color: '#cbd5e1', lineHeight: '1.5' }}>
                  {selectedAgentMeta.responsibilities.map((resp, i) => (
                    <li key={i}>{resp}</li>
                  ))}
                </ul>
              </div>

              {/* Input / Output Topics */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div style={{ background: '#0a0f17', padding: '8px 10px', borderRadius: '4px', border: '1px solid #1a2536' }}>
                  <span style={{ fontSize: '0.65rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                    Subscribed Inputs:
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                    {selectedAgentMeta.inputs.map((inp) => (
                      <code key={inp} style={{ fontSize: '0.68rem', color: '#38bdf8', background: '#131e2c', padding: '2px 4px', borderRadius: '3px' }}>
                        {inp}
                      </code>
                    ))}
                  </div>
                </div>

                <div style={{ background: '#0a0f17', padding: '8px 10px', borderRadius: '4px', border: '1px solid #1a2536' }}>
                  <span style={{ fontSize: '0.65rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                    Emitted Topics:
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                    {selectedAgentMeta.outputs.map((out) => (
                      <code key={out} style={{ fontSize: '0.68rem', color: '#10b981', background: '#0f241d', padding: '2px 4px', borderRadius: '3px' }}>
                        {out}
                      </code>
                    ))}
                  </div>
                </div>
              </div>

              {/* Execution Metrics Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                <div style={{ background: '#090e16', padding: '8px', borderRadius: '4px', border: '1px solid #1c2738' }}>
                  <span style={{ fontSize: '0.62rem', color: '#64748b' }}>PROCESSED</span>
                  <strong style={{ fontSize: '0.9rem', color: '#f8fafc', display: 'block', fontFamily: 'var(--font-mono)' }}>
                    {selectedAgentMetric?.processed_inputs ?? 0}
                  </strong>
                </div>
                <div style={{ background: '#090e16', padding: '8px', borderRadius: '4px', border: '1px solid #1c2738' }}>
                  <span style={{ fontSize: '0.62rem', color: '#64748b' }}>FINDINGS</span>
                  <strong style={{ fontSize: '0.9rem', color: '#f59e0b', display: 'block', fontFamily: 'var(--font-mono)' }}>
                    {selectedAgentMetric?.findings_emitted ?? 0}
                  </strong>
                </div>
                <div style={{ background: '#090e16', padding: '8px', borderRadius: '4px', border: '1px solid #1c2738' }}>
                  <span style={{ fontSize: '0.62rem', color: '#64748b' }}>p95 LATENCY</span>
                  <strong style={{ fontSize: '0.9rem', color: '#38bdf8', display: 'block', fontFamily: 'var(--font-mono)' }}>
                    {selectedAgentMetric?.p95_latency_ms ? `${selectedAgentMetric.p95_latency_ms.toFixed(1)}ms` : '—'}
                  </strong>
                </div>
                <div style={{ background: '#090e16', padding: '8px', borderRadius: '4px', border: '1px solid #1c2738' }}>
                  <span style={{ fontSize: '0.62rem', color: '#64748b' }}>FAILURES</span>
                  <strong style={{ fontSize: '0.9rem', color: '#10b981', display: 'block', fontFamily: 'var(--font-mono)' }}>
                    {(selectedAgentMetric as any)?.failures ?? 0}
                  </strong>
                </div>
              </div>

              {/* Recent Findings Stream */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                    Recent Synthesized Findings ({findings.length}):
                  </span>
                  {loadingFindings && <span style={{ fontSize: '0.68rem', color: '#38bdf8' }}>Updating...</span>}
                </div>

                <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {findings.length === 0 ? (
                    <div style={{ padding: '16px', textAlign: 'center', color: '#64748b', fontSize: '0.75rem', background: '#0a0f17', borderRadius: '4px' }}>
                      No active findings emitted during current window.
                    </div>
                  ) : (
                    findings.slice(0, 5).map((f) => (
                      <div
                        key={f.finding_id}
                        style={{
                          padding: '8px 10px',
                          background: '#0a0f17',
                          borderRadius: '4px',
                          border: '1px solid #1a2536',
                          fontSize: '0.73rem',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <code style={{ color: '#38bdf8', fontWeight: 700 }}>{f.finding_id}</code>
                          <span style={{ fontSize: '0.65rem', color: '#10b981', fontWeight: 700 }}>{f.assessment_status}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#94a3b8', fontSize: '0.68rem' }}>
                          <span>Type: <strong style={{ color: '#e2e8f0' }}>{f.finding_type}</strong></span>
                          <span>Time: <code>{f.as_of_event_time?.split('T')[1] || f.as_of_event_time}</code></span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: TARGET ARCHETYPES (A1–A5 SPECIFICATION) */}
      {activeTab === 'TARGET_ARCHETYPES' && (
        <section className="panel target-archetypes-section" style={{ padding: '18px' }}>
          <div className="panel-heading" style={{ marginBottom: '16px' }}>
            <div>
              <p className="eyebrow">Architectural Specification & Decoupled Library</p>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                Five Specialist Agent Archetypes (calibre_core/agents/)
              </h3>
            </div>
            <span className="subtle-chip">Pure Observation Archetypes · Unit Tested</span>
          </div>

          <div
            style={{
              padding: '12px 16px',
              background: 'rgba(56, 189, 248, 0.05)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: '6px',
              marginBottom: '18px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <ShieldIcon size={20} style={{ color: '#38bdf8', flexShrink: 0 }} />
            <div style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: '1.4' }}>
              <strong style={{ color: '#f8fafc' }}>Epistemic Separation of Concerns (Rule AR-1): </strong>
              <em>Agents observe; they never evaluate integrity.</em> Specialist agents emit pure, timestamped evidence
              atoms with declared uncertainties. All integrity determinations and verdict mutations are strictly reserved
              for the Scoped Integrity Algebra (SIA) Evaluator Kernel.
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {TARGET_ARCHETYPES.map((arch) => (
              <div
                key={arch.id}
                style={{
                  padding: '14px 16px',
                  background: '#0d131c',
                  border: '1px solid #1d293a',
                  borderRadius: '6px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <strong style={{ fontSize: '0.88rem', color: '#f8fafc' }}>{arch.name}</strong>
                    <span style={{ fontSize: '0.68rem', color: '#38bdf8', background: '#131e2c', padding: '2px 6px', borderRadius: '4px' }}>
                      Scope: {arch.scope}
                    </span>
                  </div>
                  <code style={{ fontSize: '0.72rem', color: '#94a3b8' }}>{arch.file}</code>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(200px, 1.2fr) minmax(200px, 1fr)', gap: '12px', fontSize: '0.75rem' }}>
                  <div>
                    <span style={{ color: '#64748b', display: 'block', fontSize: '0.68rem', textTransform: 'uppercase', fontWeight: 700 }}>
                      Emitted Evidence Roles:
                    </span>
                    <span style={{ color: '#cbd5e1' }}>{arch.emits}</span>
                  </div>

                  <div>
                    <span style={{ color: '#64748b', display: 'block', fontSize: '0.68rem', textTransform: 'uppercase', fontWeight: 700 }}>
                      Target SIA Contracts:
                    </span>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '2px' }}>
                      {arch.contracts.map((c) => (
                        <code key={c} style={{ fontSize: '0.7rem', color: '#10b981', background: '#0e1f18', padding: '2px 5px', borderRadius: '3px' }}>
                          {c}
                        </code>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #16202c', paddingTop: '8px', marginTop: '2px', fontSize: '0.72rem' }}>
                  <span style={{ color: '#f59e0b', fontWeight: 600 }}>{arch.rule}</span>
                  <span style={{ color: '#64748b' }}>
                    Verified: <code>{arch.testRef}</code>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* TAB 3: TRANSPORT & NORMALIZER DIAGNOSTICS */}
      {activeTab === 'TOPOLOGY' && (
        <section className="panel" style={{ padding: '18px' }}>
          <div className="panel-heading" style={{ marginBottom: '16px' }}>
            <div>
              <p className="eyebrow">Truth in Observability</p>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                Dual-Transport & Stream Normalization Diagnostics
              </h3>
            </div>
            <span className="subtle-chip">Active Transport Diagnostics</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            {/* Event Bus Transport Card */}
            <div style={{ padding: '16px', background: '#0c121b', border: '1px solid #1a2536', borderRadius: '6px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                EVENT BUS TRANSPORT
              </span>
              <strong style={{ fontSize: '1.1rem', color: '#f8fafc' }}>{transportMode}</strong>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: isKafkaOnline ? '#10b981' : '#38bdf8' }}>
                <CheckCircleIcon size={14} />
                <span>{isKafkaOnline ? 'Apache Kafka Cluster Online' : 'Deterministic In-Memory Replay Bus Active'}</span>
              </div>
              <p style={{ margin: 0, fontSize: '0.74rem', color: '#94a3b8', lineHeight: '1.4' }}>
                {isKafkaOnline
                  ? `Clustered multi-broker Apache Kafka (${pipelineData?.kafka?.bootstrap_servers ?? 'KRaft'}) active across ${pipelineData?.kafka?.topic_count ?? 70} verified topics with consumer group coordination.`
                  : 'Zero external broker dependency. In-memory event bus guarantees strict microsecond ordering for deterministic re-simulation.'}
              </p>
            </div>

            {/* Stream Normalizer Card */}
            <div style={{ padding: '16px', background: '#0c121b', border: '1px solid #1a2536', borderRadius: '6px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                STREAM NORMALIZER
              </span>
              <strong style={{ fontSize: '1.1rem', color: '#f8fafc' }}>
                {flinkStatus === 'RUNNING' ? 'APACHE FLINK STREAMING' : 'PYTHON IN-PROCESS FALLBACK'}
              </strong>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: flinkStatus === 'RUNNING' ? '#10b981' : '#f59e0b' }}>
                <CheckCircleIcon size={14} />
                <span>{flinkStatus === 'RUNNING' ? `Flink Running (${pipelineData?.flink?.checkpoints_completed ?? 0} Checkpoints)` : 'In-Process Python Normalizer Operating'}</span>
              </div>
              <p style={{ margin: 0, fontSize: '0.74rem', color: '#94a3b8', lineHeight: '1.4' }}>
                {flinkStatus === 'RUNNING'
                  ? `Job ${pipelineData?.flink?.job_name ?? 'pulse-canonical-normalizer-v3'} running with stateful checkpointing (${pipelineData?.flink?.read_records ?? 0} in / ${pipelineData?.flink?.write_records ?? 0} out).`
                  : 'Operating in self-contained mode with Python high-frequency stream adapter and bounded buffer queues.'}
              </p>
            </div>

            {/* J1 Admission Sequencer Card */}
            <div style={{ padding: '16px', background: '#0c121b', border: '1px solid #1a2536', borderRadius: '6px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                J1 ADMISSION SEQUENCER
              </span>
              <strong style={{ fontSize: '1.1rem', color: '#f8fafc' }}>CANONICAL LOG v1.0</strong>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#10b981' }}>
                <CheckCircleIcon size={14} />
                <span>Monotonic Knowledge-Time Active</span>
              </div>
              <p style={{ margin: 0, fontSize: '0.74rem', color: '#94a3b8', lineHeight: '1.4' }}>
                Appends, deduplicates, and assigns strictly monotonic integer-microsecond knowledge timestamps (K) to incoming evidence atoms prior to SIA evaluation.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* TAB 4: VERIFICATION & LINEAGE LAB */}
      {activeTab === 'PIPELINE_LAB' && <PipelineLabView />}

      {/* SLIDE-OVER AGENT DETAIL INSPECTOR DRAWER */}
      {isDrawerOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(4px)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
          onClick={() => setIsDrawerOpen(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '560px',
              height: '100%',
              background: '#0d131c',
              borderLeft: '1px solid #233144',
              padding: '24px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '18px',
              boxShadow: '-8px 0 24px rgba(0, 0, 0, 0.6)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div>
                <span className="eyebrow">Agent Runtime Inspector</span>
                <h3 style={{ margin: '4px 0 0 0', fontSize: '1.2rem', fontWeight: 800, color: '#f8fafc' }}>
                  {selectedAgentMeta.title}
                </h3>
                <code style={{ fontSize: '0.75rem', color: '#38bdf8' }}>{selectedAgentId}</code>
              </div>
              <button
                type="button"
                onClick={() => setIsDrawerOpen(false)}
                style={{
                  background: '#1a2536',
                  border: '1px solid #28394e',
                  color: '#94a3b8',
                  borderRadius: '4px',
                  padding: '6px 12px',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                }}
              >
                Close [X]
              </button>
            </div>

            {/* Operational Role */}
            <div style={{ padding: '12px', background: '#070b10', borderRadius: '6px', border: '1px solid #16202c' }}>
              <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                Operational Role & Scope:
              </span>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.78rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                {selectedAgentMeta.role}
              </p>
            </div>

            {/* Diagnostics Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              <div style={{ padding: '10px', background: '#0a1017', borderRadius: '4px', border: '1px solid #1a2536' }}>
                <span style={{ fontSize: '0.65rem', color: '#64748b' }}>PROCESSED</span>
                <strong style={{ fontSize: '1.1rem', color: '#f8fafc', display: 'block', fontFamily: 'var(--font-mono)' }}>
                  {selectedAgentMetric?.processed_inputs ?? 0}
                </strong>
              </div>
              <div style={{ padding: '10px', background: '#0a1017', borderRadius: '4px', border: '1px solid #1a2536' }}>
                <span style={{ fontSize: '0.65rem', color: '#64748b' }}>FINDINGS</span>
                <strong style={{ fontSize: '1.1rem', color: '#f59e0b', display: 'block', fontFamily: 'var(--font-mono)' }}>
                  {selectedAgentMetric?.findings_emitted ?? 0}
                </strong>
              </div>
              <div style={{ padding: '10px', background: '#0a1017', borderRadius: '4px', border: '1px solid #1a2536' }}>
                <span style={{ fontSize: '0.65rem', color: '#64748b' }}>p95 LATENCY</span>
                <strong style={{ fontSize: '1.1rem', color: '#38bdf8', display: 'block', fontFamily: 'var(--font-mono)' }}>
                  {selectedAgentMetric?.p95_latency_ms ? `${selectedAgentMetric.p95_latency_ms.toFixed(1)}ms` : '—'}
                </strong>
              </div>
            </div>

            {/* Findings List in Drawer */}
            <div>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '8px' }}>
                All Emitted Findings ({findings.length}):
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {findings.map((f) => (
                  <div
                    key={f.finding_id}
                    style={{
                      padding: '10px 12px',
                      background: '#090e15',
                      borderRadius: '6px',
                      border: '1px solid #1a2636',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <code style={{ fontSize: '0.75rem', color: '#38bdf8', fontWeight: 700 }}>{f.finding_id}</code>
                      <span style={{ fontSize: '0.68rem', color: '#10b981', fontWeight: 700 }}>{f.assessment_status}</span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#cbd5e1' }}>
                      Type: <strong>{f.finding_type}</strong>
                    </div>
                    <div style={{ fontSize: '0.68rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                      Time: {f.as_of_event_time}
                    </div>
                    {(f as any).reason_codes && (f as any).reason_codes.length > 0 && (
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '2px' }}>
                        {(f as any).reason_codes.map((rc: string) => (
                          <span key={rc} style={{ fontSize: '0.65rem', color: '#f59e0b', background: '#1c1708', padding: '1px 5px', borderRadius: '3px' }}>
                            {rc}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
