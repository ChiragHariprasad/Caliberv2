import React, { useState } from 'react';
import type { Driver } from '../../types';
import { BarChartIcon } from '../icons';

interface ParticipantShelfProps {
  drivers: Driver[];
  selectedDriverNumber: number | null;
  onSelectDriver: (driverNumber: number) => void;
  onInspectTelemetry?: (driverNumber: number) => void;
  onHoverDriver?: (driver: Driver | null) => void;
  className?: string;
}

const TYRE_CLASSES: Record<string, string> = {
  S: 'tyre-soft',
  M: 'tyre-med',
  H: 'tyre-hard',
  I: 'tyre-inter',
  W: 'tyre-wet',
};

export const ParticipantShelf: React.FC<ParticipantShelfProps> = ({
  drivers,
  selectedDriverNumber,
  onSelectDriver,
  onInspectTelemetry,
  onHoverDriver,
  className = '',
}) => {
  const [filter, setFilter] = useState<'ALL' | 'ACTIVE' | 'PIT_LANE' | 'RETIRED'>('ALL');
  const [search, setSearch] = useState<string>('');

  const filtered = drivers
    .filter((d) => {
      if (filter === 'ACTIVE') return d.status === 'ACTIVE' || !d.status;
      if (filter === 'PIT_LANE') return d.status === 'PIT_LANE';
      if (filter === 'RETIRED') return d.status === 'RETIRED' || d.status === 'DNS';
      return true;
    })
    .filter((d) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        d.name.toLowerCase().includes(q) ||
        d.team.toLowerCase().includes(q) ||
        d.number.toString().includes(q)
      );
    })
    .sort((a, b) => (a.position - b.position) || (a.number - b.number));

  return (
    <aside className={`participant-shelf ${className}`} aria-label="Participant Telemetry Shelf">
      {/* Header & Filter Controls */}
      <div className="participant-shelf__header">
        <div className="shelf-title-row">
          <h3>Participants ({drivers.length})</h3>
          <span className="shelf-subtitle">Live CAN-Bus & Transponder Streams</span>
        </div>

        <div className="shelf-controls">
          <input
            id="participant-search"
            name="participant_search"
            type="search"
            className="shelf-search-input"
            placeholder="Search driver or car #..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Filter participants by name or number"
          />

          <div className="shelf-filter-chips">
            {(['ALL', 'ACTIVE', 'PIT_LANE', 'RETIRED'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                className={`shelf-chip ${filter === mode ? 'is-active' : ''}`}
                onClick={() => setFilter(mode)}
              >
                {mode === 'ALL' ? 'All' : mode === 'ACTIVE' ? 'Track' : mode === 'PIT_LANE' ? 'Pit' : 'Out'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Scrollable Cards List */}
      <div className="participant-shelf__list">
        {filtered.length === 0 ? (
          <div className="shelf-empty-state">
            <p>No participants match current filter.</p>
          </div>
        ) : (
          filtered.map((driver) => {
            const isSelected = selectedDriverNumber === driver.number;
            const teamColor = driver.teamColor || '#E80020';
            const speedVal = driver.telemetry?.speed?.value ?? '—';
            const throttleVal = typeof driver.telemetry?.throttle?.value === 'number' ? driver.telemetry.throttle.value : 0;
            const brakeVal = typeof driver.telemetry?.brake?.value === 'number' ? driver.telemetry.brake.value : 0;
            const gearVal = driver.telemetry?.gear?.value ?? '—';
            const drsVal = driver.telemetry?.drs?.value;
            const isDRSActive = drsVal === 1 || drsVal === '1';
            const tyreClass = TYRE_CLASSES[driver.tyre] || 'tyre-med';

            return (
              <div
                key={driver.number}
                className={`participant-card ${isSelected ? 'is-selected' : ''} ${driver.status === 'RETIRED' ? 'is-retired' : ''}`}
                style={{ borderLeftColor: teamColor }}
                onMouseEnter={() => onHoverDriver?.(driver)}
                onMouseLeave={() => onHoverDriver?.(null)}
              >
                {/* Header: Pos, Car#, Name, Status */}
                <button
                  type="button"
                  className="participant-card__select-surface"
                  onClick={() => {
                    onSelectDriver(driver.number);
                    onInspectTelemetry?.(driver.number);
                  }}
                  aria-label={`Select and inspect Car #${driver.number} ${driver.name} Position ${driver.position}`}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    padding: 0,
                    margin: 0,
                    width: '100%',
                    textAlign: 'left',
                    color: 'inherit',
                    cursor: 'pointer',
                    display: 'block',
                  }}
                >
                <div className="participant-card__header">
                  <div className="p-ident">
                    <span className="p-pos-tag" style={{ backgroundColor: teamColor }}>
                      P{driver.position}
                    </span>
                    <span className="p-car-num">#{driver.number}</span>
                    <strong className="p-name">{driver.name}</strong>
                  </div>
                  <span className={`p-status-pill p-status--${driver.status?.toLowerCase() ?? 'active'}`}>
                    {driver.status ?? 'ACTIVE'}
                  </span>
                </div>

                {/* Metrics Row: Speed, Gear, Throttle/Brake, DRS */}
                <div className="participant-card__metrics">
                  <div className="metric-col speed-col">
                    <span className="val-speed">{speedVal}</span>
                    <span className="unit-label">km/h</span>
                  </div>

                  <div className="metric-col gear-col">
                    <span className="val-gear">G{gearVal}</span>
                    <span className={`drs-pill ${isDRSActive ? 'drs-on' : 'drs-off'}`}>
                      {isDRSActive ? 'DRS' : 'DRS OFF'}
                    </span>
                  </div>

                  {/* Throttle & Brake Micro-Bars */}
                  <div className="pedal-bars-col">
                    <div className="pedal-bar-track">
                      <div className="pedal-bar-fill fill-throttle" style={{ width: `${Math.min(100, throttleVal)}%` }} />
                    </div>
                    <div className="pedal-bar-track">
                      <div className="pedal-bar-fill fill-brake" style={{ width: `${Math.min(100, brakeVal)}%` }} />
                    </div>
                  </div>

                  {/* Tyre & Gap */}
                  <div className="tyre-gap-col">
                    <span className={`tyre-badge ${tyreClass}`}>
                      {driver.tyre} <small>{driver.tyreAge}L</small>
                    </span>
                    <span className="val-gap">{driver.gap || 'LEAD'}</span>
                  </div>
                </div>
                </button>

                {/* Footer: Evidence & Contract Links */}
                <div className="participant-card__footer">
                  <div className="evidence-link-tags">
                    <span className="ev-tag" title="Evidence evaluated in Lap Time Consistency (C01)">C01 Lap</span>
                    <span className="ev-tag" title="Evidence evaluated in Pit Lane Speed Integrity (C03)">C03 Pit</span>
                    {driver.position <= 5 && (
                      <span className="ev-tag" title="Evidence evaluated in Kinematic Plausibility (C04)">C04 Kinem</span>
                    )}
                  </div>

                  <button
                    type="button"
                    className="shelf-inspect-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      onInspectTelemetry?.(driver.number);
                    }}
                    title="Open live telemetry waveform modal"
                  >
                    <BarChartIcon size={12} className="inline mr-1" />
                    Inspect
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
