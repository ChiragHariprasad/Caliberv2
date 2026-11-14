import React, { useState } from 'react';
import type { StrategyOption, TrackSector } from '../../types';
import { ChevronDownIcon, ChevronUpIcon } from '../icons';
import { PitWindowCard } from '../PitWindowCard';

interface TacticalDrawerProps {
  strategies: StrategyOption[];
  sectors: TrackSector[];
  activeEvent: string;
  defaultExpanded?: boolean;
}

export const TacticalDrawer: React.FC<TacticalDrawerProps> = ({
  strategies,
  sectors,
  activeEvent,
  defaultExpanded = false,
}) => {
  const [expanded, setExpanded] = useState<boolean>(defaultExpanded);

  return (
    <section className="tactical-drawer panel" aria-labelledby="tactical-drawer-title">
      <div
        className="tactical-drawer__header"
        onClick={() => setExpanded(!expanded)}
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
      >
        <div className="tactical-drawer__title-group">
          <span className="eyebrow">Secondary Analytics</span>
          <h3 id="tactical-drawer-title">Tactical Strategy Models & Sector Weather (Optional Advisory)</h3>
          <span className="tactical-advisory-tag">NON-EPISTEMIC · STRATEGY PREDICTION</span>
        </div>

        <button
          type="button"
          className="tactical-drawer__toggle-btn"
          aria-label={expanded ? 'Collapse tactical strategy drawer' : 'Expand tactical strategy drawer'}
        >
          {expanded ? <ChevronUpIcon size={16} /> : <ChevronDownIcon size={16} />}
          <span className="toggle-label">{expanded ? 'Hide Strategy' : 'View Strategy Advisory'}</span>
        </button>
      </div>

      {expanded && (
        <div className="tactical-drawer__content">
          <div className="tactical-grid-two">
            <PitWindowCard strategies={strategies} activeEvent={activeEvent} />

            <div className="sector-conditions-card">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Physical Surface Analysis</p>
                  <h4>Track Sector Weather & Grip Baselines</h4>
                </div>
              </div>
              <div className="sectors-list">
                {sectors.map((s) => (
                  <div key={s.id} className="sector-condition-row">
                    <span className={`sector-indicator indicator--${s.tone}`} />
                    <div className="sector-info">
                      <strong>{s.label}</strong>
                      <span>{s.condition}</span>
                    </div>
                    <span className="sector-conf">Grip Confidence: {(s.confidence * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

