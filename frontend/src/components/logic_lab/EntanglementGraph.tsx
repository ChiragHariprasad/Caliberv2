import React, { useState } from 'react';
import { InfoIcon, ShieldIcon, AlertTriangleIcon, CheckCircleIcon } from '../icons';

interface EntanglementGraphProps {
  decisionId?: string;
  contractId?: string;
  corroborationDepth?: number;
  hasCommonCause?: boolean;
  className?: string;
}

interface GraphNode {
  id: string;
  name: string;
  category: 'SOURCE_ORIGIN' | 'PROCESSING_ORIGIN' | 'PROVIDER' | 'EVIDENCE_ATOM' | 'DECISION';
  x: number;
  y: number;
  upstream: string[];
  failureDomain: string;
  closure: string[];
  commonCauseExposure: number;
  ruleRef: string;
}

const NODES_SOURCE_AXIS: Record<string, GraphNode> = {
  'src-fom': {
    id: 'src-fom',
    name: 'FOM_OPTICAL_LOOP',
    category: 'SOURCE_ORIGIN',
    x: 80,
    y: 120,
    upstream: [],
    failureDomain: 'Trackside optical transponder loop infrastructure',
    closure: ['FOM_OPTICAL_LOOP'],
    commonCauseExposure: 0.65,
    ruleRef: 'Rule AR-2: Shared optical loop limits corroboration depth if uncorroborated.',
  },
  'src-ecu': {
    id: 'src-ecu',
    name: 'CAN_BUS_GATEWAY',
    category: 'SOURCE_ORIGIN',
    x: 80,
    y: 280,
    upstream: [],
    failureDomain: 'In-car ECU CAN-bus serial telemetry transceiver',
    closure: ['CAN_BUS_GATEWAY'],
    commonCauseExposure: 0.15,
    ruleRef: 'Independent onboard physical telemetry source.',
  },
  'src-reg': {
    id: 'src-reg',
    name: 'FIA_GEOMETRY_REGIME',
    category: 'SOURCE_ORIGIN',
    x: 80,
    y: 440,
    upstream: [],
    failureDomain: 'Static regulatory circuit gate distance specification',
    closure: ['FIA_GEOMETRY_REGIME'],
    commonCauseExposure: 0.0,
    ruleRef: 'Immutable reference origin for distance checks.',
  },
  'prov-pitwall': {
    id: 'prov-pitwall',
    name: 'PROVIDER: PITWALL',
    category: 'PROVIDER',
    x: 280,
    y: 160,
    upstream: ['src-fom'],
    failureDomain: 'High-speed trackside decoding adapter',
    closure: ['FOM_OPTICAL_LOOP', 'PROVIDER_PITWALL'],
    commonCauseExposure: 0.45,
    ruleRef: 'Admissible origin for timing_speed and sector records.',
  },
  'prov-tracing': {
    id: 'prov-tracing',
    name: 'PROVIDER: CAN_TELEMETRY',
    category: 'PROVIDER',
    x: 280,
    y: 360,
    upstream: ['src-ecu'],
    failureDomain: 'ECU serial packet telemetry decoder',
    closure: ['CAN_BUS_GATEWAY', 'PROVIDER_CAN'],
    commonCauseExposure: 0.10,
    ruleRef: 'Admissible origin for vehicle_speed and throttle telemetry.',
  },
  'atom-timing': {
    id: 'atom-timing',
    name: 'atm-timing-spd-01',
    category: 'EVIDENCE_ATOM',
    x: 480,
    y: 160,
    upstream: ['prov-pitwall'],
    failureDomain: 'Measured value: 79.2 km/h at Gate G02',
    closure: ['FOM_OPTICAL_LOOP', 'PROVIDER_PITWALL'],
    commonCauseExposure: 0.45,
    ruleRef: 'Content hash: blake3:93ef25d6314c46e9 · Quality: HEALTHY',
  },
  'atom-vehicle': {
    id: 'atom-vehicle',
    name: 'atm-vehicle-spd-02',
    category: 'EVIDENCE_ATOM',
    x: 480,
    y: 360,
    upstream: ['prov-tracing'],
    failureDomain: 'Measured value: 78.8 km/h at timestamp T0',
    closure: ['CAN_BUS_GATEWAY', 'PROVIDER_CAN'],
    commonCauseExposure: 0.10,
    ruleRef: 'Content hash: blake3:ba024b6bebe1a64f · Quality: HEALTHY',
  },
  'dec-target': {
    id: 'dec-target',
    name: 'pit_speed@16 (DECISION)',
    category: 'DECISION',
    x: 680,
    y: 260,
    upstream: ['atom-timing', 'atom-vehicle'],
    failureDomain: 'Final verdict evaluation under pit_speed contract',
    closure: ['FOM_OPTICAL_LOOP', 'CAN_BUS_GATEWAY', 'FIA_GEOMETRY_REGIME'],
    commonCauseExposure: 0.25,
    ruleRef: 'D=2 Independent corroboration achieved across disjoint origin closures.',
  },
};

const NODES_PROCESSING_AXIS: Record<string, GraphNode> = {
  'proc-flink': {
    id: 'proc-flink',
    name: 'FLINK_STREAM_JOB_01',
    category: 'PROCESSING_ORIGIN',
    x: 100,
    y: 140,
    upstream: [],
    failureDomain: 'Distributed stateful streaming normalizer container',
    closure: ['FLINK_STREAM_JOB_01'],
    commonCauseExposure: 0.30,
    ruleRef: 'Normalizer origin for raw optical event deduplication.',
  },
  'proc-inproc': {
    id: 'proc-inproc',
    name: 'IN_PROCESS_SEQUENCER',
    category: 'PROCESSING_ORIGIN',
    x: 100,
    y: 340,
    upstream: [],
    failureDomain: 'Local Python async memory bus sequencer',
    closure: ['IN_PROCESS_SEQUENCER'],
    commonCauseExposure: 0.05,
    ruleRef: 'Direct in-memory queue dispatch.',
  },
  'pipe-j1': {
    id: 'pipe-j1',
    name: 'J1_EVENT_SEQUENCER',
    category: 'PROVIDER',
    x: 320,
    y: 180,
    upstream: ['proc-flink'],
    failureDomain: 'Event time ordering and monotonic stamp validation',
    closure: ['FLINK_STREAM_JOB_01', 'J1_EVENT_SEQUENCER'],
    commonCauseExposure: 0.20,
    ruleRef: 'Guarantees monotonic knowledge time progression.',
  },
  'pipe-j2': {
    id: 'pipe-j2',
    name: 'J2_EVALUATOR_BRIDGE',
    category: 'PROVIDER',
    x: 320,
    y: 340,
    upstream: ['proc-inproc'],
    failureDomain: 'SIA bridge translation and atom admission',
    closure: ['IN_PROCESS_SEQUENCER', 'J2_EVALUATOR_BRIDGE'],
    commonCauseExposure: 0.05,
    ruleRef: 'Converts EventEnvelope to SIA EvidenceAtom.',
  },
  'atom-proc-1': {
    id: 'atom-proc-1',
    name: 'atm-ordered-stream',
    category: 'EVIDENCE_ATOM',
    x: 520,
    y: 180,
    upstream: ['pipe-j1'],
    failureDomain: 'Sequenced timing event stream partition',
    closure: ['FLINK_STREAM_JOB_01', 'J1_EVENT_SEQUENCER'],
    commonCauseExposure: 0.20,
    ruleRef: 'Processed with exactly-once deterministic semantics.',
  },
  'atom-proc-2': {
    id: 'atom-proc-2',
    name: 'atm-admitted-atom',
    category: 'EVIDENCE_ATOM',
    x: 520,
    y: 340,
    upstream: ['pipe-j2'],
    failureDomain: 'Admitted SIA evidence tuple',
    closure: ['IN_PROCESS_SEQUENCER', 'J2_EVALUATOR_BRIDGE'],
    commonCauseExposure: 0.05,
    ruleRef: 'Admitted at knowledge time K without delay.',
  },
  'dec-target-proc': {
    id: 'dec-target-proc',
    name: 'pit_speed@16 (EVALUATION)',
    category: 'DECISION',
    x: 700,
    y: 260,
    upstream: ['atom-proc-1', 'atom-proc-2'],
    failureDomain: 'SIA Core v3 hash-chain sealed verdict',
    closure: ['FLINK_STREAM_JOB_01', 'IN_PROCESS_SEQUENCER'],
    commonCauseExposure: 0.12,
    ruleRef: 'Processing closure is disjoint across telemetry and timing channels.',
  },
};

export const EntanglementGraph: React.FC<EntanglementGraphProps> = ({
  decisionId = 'dec-pit_speed-d16',
  contractId = 'pit_speed',
  corroborationDepth = 2,
  hasCommonCause = false,
  className = '',
}) => {
  const [axis, setAxis] = useState<'SOURCE' | 'PROCESSING'>('SOURCE');
  const [selectedNodeId, setSelectedNodeId] = useState<string>('src-fom');
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);

  const activeNodes = axis === 'SOURCE' ? NODES_SOURCE_AXIS : NODES_PROCESSING_AXIS;
  const selectedNode = activeNodes[selectedNodeId] || Object.values(activeNodes)[0];

  const handleZoomIn = () => setZoomLevel((z) => Math.min(1.6, z + 0.15));
  const handleZoomOut = () => setZoomLevel((z) => Math.max(0.7, z - 0.15));
  const handleResetZoom = () => setZoomLevel(1.0);

  return (
    <div className={`provenance-graph-workspace ${className}`}>
      {/* 3-Zone Workspace Layout */}
      <div className="provenance-three-zone-grid">
        {/* ============================================================ */}
        {/* ZONE 1: LEFT CONTROLS & SOURCE LIST (~280px)                 */}
        {/* ============================================================ */}
        <aside className="zone-controls-column">
          <div className="zone-section-header">
            <span className="eyebrow-accent">ANALYSIS CONTROLS</span>
            <h3 className="zone-title">Provenance Axis</h3>
          </div>

          {/* Axis Switcher Toggle */}
          <div className="axis-selector-box">
            <button
              type="button"
              className={`axis-toggle-btn ${axis === 'SOURCE' ? 'is-active-axis' : ''}`}
              onClick={() => {
                setAxis('SOURCE');
                setSelectedNodeId('src-fom');
              }}
            >
              Source Origin Axis
            </button>
            <button
              type="button"
              className={`axis-toggle-btn ${axis === 'PROCESSING' ? 'is-active-axis' : ''}`}
              onClick={() => {
                setAxis('PROCESSING');
                setSelectedNodeId('proc-flink');
              }}
            >
              Processing Origin Axis
            </button>
          </div>

          {/* Decision Summary Card */}
          <div className="decision-brief-card">
            <span className="brief-label">TARGET DECISION:</span>
            <strong className="brief-id font-mono text-cyan-400">{decisionId}</strong>
            <span className="brief-sub text-slate-400">Contract: {contractId}</span>
            <div className="brief-stat-row">
              <span>Corroboration: <strong>D={corroborationDepth}</strong></span>
              <span className="text-emerald-400 font-semibold">[OK] DISJOINT</span>
            </div>
          </div>

          {/* Graph Interactive Controls */}
          <div className="graph-controls-card">
            <span className="brief-label">VIEWPORT CONTROLS:</span>
            <div className="zoom-buttons-group">
              <button type="button" className="btn-zoom" onClick={handleZoomIn} title="Zoom in">
                + Zoom
              </button>
              <button type="button" className="btn-zoom" onClick={handleZoomOut} title="Zoom out">
                &minus; Zoom
              </button>
              <button type="button" className="btn-zoom" onClick={handleResetZoom} title="Reset zoom">
                Fit 100%
              </button>
            </div>
            <span className="text-xs text-slate-400 mt-2 block">
              Scale: {(zoomLevel * 100).toFixed(0)}% &bull; Pan active
            </span>
          </div>

          {/* Available Nodes List */}
          <div className="nodes-selector-list">
            <span className="brief-label">PARTICIPATING ORIGINS &amp; NODES:</span>
            <div className="nodes-list-scroll">
              {Object.values(activeNodes).map((node) => (
                <div
                  key={node.id}
                  className={`node-list-item ${node.id === selectedNode.id ? 'is-selected-item' : ''}`}
                  onClick={() => setSelectedNodeId(node.id)}
                  role="button"
                  tabIndex={0}
                >
                  <span className={`node-type-dot node-type--${node.category.toLowerCase()}`} />
                  <span className="node-item-name">{node.name}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* ============================================================ */}
        {/* ZONE 2: CENTRE LARGE INTERACTIVE SVG GRAPH                   */}
        {/* ============================================================ */}
        <section className="zone-graph-centre">
          <div className="graph-canvas-header">
            <div className="canvas-header-left">
              <span className="canvas-title">
                {axis === 'SOURCE' ? 'Physical Ingestion & Source Origin Topology' : 'Stream Transformation & Processing Topology'}
              </span>
              <span className="canvas-subtitle text-slate-400">
                Click nodes to inspect origin closure, common-cause exposure, and depth
              </span>
            </div>

            {/* Legend */}
            <div className="graph-legend-strip">
              <span className="legend-item">
                <span className="legend-chip legend-chip--source" /> Source Origin
              </span>
              <span className="legend-item">
                <span className="legend-chip legend-chip--provider" /> Provider
              </span>
              <span className="legend-item">
                <span className="legend-chip legend-chip--atom" /> Evidence Atom
              </span>
              <span className="legend-item">
                <span className="legend-chip legend-chip--decision" /> Decision
              </span>
            </div>
          </div>

          <div className="graph-svg-viewport">
            <svg
              className="provenance-svg-canvas"
              viewBox="0 0 820 540"
              style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'top center' }}
            >
              <defs>
                <marker
                  id="prov-arrow"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569" />
                </marker>
                <marker
                  id="prov-arrow-active"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
                </marker>
              </defs>

              {/* Render Directed Edges */}
              {Object.values(activeNodes).map((node) =>
                node.upstream.map((upId) => {
                  const upNode = activeNodes[upId];
                  if (!upNode) return null;
                  const isConnectedToSelected = node.id === selectedNode.id || upNode.id === selectedNode.id;

                  return (
                    <g key={`${upId}->${node.id}`}>
                      <path
                        d={`M ${upNode.x + 60} ${upNode.y + 20} C ${upNode.x + 120} ${upNode.y + 20}, ${
                          node.x - 60
                        } ${node.y + 20}, ${node.x} ${node.y + 20}`}
                        fill="none"
                        stroke={isConnectedToSelected ? '#38bdf8' : '#334155'}
                        strokeWidth={isConnectedToSelected ? 2.5 : 1.5}
                        strokeDasharray={isConnectedToSelected ? 'none' : '4 2'}
                        markerEnd={isConnectedToSelected ? 'url(#prov-arrow-active)' : 'url(#prov-arrow)'}
                      />
                    </g>
                  );
                })
              )}

              {/* Render Graph Nodes */}
              {Object.values(activeNodes).map((node) => {
                const isSelected = node.id === selectedNode.id;
                let strokeColor = '#3b82f6';
                let fillColor = '#0f172a';

                if (node.category === 'SOURCE_ORIGIN' || node.category === 'PROCESSING_ORIGIN') {
                  strokeColor = '#38bdf8';
                } else if (node.category === 'PROVIDER') {
                  strokeColor = '#a855f7';
                } else if (node.category === 'EVIDENCE_ATOM') {
                  strokeColor = '#10b981';
                } else if (node.category === 'DECISION') {
                  strokeColor = '#f59e0b';
                  fillColor = '#1e1b18';
                }

                return (
                  <g
                    key={node.id}
                    className="provenance-node-group"
                    onClick={() => setSelectedNodeId(node.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    {/* Selection Ring */}
                    {isSelected && (
                      <rect
                        x={node.x - 6}
                        y={node.y - 6}
                        width={132}
                        height={52}
                        rx={8}
                        fill="none"
                        stroke="#60a5fa"
                        strokeWidth={2}
                        strokeDasharray="4 2"
                        className="node-selection-halo"
                      />
                    )}

                    {/* Node Rectangle */}
                    <rect
                      x={node.x}
                      y={node.y}
                      width={120}
                      height={40}
                      rx={6}
                      fill={fillColor}
                      stroke={strokeColor}
                      strokeWidth={isSelected ? 2 : 1}
                    />

                    {/* Category Label */}
                    <text
                      x={node.x + 8}
                      y={node.y + 14}
                      fill="#64748b"
                      fontSize={8}
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      {node.category}
                    </text>

                    {/* Node Name */}
                    <text
                      x={node.x + 8}
                      y={node.y + 30}
                      fill={isSelected ? '#ffffff' : '#cbd5e1'}
                      fontSize={10}
                      fontWeight="bold"
                      fontFamily="sans-serif"
                    >
                      {node.name.length > 18 ? `${node.name.slice(0, 16)}..` : node.name}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </section>

        {/* ============================================================ */}
        {/* ZONE 3: RIGHT NODE INSPECTOR CARD (~320px)                   */}
        {/* ============================================================ */}
        <aside className="zone-inspector-column">
          <div className="zone-section-header">
            <span className="eyebrow-accent">NODE INSPECTOR</span>
            <h3 className="zone-title">Selected Element</h3>
          </div>

          <div className="inspector-card-body">
            <div className="ins-header-block">
              <span className={`ins-category-badge category--${selectedNode.category.toLowerCase()}`}>
                {selectedNode.category}
              </span>
              <h4 className="ins-node-name">{selectedNode.name}</h4>
              <code className="ins-node-id font-mono text-cyan-400">{selectedNode.id}</code>
            </div>

            {/* Failure Domain */}
            <div className="ins-property-box">
              <span className="prop-label">FAILURE DOMAIN / SCOPE:</span>
              <p className="prop-desc">{selectedNode.failureDomain}</p>
            </div>

            {/* Origin Closure */}
            <div className="ins-property-box">
              <span className="prop-label">ORIGIN CLOSURE SET:</span>
              <div className="closure-tags-wrap">
                {selectedNode.closure.map((cl) => (
                  <span key={cl} className="closure-tag font-mono">
                    {cl}
                  </span>
                ))}
              </div>
            </div>

            {/* Common-Cause Exposure Metric */}
            <div className="ins-property-box">
              <div className="prop-header-row">
                <span className="prop-label">COMMON-CAUSE EXPOSURE:</span>
                <span className="prop-val font-mono">{selectedNode.commonCauseExposure.toFixed(2)}</span>
              </div>
              <div className="exposure-meter-bar">
                <div
                  className="exposure-meter-fill"
                  style={{
                    width: `${selectedNode.commonCauseExposure * 100}%`,
                    backgroundColor:
                      selectedNode.commonCauseExposure > 0.5
                        ? '#ff4d4f'
                        : selectedNode.commonCauseExposure > 0.2
                        ? '#ffd000'
                        : '#00ff88',
                  }}
                />
              </div>
              <span className="text-xs text-slate-400 mt-1 block">
                {selectedNode.commonCauseExposure === 0
                  ? 'Zero shared failure modes (Maximum epistemic independence)'
                  : selectedNode.commonCauseExposure > 0.4
                  ? 'Shared hardware / bus tap (Corroboration limited)'
                  : 'Low shared transit exposure'}
              </span>
            </div>

            {/* Regulatory Rule Callout */}
            <div className="ins-rule-box">
              <div className="rule-header">
                <ShieldIcon size={13} className="text-emerald-400" />
                <span className="rule-title">SIA Regulatory Precedence</span>
              </div>
              <p className="rule-text">{selectedNode.ruleRef}</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};
