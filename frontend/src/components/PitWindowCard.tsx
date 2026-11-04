import type { StrategyOption } from '../types';

interface PitWindowCardProps {
  strategies: StrategyOption[];
  activeEvent: string;
}

export function PitWindowCard({ strategies, activeEvent }: PitWindowCardProps) {
  const isVSC = activeEvent.toLowerCase().includes('vsc') || activeEvent.toLowerCase().includes('virtual');

  return (
    <section className="panel pit-window-panel" aria-labelledby="pit-window-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Strategic Opportunity Analysis</p>
          <h2 id="pit-window-title">VSC Pit Loss Window Compression</h2>
        </div>
        <div className="pit-badge-group">
          <span className="pit-opportunity-pill">
            <span className="sparkle-icon">⚡</span>
            <strong>+10.5s FREE STOP WINDOW</strong>
          </span>
        </div>
      </div>

      <div className="pit-window-content">
        {/* Visual comparison bar graph */}
        <div className="pit-delta-comparison">
          <div className="delta-bar-group">
            <div className="delta-label-row">
              <span className="bar-title">Standard Green Flag Pit Loss</span>
              <span className="bar-time">21.5s total transit</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill progress-fill--standard" style={{ width: '100%' }}>
                <span>21.5s</span>
              </div>
            </div>
          </div>

          <div className="delta-bar-group delta-bar-group--highlight">
            <div className="delta-label-row">
              <span className="bar-title">
                <strong>VSC Neutralised Pit Loss</strong>
                <span className="saving-tag">DISCOUNTED</span>
              </span>
              <span className="bar-time highlight-text">11.0s effective loss</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill progress-fill--vsc" style={{ width: '51.1%' }}>
                <span>11.0s</span>
              </div>
              <div className="saving-indicator-marker" style={{ left: '51.1%', width: '48.9%' }}>
                <span className="saving-text">★ 10.5s Net Saved vs Rivals</span>
              </div>
            </div>
          </div>
        </div>

        {/* Tactical Scenario Cards */}
        <div className="strategy-scenarios-grid">
          {strategies.map((option, idx) => (
            <div
              key={idx}
              className={`strategy-scenario-card strategy-scenario-card--${option.tone}`}
            >
              <div className="scenario-card-header">
                <span className="scenario-label">{option.label}</span>
                <span className="scenario-score" title="Strategy confidence score">
                  {option.score}%
                </span>
              </div>
              <h4 className="scenario-action">{option.action}</h4>
              <div className="scenario-delta">
                <span className="delta-icon">⏱</span>
                <span>{option.delta}</span>
              </div>
              <p className="scenario-note">{option.note}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="panel-footer-note">
        <span>ℹ️ VSC neutralisation cuts the field pace by ~40% under delta regulations while pit lane speed limits remain constant at 80 km/h, creating a ~10.5s advantage for drivers stopping during the period.</span>
      </div>
    </section>
  );
}
