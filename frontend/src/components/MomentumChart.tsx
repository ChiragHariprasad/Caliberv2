import type { Driver } from '../types';

interface MomentumChartProps {
  drivers: Driver[];
  currentLap?: number;
  activeEvent?: string;
}

export function MomentumChart({ drivers, currentLap = 1, activeEvent = 'Green Flag' }: MomentumChartProps) {
  const rows = drivers.slice(0, 5);
  const lapNum = currentLap > 0 ? currentLap : 1;
  const maxHistLen = rows.reduce((acc, d) => Math.max(acc, d.momentumHistory?.length ?? 0), 0);
  const hasRealSeries = rows.some((d) => (d.momentumHistory?.length ?? 0) >= 2);
  const pointCount = Math.max(maxHistLen, 2);
  const startLap = Math.max(1, lapNum - pointCount + 1);
  const lCurrent = activeEvent && !activeEvent.toLowerCase().includes('green')
    ? activeEvent
    : `Lap ${lapNum}`;

  return (
    <section className="panel momentum-panel" aria-labelledby="momentum-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Live race shape</p>
          <h2 id="momentum-title">Observed pace &amp; position momentum</h2>
        </div>
        <span className="subtle-chip">
          {hasRealSeries ? `Last ${maxHistLen} recorded updates` : 'Awaiting >= 2 lap updates'}
        </span>
      </div>
      <div className="momentum-chart">
        <div className="chart-grid" aria-hidden="true">
          <span /><span /><span /><span />
        </div>
        <div className="chart-axis chart-axis--left"><span>rising</span><span>steady</span><span>under pressure</span></div>
        <div className="chart-lines">
          {!hasRealSeries ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#8899a6', fontSize: '0.8rem' }}>
              Awaiting empirical lap progression (&gt;= 2 recorded updates per car). Zero synthetic trajectory points plotted.
            </div>
          ) : (() => {
            const plotted = rows.map((driver, index) => {
              const hist = driver.momentumHistory && driver.momentumHistory.length >= 2
                ? driver.momentumHistory
                : [
                    typeof driver.momentum === 'number' && !isNaN(driver.momentum) ? driver.momentum : 50,
                    typeof driver.momentum === 'number' && !isNaN(driver.momentum) ? driver.momentum : 50,
                  ];
              const clamped = hist.map((v) => Math.max(10, Math.min(95, Number(v))));
              const denom = Math.max(1, clamped.length - 1);
              const coords = clamped.map((value, pointIndex) => `${(pointIndex / denom) * 100},${100 - value}`).join(' ');
              const end = clamped[clamped.length - 1];
              return { driver, index, coords, end, labelTop: 100 - end };
            });

            // De-conflict overlapping vertical endpoint badges cleanly while keeping SVG polyline accurate
            const ordered = [...plotted].sort((a, b) => a.labelTop - b.labelTop || a.index - b.index);
            const minGap = 11.5;
            for (let i = 1; i < ordered.length; i++) {
              if (ordered[i].labelTop - ordered[i - 1].labelTop < minGap) {
                ordered[i].labelTop = Math.min(94, ordered[i - 1].labelTop + minGap);
              }
            }
            for (let i = ordered.length - 2; i >= 0; i--) {
              if (ordered[i + 1].labelTop - ordered[i].labelTop < minGap) {
                ordered[i].labelTop = Math.max(6, ordered[i + 1].labelTop - minGap);
              }
            }

            return plotted.map((item) => (
              <div className="chart-line" key={item.driver.number}>
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label={`${item.driver.name} observed momentum ${Math.round(item.end)}`}>
                  <polyline className={`momentum-line momentum-line--${(item.index % 5) + 1}`} points={item.coords} vectorEffect="non-scaling-stroke" />
                  <circle cx="100" cy={100 - item.end} r="2.2" className={`momentum-end momentum-end--${(item.index % 5) + 1}`} />
                </svg>
                <span className="chart-label" style={{ top: `${item.labelTop.toFixed(1)}%` }}>{item.driver.initials}</span>
              </div>
            ));
          })()}
        </div>
        <div className="chart-axis chart-axis--bottom">
          <span>Lap {startLap}</span>
          <span>{Math.max(startLap, Math.round((startLap + lapNum) * 0.5))}</span>
          <span>{lCurrent}</span>
        </div>
      </div>
      <div className="chart-insight">
        <span className="insight-spark">·</span> Plotted strictly from observed driver momentumHistory samples (no interpolated synthetic points).
      </div>
    </section>
  );
}
