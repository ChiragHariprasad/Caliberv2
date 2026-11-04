import { useState } from 'react';
import type { CircuitGeometry, Driver, TrackSector } from '../types';
import { BarChartIcon } from './icons';

interface TrackMapProps {
  circuit: CircuitGeometry | null;
  sectors: TrackSector[];
  drivers: Driver[];
  activeEvent: string;
  selectedDriverNumber?: number | null;
  onSelectDriver?: (driverNumber: number) => void;
  onInspectTelemetry?: (driverNumber: number) => void;
}

// Fallback Monaco centreline waypoints if circuit asset is loading
const FALLBACK_CENTRELINE: [number, number][] = [
  [440, 560], [540, 550], [640, 520], [630, 420], [590, 310], [530, 260],
  [460, 290], [390, 275], [430, 340], [490, 370], [550, 395], [610, 430],
  [520, 465], [420, 485], [360, 500], [310, 515], [240, 525], [260, 580], [330, 575]
];

function interpolateAlongPoints(points: [number, number][], progress: number): [number, number] {
  const n = points.length;
  if (n === 0) return [0, 0];
  if (n === 1) return points[0];

  const p = Math.max(0, Math.min(0.9999, progress % 1.0));
  const totalSegments = n;
  const floatIdx = p * totalSegments;
  const idx = Math.floor(floatIdx);
  const nextIdx = (idx + 1) % n;
  const frac = floatIdx - idx;

  const [x1, y1] = points[idx];
  const [x2, y2] = points[nextIdx];
  return [x1 + frac * (x2 - x1), y1 + frac * (y2 - y1)];
}

export function TrackMap({
  circuit,
  sectors,
  drivers,
  activeEvent,
  selectedDriverNumber,
  onSelectDriver,
  onInspectTelemetry,
}: TrackMapProps) {
  const [hoveredDriver, setHoveredDriver] = useState<Driver | null>(null);
  const [hoveredCorner, setHoveredCorner] = useState<any | null>(null);

  const centreline = circuit?.centreline ?? FALLBACK_CENTRELINE;
  const viewBox = circuit?.view_box ?? { min_x: 180, min_y: 190, width: 540, height: 460 };

  const centrelinePath = `M ${centreline.map((pt) => `${pt[0]},${pt[1]}`).join(' L ')} Z`;
  const outerPath = circuit?.outer_boundary?.length
    ? `M ${circuit.outer_boundary.map((pt) => `${pt[0]},${pt[1]}`).join(' L ')} Z`
    : null;
  const innerPath = circuit?.inner_boundary?.length
    ? `M ${circuit.inner_boundary.map((pt) => `${pt[0]},${pt[1]}`).join(' L ')} Z`
    : null;
  const pitPath = circuit?.pit_lane?.path?.length
    ? `M ${circuit.pit_lane.path.map((pt) => `${pt[0]},${pt[1]}`).join(' L ')}`
    : null;

  return (
    <section className="panel track-panel" aria-labelledby="track-title">
      <div className="panel-heading">
        <div>
          <div className="circuit-header-row">
            <p className="eyebrow">Circuit Geometry & Live Grid</p>
            {circuit && (
              <span className="circuit-provenance-tag" title={`Source: ${circuit.source_attribution} · Checksum: ${circuit.checksum_sha256}`}>
                {circuit.name} · {circuit.layout_version} ({(circuit.length_meters / 1000).toFixed(3)} km)
              </span>
            )}
          </div>
          <h2 id="track-title">{circuit?.name ?? 'Circuit de Monaco'} — Real-Time Spatial Tracking</h2>
        </div>
        <span className="event-pill">
          <span className="event-dot" />
          {activeEvent}
        </span>
      </div>

      <div className="track-visual-container">
        <svg
          viewBox={`${viewBox.min_x} ${viewBox.min_y} ${viewBox.width} ${viewBox.height}`}
          className="circuit-svg"
          role="img"
          aria-label={`Circuit map of ${circuit?.name ?? 'Monaco'} with all session drivers`}
        >
          <defs>
            <filter id="car-glow-selected" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <linearGradient id="drs-gradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#00ff88" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#00cc66" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          {/* Track Surface & Boundaries */}
          {outerPath && <path d={outerPath} className="track-boundary outer" />}
          {innerPath && <path d={innerPath} className="track-boundary inner" />}

          {/* Centreline Racing Line */}
          <path d={centrelinePath} className="track-line track-line--base" />

          {/* Pit Lane Geometry */}
          {pitPath && <path d={pitPath} className="pit-lane-path" strokeDasharray="4 3" />}

          {/* Start / Finish Line */}
          {circuit?.start_finish_line && (
            <line
              x1={circuit.start_finish_line[0][0]}
              y1={circuit.start_finish_line[0][1]}
              x2={circuit.start_finish_line[1][0]}
              y2={circuit.start_finish_line[1][1]}
              className="start-finish-grid-line"
            />
          )}

          {/* DRS Zones */}
          {circuit?.drs_zones?.map((drs) => (
            <g key={drs.zone_id} className="drs-zone-marker">
              <circle cx={drs.activation_point[0]} cy={drs.activation_point[1]} r="4" fill="#00ff88" />
              <text x={drs.activation_point[0] + 6} y={drs.activation_point[1] - 4} className="drs-label">
                DRS {drs.zone_id}
              </text>
            </g>
          ))}

          {/* Corner Number Markers */}
          {circuit?.corners?.map((c) => (
            <g
              key={c.number}
              className="corner-pin"
              onMouseEnter={() => setHoveredCorner(c)}
              onMouseLeave={() => setHoveredCorner(null)}
            >
              <circle cx={c.x} cy={c.y} r="3" className="corner-dot" />
              <text x={c.x} y={c.y - 5} className="corner-number-text">
                {c.number}
              </text>
            </g>
          ))}

          {/* Interactive Full-Grid Driver Markers */}
          {drivers
            .filter((d) => d.status !== 'DNS' && d.status !== 'INACTIVE')
            .map((driver) => {
              const inPit = driver.status === 'PIT_LANE';
              const isSelected = selectedDriverNumber === driver.number;
              const isRetired = driver.status === 'RETIRED';

              let x: number;
              let y: number;

              if (inPit && circuit?.pit_lane?.path?.length) {
                const idx = Math.floor((driver.progress ?? 0.5) * (circuit.pit_lane.path.length - 1));
                const pt = circuit.pit_lane.path[idx];
                x = pt[0];
                y = pt[1];
              } else if (isRetired) {
                // Retired car parked off track or at start/finish
                x = (circuit?.view_box.min_x ?? 180) + 40;
                y = (circuit?.view_box.min_y ?? 190) + 40 + (driver.position % 5) * 15;
              } else {
                const p = driver.progress ?? (1.0 - (driver.position - 1) * 0.045);
                [x, y] = interpolateAlongPoints(centreline, p);
              }

              const teamColor = driver.teamColor || '#FFFFFF';

              return (
                <g
                  key={driver.number}
                  className={`car-node ${isSelected ? 'is-selected' : ''} ${isRetired ? 'is-retired' : ''}`}
                  style={{ transform: `translate(${x}px, ${y}px)` }}
                  onClick={() => onSelectDriver?.(driver.number)}
                  onMouseEnter={() => setHoveredDriver(driver)}
                  onMouseLeave={() => setHoveredDriver(null)}
                  role="button"
                  tabIndex={0}
                  aria-label={`Car #${driver.number} ${driver.name} Position ${driver.position}`}
                >
                  {/* Selection Pulsing Halo */}
                  {isSelected && (
                    <circle r="16" className="car-halo" style={{ stroke: teamColor }} />
                  )}

                  {/* Car Circle with Team Color Border */}
                  <circle
                    r={isSelected ? '10' : '8'}
                    className="car-circle"
                    style={{
                      fill: isRetired ? '#222' : teamColor,
                      stroke: '#0d1117',
                      strokeWidth: '2',
                    }}
                  />

                  {/* Driver Number Badge */}
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="car-node-text"
                    style={{ fill: isRetired ? '#888' : '#FFFFFF' }}
                  >
                    {driver.number}
                  </text>

                  {/* Position Tag for Top 5 */}
                  {driver.position <= 5 && !isRetired && (
                    <text
                      x="0"
                      y={-12}
                      textAnchor="middle"
                      className="car-pos-tag"
                      style={{ fill: teamColor }}
                    >
                      P{driver.position}
                    </text>
                  )}
                </g>
              );
            })}
        </svg>

        {/* Hover Corner Tooltip */}
        {hoveredCorner && (
          <div className="corner-tooltip-card">
            <span className="tooltip-corner-num">Turn {hoveredCorner.number}</span>
            <span className="tooltip-corner-name">{hoveredCorner.name}</span>
            <small>Sector {hoveredCorner.sector} {hoveredCorner.apex_speed_kmh ? `· ${hoveredCorner.apex_speed_kmh} km/h apex` : ''}</small>
          </div>
        )}

        {/* Hover / Click Driver Telemetry Inspector Card */}
        {hoveredDriver && (
          <div className="driver-hover-card" style={{ borderColor: hoveredDriver.teamColor }}>
            <div className="hover-card-header">
              <span className="hover-pos-badge" style={{ backgroundColor: hoveredDriver.teamColor }}>
                P{hoveredDriver.position}
              </span>
              <div className="hover-driver-name">
                <strong>{hoveredDriver.name}</strong>
                <span>{hoveredDriver.team} #{hoveredDriver.number}</span>
              </div>
              <span className={`status-pill status-pill--${hoveredDriver.status?.toLowerCase() ?? 'active'}`}>
                {hoveredDriver.status ?? 'ACTIVE'}
              </span>
            </div>

            <div className="hover-card-metrics">
              <div className="metric-chip">
                <span className="m-label">SPEED</span>
                <span className="m-val">{hoveredDriver.telemetry?.speed?.quality === 'AVAILABLE' ? `${hoveredDriver.telemetry.speed.value} km/h` : 'UNAVAILABLE'}</span>
              </div>
              <div className="metric-chip">
                <span className="m-label">THROTTLE</span>
                <span className="m-val">{hoveredDriver.telemetry?.throttle?.quality === 'AVAILABLE' ? `${hoveredDriver.telemetry.throttle.value}%` : 'UNAVAILABLE'}</span>
              </div>
              <div className="metric-chip">
                <span className="m-label">GEAR</span>
                <span className="m-val">{hoveredDriver.telemetry?.gear?.quality === 'AVAILABLE' ? `G${hoveredDriver.telemetry.gear.value}` : 'UNAVAILABLE'}</span>
              </div>
              <div className="metric-chip">
                <span className="m-label">TYRE</span>
                <span className="m-val">{hoveredDriver.tyre} ({hoveredDriver.tyreAge}L)</span>
              </div>
              <div className="metric-chip">
                <span className="m-label">GAP</span>
                <span className="m-val">{hoveredDriver.gap}</span>
              </div>
              <div className="metric-chip">
                <span className="m-label">PROVENANCE</span>
                <span className="m-val">{hoveredDriver.positionMode ?? 'TIMING_ESTIMATED'}</span>
              </div>
            </div>

            <div className="hover-card-footer">
              <button
                type="button"
                className="btn-inspect-telemetry"
                onClick={() => onInspectTelemetry?.(hoveredDriver.number)}
              >
                <BarChartIcon size={14} className="inline mr-1" />
                Open Live Telemetry Inspector
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Sector Status Legend */}
      <div className="track-legend-bar">
        {sectors.map((sector) => (
          <div className="track-legend__item" key={sector.id}>
            <span className={`legend-swatch legend-swatch--${sector.tone}`} />
            <span>
              <strong>{sector.label}</strong>
              <small>{sector.condition}</small>
            </span>
          </div>
        ))}
        <div className="track-legend-provenance">
          <span>* Vehicle positions derived from transponder timing line progress (ESTIMATED). GPS coordinates mapped when telemetry available.</span>
        </div>
      </div>
    </section>
  );
}
