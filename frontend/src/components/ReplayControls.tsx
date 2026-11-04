import { useState } from 'react';

interface ReplayControlsProps {
  onControl: (action: 'START' | 'PAUSE' | 'RESUME' | 'RESTART' | 'SPEED', speed?: number) => void;
  status: string;
  speed: number;
}

export function ReplayControls({ onControl, status, speed }: ReplayControlsProps) {
  const [currentSpeed, setCurrentSpeed] = useState<number>(speed || 1.0);
  const isPaused = status.toLowerCase() === 'paused';
  const isRunning = status.toLowerCase() === 'running';

  const handleTogglePlay = () => {
    if (isRunning) {
      onControl('PAUSE');
    } else {
      onControl('RESUME');
    }
  };

  const handleSpeedSelect = (s: number) => {
    setCurrentSpeed(s);
    onControl('SPEED', s);
  };

  return (
    <div className="replay-controls-bar" role="region" aria-label="Replay Controls">
      <div className="replay-controls-group">
        <button
          type="button"
          className={`control-btn play-btn ${isRunning ? 'is-active' : ''}`}
          onClick={handleTogglePlay}
          title={isRunning ? 'Pause Replay' : 'Play / Resume Replay'}
        >
          {isRunning ? (
            <>
              <span className="btn-icon">⏸</span>
              <span>Pause</span>
            </>
          ) : (
            <>
              <span className="btn-icon">▶</span>
              <span>Resume</span>
            </>
          )}
        </button>

        <button
          type="button"
          className="control-btn restart-btn"
          onClick={() => onControl('RESTART')}
          title="Restart Scenario"
        >
          <span className="btn-icon">↺</span>
          <span>Restart</span>
        </button>
      </div>

      <div className="speed-selector-group">
        <span className="speed-label">REPLAY SPEED:</span>
        {[0.5, 1.0, 2.0, 4.0].map((s) => (
          <button
            key={s}
            type="button"
            className={`speed-chip ${currentSpeed === s ? 'is-selected' : ''}`}
            onClick={() => handleSpeedSelect(s)}
          >
            {s}x
          </button>
        ))}
      </div>

      <div className="replay-status-indicator">
        <span className={`status-orb status-orb--${status.toLowerCase()}`} />
        <span className="status-text">{status.toUpperCase()}</span>
      </div>
    </div>
  );
}
