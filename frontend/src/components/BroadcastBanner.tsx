import type { DataMode, PipelineStatus } from '../types';
import { AlertTriangleIcon, BrainIcon, FlagIcon, FlaskIcon, ScaleIcon } from './icons';

interface BroadcastBannerProps {
  sessionName: string;
  lap: number;
  totalLaps: number;
  elapsed: string;
  activeEvent: string;
  mode: DataMode;
  pipelineStatus: PipelineStatus;
  status: string;
  connected: boolean;
  circuitId?: string;
  onChangeCircuit?: (circuitId: string) => void;
  sessionId?: string;
  onChangeSession?: (sessionId: string) => void;
  activeView: 'COCKPIT' | 'RACE_CONTROL' | 'AGENTS' | 'PIPELINE_LAB';
  onChangeView: (view: 'COCKPIT' | 'RACE_CONTROL' | 'AGENTS' | 'PIPELINE_LAB') => void;
}

export function BroadcastBanner({
  sessionName,
  lap,
  totalLaps,
  elapsed,
  activeEvent,
  mode,
  pipelineStatus,
  connected,
  circuitId = 'monaco',
  onChangeCircuit,
  sessionId = 'f1-2026-monaco-sim',
  onChangeSession,
  activeView,
  onChangeView,
}: BroadcastBannerProps) {
  const isVSC = activeEvent.toLowerCase().includes('vsc') || activeEvent.toLowerCase().includes('virtual');
  const isSafetyCar = activeEvent.toLowerCase().includes('safety car') && !isVSC;

  const handleSessionChange = (val: string) => {
    if (val === 'f1-2023-silverstone-race') {
      onChangeCircuit?.('silverstone');
      onChangeSession?.('f1-2023-silverstone-race');
    } else if (val === 'f1-2026-suzuka-preview') {
      onChangeCircuit?.('suzuka');
      onChangeSession?.('f1-2026-suzuka-preview');
    } else {
      onChangeCircuit?.('monaco');
      onChangeSession?.('f1-2026-monaco-sim');
    }
  };

  return (
    <header className="broadcast-banner" role="banner">
      <div className="broadcast-banner__left">
        <div className="f1-brand-badge">
          <span className="brand-dot" />
          <span className="brand-text">PULSE</span>
          <span className="brand-sub">F1 COCKPIT</span>
        </div>

        {/* View Switcher Navigation Tabs */}
        <nav className="cockpit-nav-tabs" aria-label="Cockpit navigation">
          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'COCKPIT' ? 'active' : ''}`}
            onClick={() => onChangeView('COCKPIT')}
          >
            <FlagIcon size={14} className="nav-icon" />
            <span>Cockpit</span>
          </button>
          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'RACE_CONTROL' ? 'active' : ''}`}
            onClick={() => onChangeView('RACE_CONTROL')}
          >
            <ScaleIcon size={14} className="nav-icon" />
            <span>Race Control & Stewarding</span>
          </button>
          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'AGENTS' ? 'active' : ''}`}
            onClick={() => onChangeView('AGENTS')}
          >
            <BrainIcon size={14} className="nav-icon" />
            <span>Agent Operations</span>
          </button>
          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'PIPELINE_LAB' ? 'active' : ''}`}
            onClick={() => onChangeView('PIPELINE_LAB')}
          >
            <FlaskIcon size={14} className="nav-icon" />
            <span>Pipeline Lab</span>
          </button>
        </nav>
      </div>

      <div className="broadcast-banner__center">
        {/* Dynamic Circuit / Session Selector Dropdown */}
        <div className="circuit-picker-dropdown">
          <label htmlFor="circuit-select" className="sr-only">Select Session and Circuit</label>
          <select
            id="circuit-select"
            className="circuit-select-input"
            value={sessionId}
            onChange={(e) => handleSessionChange(e.target.value)}
          >
            <option value="f1-2026-monaco-sim">Monaco GP · Simulation (3.337 km)</option>
            <option value="f1-2023-silverstone-race">Silverstone 2023 · Historical Replay (5.891 km)</option>
            <option value="f1-2026-suzuka-preview">Suzuka Preview · (No Session Data)</option>
          </select>
        </div>

        {/* Caution Ticker */}
        {isVSC && (
          <div className="vsc-alert-ticker pulse-caution-banner">
            <AlertTriangleIcon size={14} className="ticker-icon" />
            <span className="ticker-label">VIRTUAL SAFETY CAR ACTIVE</span>
            <span className="ticker-sub">DELTA TIME ENFORCED · SECTOR 2</span>
          </div>
        )}
        {isSafetyCar && (
          <div className="sc-alert-ticker pulse-caution-banner">
            <AlertTriangleIcon size={14} className="ticker-icon" />
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
        {/* Session Time & Lap */}
        <div className="broadcast-telemetry-pill">
          <span className="telemetry-label">LAP {lap}/{totalLaps}</span>
          <span className="telemetry-value">{elapsed}</span>
        </div>

        {/* Explicit DATA MODE (Strictly separated from Pipeline Status) */}
        <div className={`mode-badge mode-badge--${mode.toLowerCase()}`} title={`Data mode: ${mode}`}>
          <span className="mode-dot" />
          <span>MODE: {mode}</span>
        </div>

        {/* Explicit PIPELINE STATUS */}
        <div className={`pipeline-indicator status-${pipelineStatus.toLowerCase()} ${connected ? 'is-connected' : 'is-disconnected'}`} title={`Pipeline status: ${pipelineStatus}`}>
          <span className="pulse-ping" />
          <span>{connected ? `STREAM: ${pipelineStatus}` : 'RECONNECTING'}</span>
        </div>
      </div>
    </header>
  );
}
