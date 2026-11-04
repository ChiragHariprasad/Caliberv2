import { fallbackSnapshot } from './data';
import type {
  AgentFinding,
  AgentTelemetry,
  CircuitGeometry,
  LineageTraceEvent,
  OfficialNotice,
  PipelineStatusData,
  PulseSnapshot,
  ReplayStatusData,
  SessionInfo,
  VerificationRun,
} from './types';

const API_ROOT = '/api';

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_ROOT}${path}`, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function postJson<T>(path: string, body?: any): Promise<T | null> {
  try {
    const response = await fetch(`${API_ROOT}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/**
 * Loads the current snapshot from /api/snapshot (or individual slices if offline).
 */
export async function loadSnapshot(): Promise<{ snapshot: PulseSnapshot; connected: boolean }> {
  const directSnapshot = await fetchJson<PulseSnapshot>('/snapshot');
  if (directSnapshot && directSnapshot.drivers && directSnapshot.drivers.length > 0) {
    return {
      connected: true,
      snapshot: directSnapshot,
    };
  }

  // Fallback to loading individual slices
  const [session, drivers, timeline, assessments, strategy, track, notices] = await Promise.all([
    fetchJson<Partial<PulseSnapshot>>('/session'),
    fetchJson<PulseSnapshot['drivers']>('/drivers'),
    fetchJson<PulseSnapshot['timeline']>('/timeline'),
    fetchJson<PulseSnapshot['assessments']>('/assessments'),
    fetchJson<PulseSnapshot['strategies']>('/strategy'),
    fetchJson<PulseSnapshot['sectors']>('/track'),
    fetchJson<OfficialNotice[]>('/race-control'),
  ]);

  const connected = Boolean(session || (drivers && drivers.length));
  if (!connected) return { snapshot: fallbackSnapshot, connected: false };

  return {
    connected: true,
    snapshot: {
      ...fallbackSnapshot,
      ...session,
      drivers: drivers ?? fallbackSnapshot.drivers,
      timeline: timeline ?? fallbackSnapshot.timeline,
      assessments: assessments ?? fallbackSnapshot.assessments,
      strategies: strategy ?? fallbackSnapshot.strategies,
      sectors: track ?? fallbackSnapshot.sectors,
      officialNotices: notices ?? fallbackSnapshot.officialNotices,
      lastUpdated: 'live',
    },
  };
}

/**
 * Session Registry APIs
 */
export async function fetchSessions(): Promise<SessionInfo[]> {
  const res = await fetchJson<SessionInfo[]>('/sessions');
  return res ?? [];
}

export async function selectSession(sessionId: string): Promise<any> {
  return await postJson<any>('/sessions/select', { session_id: sessionId });
}

/**
 * Backend Replay Controller APIs
 */
export async function fetchReplayStatus(): Promise<ReplayStatusData | null> {
  return await fetchJson<ReplayStatusData>('/replay/status');
}

export async function startReplay(speed?: number): Promise<ReplayStatusData | null> {
  return await postJson<ReplayStatusData>('/replay/start', speed ? { speed } : undefined);
}

export async function pauseReplay(): Promise<ReplayStatusData | null> {
  return await postJson<ReplayStatusData>('/replay/pause');
}

export async function resumeReplay(): Promise<ReplayStatusData | null> {
  return await postJson<ReplayStatusData>('/replay/resume');
}

export async function resetReplay(): Promise<ReplayStatusData | null> {
  return await postJson<ReplayStatusData>('/replay/reset');
}

export async function seekReplay(params: {
  targetLap?: number;
  targetIndex?: number;
  targetElapsedMs?: number;
}): Promise<ReplayStatusData | null> {
  return await postJson<ReplayStatusData>('/replay/seek', {
    target_lap: params.targetLap,
    target_index: params.targetIndex,
    target_elapsed_ms: params.targetElapsedMs,
  });
}

export async function setReplaySpeed(speed: number): Promise<ReplayStatusData | null> {
  return await postJson<ReplayStatusData>('/replay/speed', { speed });
}

/**
 * Legacy compatibility replay controls
 */
export async function requestReplayControl(
  action: 'START' | 'PAUSE' | 'RESUME' | 'RESTART' | 'RESET' | 'SPEED',
  speed?: number,
): Promise<boolean> {
  if (action === 'START') {
    const res = await startReplay(speed);
    return Boolean(res);
  }
  if (action === 'PAUSE') {
    const res = await pauseReplay();
    return Boolean(res);
  }
  if (action === 'RESUME') {
    const res = await resumeReplay();
    return Boolean(res);
  }
  if (action === 'RESTART' || action === 'RESET') {
    const res = await resetReplay();
    return Boolean(res);
  }
  if (action === 'SPEED') {
    const res = await setReplaySpeed(speed ?? 1.0);
    return Boolean(res);
  }
  return false;
}

/**
 * Circuit Catalogue APIs
 */
export async function fetchCircuitsList(): Promise<any[]> {
  const res = await fetchJson<any[]>('/circuits');
  return res ?? [];
}

export async function fetchCircuit(circuitId: string): Promise<CircuitGeometry | null> {
  return await fetchJson<CircuitGeometry>(`/circuit/${circuitId}`);
}

/**
 * Driver Telemetry APIs
 */
export async function fetchDriverTelemetry(driverNumber: number): Promise<any | null> {
  return await fetchJson<any>(`/telemetry/${driverNumber}`);
}

/**
 * Race Control & Stewarding Notices
 */
export async function fetchRaceControlNotices(): Promise<OfficialNotice[]> {
  const res = await fetchJson<OfficialNotice[]>('/race-control');
  return res ?? [];
}

/**
 * Agent Operations & Transparency Metrics
 */
export async function fetchAgentsMetrics(): Promise<Record<string, AgentTelemetry>> {
  const res = await fetchJson<Record<string, AgentTelemetry>>('/agents/metrics');
  return res ?? {};
}

export async function fetchFindings(agentId?: string): Promise<AgentFinding[]> {
  const q = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
  const res = await fetchJson<AgentFinding[]>(`/findings${q}`);
  return res ?? [];
}

/**
 * Pipeline Lab Status & Lineage
 */
export async function fetchPipelineStatus(): Promise<PipelineStatusData | null> {
  return await fetchJson<PipelineStatusData>('/pipeline/status');
}

export async function fetchVerificationRuns(): Promise<VerificationRun[]> {
  const res = await fetchJson<VerificationRun[]>('/pipeline/verification-runs');
  return res ?? [];
}

export async function fetchVerificationRunDetail(runId: string): Promise<any | null> {
  return await fetchJson<any>(`/pipeline/verification-runs/${runId}`);
}

export async function fetchPipelineLineage(): Promise<LineageTraceEvent[]> {
  const res = await fetchJson<LineageTraceEvent[]>('/pipeline/lineage');
  return res ?? [];
}

export interface StreamCallbacks {
  onSnapshot?: (snapshot: PulseSnapshot) => void;
  onSessionUpdate?: (data: any) => void;
  onDriverUpdate?: (data: any) => void;
  onTelemetryUpdate?: (data: any) => void;
  onTrackUpdate?: (data: any) => void;
  onRaceControlUpdate?: (data: any) => void;
  onAgentStatusUpdate?: (data: any) => void;
  onAgentFindingUpdate?: (data: any) => void;
  onImpactAssessmentUpdate?: (data: any) => void;
  onReplayStatusUpdate?: (data: ReplayStatusData) => void;
  onHeartbeat?: (data: any) => void;
  onConnectionChange?: (state: 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED') => void;
}

/**
 * Sets up Continuous Server-Sent Events (SSE) connection to /api/stream with typed domain dispatch.
 */
export function connectEventStream(
  callbacks: StreamCallbacks | ((snapshot: PulseSnapshot) => void),
  legacyRefresh?: () => void,
): () => void {
  const cbs: StreamCallbacks = typeof callbacks === 'function'
    ? {
        onSnapshot: callbacks,
        onSessionUpdate: legacyRefresh,
        onDriverUpdate: legacyRefresh,
        onTelemetryUpdate: legacyRefresh,
        onTrackUpdate: legacyRefresh,
        onRaceControlUpdate: legacyRefresh,
        onAgentStatusUpdate: legacyRefresh,
        onAgentFindingUpdate: legacyRefresh,
        onImpactAssessmentUpdate: legacyRefresh,
      }
    : callbacks;

  let eventSource: EventSource | null = null;
  let active = true;
  let lastEventId: string | null = null;

  const connect = () => {
    if (!active) return;
    try {
      const url = `${API_ROOT}/stream`;
      eventSource = new EventSource(url);

      cbs.onConnectionChange?.('CONNECTED');

      eventSource.addEventListener('snapshot', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const snap = JSON.parse(e.data) as PulseSnapshot;
          cbs.onSnapshot?.(snap);
        } catch {
          // ignore parsing error
        }
      });

      eventSource.addEventListener('SESSION_STATE_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onSessionUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('DRIVER_STATE_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onDriverUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('TELEMETRY_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onTelemetryUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('TRACK_STATE_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onTrackUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('RACE_CONTROL_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onRaceControlUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('AGENT_STATUS_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onAgentStatusUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('AGENT_FINDING_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onAgentFindingUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('IMPACT_ASSESSMENT_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onImpactAssessmentUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('REPLAY_STATUS_UPDATED', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onReplayStatusUpdate?.(parsed.data ?? parsed);
        } catch {}
      });

      eventSource.addEventListener('heartbeat', (e: MessageEvent) => {
        try {
          if (e.lastEventId) lastEventId = e.lastEventId;
          const parsed = JSON.parse(e.data);
          cbs.onHeartbeat?.(parsed.data ?? parsed);
        } catch {}
      });

      // Legacy events
      eventSource.addEventListener('event', () => cbs.onSessionUpdate?.({}));
      eventSource.addEventListener('finding', () => cbs.onAgentFindingUpdate?.({}));
      eventSource.addEventListener('assessment', () => cbs.onImpactAssessmentUpdate?.({}));

      eventSource.onerror = () => {
        if (!active) return;
        cbs.onConnectionChange?.('RECONNECTING');
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        setTimeout(connect, 2000);
      };
    } catch {
      cbs.onConnectionChange?.('DISCONNECTED');
    }
  };

  connect();

  return () => {
    active = false;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  };
}
