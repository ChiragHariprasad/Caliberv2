import { useEffect, useState } from 'react';
import {
  connectEventStream,
  fetchCircuit,
  fetchReplayStatus,
  loadSnapshot,
  pauseReplay,
  resetReplay,
  resumeReplay,
  seekReplay,
  selectSession,
  setReplaySpeed,
  startReplay,
} from './api';
import { AgentOperationsView } from './components/AgentOperationsView';
import { BroadcastBanner } from './components/BroadcastBanner';
import { DriverTelemetryModal } from './components/DriverTelemetryModal';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { AlertTriangleIcon, InfoIcon, MapPinIcon } from './components/icons';
import { ImpactCard } from './components/ImpactCard';
import { LeaderboardTable } from './components/LeaderboardTable';
import { PipelineLabView } from './components/PipelineLabView';
import { PitWindowCard } from './components/PitWindowCard';
import { PulseTimeline } from './components/PulseTimeline';
import { RaceControlView } from './components/RaceControlView';
import { ReplayControls } from './components/ReplayControls';
import { TrackMap } from './components/TrackMap';
import { fallbackSnapshot } from './data';
import type { Assessment, CircuitGeometry, Driver, PulseSnapshot, ReplayStatusData } from './types';

export default function App() {
  const [snapshot, setSnapshot] = useState<PulseSnapshot>(fallbackSnapshot);
  const [connected, setConnected] = useState<boolean>(false);
  const [activeView, setActiveView] = useState<'COCKPIT' | 'RACE_CONTROL' | 'AGENTS' | 'PIPELINE_LAB'>('COCKPIT');
  const [circuitId, setCircuitId] = useState<string>('monaco');
  const [sessionId, setSessionId] = useState<string>('f1-2026-monaco-sim');
  const [circuitGeometry, setCircuitGeometry] = useState<CircuitGeometry | null>(null);
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(16);
  const [inspectingDriverNumber, setInspectingDriverNumber] = useState<number | null>(null);
  const [activeEvidenceAssessment, setActiveEvidenceAssessment] = useState<Assessment | null>(null);
  const [replayStatusData, setReplayStatusData] = useState<ReplayStatusData | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'>('DISCONNECTED');

  const isNoSessionData = sessionId === 'f1-2026-suzuka-preview' || snapshot.status === 'NO_SESSION_DATA';

  const refreshState = async () => {
    const res = await loadSnapshot();
    setSnapshot(res.snapshot);
    setConnected(res.connected);
    const rStatus = await fetchReplayStatus();
    if (rStatus) {
      setReplayStatusData(rStatus);
    }
  };

  // Switch session handler
  const handleSessionChange = async (newSessionId: string) => {
    setSessionId(newSessionId);
    let newCircuit = 'monaco';
    if (newSessionId === 'f1-2023-silverstone-race') newCircuit = 'silverstone';
    if (newSessionId === 'f1-2026-suzuka-preview') newCircuit = 'suzuka';
    setCircuitId(newCircuit);

    await selectSession(newSessionId);
    await refreshState();
  };

  // Load circuit geometry when circuitId changes
  useEffect(() => {
    let active = true;
    const loadGeo = async () => {
      const geo = await fetchCircuit(circuitId);
      if (active && geo) {
        setCircuitGeometry(geo);
      }
    };
    loadGeo();
    return () => {
      active = false;
    };
  }, [circuitId]);

  useEffect(() => {
    // Initial fetch
    refreshState();

    // Setup continuous SSE stream with granular typed domain updates
    const unsubscribe = connectEventStream({
      onSnapshot: (newSnapshot) => {
        setSnapshot(newSnapshot);
        setConnected(true);
      },
      onSessionUpdate: (data) => {
        setSnapshot((prev) => ({
          ...prev,
          lap: data.lap ?? prev.lap,
          totalLaps: data.totalLaps ?? prev.totalLaps,
          elapsed: data.elapsed ?? prev.elapsed,
          status: data.status ?? prev.status,
          activeEvent: data.activeEvent ?? prev.activeEvent,
          mode: data.mode ?? prev.mode,
          pipelineStatus: data.pipelineStatus ?? prev.pipelineStatus,
          lastUpdated: 'live',
        }));
      },
      onDriverUpdate: (data) => {
        if (data && Array.isArray(data.drivers)) {
          setSnapshot((prev) => ({ ...prev, drivers: data.drivers, lastUpdated: 'live' }));
        } else if (data && data.driver_number) {
          setSnapshot((prev) => ({
            ...prev,
            drivers: prev.drivers.map((d) => (d.number === data.driver_number ? { ...d, ...data } : d)),
            lastUpdated: 'live',
          }));
        }
      },
      onTrackUpdate: (data) => {
        if (data && Array.isArray(data.sectors)) {
          setSnapshot((prev) => ({ ...prev, sectors: data.sectors, lastUpdated: 'live' }));
        }
      },
      onRaceControlUpdate: (data) => {
        if (data && Array.isArray(data.notices)) {
          setSnapshot((prev) => ({ ...prev, officialNotices: data.notices, lastUpdated: 'live' }));
        }
      },
      onReplayStatusUpdate: (rStatus) => {
        setReplayStatusData(rStatus);
        setSnapshot((prev) => ({
          ...prev,
          lap: rStatus.currentLap ?? prev.lap,
          totalLaps: rStatus.totalLaps ?? prev.totalLaps,
          elapsed: rStatus.elapsed ?? prev.elapsed,
          lastUpdated: 'live',
        }));
      },
      onConnectionChange: (state) => {
        setConnectionStatus(state);
        setConnected(state === 'CONNECTED');
      },
    });

    // Periodic safety sync every 4 seconds
    const interval = setInterval(async () => {
      const rStatus = await fetchReplayStatus();
      if (rStatus) setReplayStatusData(rStatus);
    }, 4000);

    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, []);

  const handleControlAction = async (
    action: 'START' | 'PAUSE' | 'RESUME' | 'RESTART' | 'RESET' | 'SEEK' | 'SPEED',
    val?: any,
  ) => {
    let res: ReplayStatusData | null = null;
    if (action === 'START') {
      res = await startReplay(val);
    } else if (action === 'PAUSE') {
      res = await pauseReplay();
    } else if (action === 'RESUME') {
      res = await resumeReplay();
    } else if (action === 'RESET' || action === 'RESTART') {
      res = await resetReplay();
    } else if (action === 'SEEK') {
      res = await seekReplay({
        targetIndex: val?.targetIndex,
        targetLap: val?.targetLap,
        targetElapsedMs: val?.targetElapsedMs,
      });
    } else if (action === 'SPEED') {
      res = await setReplaySpeed(val);
    }

    if (res) {
      setReplayStatusData(res);
    }
    setTimeout(refreshState, 200);
  };

  return (
    <div className="pulse-app">
      {/* Live Broadcast Header with View Tabs & Circuit / Session Selector */}
      <BroadcastBanner
        sessionName={snapshot.sessionName}
        lap={replayStatusData?.currentLap ?? snapshot.lap}
        totalLaps={replayStatusData?.totalLaps ?? snapshot.totalLaps}
        elapsed={replayStatusData?.elapsed ?? snapshot.elapsed}
        activeEvent={snapshot.activeEvent}
        mode={snapshot.mode}
        pipelineStatus={snapshot.pipelineStatus ?? (connected ? 'CONNECTED' : 'DEGRADED')}
        status={snapshot.status}
        connected={connected}
        circuitId={circuitId}
        onChangeCircuit={(newCircuit) => setCircuitId(newCircuit)}
        sessionId={sessionId}
        onChangeSession={handleSessionChange}
        activeView={activeView}
        onChangeView={(view) => setActiveView(view)}
      />

      <main className="dashboard-content">
        {/* Backend Replay and Speed Controls Bar */}
        <ReplayControls
          statusData={replayStatusData}
          onControl={handleControlAction}
          status={replayStatusData?.status ?? 'READY'}
          speed={replayStatusData?.speed ?? 1.0}
          currentLap={replayStatusData?.currentLap ?? snapshot.lap}
          totalLaps={replayStatusData?.totalLaps ?? snapshot.totalLaps}
          elapsed={replayStatusData?.elapsed ?? snapshot.elapsed}
        />

        {/* Empty State Banner if NO_SESSION_DATA is active */}
        {isNoSessionData && (
          <div className="no-session-data-card" role="status">
            <div className="no-session-header">
              <AlertTriangleIcon size={18} className="text-amber-400" />
              <h3>NO SESSION DATA AVAILABLE</h3>
            </div>
            <p>
              Circuit geometry and centerline coordinate projection for <strong>Suzuka International Racing Course</strong> are active and verified.
              However, timing transponder, CAN-bus telemetry, and race control telemetry captures are not loaded for this session.
            </p>
            <p className="no-session-help">
              To inspect live multi-agent streaming and driver consequence models, select <strong>Monaco GP (Simulation)</strong> or <strong>Silverstone 2023 (Historical Replay)</strong> from the header selector.
            </p>
          </div>
        )}

        {/* VIEW 1: COCKPIT */}
        {activeView === 'COCKPIT' && (
          <div className="cockpit-view-container">
            {/* Row 1: Tactical Pit Window & Interactive Circuit Map */}
            <div className="grid-two-columns">
              {isNoSessionData ? (
                <div className="panel empty-cockpit-panel">
                  <div className="panel-heading">
                    <p className="eyebrow">Strategic Window Analysis</p>
                    <h2>Pit Loss Window Compression</h2>
                  </div>
                  <div className="empty-panel-body">
                    <p>No tyre stint or telemetry data for this circuit.</p>
                  </div>
                </div>
              ) : (
                <PitWindowCard
                  strategies={snapshot.strategies}
                  activeEvent={snapshot.activeEvent}
                />
              )}

              <TrackMap
                circuit={circuitGeometry}
                sectors={snapshot.sectors}
                drivers={snapshot.drivers}
                activeEvent={snapshot.activeEvent}
                selectedDriverNumber={selectedDriverNumber}
                onSelectDriver={(num) => setSelectedDriverNumber(num)}
                onInspectTelemetry={(num) => setInspectingDriverNumber(num)}
              />
            </div>

            {/* Row 2: Full-Grid Leaderboard (20+ Cars) */}
            <div className="leaderboard-full-row">
              {isNoSessionData ? (
                <div className="panel empty-cockpit-panel">
                  <div className="panel-heading">
                    <p className="eyebrow">Driver Standings</p>
                    <h2>Full Grid Entry List</h2>
                  </div>
                  <div className="empty-panel-body">
                    <p>No active driver timing transponders broadcasting in this preview session.</p>
                  </div>
                </div>
              ) : (
                <LeaderboardTable
                  drivers={snapshot.drivers}
                  selectedDriverNumber={selectedDriverNumber}
                  onSelectDriver={(num) => setSelectedDriverNumber(num)}
                  onInspectTelemetry={(num) => setInspectingDriverNumber(num)}
                />
              )}
            </div>

            {/* Row 3: Live Tactical Consequence Feed & Timeline */}
            <div className="grid-two-columns">
              {isNoSessionData ? (
                <div className="panel empty-cockpit-panel">
                  <div className="panel-heading">
                    <p className="eyebrow">Consequence Intelligence</p>
                    <h2>Live Tactical Feed</h2>
                  </div>
                  <div className="empty-panel-body">
                    <p>Consequence Fusion Engine is idle (no input telemetry streams).</p>
                  </div>
                </div>
              ) : (
                <section className="panel impact-feed-panel" aria-labelledby="assessments-title">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">Fused Multi-Agent Intelligence</p>
                      <h2 id="assessments-title">Live Tactical Consequence Feed</h2>
                    </div>
                    <span className="subtle-chip">Agent 5 Fusion</span>
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
              )}

              <PulseTimeline events={snapshot.timeline} />
            </div>
          </div>
        )}

        {/* VIEW 2: RACE CONTROL & STEWARDING */}
        {activeView === 'RACE_CONTROL' && (
          <RaceControlView
            notices={snapshot.officialNotices ?? []}
            timeline={snapshot.timeline}
            assessments={snapshot.assessments}
          />
        )}

        {/* VIEW 3: AGENT OPERATIONS */}
        {activeView === 'AGENTS' && (
          <AgentOperationsView />
        )}

        {/* VIEW 4: PIPELINE LAB */}
        {activeView === 'PIPELINE_LAB' && (
          <PipelineLabView />
        )}
      </main>

      {/* Interactive Driver Telemetry Inspector Modal */}
      {inspectingDriverNumber && (
        <DriverTelemetryModal
          driverNumber={inspectingDriverNumber}
          onClose={() => setInspectingDriverNumber(null)}
        />
      )}

      {/* Slide-over Evidence Drawer ("Why this?") */}
      <EvidenceDrawer
        assessment={activeEvidenceAssessment}
        driver={snapshot.drivers.find((d) => d.number === activeEvidenceAssessment?.driverNumber)}
        onClose={() => setActiveEvidenceAssessment(null)}
      />
    </div>
  );
}
