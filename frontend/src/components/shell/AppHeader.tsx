import React from 'react';
import type { DataMode, PipelineStatus } from '../../types';
import type { PulseView } from '../../types/calibre';
import {
  AlertTriangleIcon,
  BrainIcon,
  ClockIcon,
  FlagIcon,
  FlaskIcon,
  ScaleIcon,
  ShieldIcon,
  ZapIcon,
} from '../icons';
import { RegimePill, type DataRegime } from '../shared/RegimePill';

export interface AppHeaderProps {
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
  activeView: PulseView;
  onChangeView: (view: PulseView) => void;
  dataRegime?: DataRegime | string;
  validTimeUtc?: string | null;
  knowledgeTimeUtc?: string | null;
  transportMode?: string;
}

export const SESSION_OPTIONS = [
  // Landmark Controversy Historical Corpus
  { id: 'f1-2021-abu-dhabi', circuitId: 'yas_marina', label: 'Abu Dhabi Grand Prix 2021 · Yas Marina (5.281 km) [Historical]' },
  { id: 'f1-2021-belgium', circuitId: 'spa', label: 'Belgian Grand Prix 2021 · Spa-Francorchamps (7.004 km) [Historical]' },
  { id: 'f1-2021-saudi-arabia', circuitId: 'jeddah', label: 'Saudi Arabian Grand Prix 2021 · Jeddah Corniche (6.174 km) [Historical]' },
  { id: 'f1-2023-silverstone-race', circuitId: 'silverstone', label: 'British Grand Prix 2023 · Silverstone (5.891 km) [Historical]' },
  { id: 'f1-2023-austria', circuitId: 'red_bull_ring', label: 'Austrian Grand Prix 2023 · Red Bull Ring (4.318 km) [Historical]' },
  { id: 'f1-2023-australia', circuitId: 'albert_park', label: 'Australian Grand Prix 2023 · Albert Park (5.278 km) [Historical]' },
  { id: 'f1-2024-united-states', circuitId: 'cota', label: 'United States Grand Prix 2024 · COTA (5.513 km) [Historical]' },
  { id: 'f1-2023-las-vegas', circuitId: 'las_vegas', label: 'Las Vegas Grand Prix 2023 · Las Vegas Strip (6.201 km) [Historical]' },
  // Real-Time High-Density Simulations & Homologated Previews
  { id: 'f1-2026-monaco-sim', circuitId: 'monaco', label: 'Monaco Grand Prix · Circuit de Monaco (3.337 km) [Sim]' },
  { id: 'f1-2026-suzuka-race', circuitId: 'suzuka', label: 'Japanese Grand Prix · Suzuka Circuit (5.807 km) [Sim]' },
  { id: 'f1-2026-suzuka-preview', circuitId: 'suzuka', label: 'Suzuka Preview · Homologated Geometry [Preview]' },
];

export const AppHeader: React.FC<AppHeaderProps> = ({
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
  dataRegime = 'PUBLIC',
  validTimeUtc,
  knowledgeTimeUtc,
  transportMode = 'IN-MEMORY BUS',
}) => {
  const isVSC = activeEvent.toLowerCase().includes('vsc') || activeEvent.toLowerCase().includes('virtual');
  const isSafetyCar = activeEvent.toLowerCase().includes('safety car') && !isVSC;

  const handleSessionChange = (val: string) => {
    const match = SESSION_OPTIONS.find((s) => s.id === val);
    if (match) {
      onChangeCircuit?.(match.circuitId);
      onChangeSession?.(match.id);
    }
  };

  return (
    <header className="app-header broadcast-banner" role="banner">
      {/* Brand & Primary Navigation Tabs */}
      <div className="app-header__left broadcast-banner__left">
        <div className="f1-brand-badge" title="PULSE — CALIBRE Evidence Integrity Platform">
          <span className="brand-dot" />
          <span className="brand-text">PULSE</span>
          <span className="brand-sub">CALIBRE F1</span>
        </div>

        {/* 5 Principal Operational View Tabs */}
        <nav className="cockpit-nav-tabs" aria-label="PULSE Primary Navigation">
          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'TRACKSIDE' ? 'active' : ''}`}
            onClick={() => onChangeView('TRACKSIDE')}
            title="Trackside: Spatial tracking & participant telemetry shelf"
          >
            <FlagIcon size={14} className="nav-icon" />
            <span>Trackside</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'INTEGRITY_BOARD' ? 'active' : ''}`}
            onClick={() => onChangeView('INTEGRITY_BOARD')}
            title="Integrity Board: Multi-contract evidence matrix & 3-click inspector"
          >
            <ShieldIcon size={14} className="nav-icon" />
            <span>Integrity Board</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'SIA_LOGIC_LAB' ? 'active' : ''}`}
            onClick={() => onChangeView('SIA_LOGIC_LAB')}
            title="SIA Logic Lab: Possible-world superposition & origin entanglement"
          >
            <BrainIcon size={14} className="nav-icon" />
            <span>SIA Logic Lab</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'AGENTS_PIPELINE' ? 'active' : ''}`}
            onClick={() => onChangeView('AGENTS_PIPELINE')}
            title="Agents & Pipeline: Execution transparency & stream transport diagnostics"
          >
            <ZapIcon size={14} className="nav-icon" />
            <span>Agents & Pipeline</span>
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeView === 'REPLAY_AUDIT' ? 'active' : ''}`}
            onClick={() => onChangeView('REPLAY_AUDIT')}
            title="Replay & Audit: Bitemporal time machine & hash-chain ledger verification"
          >
            <ClockIcon size={14} className="nav-icon" />
            <span>Replay & Audit</span>
          </button>
        </nav>
      </div>

      {/* Center: Session Dropdown & Active Directives */}
      <div className="app-header__center broadcast-banner__center">
        <div className="circuit-picker-dropdown">
          <label htmlFor="circuit-select" className="sr-only">Select Session and Circuit</label>
          <select
            id="circuit-select"
            name="circuit_select"
            className="circuit-select-input"
            value={sessionId}
            onChange={(e) => handleSessionChange(e.target.value)}
          >
            <optgroup label="FIA Historical Controversy Corpus (2021–2024)">
              {SESSION_OPTIONS.filter((s) => s.id.includes('historical') || !s.id.includes('sim') && !s.id.includes('preview')).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </optgroup>
            <optgroup label="Real-Time Simulations & Homologated Previews">
              {SESSION_OPTIONS.filter((s) => s.id.includes('sim') || s.id.includes('preview')).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </optgroup>
          </select>
        </div>

        {/* Cautions / Safety Car Alert */}
        {isVSC && (
          <div className="vsc-alert-ticker pulse-caution-banner" role="alert">
            <AlertTriangleIcon size={14} className="ticker-icon" />
            <span className="ticker-text">VIRTUAL SAFETY CAR DEPLOYED · SPEED REDUCTION ACTIVE</span>
          </div>
        )}
        {isSafetyCar && (
          <div className="safety-car-ticker pulse-caution-banner" role="alert">
            <AlertTriangleIcon size={14} className="ticker-icon text-amber-400" />
            <span className="ticker-text">PHYSICAL SAFETY CAR DEPLOYED</span>
          </div>
        )}
      </div>

      {/* Right: Data Regime Pill & Persistent Dual-Time Coordinates */}
      <div className="app-header__right broadcast-banner__right">
        <RegimePill regime={dataRegime} showWarning={true} />

        <div className="dual-time-readout" title="Bitemporal Coordinates: Valid Time (Track) vs Knowledge Time (Sequencer)">
          <div className="time-coord">
            <span className="time-coord__label">VALID-T:</span>
            <span className="time-coord__val">L{lap}/{totalLaps} · {elapsed}</span>
          </div>
          <div className="time-coord">
            <span className="time-coord__label">TRANSPORT:</span>
            <span className={`time-coord__status ${connected ? 'is-connected' : 'is-disconnected'}`}>
              {connected ? transportMode : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};

