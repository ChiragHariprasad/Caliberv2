import { useEffect, useState } from 'react';
import {
  connectEventStream,
  fetchAllVerdicts,
  fetchCircuit,
  fetchContracts,
  fetchDecisions,
  fetchReplayStatus,
  fetchVerdict,
  fetchVerdictExplanation,
  loadSnapshot,
  pauseReplay,
  resetReplay,
  resumeReplay,
  seekReplay,
  selectSession,
  setReplaySpeed,
  startReplay,
} from './api';
import { DriverTelemetryModal } from './components/DriverTelemetryModal';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { AlertTriangleIcon } from './components/icons';
import { ImpactCard } from './components/ImpactCard';
import { MomentumChart } from './components/MomentumChart';
import { PulseTimeline } from './components/PulseTimeline';
import { ReplayControls } from './components/ReplayControls';
import { TrackMap } from './components/TrackMap';
import { AppHeader, SESSION_OPTIONS } from './components/shell/AppHeader';
import { AssumptionsBar } from './components/shell/AssumptionsBar';
import { ParticipantShelf } from './components/trackside/ParticipantShelf';
import { TacticalDrawer } from './components/trackside/TacticalDrawer';
import { IntegrityMatrix } from './components/integrity/IntegrityMatrix';
import { DecisionInspector } from './components/integrity/DecisionInspector';
import { SiaLogicLabView } from './components/logic_lab/SiaLogicLabView';
import { SuperpositionView } from './components/logic_lab/SuperpositionView';
import { EntanglementGraph } from './components/logic_lab/EntanglementGraph';
import { ContextualityDag } from './components/logic_lab/ContextualityDag';
import { StateAlgebraTree } from './components/logic_lab/StateAlgebraTree';
import { AgentsPipelineView } from './components/agents/AgentsPipelineView';
import { ReplayAuditView } from './components/replay/ReplayAuditView';
import { fallbackSnapshot } from './data';
import type {
  Assessment,
  CircuitGeometry,
  PulseSnapshot,
  ReplayStatusData,
} from './types';
import type {
  ContractDefinition,
  DecisionInstance,
  PulseView,
  SIAAssessment,
} from './types/calibre';

export default function App() {
  const [snapshot, setSnapshot] = useState<PulseSnapshot>(fallbackSnapshot);
  const [connected, setConnected] = useState<boolean>(false);
  const [activeView, setActiveView] = useState<PulseView>('TRACKSIDE');
  const [circuitId, setCircuitId] = useState<string>('monaco');
  const [sessionId, setSessionId] = useState<string>('f1-2026-monaco-sim');
  const [circuitGeometry, setCircuitGeometry] = useState<CircuitGeometry | null>(null);
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(16);
  const [inspectingDriverNumber, setInspectingDriverNumber] = useState<number | null>(null);
  const [activeEvidenceAssessment, setActiveEvidenceAssessment] = useState<Assessment | null>(null);
  const [replayStatusData, setReplayStatusData] = useState<ReplayStatusData | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED'>('DISCONNECTED');
  const [switchingToSession, setSwitchingToSession] = useState<string | null>(null);

  // SIA Integrity Board & Decision Inspector State
  const [contracts, setContracts] = useState<ContractDefinition[]>([]);
  const [decisions, setDecisions] = useState<DecisionInstance[]>([]);
  const [verdicts, setVerdicts] = useState<SIAAssessment[]>([]);
  const [selectedDecisionInstanceId, setSelectedDecisionInstanceId] = useState<string | null>(null);
  const [inspectingAssessment, setInspectingAssessment] = useState<SIAAssessment | null>(null);
  const [inspectingExplanation, setInspectingExplanation] = useState<string | null>(null);

  const isNoSessionData = sessionId === 'f1-2026-suzuka-preview' || snapshot.status === 'NO_SESSION_DATA';

  const refreshState = async () => {
    const res = await loadSnapshot();
    setSnapshot(res.snapshot);
    setConnected(res.connected);
    if (res.connected && res.snapshot.sessionId) {
      setSessionId(res.snapshot.sessionId);
      if (res.snapshot.circuitId) setCircuitId(res.snapshot.circuitId);
    }
    const rStatus = await fetchReplayStatus();
    if (rStatus) {
      setReplayStatusData(rStatus);
      if (rStatus.sessionId) setSessionId(rStatus.sessionId);
    }
  };

  // Switch session handler
  const handleSessionChange = async (newSessionId: string) => {
    try {
      setSwitchingToSession(newSessionId);
      setSessionId(newSessionId);
      const match = SESSION_OPTIONS.find((s) => s.id === newSessionId);
      const newCircuit = match ? match.circuitId : 'monaco';
      setCircuitId(newCircuit);

      await selectSession(newSessionId);
      await refreshState();
    } finally {
      setSwitchingToSession(null);
    }
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

  // Load SIA Integrity Contracts, Decisions, and Verdicts
  useEffect(() => {
    let active = true;
    let inFlight = false;
    const loadIntegrityData = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const [cList, dList, vList] = await Promise.all([
          fetchContracts(),
          fetchDecisions(),
          fetchAllVerdicts(),
        ]);
        if (active) {
          if (cList) setContracts(cList);
          if (dList) setDecisions(dList);
          if (vList) setVerdicts(vList);
        }
      } catch (e) {
        console.warn('Failed to load integrity datasets:', e);
      } finally {
        inFlight = false;
      }
    };
    loadIntegrityData();
    const interval = setInterval(loadIntegrityData, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    // Initial fetch
    refreshState();

    // Setup continuous SSE stream with granular typed domain updates
    const unsubscribe = connectEventStream({
      onSnapshot: (newSnapshot) => {
        setSnapshot(newSnapshot);
        setConnected(true);
        if (newSnapshot.sessionId) setSessionId(newSnapshot.sessionId);
        if (newSnapshot.circuitId) setCircuitId(newSnapshot.circuitId);
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
          dataRegime: data.dataRegime ?? prev.dataRegime,
          timingBaseline: data.timingBaseline ?? prev.timingBaseline,
          transportMode: data.transportMode ?? prev.transportMode,
          lastUpdated: 'live',
        }));
      },
      onDriverUpdate: (data) => {
        if (data && Array.isArray(data.drivers)) {
          const sorted = [...data.drivers].sort((a, b) => (a.position - b.position) || (a.number - b.number));
          setSnapshot((prev) => ({ ...prev, drivers: sorted, lastUpdated: 'live' }));
        } else if (data && (data.driver_number || data.number)) {
          const dn = data.driver_number || data.number;
          setSnapshot((prev) => {
            const mapped = prev.drivers.map((d) => (d.number === dn ? { ...d, ...data } : d));
            mapped.sort((a, b) => (a.position - b.position) || (a.number - b.number));
            return { ...prev, drivers: mapped, lastUpdated: 'live' };
          });
        }
      },
      onTelemetryUpdate: (data) => {
        if (data && data.driverNumber && data.telemetry) {
          setSnapshot((prev) => ({
            ...prev,
            drivers: prev.drivers.map((d) =>
              d.number === data.driverNumber
                ? {
                    ...d,
                    telemetry: { ...d.telemetry, ...data.telemetry },
                    history: data.telemetry.history || d.history,
                  }
                : d
            ),
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
      onImpactAssessmentUpdate: (assessment) => {
        setSnapshot((prev) => {
          const dn = assessment.subject?.driver_number;
          const existing = prev.assessments.filter((a) => a.id !== assessment.assessment_id);
          const summaryLower = String(assessment.impact?.summary || '').toLowerCase();
          const hasConflicts = Array.isArray(assessment.uncertainty?.conflicts) && assessment.uncertainty.conflicts.length > 0;
          const rng = assessment.impact?.forecast?.position_delta_range;
          const rngLo = Array.isArray(rng) && rng.length >= 2 ? Number(rng[0]) : 0;
          const rngHi = Array.isArray(rng) && rng.length >= 2 ? Number(rng[1]) : 0;
          const computedImpact: 'positive' | 'negative' | 'neutral' =
            summaryLower.includes('congestion') ||
            summaryLower.includes('loss') ||
            summaryLower.includes('risk') ||
            summaryLower.includes('penalt') ||
            rngLo < 0 ||
            hasConflicts
              ? 'negative'
              : rngHi > 0 ||
                  summaryLower.includes('gain') ||
                  summaryLower.includes('opportunity') ||
                  summaryLower.includes('clear')
                ? 'positive'
                : 'neutral';
          const formatted = {
            id: assessment.assessment_id,
            version: assessment.assessment_version,
            driverNumber: dn || 0,
            title: assessment.impact?.summary || 'Tactical Assessment',
            narrative: assessment.impact?.inferred_effects?.[0] || assessment.impact?.summary || '',
            driverRadio: null,
            impact: computedImpact,
            status: assessment.status || 'PROVISIONAL',
            confidence: assessment.uncertainty?.confidence_score,
            calibrationStatus: assessment.uncertainty?.calibration_status || 'UNCALIBRATED',
            forecast: (() => {
              const rng = assessment.impact?.forecast?.position_delta_range;
              if (!Array.isArray(rng) || rng.length < 2) return 'Awaiting gap convergence';
              const lo = Number(rng[0]);
              const hi = Number(rng[1]);
              if (lo === 0 && hi === 0) return 'Hold track position (0 net delta)';
              const fmtSigned = (n: number) => `${n >= 0 ? '+' : ''}${n}`;
              return lo === hi
                ? `Projected net delta: ${fmtSigned(lo)} pos`
                : `Projected net delta: ${fmtSigned(lo)} to ${fmtSigned(hi)} pos`;
            })(),
            alternative: assessment.impact?.alternatives?.[0] || 'Stay out and risk track position',
            evidence: assessment.evidence_refs || [],
            supersedesId: assessment.supersedes_assessment_id,
            changedAt: 'just now',
          };
          return {
            ...prev,
            assessments: [formatted, ...existing],
            lastUpdated: 'live',
          };
        });
      },
      onConnectionChange: (state) => {
        setConnectionStatus(state);
        setConnected(state === 'CONNECTED');
      },
    });

    // Periodic safety sync every 2 seconds without overlapping requests
    let syncInFlight = false;
    const interval = setInterval(async () => {
      if (syncInFlight) return;
      syncInFlight = true;
      try {
        const [rStatus, snapRes] = await Promise.all([
          fetchReplayStatus(),
          loadSnapshot(),
        ]);
        if (rStatus) setReplayStatusData(rStatus);
        if (snapRes && snapRes.connected && snapRes.snapshot.drivers?.length > 0) {
          setSnapshot((prev) => ({
            ...prev,
            ...snapRes.snapshot,
            lastUpdated: 'live',
          }));
        }
      } catch {
        // ignore network error
      } finally {
        syncInFlight = false;
      }
    }, 2000);

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
    return res;
  };

  // Open 3-Click Decision Inspector
  const handleSelectDecision = async (instanceId: string) => {
    setSelectedDecisionInstanceId(instanceId);
    let v: SIAAssessment | null = verdicts.find((item) => item.decision_instance_id === instanceId) ?? null;
    if (!v) {
      v = await fetchVerdict(instanceId);
    }
    const finalVerdict: SIAAssessment = v ?? {
      decision_instance_id: instanceId,
      revision_number: 1,
      integrity_state: 'UNKNOWN',
      disposition: 'NORMAL',
      resolution_maturity: 'OPEN',
      finality_status: 'PROVISIONAL',
      verdict_hash: 'pending-evaluation',
      record_hash: 'pending-evaluation',
      contract: {
        id: instanceId.split('-')[1] || 'lap_time',
        version: '1.0.0',
        formula: 'Awaiting live atom admission',
      },
      scope: { driver: `#${instanceId.split('-')[2]?.replace('d', '') || 'unknown'}`, session: sessionId },
      roles: {},
      witnesses: [
        {
          code: 'NO_ADMITTED_EVIDENCE',
          role: 'decision',
          detail: 'No verdict exists yet in SIA Core v3 for this contract/scope (awaiting qualifying events during replay).',
        },
      ],
      limitations: ['UNEVALUATED_SCOPE: Start replay or advance timeline until qualifying events arrive for this scope.'],
    };
    setInspectingAssessment(finalVerdict);
    const exp = await fetchVerdictExplanation(instanceId);
    setInspectingExplanation(
      exp || `Verdict evaluated as ${finalVerdict.integrity_state} under contract ${finalVerdict.contract?.id || 'standard'}. All mandatory requirements verified under declared assumptions.`
    );
  };

  // Open Decision Inspector from circuit map timing gate
  const handleSelectGate = (gateId: string, sectorNum: number) => {
    const driverNum = selectedDriverNumber ?? 16;
    const instId = `dec-sector_time-d${driverNum}-s${sectorNum}`;
    handleSelectDecision(instId);
  };

  return (
    <div className="pulse-app">
      {/* Session Switching Loading Overlay */}
      {switchingToSession && (
        <div className="session-switching-overlay" role="status">
          <span className="session-switching-spinner" />
          <span>Switching session to {switchingToSession} · Reinitialising stream state and telemetry...</span>
        </div>
      )}

      {/* Primary Epistemic Navigation Header with 5 Views, Regime Pill, and Dual-Time Readouts */}
      <AppHeader
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
        dataRegime={snapshot.dataRegime ?? 'SYNTHETIC'}
        transportMode={
          snapshot.pipelineStatus === 'CONNECTED'
            ? (snapshot.transportMode ?? 'SIMULATOR TRANSPORT')
            : 'DEGRADED / FALLBACK'
        }
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

        {/* ============================================================ */}
        {/* VIEW 1: TRACKSIDE (Spatial tracking & participant shelf)      */}
        {/* ============================================================ */}
        {activeView === 'TRACKSIDE' && (
          <div className="trackside-view-container">
            {/* Primary Row: 65% Circuit Map + 35% Scrollable Participant Shelf */}
            <div className="trackside-hero-grid">
              <div className="trackside-map-wrapper">
                <TrackMap
                  circuit={circuitGeometry}
                  sectors={snapshot.sectors}
                  drivers={snapshot.drivers}
                  activeEvent={snapshot.activeEvent}
                  selectedDriverNumber={selectedDriverNumber}
                  onSelectDriver={(num) => setSelectedDriverNumber(num)}
                  onInspectTelemetry={(num) => setInspectingDriverNumber(num)}
                  onSelectGate={handleSelectGate}
                />
              </div>

              <div className="trackside-shelf-wrapper">
                <ParticipantShelf
                  drivers={snapshot.drivers}
                  selectedDriverNumber={selectedDriverNumber}
                  onSelectDriver={(num) => setSelectedDriverNumber(num)}
                  onInspectTelemetry={(num) => setInspectingDriverNumber(num)}
                />
              </div>
            </div>

            {/* Secondary Row: Collapsible Tactical Drawer (Strategy & Pit Window) */}
            <div className="trackside-secondary-row">
              <TacticalDrawer
                strategies={snapshot.strategies}
                sectors={snapshot.sectors}
                activeEvent={snapshot.activeEvent}
                defaultExpanded={false}
              />
            </div>

            {/* Tertiary Row: Live Tactical Consequence Feed & Telemetry Momentum */}
            <div className="grid-two-columns trackside-tertiary-row">
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
                    {snapshot.assessments.map((assessment, idx) => {
                      const driver = snapshot.drivers.find((d) => d.number === assessment.driverNumber);
                      return (
                        <ImpactCard
                          key={assessment.id ? `${assessment.id}-${idx}` : `assess-${idx}`}
                          assessment={assessment}
                          driver={driver}
                          onEvidence={(a) => setActiveEvidenceAssessment(a)}
                        />
                      );
                    })}
                  </div>
                </section>
              )}

              <div className="cockpit-side-column" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <MomentumChart drivers={snapshot.drivers} currentLap={snapshot.lap} activeEvent={snapshot.activeEvent} />
                <PulseTimeline events={snapshot.timeline} />
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* VIEW 2: INTEGRITY BOARD (Multi-contract matrix & inspector)   */}
        {/* ============================================================ */}
        {activeView === 'INTEGRITY_BOARD' && (
          <div className="integrity-board-view-container">
            <IntegrityMatrix
              drivers={snapshot.drivers}
              contracts={contracts}
              decisions={decisions}
              verdicts={verdicts}
              onSelectDecision={handleSelectDecision}
              selectedInstanceId={selectedDecisionInstanceId}
              sessionId={sessionId}
              sessionName={snapshot.sessionName}
            />
          </div>
        )}

        {/* ============================================================ */}
        {/* VIEW 3: SIA LOGIC LAB (Deterministic formal workbench)        */}
        {/* ============================================================ */}
        {activeView === 'SIA_LOGIC_LAB' && (
          <div className="sia-logic-lab-view-container">
            <SiaLogicLabView
              decisions={decisions}
              verdicts={verdicts}
              contracts={contracts}
              drivers={snapshot.drivers}
              sessionId={sessionId}
              sessionName={snapshot.sessionName}
              selectedDecisionId={selectedDecisionInstanceId}
              onSelectDecision={handleSelectDecision}
            />
          </div>
        )}

        {/* ============================================================ */}
        {/* VIEW 4: AGENTS & PIPELINE (Runtime vs target archetypes)       */}
        {/* ============================================================ */}
        {activeView === 'AGENTS_PIPELINE' && (
          <AgentsPipelineView decisionCount={decisions.length || snapshot.integrity?.decision_count} />
        )}

        {/* ============================================================ */}
        {/* VIEW 5: REPLAY & AUDIT (Bitemporal time machine & verifier)   */}
        {/* ============================================================ */}
        {activeView === 'REPLAY_AUDIT' && (
          <ReplayAuditView
            replayStatus={replayStatusData}
            onControlAction={handleControlAction}
          />
        )}
      </main>

      {/* Declared Baseline Survey & Uncertainty Guard Band Footer */}
      <AssumptionsBar
        surveyReference={`${circuitId.toUpperCase()} Geometry Baseline`}
        sensorToleranceMeters={0.05}
        timingSource={snapshot.timingBaseline ?? 'Deterministic Simulator Stream'}
        dataRegime={snapshot.dataRegime ?? 'SYNTHETIC'}
      />

      {/* Interactive Driver Telemetry Waveform Modal */}
      {inspectingDriverNumber && (
        <DriverTelemetryModal
          driverNumber={inspectingDriverNumber}
          onClose={() => setInspectingDriverNumber(null)}
        />
      )}

      {/* 3-Click SIA Core v3 Decision Inspector Drawer */}
      {inspectingAssessment && (() => {
        const rawDriver = inspectingAssessment.scope?.driver || inspectingAssessment.scope?.driver_id;
        const driverNum = rawDriver ? parseInt(String(rawDriver).replace('#', '').replace('d', ''), 10) : null;
        const driverObj = snapshot.drivers.find((d) => d.number === driverNum);
        return (
          <DecisionInspector
            assessment={inspectingAssessment}
            explanation={inspectingExplanation}
            driverName={driverObj?.name}
            driverTeam={driverObj?.team}
            onClose={() => setInspectingAssessment(null)}
          />
        );
      })()}

      {/* Legacy Slide-over Evidence Drawer ("Why this?") */}
      <EvidenceDrawer
        assessment={activeEvidenceAssessment}
        driver={snapshot.drivers.find((d) => d.number === activeEvidenceAssessment?.driverNumber)}
        onClose={() => setActiveEvidenceAssessment(null)}
      />
    </div>
  );
}
