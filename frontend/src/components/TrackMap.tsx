import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { CircuitGeometry, Driver, TrackSector } from '../types';
import { AlertTriangleIcon, BarChartIcon, CloseIcon } from './icons';

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

function getSplineSubPath(index: SplineDistanceIndex, startProg: number, endProg: number, step = 0.005): string {
  if (index.points.length === 0) return '';
  const pts: [number, number][] = [];
  let p = startProg;
  while (p <= endProg + 0.0001) {
    pts.push(interpolatePositionFromIndex(index, Math.min(1.0, Math.max(0.0, p))));
    p += step;
  }
  if (pts.length === 0) return '';
  return `M ${pts.map(pt => `${pt[0].toFixed(2)},${pt[1].toFixed(2)}`).join(' L ')}`;
}

interface SensorPopupData {
  gateId: string;
  sectorNumber: number;
  checkpoint: [number, number];
  name: string;
  status: 'HEALTHY' | 'SUSPECT' | 'DEGRADED';
  measurement: string;
  unit: string;
  source: string;
  contractRef: string;
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
  // Layer visibility toggles
  const [showDrivers, setShowDrivers] = useState<boolean>(true);
  const [showCorners, setShowCorners] = useState<boolean>(true);
  const [showSectors, setShowSectors] = useState<boolean>(true);
  const [showPitLane, setShowPitLane] = useState<boolean>(true);
  const [showDRS, setShowDRS] = useState<boolean>(true);
  const [showIncidents, setShowIncidents] = useState<boolean>(true);

  // Zoom & Pan state
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Hover states
  const [hoveredDriver, setHoveredDriver] = useState<Driver | null>(null);
  const [hoveredCorner, setHoveredCorner] = useState<any | null>(null);

  // Track Sensor Popup state
  const [selectedSensor, setSelectedSensor] = useState<SensorPopupData | null>(null);

  const centreline = circuit?.centreline ?? FALLBACK_CENTRELINE;
  const rawViewBox = circuit?.view_box ?? { min_x: 180, min_y: 200, width: 540, height: 450 };

  // Dynamic zoom adjusted viewBox
  const viewBox = useMemo(() => {
    const w = rawViewBox.width / zoomLevel;
    const h = rawViewBox.height / zoomLevel;
    const min_x = rawViewBox.min_x + (rawViewBox.width - w) / 2 + panOffset.x;
    const min_y = rawViewBox.min_y + (rawViewBox.height - h) / 2 + panOffset.y;
    return { min_x, min_y, width: w, height: h };
  }, [rawViewBox, zoomLevel, panOffset]);

  // Precompute distance-weighted spline arc length index
  const splineIndex = useMemo(() => {
    return buildSplineDistanceIndex(centreline);
  }, [centreline]);

  // Sector segments for visual health rendering
  const sectorPaths = useMemo(() => {
    return [
      { num: 1, path: getSplineSubPath(splineIndex, 0.0, 0.33) },
      { num: 2, path: getSplineSubPath(splineIndex, 0.33, 0.66) },
      { num: 3, path: getSplineSubPath(splineIndex, 0.66, 1.0) },
    ];
  }, [splineIndex]);

  // SVG Paths
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

  // -------------------------------------------------------------------------
  // Smooth 60 FPS continuous animation via requestAnimationFrame
  // -------------------------------------------------------------------------
  const carNodesRef = useRef<Map<number, SVGGElement>>(new Map());
  const animStateRef = useRef<Map<number, { current: number; target: number }>>(new Map());

  // Update target progress whenever drivers prop changes
  useEffect(() => {
    const animMap = animStateRef.current;
    for (const d of drivers) {
      const targetP = d.progress ?? (1.0 - (d.position - 1) * 0.045);
      const existing = animMap.get(d.number);
      if (!existing) {
        animMap.set(d.number, { current: targetP, target: targetP });
      } else {
        // Detect lap wrap (e.g. 0.98 -> 0.02)
        if (targetP < existing.current - 0.5) {
          existing.target = targetP + 1.0;
        } else {
          existing.target = targetP;
        }
      }
    }
  }, [drivers]);

  // Run 60 FPS animation loop
  useEffect(() => {
    let animId: number;
    let lastTime = performance.now();

    const loop = (now: number) => {
      const dt = Math.min(0.1, (now - lastTime) / 1000.0);
      lastTime = now;

      const animMap = animStateRef.current;
      const nodeMap = carNodesRef.current;

      for (const [num, state] of animMap.entries()) {
        const diff = state.target - state.current;
        if (Math.abs(diff) > 0.00001) {
          // Lerp towards target smoothly
          state.current += diff * Math.min(1.0, dt * 6.5);
          if (state.current >= 1.0) {
            state.current -= 1.0;
            state.target -= 1.0;
          }
        }

        const el = nodeMap.get(num);
        if (el) {
          const d = drivers.find((x) => x.number === num);
          if (d?.status === 'RETIRED') {
            const rx = rawViewBox.min_x + 30;
            const ry = rawViewBox.min_y + 30 + (d.position % 6) * 16;
            el.setAttribute('transform', `translate(${rx}, ${ry})`);
          } else {
            const [x, y] = interpolatePositionFromIndex(splineIndex, state.current);
            el.setAttribute('transform', `translate(${x.toFixed(2)}, ${y.toFixed(2)})`);
          }
        }
      }

      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [drivers, splineIndex, rawViewBox]);

  const getSectorInfo = (sec: TrackSector) => {
    const num = parseInt(sec.id.replace(/\D/g, '') || '1', 10);
    const cond = sec.condition ? sec.condition.toUpperCase() : '';
    const isYellow = cond.includes('YELLOW') || cond.includes('CAUTION');
    const isRed = cond.includes('RED') || cond.includes('DANGER');
    const isWet = sec.tone === 'wet';
    const isDamp = sec.tone === 'damp';
    const status: 'HEALTHY' | 'SUSPECT' | 'DEGRADED' = isRed ? 'DEGRADED' : isYellow || isWet ? 'SUSPECT' : 'HEALTHY';
    const color = isRed ? '#e10600' : isYellow || isWet ? '#ffd000' : isDamp ? '#38bdf8' : '#3b4b61';
    return { num, isHazard: isRed || isYellow, isRed, status, color };
  };

  // Click gate handler: opens sensor popup
  const handleGateClick = (gateId: string, sectorNumber: number, checkpoint: [number, number]) => {
    const sec = sectors.find((s) => s.id.includes(String(sectorNumber)));
    const info = sec ? getSectorInfo(sec) : { status: 'HEALTHY' as const };
    setSelectedSensor({
      gateId,
      sectorNumber,
      checkpoint,
      name: `Timing Transponder Gate ${gateId} (Sector ${sectorNumber})`,
      status: info.status,
      measurement: sec?.condition ? sec.condition : '31.428s',
      unit: 'seconds (s)',
      source: 'FOM_OPTICAL_LOOP / TIMING_TRANSPONDER_V1',
      contractRef: `C02_sector_sum_consistency / sector_time`,
    });
  };

  return (
    <section className="panel track-panel" aria-labelledby="track-title">
      <div className="panel-heading">
        <div>
          <div className="circuit-header-row">
            <p className="eyebrow">Circuit Geometry & Spatial Telemetry</p>
            {circuit && (
              <span className="circuit-provenance-tag" title={`Source: ${circuit.source_attribution} · Checksum: ${circuit.checksum_sha256}`}>
                {circuit.name} · v{circuit.layout_version} ({(circuit.length_meters / 1000).toFixed(3)} km)
              </span>
            )}
          </div>
          <h2 id="track-title">{circuit?.name ?? 'Circuit de Monaco'} — Real-Time Spatial Tracking</h2>
        </div>

        {/* Live event & Incident Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="event-pill">
            <span className="event-dot" />
            {activeEvent}
          </span>
        </div>
      </div>

      {/* Layer Toggles & Map Control Toolbar */}
      <div className="track-controls-toolbar">
        <div className="layer-toggles-group">
          <span className="toolbar-label">LAYERS:</span>
          <button
            type="button"
            className={`layer-toggle-btn ${showDrivers ? 'is-active' : ''}`}
            onClick={() => setShowDrivers(!showDrivers)}
          >
            Cars ({drivers.length})
          </button>
          <button
            type="button"
            className={`layer-toggle-btn ${showSectors ? 'is-active' : ''}`}
            onClick={() => setShowSectors(!showSectors)}
          >
            Sector Health
          </button>
          <button
            type="button"
            className={`layer-toggle-btn ${showCorners ? 'is-active' : ''}`}
            onClick={() => setShowCorners(!showCorners)}
          >
            Corners ({circuit?.corners?.length ?? 0})
          </button>
          <button
            type="button"
            className={`layer-toggle-btn ${showPitLane ? 'is-active' : ''}`}
            onClick={() => setShowPitLane(!showPitLane)}
          >
            Pit Lane
          </button>
          <button
            type="button"
            className={`layer-toggle-btn ${showDRS ? 'is-active' : ''}`}
            onClick={() => setShowDRS(!showDRS)}
          >
            DRS Zones
          </button>
          <button
            type="button"
            className={`layer-toggle-btn ${showIncidents ? 'is-active' : ''}`}
            onClick={() => setShowIncidents(!showIncidents)}
          >
            Incidents
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="zoom-controls-group">
          <span className="toolbar-label">ZOOM:</span>
          <button
            type="button"
            className="zoom-btn"
            onClick={() => setZoomLevel((z) => Math.max(0.75, z - 0.25))}
            title="Zoom Out"
          >
            −
          </button>
          <span className="zoom-indicator">{(zoomLevel * 100).toFixed(0)}%</span>
          <button
            type="button"
            className="zoom-btn"
            onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.25))}
            title="Zoom In"
          >
            +
          </button>
          <button
            type="button"
            className="zoom-reset-btn"
            onClick={() => {
              setZoomLevel(1.0);
              setPanOffset({ x: 0, y: 0 });
            }}
            title="Reset Zoom and Pan"
          >
            Reset
          </button>
        </div>
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
            <filter id="sector-hazard-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="glow" />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Explicit Boundary Polygons */}
          {outerPath && <path d={outerPath} className="track-boundary outer" />}
          {innerPath && <path d={innerPath} className="track-boundary inner" />}

          {/* Underlay Roadbed Layer */}
          <path
            d={centrelinePath}
            className="track-surface-bed"
            fill="none"
            stroke="#16202c"
            strokeWidth="14"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Base Racing Line Corridor */}
          <path
            d={centrelinePath}
            className="track-line track-line--base"
            fill="none"
            stroke="#2a3748"
            strokeWidth="8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Dynamic Sector Health Visualization Layer */}
          {showSectors &&
            sectorPaths.map((sp) => {
              const sec = sectors.find((s) => s.id.includes(String(sp.num)));
              const info = sec ? getSectorInfo(sec) : { color: '#3b4b61', isHazard: false };

              return (
                <path
                  key={sp.num}
                  d={sp.path}
                  fill="none"
                  stroke={info.color}
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  filter={info.isHazard ? 'url(#sector-hazard-glow)' : undefined}
                  className={`sector-health-segment ${info.isHazard ? 'is-hazard' : ''}`}
                />
              );
            })}

          {/* Telemetry Tracking Groove */}
          <path
            d={centrelinePath}
            className="track-racing-line"
            fill="none"
            stroke="rgba(56, 189, 248, 0.45)"
            strokeWidth="1.5"
            strokeDasharray="6 4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Pit Lane Geometry */}
          {showPitLane && pitPath && (
            <path d={pitPath} className="pit-lane-path" strokeDasharray="4 3" />
          )}

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
              onClick={() => handleGateClick(`G0${sec.sector_number}`, sec.sector_number, sec.checkpoint)}
              style={{ cursor: 'pointer' }}
              role="button"
              tabIndex={0}
              aria-label={`Timing Gate G0${sec.sector_number} Sector ${sec.sector_number}`}
            >
              <circle
                cx={sec.checkpoint[0]}
                cy={sec.checkpoint[1]}
                r="5"
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

          {/* Active Sector Incident Markers */}
          {showIncidents &&
            sectors
              .filter((s) => getSectorInfo(s).isHazard)
              .map((s) => {
                const info = getSectorInfo(s);
                const c = circuit?.sectors?.find((cs) => cs.sector_number === info.num)?.checkpoint;
                if (!c) return null;
                return (
                  <g
                    key={s.id}
                    className="incident-marker-group"
                    onClick={() => handleGateClick(`INC-S0${info.num}`, info.num, c)}
                    style={{ cursor: 'pointer' }}
                  >
                    <circle cx={c[0]} cy={c[1] - 12} r="8" fill={info.isRed ? '#e10600' : '#ffd000'} />
                    <text
                      x={c[0]}
                      y={c[1] - 9}
                      textAnchor="middle"
                      fill="#0d1117"
                      fontSize="9"
                      fontWeight="900"
                    >
                      !
                    </text>
                    <text
                      x={c[0]}
                      y={c[1] - 22}
                      textAnchor="middle"
                      fill={info.isRed ? '#ff4d4f' : '#ffd000'}
                      fontSize="7.5"
                      fontFamily="ui-monospace, monospace"
                      fontWeight="bold"
                    >
                      SEC {info.num} {info.isRed ? 'RED FLAG' : 'YELLOW FLAG'}
                    </text>
                  </g>
                );
              })}

          {/* DRS Zones */}
          {showDRS &&
            circuit?.drs_zones?.map((drs) => (
              <g key={drs.zone_id} className="drs-zone-marker">
                <circle cx={drs.activation_point[0]} cy={drs.activation_point[1]} r="4" fill="#00ff88" />
                <text x={drs.activation_point[0] + 6} y={drs.activation_point[1] - 4} className="drs-label">
                  DRS {drs.zone_id}
                </text>
              </g>
            ))}

          {/* Corner Number Markers */}
          {showCorners &&
            circuit?.corners?.map((c) => (
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

          {/* Interactive Full-Grid Driver Markers (60 FPS animated via requestAnimationFrame) */}
          {showDrivers &&
            drivers
              .filter((d) => d.status !== 'DNS' && d.status !== 'INACTIVE')
              .map((driver) => {
                const inPit = driver.status === 'PIT_LANE';
                const isSelected = selectedDriverNumber === driver.number;
                const isRetired = driver.status === 'RETIRED';

                // Initial position fallback before anim loop takes over
                const p = driver.progress ?? (1.0 - (driver.position - 1) * 0.045);
                const [initX, initY] = interpolatePositionFromIndex(splineIndex, p);
                const teamColor = driver.teamColor || '#FFFFFF';

                return (
                  <g
                    key={driver.number}
                    ref={(el) => {
                      if (el) carNodesRef.current.set(driver.number, el);
                      else carNodesRef.current.delete(driver.number);
                    }}
                    data-driver-number={driver.number}
                    className={`car-node ${isSelected ? 'is-selected' : ''} ${isRetired ? 'is-retired' : ''}`}
                    transform={`translate(${initX.toFixed(2)}, ${initY.toFixed(2)})`}
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
            <small>
              Sector {hoveredCorner.sector}{' '}
              {hoveredCorner.apex_speed_kmh ? `· ${hoveredCorner.apex_speed_kmh} km/h apex` : ''}
            </small>
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
                <span>
                  {hoveredDriver.team} #{hoveredDriver.number}
                </span>
              </div>
              <span className={`status-pill status-pill--${hoveredDriver.status?.toLowerCase() ?? 'active'}`}>
                {hoveredDriver.status ?? 'ACTIVE'}
              </span>
            </div>

            <div className="hover-telemetry-summary">
              <div className="hover-stat">
                <span className="stat-label">SPEED</span>
                <span className="stat-val">
                  {typeof hoveredDriver.telemetry?.speed === 'object'
                    ? hoveredDriver.telemetry.speed?.value ?? '—'
                    : hoveredDriver.telemetry?.speed ?? '—'}{' '}
                  km/h
                </span>
              </div>
              <div className="hover-stat">
                <span className="stat-label">GEAR</span>
                <span className="stat-val">
                  G
                  {typeof hoveredDriver.telemetry?.gear === 'object'
                    ? hoveredDriver.telemetry.gear?.value ?? '—'
                    : hoveredDriver.telemetry?.gear ?? '—'}
                </span>
              </div>
              <div className="hover-stat">
                <span className="stat-label">LAP</span>
                <span className="stat-val">{hoveredDriver.lastLap || '1'}</span>
              </div>
              <div className="hover-stat">
                <span className="stat-label">TYRE</span>
                <span className="stat-val">{hoveredDriver.tyre ?? 'M'}</span>
              </div>
            </div>

            <div className="hover-actions-bar">
              <button
                type="button"
                className="btn-inspect-telemetry"
                onClick={() => onInspectTelemetry?.(hoveredDriver.number)}
              >
                <BarChartIcon size={14} />
                Inspect Full Telemetry & Graph
              </button>
            </div>
          </div>
        )}

        {/* Dedicated Track Sensor Inspection Popup Modal */}
        {selectedSensor && (
          <div className="sensor-modal-overlay" onClick={() => setSelectedSensor(null)}>
            <div className="sensor-popup-card" onClick={(e) => e.stopPropagation()}>
              <div className="sensor-popup-header">
                <div>
                  <span className="sensor-type-badge">TIMING & INTEGRITY GATE</span>
                  <h3>{selectedSensor.name}</h3>
                </div>
                <button
                  type="button"
                  className="btn-close-sensor"
                  onClick={() => setSelectedSensor(null)}
                  aria-label="Close sensor popup"
                >
                  <CloseIcon size={14} />
                </button>
              </div>

              <div className="sensor-popup-body">
                <div className="sensor-meta-grid">
                  <div className="sensor-meta-item">
                    <span className="meta-label">GATE IDENTIFIER</span>
                    <span className="meta-val font-mono">{selectedSensor.gateId}</span>
                  </div>
                  <div className="sensor-meta-item">
                    <span className="meta-label">SECTOR</span>
                    <span className="meta-val">Sector {selectedSensor.sectorNumber}</span>
                  </div>
                  <div className="sensor-meta-item">
                    <span className="meta-label">LATEST READING</span>
                    <span className="meta-val highlight-val">{selectedSensor.measurement}</span>
                  </div>
                  <div className="sensor-meta-item">
                    <span className="meta-label">SIA INTEGRITY</span>
                    <span className={`sensor-state-badge state-${selectedSensor.status.toLowerCase()}`}>
                      {selectedSensor.status}
                    </span>
                  </div>
                  <div className="sensor-meta-item">
                    <span className="meta-label">SOURCE ORIGIN</span>
                    <span className="meta-val text-muted">{selectedSensor.source}</span>
                  </div>
                  <div className="sensor-meta-item">
                    <span className="meta-label">CONTRACT</span>
                    <span className="meta-val font-mono">{selectedSensor.contractRef}</span>
                  </div>
                </div>

                <div className="sensor-actions-row">
                  <button
                    type="button"
                    className="btn-inspect-sensor-contract"
                    onClick={() => {
                      onSelectGate?.(selectedSensor.gateId, selectedSensor.sectorNumber);
                      setSelectedSensor(null);
                    }}
                  >
                    Inspect Decision in SIA Core →
                  </button>
                  <button
                    type="button"
                    className="btn-secondary-dismiss"
                    onClick={() => setSelectedSensor(null)}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
