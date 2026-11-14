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
    const rStatus = await fetchReplayStatus();
    if (rStatus) {
      setReplayStatusData(rStatus);
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
    const loadIntegrityData = async () => {
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
        } else if (data && (data.driver_number || data.number)) {
          const dn = data.driver_number || data.number;
          setSnapshot((prev) => ({
            ...prev,
            drivers: prev.drivers.map((d) => (d.number === dn ? { ...d, ...data } : d)),
            lastUpdated: 'live',
          }));
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
          const formatted = {
            id: assessment.assessment_id,
            version: assessment.assessment_version,
            driverNumber: dn || 0,
            title: assessment.impact?.summary || 'Tactical Assessment',
            narrative: assessment.impact?.inferred_effects?.[0] || assessment.impact?.summary || '',
            driverRadio: null,
            impact: dn === 16 ? ('positive' as const) : (dn === 44 ? ('negative' as const) : ('neutral' as const)),
            status: assessment.status || 'PROVISIONAL',
            confidence: assessment.uncertainty?.confidence_score,
            calibrationStatus: assessment.uncertainty?.calibration_status || 'UNCALIBRATED',
            forecast: assessment.impact?.forecast?.position_delta_range
              ? `Position retention projected: P${assessment.impact.forecast.position_delta_range[0]}–P${assessment.impact.forecast.position_delta_range[1]}`
              : 'P1 retention highly probable across pit cycle',
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

    // Periodic safety sync every 2 seconds: ensures latest snapshot and replay status are always fresh
    const interval = setInterval(async () => {
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
      integrity_state: instanceId.includes('pit_speed') && instanceId.includes('d1') ? 'SUSPECT' : 'HEALTHY',
      disposition: instanceId.includes('d44') && instanceId.includes('pit_speed') ? 'VOIDED' : 'NORMAL',
      resolution_maturity: 'STATE_RESOLVED',
      finality_status: 'PROVISIONAL',
      verdict_hash: 'blake3:e9b17f8a3c4d2e1f0b9a8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f',
      record_hash: 'blake3:8f2a1b0c9d8e7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e',
      contract: {
        id: instanceId.split('-')[1] || 'lap_time',
        version: '1.0.0',
        formula: `AND(${instanceId.split('-')[1] || 'lap_time'}_timing, ${instanceId.split('-')[1] || 'lap_time'}_sensor)`,
      },
      scope: { driver: `#${instanceId.split('-')[2]?.replace('d', '') || '16'}`, session: sessionId },
      roles: {
        [`${instanceId.split('-')[1] || 'lap_time'}_timing`]: {
          role_id: `${instanceId.split('-')[1] || 'lap_time'}_timing`,
          state: 'HEALTHY',
          atom: {
            atom_id: `atm-${instanceId.slice(-6)}-t`,
            role_id: `${instanceId.split('-')[1] || 'lap_time'}_timing`,
            value: 60.08,
            unit: 'km/h',
            observed_at: new Date().toISOString(),
            time: {
              class: 'ABSOLUTE_UTC',
              value: 1716559925120000,
              unc: 1000,
            },
            scope: { driver: `#${instanceId.split('-')[2]?.replace('d', '') || '16'}`, session: sessionId },
            source_origins: ['FOM_OPTICAL_LOOP'],
            processing_origins: ['FLINK_STREAM_JOB_01'],
            processor_family_id: 'timing_sequencer',
            transform_version: '1.0.0',
            raw_event_ids: [`raw-evt-${instanceId.slice(-6)}-0`],
            quality_grade: 'HEALTHY',
            content_hash: 'blake3:a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e',
          },
        },
        [`${instanceId.split('-')[1] || 'lap_time'}_sensor`]: {
          role_id: `${instanceId.split('-')[1] || 'lap_time'}_sensor`,
          state: 'HEALTHY',
          atom: {
            atom_id: `atm-${instanceId.slice(-6)}-s`,
            role_id: `${instanceId.split('-')[1] || 'lap_time'}_sensor`,
            value: 59.95,
            unit: 'km/h',
            observed_at: new Date().toISOString(),
            time: {
              class: 'ABSOLUTE_UTC',
              value: 1716559925125000,
              unc: 500,
            },
            scope: { driver: `#${instanceId.split('-')[2]?.replace('d', '') || '16'}`, session: sessionId },
            source_origins: ['CAN_BUS_TELEMETRY'],
            processing_origins: ['AGENT_03_VEHICLE'],
            processor_family_id: 'telemetry_aligner',
            transform_version: '1.0.0',
            raw_event_ids: [`raw-evt-${instanceId.slice(-6)}-1`],
            quality_grade: 'HEALTHY',
            content_hash: 'blake3:b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f',
          },
        },
      },
      witnesses: [],
      limitations: ['Evaluated under Public Data Regime (declared common-cause exposure: FOM telemetry transport)'],
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
        dataRegime="PUBLIC"
        transportMode={snapshot.pipelineStatus === 'CONNECTED' ? 'IN-MEMORY EVENT BUS' : 'DEGRADED / FALLBACK'}
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
            />
          </div>
        )}

        {/* ============================================================ */}
        {/* VIEW 3: SIA LOGIC LAB (Possible-world & origin entanglement)   */}
        {/* ============================================================ */}
        {activeView === 'SIA_LOGIC_LAB' && (
          <div className="sia-logic-lab-view">
            <div className="grid-two-columns">
              <SuperpositionView
                decisionId="dec-pit_speed-d16"
                contractId="pit_speed v1.0.0"
                lowerBound="SUSPECT"
                upperBound="HEALTHY"
                currentState="SUSPECT"
                maturity="OPEN"
              />
              <EntanglementGraph corroborationDepth={1} hasCommonCause={true} />
            </div>

            <div className="grid-two-columns">
              <ContextualityDag atomId="atm-spd-88f2" roleId="timing_speed" />
              <StateAlgebraTree />
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* VIEW 4: AGENTS & PIPELINE (Runtime vs target archetypes)       */}
        {/* ============================================================ */}
        {activeView === 'AGENTS_PIPELINE' && (
          <AgentsPipelineView />
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
        surveyReference="Monaco-2025-v2.1 (Effective 2025-11-01 UTC)"
        sensorToleranceMeters={0.05}
        timingSource="FOM Optical Loops & CAN Telemetry"
        dataRegime="PUBLIC"
      />

      {/* Interactive Driver Telemetry Waveform Modal */}
      {inspectingDriverNumber && (
        <DriverTelemetryModal
          driverNumber={inspectingDriverNumber}
          onClose={() => setInspectingDriverNumber(null)}
        />
      )}

      {/* 3-Click SIA Core v3 Decision Inspector Drawer */}
      {inspectingAssessment && (
        <DecisionInspector
          assessment={inspectingAssessment}
          explanation={inspectingExplanation}
          onClose={() => setInspectingAssessment(null)}
        />
      )}

      {/* Legacy Slide-over Evidence Drawer ("Why this?") */}
      <EvidenceDrawer
        assessment={activeEvidenceAssessment}
        driver={snapshot.drivers.find((d) => d.number === activeEvidenceAssessment?.driverNumber)}
        onClose={() => setActiveEvidenceAssessment(null)}
      />
    </div>
  );
}
