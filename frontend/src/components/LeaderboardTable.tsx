import { useState } from 'react';
import type { Driver } from '../types';
import { BarChartIcon } from './icons';

interface LeaderboardTableProps {
  drivers: Driver[];
  selectedDriverNumber: number | null;
  onSelectDriver: (driverNumber: number) => void;
  onInspectTelemetry?: (driverNumber: number) => void;
}

const TEAM_COLORS: Record<string, string> = {
  Ferrari: '#E80020',
  McLaren: '#FF8000',
  'Red Bull Racing': '#3671C6',
  'Red Bull': '#3671C6',
  Mercedes: '#27F4D2',
  Williams: '#64C4FF',
  'Aston Martin': '#229971',
  Alpine: '#0093CC',
  'Racing Bulls': '#6692FF',
  'Kick Sauber': '#52E252',
  Haas: '#B6BABD',
};

const TYRE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  S: { bg: '#E80020', text: '#FFFFFF', label: 'SOFT' },
  M: { bg: '#FFD700', text: '#111111', label: 'MED' },
  H: { bg: '#FFFFFF', text: '#111111', label: 'HARD' },
  I: { bg: '#39B54A', text: '#FFFFFF', label: 'INTER' },
  W: { bg: '#0072CE', text: '#FFFFFF', label: 'WET' },
};

export function LeaderboardTable({
  drivers,
  selectedDriverNumber,
  onSelectDriver,
  onInspectTelemetry,
}: LeaderboardTableProps) {
  const [filter, setFilter] = useState<'ALL' | 'ACTIVE' | 'PIT_LANE' | 'RETIRED'>('ALL');

  const filteredDrivers = drivers.filter((d) => {
    if (filter === 'ACTIVE') return d.status === 'ACTIVE' || !d.status;
    if (filter === 'PIT_LANE') return d.status === 'PIT_LANE';
    if (filter === 'RETIRED') return d.status === 'RETIRED' || d.status === 'DNS';
    return true;
  });

  return (
    <section className="panel leaderboard-panel" aria-labelledby="leaderboard-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Timing, Standings & Telemetry</p>
          <h2 id="leaderboard-title">Live Session Leaderboard ({drivers.length} Drivers)</h2>
        </div>
        <div className="leaderboard-filters">
          <button
            type="button"
            className={`filter-btn ${filter === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilter('ALL')}
          >
            All ({drivers.length})
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'ACTIVE' ? 'active' : ''}`}
            onClick={() => setFilter('ACTIVE')}
          >
            Active ({drivers.filter((d) => d.status === 'ACTIVE' || !d.status).length})
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'PIT_LANE' ? 'active' : ''}`}
            onClick={() => setFilter('PIT_LANE')}
          >
            Pit Lane ({drivers.filter((d) => d.status === 'PIT_LANE').length})
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'RETIRED' ? 'active' : ''}`}
            onClick={() => setFilter('RETIRED')}
          >
            Out ({drivers.filter((d) => d.status === 'RETIRED' || d.status === 'DNS').length})
          </button>
        </div>
      </div>

      <div className="table-responsive">
        <table className="f1-leaderboard-table">
          <thead>
            <tr>
              <th scope="col" className="col-pos">POS</th>
              <th scope="col" className="col-driver">DRIVER</th>
              <th scope="col" className="col-status">STATUS</th>
              <th scope="col" className="col-interval">GAP / INT</th>
              <th scope="col" className="col-tyre">TYRE / AGE</th>
              <th scope="col" className="col-lastlap">LAST LAP</th>
              <th scope="col" className="col-tactical">TACTICAL SITUATION</th>
              <th scope="col" className="col-action">ACTION</th>
            </tr>
          </thead>
          <tbody>
            {filteredDrivers.map((driver) => {
              const teamColor = driver.teamColor || TEAM_COLORS[driver.team] || '#718096';
              const tyreInfo = TYRE_COLORS[driver.tyre] || { bg: '#888', text: '#FFF', label: driver.tyre };
              const isSelected = selectedDriverNumber === driver.number;
              const isRetired = driver.status === 'RETIRED' || driver.status === 'DNS';

              return (
                <tr
                  key={driver.number}
                  className={`leaderboard-row ${isSelected ? 'is-selected' : ''} ${isRetired ? 'is-retired-row' : ''}`}
                  onClick={() => onSelectDriver(driver.number)}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  onKeyDown={(e) => e.key === 'Enter' && onSelectDriver(driver.number)}
                >
                  <td className="col-pos">
                    <span className="pos-badge" style={{ borderColor: isSelected ? teamColor : 'transparent' }}>
                      P{driver.position}
                    </span>
                  </td>

                  <td className="col-driver">
                    <div className="driver-identity">
                      <span className="team-indicator-bar" style={{ backgroundColor: teamColor }} />
                      <div className="driver-names">
                        <span className="driver-full-name">{driver.name}</span>
                        <span className="driver-team-tag">{driver.team} #{driver.number}</span>
                      </div>
                    </div>
                  </td>

                  <td className="col-status">
                    <span className={`status-chip status-chip--${(driver.status ?? 'ACTIVE').toLowerCase()}`}>
                      {driver.status ?? 'ACTIVE'}
                    </span>
                  </td>

                  <td className="col-interval">
                    <div className="interval-stack">
                      <span className="gap-value">{driver.gap}</span>
                      {driver.interval !== '—' && (
                        <span className="interval-delta">Δ {driver.interval}</span>
                      )}
                    </div>
                  </td>

                  <td className="col-tyre">
                    <div className="tyre-status-combo">
                      <span
                        className="tyre-badge"
                        style={{ backgroundColor: tyreInfo.bg, color: tyreInfo.text }}
                        title={`${tyreInfo.label} Compound - Stint ${driver.stint}`}
                      >
                        {driver.tyre}
                      </span>
                      <span className="tyre-age-text">{driver.tyreAge} Laps</span>
                    </div>
                  </td>

                  <td className="col-lastlap">
                    <span className="lap-time-value">{driver.lastLap}</span>
                  </td>

                  <td className="col-tactical">
                    <div className={`tactical-badge tone-${driver.impact.tone}`}>
                      <span className="tactical-dot" />
                      <span className="tactical-text">{driver.impact.label}</span>
                    </div>
                  </td>

                  <td className="col-action" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className="btn-row-inspect"
                      title="Inspect Real-time Telemetry"
                      aria-label="Inspect Real-time Telemetry"
                      onClick={() => onInspectTelemetry?.(driver.number)}
                    >
                      <BarChartIcon size={14} className="action-icon" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
