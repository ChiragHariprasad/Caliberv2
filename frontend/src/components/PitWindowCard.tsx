import type { StrategyOption } from '../types';
import { ClockIcon, ZapIcon } from './icons';

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
          <p className="eyebrow">Strategic Window Analysis · Agent 4 (v1.2.0)</p>
          <h2 id="pit-window-title">{isVSC ? 'VSC Pit Loss Window Compression' : 'Pit Stop Loss & Delta Strategy'}</h2>
        </div>
        <div className="pit-badge-group">
          <span className="pit-opportunity-pill">
            <ZapIcon size={14} className="sparkle-icon" />
            <strong>+10.5s VSC DELTA SAVING</strong>
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
                <span className="saving-text">SAVING: 10.5s Net Saved vs Rivals</span>
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
                <span className="scenario-calc-tag">v{option.calculationVersion ?? '1.2.0'}</span>
              </div>
              <h4 className="scenario-action">{option.action}</h4>
              <div className="scenario-delta">
                <ClockIcon size={12} className="delta-icon" />
                <span>{option.delta}</span>
              </div>
              <p className="scenario-note">{option.note}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="panel-footer-note">
        <span>Calculation Lineage: Under VSC regulations, on-track delta cuts field speed by ~40% while pit lane remains regulated at 60 km/h, yielding a deterministic 10.5s pit loss compression.</span>
      </div>
    </section>
  );
}
