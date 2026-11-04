import { fallbackSnapshot } from './data';
import type { PulseSnapshot } from './types';

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

/**
 * Loads the current snapshot from /api/snapshot (or fallback if offline).
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
  const [session, drivers, timeline, assessments, strategy, track] = await Promise.all([
    fetchJson<Partial<PulseSnapshot>>('/session'),
    fetchJson<PulseSnapshot['drivers']>('/drivers'),
    fetchJson<PulseSnapshot['timeline']>('/timeline'),
    fetchJson<PulseSnapshot['assessments']>('/assessments'),
    fetchJson<PulseSnapshot['strategies']>('/strategy'),
    fetchJson<PulseSnapshot['sectors']>('/track'),
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
      lastUpdated: 'live',
    },
  };
}

export async function requestReplayControl(
  action: 'START' | 'PAUSE' | 'RESUME' | 'RESTART' | 'SPEED',
  speed?: number,
): Promise<boolean> {
  try {
    const endpoint = action === 'SPEED' ? 'speed' : action.toLowerCase();
    const body = action === 'SPEED' ? { speed: speed ?? 1.0 } : { action };
    const response = await fetch(`${API_ROOT}/replay/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Sets up Server-Sent Events (SSE) connection to /api/stream.
 */
export function connectEventStream(
  onSnapshot: (snapshot: PulseSnapshot) => void,
  onRefresh: () => void,
): () => void {
  let eventSource: EventSource | null = null;
  let active = true;

  try {
    eventSource = new EventSource(`${API_ROOT}/stream`);

    eventSource.addEventListener('snapshot', (e: MessageEvent) => {
      try {
        const snap = JSON.parse(e.data) as PulseSnapshot;
        onSnapshot(snap);
      } catch {
        onRefresh();
      }
    });

    eventSource.addEventListener('event', () => onRefresh());
    eventSource.addEventListener('finding', () => onRefresh());
    eventSource.addEventListener('assessment', () => onRefresh());

    eventSource.onerror = () => {
      // Reconnect handled automatically by browser EventSource
    };
  } catch {
    // SSE not supported or network error
  }

  return () => {
    active = false;
    if (eventSource) {
      eventSource.close();
    }
  };
}
