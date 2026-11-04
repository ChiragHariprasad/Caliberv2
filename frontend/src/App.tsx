import { useEffect, useState } from 'react';
import { connectEventStream, loadSnapshot, requestReplayControl } from './api';
import { BroadcastBanner } from './components/BroadcastBanner';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { ImpactCard } from './components/ImpactCard';
import { LeaderboardTable } from './components/LeaderboardTable';
import { MomentumChart } from './components/MomentumChart';
import { PitWindowCard } from './components/PitWindowCard';
import { PulseTimeline } from './components/PulseTimeline';
import { ReplayControls } from './components/ReplayControls';
import { TrackMap } from './components/TrackMap';
import { fallbackSnapshot } from './data';
import type { Assessment, PulseSnapshot } from './types';

export default function App() {
  const [snapshot, setSnapshot] = useState<PulseSnapshot>(fallbackSnapshot);
  const [connected, setConnected] = useState<boolean>(false);
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(16);
  const [activeEvidenceAssessment, setActiveEvidenceAssessment] = useState<Assessment | null>(null);
  const [replaySpeed, setReplaySpeed] = useState<number>(1.0);
  const [runnerStatus, setRunnerStatus] = useState<string>('RUNNING');

  const refreshState = async () => {
    const res = await loadSnapshot();
    setSnapshot(res.snapshot);
    setConnected(res.connected);
  };

  useEffect(() => {
    // Initial fetch
    refreshState();

    // Setup SSE real-time stream
    const unsubscribe = connectEventStream(
      (newSnapshot) => {
        setSnapshot(newSnapshot);
        setConnected(true);
      },
      () => {
        refreshState();
      },
    );

    // Periodic fallback polling every 3 seconds
    const interval = setInterval(refreshState, 3000);

    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, []);

  const handleControlAction = async (
    action: 'START' | 'PAUSE' | 'RESUME' | 'RESTART' | 'SPEED',
    speedVal?: number,
  ) => {
    if (action === 'PAUSE') {
      setRunnerStatus('PAUSED');
    } else if (action === 'RESUME' || action === 'START') {
      setRunnerStatus('RUNNING');
    } else if (action === 'SPEED' && speedVal !== undefined) {
      setReplaySpeed(speedVal);
    }
    await requestReplayControl(action, speedVal);
    setTimeout(refreshState, 300);
  };

  const selectedDriver = snapshot.drivers.find((d) => d.number === selectedDriverNumber);

  return (
    <div className="pulse-app">
      {/* Live Broadcast Header */}
      <BroadcastBanner
        sessionName={snapshot.sessionName}
        lap={snapshot.lap}
        totalLaps={snapshot.totalLaps}
        elapsed={snapshot.elapsed}
        activeEvent={snapshot.activeEvent}
        mode={snapshot.mode}
        status={snapshot.status}
        connected={connected}
      />

      <main className="dashboard-content">
        {/* Replay and Speed Controls Bar */}
        <ReplayControls
          onControl={handleControlAction}
          status={runnerStatus}
          speed={replaySpeed}
        />

        {/* Section 1: Tactical Pit Window & Circuit Map */}
        <div className="grid-two-columns">
          <PitWindowCard
            strategies={snapshot.strategies}
            activeEvent={snapshot.activeEvent}
          />
          <TrackMap
            sectors={snapshot.sectors}
            drivers={snapshot.drivers}
            activeEvent={snapshot.activeEvent}
          />
        </div>

        {/* Section 2: Driver Leaderboard & Momentum Trendlines */}
        <div className="grid-two-columns leaderboard-momentum-row">
          <LeaderboardTable
            drivers={snapshot.drivers}
            selectedDriverNumber={selectedDriverNumber}
            onSelectDriver={(num) => setSelectedDriverNumber(num)}
          />
          <MomentumChart drivers={snapshot.drivers} />
        </div>

        {/* Section 3: AI Consequence Assessments & Chronological Timeline */}
        <div className="grid-two-columns">
          <section className="panel impact-feed-panel" aria-labelledby="assessments-title">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Fused Intelligence</p>
                <h2 id="assessments-title">Live Tactical Consequence Feed</h2>
              </div>
              <span className="subtle-chip">Deterministic Fusion Engine</span>
            </div>

            <div className="impact-cards-stack">
              {snapshot.assessments.map((assessment) => {
                const driver = snapshot.drivers.find((d) => d.number === assessment.driverNumber);
                return (
                  <ImpactCard
                    key={assessment.id}
                    assessment={assessment}
                    driver={driver}
                    onEvidence={(a) => setActiveEvidenceAssessment(a)}
                  />
                );
              })}
            </div>
          </section>

          <PulseTimeline events={snapshot.timeline} />
        </div>
      </main>

      {/* Slide-over Evidence Drawer ("Why this?") */}
      <EvidenceDrawer
        assessment={activeEvidenceAssessment}
        driver={snapshot.drivers.find((d) => d.number === activeEvidenceAssessment?.driverNumber)}
        onClose={() => setActiveEvidenceAssessment(null)}
      />
    </div>
  );
}
