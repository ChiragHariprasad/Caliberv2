import { useEffect, useState } from 'react';
import { fetchDriverTelemetry } from '../api';
import { AlertTriangleIcon, CloseIcon } from './icons';

interface DriverTelemetryModalProps {
  driverNumber: number | null;
  onClose: () => void;
}

export function DriverTelemetryModal({ driverNumber, onClose }: DriverTelemetryModalProps) {
  const [telemetry, setTelemetry] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!driverNumber) return;
    let active = true;

    const load = async () => {
      const data = await fetchDriverTelemetry(driverNumber);
      if (active) {
        setTelemetry(data);
        setLoading(false);
      }
    };

    load();
    const interval = setInterval(load, 500);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [driverNumber]);

  if (!driverNumber) return null;

  const channels = telemetry?.channels ?? {};
  const history = telemetry?.history ?? [];
  const isRetired = telemetry?.status === 'RETIRED';

  // Render SVG time-series graph
  const renderHistoryGraph = () => {
    if (!history.length || isRetired) {
      return (
        <div className="telemetry-unavailable-banner">
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <AlertTriangleIcon size={14} className="text-amber-400" />
            Historical telemetry buffer is unavailable for Car #{driverNumber} ({telemetry?.status ?? 'INACTIVE'}).
          </span>
        </div>
      );
    }

    const width = 640;
    const height = 180;
    const maxSpeed = 350;

    const speedPoints = history.map((pt: any, i: number) => {
      const x = (i / (history.length - 1)) * (width - 40) + 20;
      const y = height - 20 - (pt.speed / maxSpeed) * (height - 40);
      return `${x},${y}`;
    }).join(' ');

    const throttlePoints = history.map((pt: any, i: number) => {
      const x = (i / (history.length - 1)) * (width - 40) + 20;
      const y = height - 20 - (pt.throttle / 100) * (height - 40);
      return `${x},${y}`;
    }).join(' ');

    const brakePoints = history.map((pt: any, i: number) => {
      const x = (i / (history.length - 1)) * (width - 40) + 20;
      const y = height - 20 - (pt.brake / 100) * (height - 40);
      return `${x},${y}`;
    }).join(' ');

    return (
      <div className="telemetry-graph-card">
        <div className="graph-header">
          <h4>Multi-Channel Telemetry Time-Series (Last 10 Seconds)</h4>
          <div className="graph-legend">
            <span className="legend-tag speed">Speed (km/h)</span>
            <span className="legend-tag throttle">Throttle (%)</span>
            <span className="legend-tag brake">Brake (%)</span>
          </div>
        </div>
        <svg viewBox={`0 0 ${width} ${height}`} className="telemetry-svg">
          {/* Grid lines */}
          <line x1="20" y1="20" x2={width - 20} y2="20" stroke="#222e3d" strokeDasharray="3 3" />
          <line x1="20" y1="90" x2={width - 20} y2="90" stroke="#222e3d" strokeDasharray="3 3" />
          <line x1="20" y1={height - 20} x2={width - 20} y2={height - 20} stroke="#445566" />

          {/* Curves */}
          <polyline points={speedPoints} fill="none" stroke="#27f4d2" strokeWidth="2.5" />
          <polyline points={throttlePoints} fill="none" stroke="#00ff88" strokeWidth="1.8" strokeDasharray="2 2" />
          <polyline points={brakePoints} fill="none" stroke="#ff3b30" strokeWidth="2" />
        </svg>
      </div>
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="telemetry-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header" style={{ borderLeft: `6px solid ${telemetry?.team_color ?? '#e80020'}` }}>
          <div>
            <div className="driver-sub-id">
              <span className="car-pos-badge" style={{ backgroundColor: telemetry?.team_color ?? '#e80020' }}>
                P{telemetry?.position ?? '—'}
              </span>
              <span className="team-name">{telemetry?.team ?? 'Formula 1 Team'}</span>
              <span className={`status-pill status-pill--${telemetry?.status?.toLowerCase() ?? 'active'}`}>
                {telemetry?.status ?? 'ACTIVE'}
              </span>
            </div>
            <h2>{telemetry?.name ?? `Car #${driverNumber}`} · Detailed Telemetry Inspection</h2>
          </div>
          <button type="button" className="btn-close-modal" onClick={onClose} aria-label="Close modal">
            <CloseIcon size={16} />
          </button>
        </div>

        {loading ? (
          <div className="modal-loading-state">
            <span className="loading-spinner" />
            <p>Fetching CAN-bus & timing transponder telemetry for Driver #{driverNumber}...</p>
          </div>
        ) : (
          <div className="modal-body">
            {/* Primary Telemetry Gauges Grid */}
            <div className="telemetry-gauges-grid">
              {/* Speed */}
              <div className="gauge-card">
                <span className="gauge-label">VEHICLE SPEED</span>
                <span className="gauge-val">
                  {channels.speed?.quality === 'AVAILABLE' ? (
                    <><strong>{channels.speed.value}</strong> <small>{channels.speed.unit}</small></>
                  ) : (
                    <span className="val-unavailable">UNAVAILABLE</span>
                  )}
                </span>
                <span className="gauge-meta">{channels.speed?.source} · {channels.speed?.freshness_ms}ms freshness</span>
              </div>

              {/* Throttle */}
              <div className="gauge-card">
                <span className="gauge-label">THROTTLE PEDAL</span>
                <span className="gauge-val">
                  {channels.throttle?.quality === 'AVAILABLE' ? (
                    <><strong>{channels.throttle.value}</strong> <small>%</small></>
                  ) : (
                    <span className="val-unavailable">UNAVAILABLE</span>
                  )}
                </span>
                <div className="gauge-bar-track">
                  <div
                    className="gauge-bar-fill throttle-bar"
                    style={{ width: `${channels.throttle?.value ?? 0}%` }}
                  />
                </div>
              </div>

              {/* Brake */}
              <div className="gauge-card">
                <span className="gauge-label">BRAKE PRESSURE</span>
                <span className="gauge-val">
                  {channels.brake?.quality === 'AVAILABLE' ? (
                    <><strong>{channels.brake.value}</strong> <small>%</small></>
                  ) : (
                    <span className="val-unavailable">UNAVAILABLE</span>
                  )}
                </span>
                <div className="gauge-bar-track">
                  <div
                    className="gauge-bar-fill brake-bar"
                    style={{ width: `${channels.brake?.value ?? 0}%` }}
                  />
                </div>
              </div>

              {/* Gear & RPM */}
              <div className="gauge-card">
                <span className="gauge-label">GEAR & ENGINE RPM</span>
                <span className="gauge-val">
                  {channels.gear?.quality === 'AVAILABLE' ? (
                    <><strong>G{channels.gear.value}</strong> <small>({channels.rpm?.value ?? 0} RPM)</small></>
                  ) : (
                    <span className="val-unavailable">UNAVAILABLE</span>
                  )}
                </span>
                <span className="gauge-meta">{channels.rpm?.source}</span>
              </div>

              {/* DRS */}
              <div className="gauge-card">
                <span className="gauge-label">DRS WING STATE</span>
                <span className="gauge-val">
                  {channels.drs?.quality === 'AVAILABLE' ? (
                    <span className={`drs-indicator ${channels.drs.value === 1 ? 'drs-open' : 'drs-closed'}`}>
                      {channels.drs.value === 1 ? 'OPEN (ACTIVE)' : 'CLOSED'}
                    </span>
                  ) : (
                    <span className="val-unavailable">UNAVAILABLE</span>
                  )}
                </span>
                <span className="gauge-meta">{channels.drs?.source}</span>
              </div>

              {/* Tyre & Stint */}
              <div className="gauge-card">
                <span className="gauge-label">TYRE COMPOUND & AGE</span>
                <span className="gauge-val">
                  <strong>{channels.tyre_compound?.value ?? '—'}</strong> <small>({channels.stint_age?.value ?? 0} Laps)</small>
                </span>
                <span className="gauge-meta">{channels.tyre_compound?.source}</span>
              </div>
            </div>

            {/* Time-Series historical graph */}
            {renderHistoryGraph()}

            {/* Channel Quality & Lineage Footer */}
            <div className="telemetry-provenance-footer">
              <span className="prov-title">Telemetry Lineage:</span>
              <span>All telemetry channels are acquired via calibrated timing loops and ECU packets. Missing channels are reported as UNAVAILABLE and are strictly never synthetic.</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

