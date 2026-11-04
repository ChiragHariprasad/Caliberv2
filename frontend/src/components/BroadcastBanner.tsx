import type { DataMode } from '../types';

interface BroadcastBannerProps {
  sessionName: string;
  lap: number;
  totalLaps: number;
  elapsed: string;
  activeEvent: string;
  mode: DataMode;
  status: string;
  connected: boolean;
}

export function BroadcastBanner({
  sessionName,
  lap,
  totalLaps,
  elapsed,
  activeEvent,
  mode,
  status,
  connected,
}: BroadcastBannerProps) {
  const isVSC = activeEvent.toLowerCase().includes('vsc') || activeEvent.toLowerCase().includes('virtual');
  const isSafetyCar = activeEvent.toLowerCase().includes('safety car') && !isVSC;

  return (
    <header className="broadcast-banner" role="banner">
      <div className="broadcast-banner__left">
        <div className="f1-brand-badge">
          <span className="brand-dot" />
          <span className="brand-text">PULSE</span>
          <span className="brand-sub">RACE INTELLIGENCE</span>
        </div>

        <div className="broadcast-session-tag">
          <span className="session-flag">🏁</span>
          <span className="session-title">{sessionName}</span>
          <span className="session-sep">•</span>
          <span className="session-lap">LAP {lap} <span className="lap-total">/ {totalLaps}</span></span>
        </div>
      </div>

      <div className="broadcast-banner__center">
        {isVSC && (
          <div className="vsc-alert-ticker pulse-caution-banner">
            <span className="ticker-icon">⚠️</span>
            <span className="ticker-label">VIRTUAL SAFETY CAR ACTIVE</span>
            <span className="ticker-sub">DELTA TIME ENFORCED · SECTOR 2 INCIDENT</span>
          </div>
        )}
        {isSafetyCar && (
          <div className="sc-alert-ticker pulse-caution-banner">
            <span className="ticker-icon">🚨</span>
            <span className="ticker-label">SAFETY CAR DEPLOYED</span>
          </div>
        )}
        {!isVSC && !isSafetyCar && (
          <div className="green-flag-ticker">
            <span className="green-indicator" />
            <span className="green-text">TRACK CLEAR · RACING PACE</span>
          </div>
        )}
      </div>

      <div className="broadcast-banner__right">
        <div className="broadcast-telemetry-pill">
          <span className="telemetry-label">SESSION TIME</span>
          <span className="telemetry-value">{elapsed}</span>
        </div>

        <div className={`mode-badge mode-badge--${mode.toLowerCase()}`} title={`Data mode: ${mode}`}>
          <span className="mode-dot" />
          <span>{mode}</span>
        </div>

        <div className={`pipeline-indicator ${connected ? 'is-connected' : 'is-disconnected'}`} title={connected ? 'Streaming pipeline connected' : 'Connecting to stream...'}>
          <span className="pulse-ping" />
          <span>{connected ? 'STREAM CONNECTED' : 'RECONNECTING'}</span>
        </div>
      </div>
    </header>
  );
}
