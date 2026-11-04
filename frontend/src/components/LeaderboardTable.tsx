import type { Driver } from '../types';

interface LeaderboardTableProps {
  drivers: Driver[];
  selectedDriverNumber: number | null;
  onSelectDriver: (driverNumber: number) => void;
}

const TEAM_COLORS: Record<string, string> = {
  Ferrari: '#E80020',
  McLaren: '#FF8000',
  'Red Bull Racing': '#3671C6',
  'Red Bull': '#3671C6',
  Mercedes: '#27F4D2',
  Williams: '#64C4FF',
  'Aston Martin': '#229971',
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
}: LeaderboardTableProps) {
  return (
    <section className="panel leaderboard-panel" aria-labelledby="leaderboard-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Timing & Positions</p>
          <h2 id="leaderboard-title">Live Driver Standings</h2>
        </div>
        <span className="subtle-chip">{drivers.length} Cars Tracked</span>
      </div>

      <div className="table-responsive">
        <table className="f1-leaderboard-table">
          <thead>
            <tr>
              <th scope="col" className="col-pos">POS</th>
              <th scope="col" className="col-driver">DRIVER</th>
              <th scope="col" className="col-interval">GAP / INT</th>
              <th scope="col" className="col-tyre">TYRE / AGE</th>
              <th scope="col" className="col-lastlap">LAST LAP</th>
              <th scope="col" className="col-momentum">MOMENTUM</th>
              <th scope="col" className="col-tactical">TACTICAL SITUATION</th>
            </tr>
          </thead>
          <tbody>
            {drivers.map((driver) => {
              const teamColor = TEAM_COLORS[driver.team] || '#718096';
              const tyreInfo = TYRE_COLORS[driver.tyre] || { bg: '#888', text: '#FFF', label: driver.tyre };
              const isSelected = selectedDriverNumber === driver.number;
              const degradationPercent = Math.min(100, Math.round((driver.tyreAge / 32) * 100));

              return (
                <tr
                  key={driver.number}
                  className={`leaderboard-row ${isSelected ? 'is-selected' : ''}`}
                  onClick={() => onSelectDriver(driver.number)}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  onKeyDown={(e) => e.key === 'Enter' && onSelectDriver(driver.number)}
                >
                  <td className="col-pos">
                    <span className="pos-badge">P{driver.position}</span>
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
                      <div className="tyre-age-gauge">
                        <span className="age-label">{driver.tyreAge} Laps</span>
                        <div className="mini-progress-bar" title={`Tyre degradation ~${degradationPercent}%`}>
                          <div
                            className={`mini-progress-fill ${degradationPercent > 70 ? 'fill-worn' : ''}`}
                            style={{ width: `${degradationPercent}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </td>

                  <td className="col-lastlap">
                    <span className="lap-time-code">{driver.lastLap}</span>
                  </td>

                  <td className="col-momentum">
                    <div className="momentum-score-wrapper">
                      <div className="momentum-bar-bg">
                        <div
                          className={`momentum-bar-fill ${driver.momentum > 70 ? 'momentum-high' : driver.momentum < 40 ? 'momentum-low' : 'momentum-mid'}`}
                          style={{ width: `${driver.momentum}%` }}
                        />
                      </div>
                      <span className="momentum-val">{driver.momentum}</span>
                    </div>
                  </td>

                  <td className="col-tactical">
                    <span className={`tactical-pill tactical-pill--${driver.impact.tone}`}>
                      <span className="pill-dot" />
                      {driver.impact.label}
                    </span>
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
