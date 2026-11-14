import { useMemo, useState } from 'react';
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
  onSelectGate?: (gateId: string, sectorNumber: number) => void;
}

// Fallback Monaco centreline waypoints aligned with homologated GeoJSON coordinates
const FALLBACK_CENTRELINE: [number, number][] = [
  [500.68, 291.58], [552.64, 210.95], [570.61, 219.56], [582.83, 245.69],
  [593.17, 245.69], [576.76, 221.61], [614.14, 208.85], [609.62, 274.46],
  [590.42, 323.81], [530.07, 373.50], [463.58, 396.82], [354.27, 479.52],
  [296.88, 597.51], [305.53, 642.49], [339.46, 626.83], [361.34, 550.95],
  [380.05, 529.83], [428.18, 484.09], [468.96, 401.59], [500.68, 291.58]
];

interface SplineDistanceIndex {
  points: [number, number][];
  distances: number[];
  cumulative: number[];
  totalLength: number;
}

function buildSplineDistanceIndex(points: [number, number][]): SplineDistanceIndex {
  const n = points.length;
  if (n === 0) {
    return { points: [], distances: [], cumulative: [], totalLength: 0 };
  }
  const distances: number[] = new Array(n);
  const cumulative: number[] = new Array(n);
  let total = 0;
  for (let i = 0; i < n; i++) {
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const d = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
    distances[i] = d;
    cumulative[i] = total;
    total += d;
  }
  return { points, distances, cumulative, totalLength: total };
}

function interpolatePositionFromIndex(index: SplineDistanceIndex, progress: number): [number, number] {
  const { points, distances, cumulative, totalLength } = index;
  const n = points.length;
  if (n === 0) return [0, 0];
  if (n === 1 || totalLength === 0) return points[0];

  let p = progress % 1.0;
  if (p < 0) p += 1.0;

  const targetDist = p * totalLength;

  // Binary search for cumulative segment index
  let low = 0;
  let high = n - 1;
  let idx = 0;

  while (low <= high) {
    const mid = (low + high) >> 1;
    if (cumulative[mid] <= targetDist) {
      idx = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  const segLen = distances[idx];
  const frac = segLen > 0 ? Math.max(0, Math.min(1, (targetDist - cumulative[idx]) / segLen)) : 0;
  const p1 = points[idx];
  const p2 = points[(idx + 1) % n];

  return [
    p1[0] + frac * (p2[0] - p1[0]),
    p1[1] + frac * (p2[1] - p1[1]),
  ];
}

export function TrackMap({
  circuit,
  sectors,
  drivers,
  activeEvent,
  selectedDriverNumber,
  onSelectDriver,
  onInspectTelemetry,
  onSelectGate,
}: TrackMapProps) {
  const [hoveredDriver, setHoveredDriver] = useState<Driver | null>(null);
  const [hoveredCorner, setHoveredCorner] = useState<any | null>(null);

  const centreline = circuit?.centreline ?? FALLBACK_CENTRELINE;
  const viewBox = circuit?.view_box ?? { min_x: 180, min_y: 200, width: 540, height: 450 };

  // Precompute distance-weighted spline arc length index for smooth 60fps interpolation
  const splineIndex = useMemo(() => {
    return buildSplineDistanceIndex(centreline);
  }, [centreline]);

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
                {circuit.name} · v{circuit.layout_version} ({(circuit.length_meters / 1000).toFixed(3)} km)
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

          {/* Explicit Boundary Polygons (if supplied by dataset) */}
          {outerPath && <path d={outerPath} className="track-boundary outer" />}
          {innerPath && <path d={innerPath} className="track-boundary inner" />}

          {/* Underlay Roadbed Layer (ensures solid asphalt corridor on all tracks) */}
          <path
            d={centrelinePath}
            className="track-surface-bed"
            fill="none"
            stroke="#1b2533"
            strokeWidth="14"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Main Racing Line Corridor */}
          <path
            d={centrelinePath}
            className="track-line track-line--base"
            fill="none"
            stroke="#3b4b61"
            strokeWidth="8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Telemetry Tracking Groove */}
          <path
            d={centrelinePath}
            className="track-racing-line"
            fill="none"
            stroke="rgba(56, 189, 248, 0.4)"
            strokeWidth="1.5"
            strokeDasharray="6 4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

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

          {/* Timing Gates / Micro-Sector Boundaries (Clickable) */}
          {circuit?.sectors?.map((sec) => (
            <g
              key={sec.sector_number}
              className="timing-gate-group"
              onClick={() => onSelectGate?.(`G0${sec.sector_number}`, sec.sector_number)}
              style={{ cursor: 'pointer' }}
              role="button"
              tabIndex={0}
              aria-label={`Timing Gate G0${sec.sector_number} Sector ${sec.sector_number}`}
            >
              <circle
                cx={sec.checkpoint[0]}
                cy={sec.checkpoint[1]}
                r="4.5"
                fill="#ffd000"
                stroke="#0d1117"
                strokeWidth="1.5"
              />
              <text
                x={sec.checkpoint[0] + 6}
                y={sec.checkpoint[1] + 3}
                className="timing-gate-label"
                fill="#ffd000"
                fontSize="8.5"
                fontFamily="ui-monospace, monospace"
                fontWeight="bold"
              >
                G0{sec.sector_number}
              </text>
            </g>
          ))}

          {/* DRS Zones (when mapped) */}
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
              <circle cx={c.x} cy={c.y} r="2.8" className="corner-dot" />
              <text x={c.x} y={c.y - 4} className="corner-number-text">
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
              } else if (inPit) {
                // If explicit pit-lane geometry is not supplied, offset car near the start/finish straight
                const sf = circuit?.start_finish_line;
                if (sf) {
                  const dx = sf[1][0] - sf[0][0];
                  const dy = sf[1][1] - sf[0][1];
                  const pitOffsetRatio = 0.8;
                  x = sf[0][0] + dx * pitOffsetRatio;
                  y = sf[0][1] + dy * pitOffsetRatio + (driver.position % 5) * 8;
                } else {
                  [x, y] = interpolatePositionFromIndex(splineIndex, driver.progress ?? 0.0);
                }
              } else if (isRetired) {
                // Retired car parked in collection paddock
                x = viewBox.min_x + 30;
                y = viewBox.min_y + 30 + (driver.position % 6) * 16;
              } else {
                const p = driver.progress ?? (1.0 - (driver.position - 1) * 0.045);
                [x, y] = interpolatePositionFromIndex(splineIndex, p);
              }

              const teamColor = driver.teamColor || '#FFFFFF';

              return (
                <g
                  key={driver.number}
                  data-driver-number={driver.number}
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

                  {/* Position Tag for Top 5 or Pit Badge */}
                  {inPit ? (
                    <text
                      x="0"
                      y={-12}
                      textAnchor="middle"
                      className="car-pos-tag car-pos-tag--pit"
                      style={{ fill: '#ffd000' }}
                    >
                      PIT
                    </text>
                  ) : driver.position <= 5 && !isRetired ? (
                    <text
                      x="0"
                      y={-12}
                      textAnchor="middle"
                      className="car-pos-tag"
                      style={{ fill: teamColor }}
                    >
                      P{driver.position}
                    </text>
                  ) : null}
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
