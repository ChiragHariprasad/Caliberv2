import React, { useState } from 'react';

interface EntanglementGraphProps {
  corroborationDepth?: number;
  hasCommonCause?: boolean;
  className?: string;
}

export const EntanglementGraph: React.FC<EntanglementGraphProps> = ({
  corroborationDepth = 1,
  hasCommonCause = true,
  className = '',
}) => {
  const [axisMode, setAxisMode] = useState<'SOURCE' | 'PROCESSING'>('SOURCE');

  return (
    <div className={`entanglement-graph-card panel ${className}`}>
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Two-Axis Origin Independence</p>
          <h3>Dependency Entanglement & Provenance Graph</h3>
        </div>

        <div className="graph-mode-toggle">
          <button
            type="button"
            className={`mode-btn ${axisMode === 'SOURCE' ? 'is-active' : ''}`}
            onClick={() => setAxisMode('SOURCE')}
          >
            Source Origin Axis
          </button>
          <button
            type="button"
            className={`mode-btn ${axisMode === 'PROCESSING' ? 'is-active' : ''}`}
            onClick={() => setAxisMode('PROCESSING')}
          >
            Processing Origin Axis
          </button>
        </div>
      </div>

      <div className="entanglement-body">
        {/* Metric Bar */}
        <div className="entanglement-metrics-strip">
          <div className="e-metric">
            <span className="e-label">CORROBORATION DEPTH:</span>
            <strong className="e-val text-amber-400">{corroborationDepth} Origin-Disjoint Set</strong>
          </div>
          <div className="e-metric">
            <span className="e-label">INDEPENDENCE AXIS:</span>
            <strong className="e-val">{axisMode} AXIS CLOSURE</strong>
          </div>
          <div className="e-metric">
            <span className="e-label">EPISTEMIC LIMITATION:</span>
            <span className="limitation-pill">
              {hasCommonCause ? 'COMMON-CAUSE EXPOSURE DETECTED' : 'FULLY DISJOINT ORIGINS'}
            </span>
          </div>
        </div>

        {/* Visual Graph Canvas / SVG */}
        <div className="provenance-graph-canvas">
          <svg viewBox="0 0 700 280" className="entanglement-svg">
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
              </marker>
              <marker id="arrow-warn" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
              </marker>
            </defs>

            {axisMode === 'SOURCE' ? (
              // Source Axis Graph
              <g className="source-axis-graph">
                {/* Level 1: Root Upstream Infrastructure */}
                <g className="node-group" transform="translate(350, 40)">
                  <rect x="-120" y="-20" width="240" height="40" rx="6" fill="#1e293b" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4 2" />
                  <text x="0" y="5" textAnchor="middle" fill="#fde68a" fontSize="11" fontFamily="ui-monospace, monospace" fontWeight="bold">
                    FOM Common Timing Infrastructure
                  </text>
                  <text x="0" y="-26" textAnchor="middle" fill="#94a3b8" fontSize="9" fontFamily="sans-serif">
                    [Single Shared Upstream Hardware Source]
                  </text>
                </g>

                {/* Level 2: Intermediary Providers */}
                <line x1="280" y1="60" x2="190" y2="120" stroke="#f59e0b" strokeWidth="1.5" markerEnd="url(#arrow-warn)" />
                <line x1="420" y1="60" x2="510" y2="120" stroke="#f59e0b" strokeWidth="1.5" markerEnd="url(#arrow-warn)" />

                <g className="node-group" transform="translate(190, 140)">
                  <polygon points="-60,-18 60,-18 75,18 -75,18" fill="#182234" stroke="#38bdf8" strokeWidth="1.5" />
                  <text x="0" y="4" textAnchor="middle" fill="#38bdf8" fontSize="10" fontFamily="ui-monospace, monospace" fontWeight="bold">
                    Provider: PITWALL
                  </text>
                </g>

                <g className="node-group" transform="translate(510, 140)">
                  <polygon points="-60,-18 60,-18 75,18 -75,18" fill="#182234" stroke="#38bdf8" strokeWidth="1.5" />
                  <text x="0" y="4" textAnchor="middle" fill="#38bdf8" fontSize="10" fontFamily="ui-monospace, monospace" fontWeight="bold">
                    Provider: TRACINGINSIGHTS
                  </text>
                </g>

                {/* Level 3: Resulting Evidence Atoms */}
                <line x1="190" y1="160" x2="250" y2="220" stroke="#64748b" strokeWidth="1.2" markerEnd="url(#arrow)" />
                <line x1="510" y1="160" x2="450" y2="220" stroke="#64748b" strokeWidth="1.2" markerEnd="url(#arrow)" />

                <g className="node-group" transform="translate(250, 240)">
                  <circle r="22" fill="#0f172a" stroke="#10b981" strokeWidth="1.5" />
                  <text x="0" y="4" textAnchor="middle" fill="#10b981" fontSize="9" fontFamily="ui-monospace, monospace" fontWeight="bold">
                    atm-spd-01
                  </text>
                </g>

                <g className="node-group" transform="translate(450, 240)">
                  <circle r="22" fill="#0f172a" stroke="#10b981" strokeWidth="1.5" />
                  <text x="0" y="4" textAnchor="middle" fill="#10b981" fontSize="9" fontFamily="ui-monospace, monospace" fontWeight="bold">
                    atm-spd-02
                  </text>
                </g>

                {/* Meet Convergence */}
                <line x1="272" y1="240" x2="428" y2="240" stroke="#f59e0b" strokeWidth="1" strokeDasharray="3 3" />
                <text x="350" y="235" textAnchor="middle" fill="#fbbf24" fontSize="9" fontFamily="ui-monospace, monospace">
                  Origin Closures Intersect (Depth: 1)
                </text>
              </g>
            ) : (
              // Processing Axis Graph
              <g className="processing-axis-graph">
                <g className="node-group" transform="translate(200, 60)">
                  <rect x="-80" y="-18" width="160" height="36" rx="4" fill="#1e293b" stroke="#3b82f6" strokeWidth="1.5" />
                  <text x="0" y="4" textAnchor="middle" fill="#93c5fd" fontSize="10" fontFamily="ui-monospace, monospace" fontWeight="bold">
                    adapter:fastf1_normalizer
                  </text>
                </g>

                <g className="node-group" transform="translate(500, 60)">
                  <rect x="-80" y="-18" width="160" height="36" rx="4" fill="#1e293b" stroke="#a855f7" strokeWidth="1.5" />
                  <text x="0" y="4" textAnchor="middle" fill="#d8b4fe" fontSize="10" fontFamily="ui-monospace, monospace" fontWeight="bold">
                    adapter:can_telemetry_v2
                  </text>
                </g>

                <line x1="200" y1="80" x2="280" y2="180" stroke="#64748b" strokeWidth="1.2" markerEnd="url(#arrow)" />
                <line x1="500" y1="80" x2="420" y2="180" stroke="#64748b" strokeWidth="1.2" markerEnd="url(#arrow)" />

                <g className="node-group" transform="translate(350, 200)">
                  <rect x="-100" y="-20" width="200" height="40" rx="6" fill="#0f172a" stroke="#10b981" strokeWidth="1.5" />
                  <text x="0" y="4" textAnchor="middle" fill="#34d399" fontSize="10" fontFamily="ui-monospace, monospace" fontWeight="bold">
                    Disjoint Processing Pipelines (v1.0.0)
                  </text>
                </g>
              </g>
            )}
          </svg>
        </div>

        <div className="entanglement-explanation-card">
          <p>
            <strong>Mathematical Principle:</strong> In Scoped Integrity Algebra, corroboration depth is computed as the{' '}
            <em>cardinality of the largest pairwise origin-disjoint agreeing subset of sources</em>. Common-cause exposure
            is documented as an informational limitation; it does not automatically force a verdict to SUSPECT unless a
            minimum disjoint depth is strictly mandated by contract policy.
          </p>
        </div>
      </div>
    </div>
  );
};

