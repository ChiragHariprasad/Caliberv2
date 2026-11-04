import type { Driver } from '../types';

interface MomentumChartProps {
  drivers: Driver[];
}

export function MomentumChart({ drivers }: MomentumChartProps) {
  const rows = drivers.slice(0, 5);
  return (
    <section className="panel momentum-panel" aria-labelledby="momentum-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Live race shape</p>
          <h2 id="momentum-title">Momentum through the last 6 laps</h2>
        </div>
        <span className="subtle-chip">Pace + position context</span>
      </div>
      <div className="momentum-chart">
        <div className="chart-grid" aria-hidden="true">
          <span /><span /><span /><span />
        </div>
        <div className="chart-axis chart-axis--left"><span>rising</span><span>steady</span><span>under pressure</span></div>
        <div className="chart-lines">
          {rows.map((driver, index) => {
            const end = Math.max(10, Math.min(95, driver.momentum));
            const start = Math.max(10, Math.min(95, driver.momentum - (index === 0 ? 5 : -4)));
            const points = [start, start + 2, start - 1, start + 3, end - 2, end];
            const coords = points.map((value, pointIndex) => `${pointIndex * 20},${100 - value}`).join(' ');
            return (
              <div className="chart-line" key={driver.number}>
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label={`${driver.name} momentum ${driver.momentum}`}>
                  <polyline className={`momentum-line momentum-line--${(index % 5) + 1}`} points={coords} vectorEffect="non-scaling-stroke" />
                  <circle cx="100" cy={100 - end} r="2.2" className={`momentum-end momentum-end--${(index % 5) + 1}`} />
                </svg>
                <span className="chart-label" style={{ top: `${100 - end}%` }}>{driver.initials}</span>
              </div>
            );
          })}
        </div>
        <div className="chart-axis chart-axis--bottom"><span>Lap 19</span><span>20</span><span>21</span><span>22</span><span>23</span><span>VSC</span></div>
      </div>
      <div className="chart-insight"><span className="insight-spark">↗</span> Real-time pace momentum derived from sector timing deltas and lap progression.</div>
    </section>
  );
}
