import React, { useMemo, useState } from 'react';
import type { SIAAssessment } from '../../types/calibre';
import { InfoIcon, ShieldIcon, AlertTriangleIcon, CheckCircleIcon } from '../icons';

interface EntanglementGraphProps {
  decisionId?: string;
  contractId?: string;
  corroborationDepth?: number;
  hasCommonCause?: boolean;
  verdict?: SIAAssessment | null;
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

const buildLiveGraphNodes = (
  decisionId: string,
  contractId: string,
  verdict: SIAAssessment | null | undefined,
  axis: 'SOURCE' | 'PROCESSING',
): Record<string, GraphNode> => {
  const nodes: Record<string, GraphNode> = {};
  if (!verdict || !verdict.roles || Object.keys(verdict.roles).length === 0) {
    nodes['dec-empty'] = {
      id: 'dec-empty',
      name: decisionId || 'Awaiting evaluation',
      category: 'DECISION',
      x: 360,
      y: 220,
      upstream: [],
      failureDomain: `No live evidence atoms admitted yet for contract ${contractId}`,
      closure: [],
      commonCauseExposure: 0,
      ruleRef: 'Start or seek replay to populate real source and processing lineage DAGs.',
    };
    return nodes;
  }

  const critSet = new Set((verdict.resilience?.critical_origins || []).map(String));
  const exposure = typeof verdict.common_cause_exposure === 'number' ? verdict.common_cause_exposure : critSet.size > 0 ? 1.0 : 0.0;
  const origins =
    axis === 'SOURCE'
      ? (verdict.source_origins || []).map((o) => `S:${o}`)
      : (verdict.processing_origins || []).map((p) => `P:${p}`);
  const uniqOrigins = origins.length > 0 ? origins : [axis === 'SOURCE' ? 'S:UNASSIGNED' : 'P:DIRECT_ADMISSION'];

  uniqOrigins.forEach((orig, idx) => {
    const id = `orig-${idx}`;
    const y = Math.min(460, 80 + idx * (360 / Math.max(1, uniqOrigins.length)));
    const isSpof = critSet.has(orig);
    nodes[id] = {
      id,
      name: orig.replace(/^[SP]:/, ''),
      category: axis === 'SOURCE' ? 'SOURCE_ORIGIN' : 'PROCESSING_ORIGIN',
      x: 80,
      y,
      upstream: [],
      failureDomain: isSpof
        ? `Single-point-of-failure origin dependency (${orig})`
        : `Registered SIA dependency closure (${orig})`,
      closure: [orig],
      commonCauseExposure: isSpof ? Math.max(0.5, exposure) : 0.0,
      ruleRef: isSpof ? 'Flagged in resilience.critical_origins' : 'Evaluated dependency origin',
    };
  });

  const roleEntries = Object.entries(verdict.roles);
  const atomIds: string[] = [];
  roleEntries.forEach(([rName, rRaw], idx) => {
    const r = rRaw as any;
    const atom = Array.isArray(r?.atoms_detail) ? r.atoms_detail[0] : null;
    const deps: string[] = Array.isArray(r?.dependencies) ? r.dependencies : [];
    const matchingOrigIds = uniqOrigins
      .map((o, i) => (deps.includes(o) ? `orig-${i}` : null))
      .filter((x): x is string => x !== null);
    const id = `role-${idx}`;
    atomIds.push(id);
    const y = Math.min(460, 100 + idx * (340 / Math.max(1, roleEntries.length)));
    const hashLabel = verdict.verdict_hash ? `sha256:${verdict.verdict_hash.slice(0, 14)}…` : 'unhashed';
    nodes[id] = {
      id,
      name: atom ? `${rName} (${atom.value} ${atom.unit || ''})` : `${rName} [${r?.kind || 'role'}]`,
      category: 'EVIDENCE_ATOM',
      x: 380,
      y,
      upstream: matchingOrigIds.length > 0 ? matchingOrigIds : ['orig-0'],
      failureDomain: atom ? `Atom ${String(atom.atom_id).slice(0, 12)} · ${atom.quality_grade}` : 'Awaiting role evidence',
      closure: deps,
      commonCauseExposure: exposure,
      ruleRef: `Verdict digest: ${hashLabel} · State: ${verdict.integrity_state}`,
    };
  });

  nodes['dec-target'] = {
    id: 'dec-target',
    name: `${decisionId} (${verdict.integrity_state})`,
    category: 'DECISION',
    x: 660,
    y: 230,
    upstream: atomIds,
    failureDomain: verdict.primary_binding_witness || `Evaluated under ${contractId}`,
    closure: Array.from(critSet),
    commonCauseExposure: exposure,
    ruleRef: `Corroboration D=${verdict.corroboration_depth ?? 0} · Required k=${verdict.resilience?.required_k ?? 0}`,
  };

  return nodes;
};

export const EntanglementGraph: React.FC<EntanglementGraphProps> = ({
  decisionId = '',
  contractId = 'lap_time',
  corroborationDepth = 0,
  hasCommonCause = false,
  verdict,
  className = '',
}) => {
  const [axis, setAxis] = useState<'SOURCE' | 'PROCESSING'>('SOURCE');
  const [selectedNodeId, setSelectedNodeId] = useState<string>('dec-target');
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);

  const activeNodes = useMemo(
    () => buildLiveGraphNodes(decisionId, contractId, verdict, axis),
    [decisionId, contractId, verdict, axis],
  );
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
              <span className={`${hasCommonCause ? 'text-amber-400' : 'text-emerald-400'} font-semibold`}>
                {hasCommonCause ? 'COMMON-CAUSE SPOF' : 'DISJOINT'}
              </span>
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
