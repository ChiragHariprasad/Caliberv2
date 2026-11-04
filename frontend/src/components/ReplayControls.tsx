import { useState, type ChangeEvent } from 'react';
import type { ReplayStatusData } from '../types';
import { ClockIcon, PauseIcon, PlayIcon, ResetIcon, SpeedIcon } from './icons';

interface ReplayControlsProps {
  statusData?: ReplayStatusData | null;
  onControl: (action: 'START' | 'PAUSE' | 'RESUME' | 'RESTART' | 'RESET' | 'SEEK' | 'SPEED', value?: any) => void;
  status: string;
  speed: number;
  currentLap?: number;
  totalLaps?: number;
  elapsed?: string;
}

const ALLOWED_SPEEDS = [0.25, 0.5, 1.0, 2.0, 5.0];

export function ReplayControls({
  statusData,
  onControl,
  status,
  speed,
  currentLap = 1,
  totalLaps = 52,
  elapsed = '00:00:00',
}: ReplayControlsProps) {
  const currentSpeed = statusData?.speed ?? speed ?? 1.0;
  const currentStatus = (statusData?.status ?? status ?? 'READY').toUpperCase();
  const isRunning = currentStatus === 'RUNNING';
  const totalEvents = statusData?.totalEvents ?? 100;
  const currentIndex = statusData?.currentIndex ?? 0;
  const [scrubIndex, setScrubIndex] = useState<number | null>(null);

  const displayIndex = scrubIndex !== null ? scrubIndex : currentIndex;
  const progressPercent = statusData?.progressPercent ?? Math.round((displayIndex / Math.max(1, totalEvents)) * 100);

  const handleTogglePlay = () => {
    if (isRunning) {
      onControl('PAUSE');
    } else {
      onControl('RESUME');
    }
  };

  const handleReset = () => {
    setScrubIndex(null);
    onControl('RESET');
  };

  const handleSpeedSelect = (s: number) => {
    onControl('SPEED', s);
  };

  const handleSliderChange = (e: ChangeEvent<HTMLInputElement>) => {
    setScrubIndex(Number(e.target.value));
  };

  const handleSliderCommit = () => {
    if (scrubIndex !== null) {
      onControl('SEEK', { targetIndex: scrubIndex });
      setScrubIndex(null);
    }
  };

  return (
    <div className="replay-controls-bar" role="region" aria-label="Replay Controls">
      {/* Playback Action Buttons */}
      <div className="replay-controls-group">
        <button
          type="button"
          className={`control-btn play-btn ${isRunning ? 'is-active' : ''}`}
          onClick={handleTogglePlay}
          title={isRunning ? 'Pause Replay Stream' : 'Resume / Play Stream'}
          aria-label={isRunning ? 'Pause Replay' : 'Play Replay'}
        >
          {isRunning ? (
            <>
              <PauseIcon size={14} className="btn-icon" />
              <span>Pause</span>
            </>
          ) : (
            <>
              <PlayIcon size={14} className="btn-icon" />
              <span>{currentStatus === 'READY' ? 'Start' : 'Resume'}</span>
            </>
          )}
        </button>

        <button
          type="button"
          className="control-btn restart-btn"
          onClick={handleReset}
          title="Reset to Initial Envelope Cursor"
          aria-label="Reset Replay"
        >
          <ResetIcon size={14} className="btn-icon" />
          <span>Reset</span>
        </button>
      </div>

      {/* Scrub / Seek Timeline Slider */}
      <div className="timeline-scrubber-group">
        <div className="scrubber-header-row">
          <span className="scrubber-label">TIMELINE SCRUBBER</span>
          <span className="scrubber-progress-readout">
            Event {displayIndex} / {totalEvents} ({progressPercent}%)
          </span>
        </div>
        <input
          type="range"
          className="timeline-slider"
          min={0}
          max={Math.max(1, totalEvents - 1)}
          value={displayIndex}
          onChange={handleSliderChange}
          onMouseUp={handleSliderCommit}
          onTouchEnd={handleSliderCommit}
          onKeyUp={handleSliderCommit}
          aria-label="Seek timeline position"
        />
      </div>

      {/* Playback Acceleration Speed Chips */}
      <div className="speed-selector-group">
        <div className="speed-label-wrapper">
          <SpeedIcon size={12} className="inline text-muted" />
          <span className="speed-label">SPEED:</span>
        </div>
        {ALLOWED_SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            className={`speed-chip ${currentSpeed === s ? 'is-selected' : ''}`}
            onClick={() => handleSpeedSelect(s)}
            aria-label={`Playback speed ${s}x`}
          >
            {s}x
          </button>
        ))}
      </div>

      {/* Lap / Elapsed Readout & Status Orb */}
      <div className="replay-readout-group">
        <div className="session-progress-pill">
          <span className="pill-lap">LAP {statusData?.currentLap ?? currentLap}/{statusData?.totalLaps ?? totalLaps}</span>
          <span className="pill-sep">·</span>
          <span className="pill-elapsed flex items-center gap-1">
            <ClockIcon size={12} className="inline" />
            {statusData?.elapsed ?? elapsed}
          </span>
        </div>

        <div className="replay-status-indicator" title={`Backend Replay Status: ${currentStatus}`}>
          <span className={`status-orb status-orb--${currentStatus.toLowerCase()}`} />
          <span className="status-text">{currentStatus}</span>
        </div>
      </div>
    </div>
  );
}
