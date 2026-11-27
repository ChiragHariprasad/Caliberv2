import type { StrategyOption } from '../types';
import { ClockIcon, ZapIcon } from './icons';

interface PitWindowCardProps {
  strategies: StrategyOption[];
  activeEvent: string;
}

export function PitWindowCard({ strategies, activeEvent }: PitWindowCardProps) {
  const isVSC = activeEvent.toLowerCase().includes('vsc') || activeEvent.toLowerCase().includes('virtual');
  const isSafetyCar = activeEvent.toLowerCase().includes('safety car') && !isVSC;
  const isNeutralised = isVSC || isSafetyCar;

  const standardLoss = 21.5;
  const effectiveLoss = isSafetyCar ? 8.7 : (isVSC ? 11.0 : 21.5);
  const savingDelta = standardLoss - effectiveLoss;
  const vscWidthPct = Math.round((effectiveLoss / standardLoss) * 1000) / 10;
  const savingWidthPct = 100 - vscWidthPct;

  return (
    <section className="panel pit-window-panel" aria-labelledby="pit-window-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Strategic Window Analysis · Agent 4 (v1.2.0)</p>
          <h2 id="pit-window-title">
            {isVSC
              ? 'VSC Pit Loss Window Compression'
              : isSafetyCar
                ? 'Safety Car Cheap Pit Window'
                : 'Pit Stop Loss & Delta Strategy'}
          </h2>
        </div>
        <div className="pit-badge-group">
          {isNeutralised ? (
            <span className="pit-opportunity-pill">
              <ZapIcon size={14} className="sparkle-icon" />
              <strong>+{savingDelta.toFixed(1)}s {isSafetyCar ? 'SC' : 'VSC'} DELTA SAVING</strong>
            </span>
          ) : (
            <span className="pit-standard-pill">
              <ClockIcon size={14} className="sparkle-icon" />
              <strong>GREEN FLAG · STANDARD STOP</strong>
            </span>
          )}
        </div>
      </div>

      <div className="pit-window-content">
        {/* Visual comparison bar graph */}
        <div className="pit-delta-comparison">
          <div className="delta-bar-group">
            <div className="delta-label-row">
              <span className="bar-title">Standard Green Flag Pit Loss</span>
              <span className="bar-time">{standardLoss.toFixed(1)}s total transit</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill progress-fill--standard" style={{ width: '100%' }}>
                <span>{standardLoss.toFixed(1)}s</span>
              </div>
            </div>
          </div>

          <div className="delta-bar-group delta-bar-group--highlight">
            <div className="delta-label-row">
              <span className="bar-title">
                <strong>{isSafetyCar ? 'Safety Car Pit Loss' : isVSC ? 'VSC Neutralised Pit Loss' : 'Current Projected Stop Loss'}</strong>
                {isNeutralised && <span className="saving-tag">DISCOUNTED</span>}
              </span>
              <span className="bar-time highlight-text">{effectiveLoss.toFixed(1)}s effective loss</span>
            </div>
            <div className="progress-track">
              <div
                className={`progress-fill ${isNeutralised ? 'progress-fill--vsc' : 'progress-fill--standard'}`}
                style={{ width: `${vscWidthPct}%` }}
              >
                <span>{effectiveLoss.toFixed(1)}s</span>
              </div>
              {isNeutralised && (
                <div className="saving-indicator-marker" style={{ left: `${vscWidthPct}%`, width: `${savingWidthPct}%` }}>
                  <span className="saving-text">SAVING: {savingDelta.toFixed(1)}s Net Saved vs Rivals</span>
                </div>
              )}
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
        <span>
          {isNeutralised
            ? `Calculation Lineage: Under neutralisation regulations, on-track delta cuts field speed by ~40% while pit lane remains regulated at 60 km/h, yielding a deterministic ${savingDelta.toFixed(1)}s pit loss compression.`
            : 'Calculation Lineage: Standard race conditions at full racing speeds. Pit lane transit penalty is ~21.5s total time loss.'}
        </span>
      </div>
    </section>
  );
}
