export type DataMode = 'SIMULATED' | 'REPLAY' | 'LIVE';
export type ImpactTone = 'positive' | 'negative' | 'neutral';
export type FindingState = 'PROVISIONAL' | 'CONFIRMED' | 'UNRESOLVED';

export interface Driver {
  number: number;
  initials: string;
  name: string;
  team: string;
  position: number;
  gap: string;
  interval: string;
  tyre: 'S' | 'M' | 'H' | 'I' | 'W';
  stint: number;
  tyreAge: number;
  lastLap: string;
  momentum: number;
  impact: {
    tone: ImpactTone;
    label: string;
  };
}

export interface RaceEvent {
  id: string;
  time: string;
  title: string;
  detail: string;
  type: 'control' | 'strategy' | 'track' | 'impact';
  active?: boolean;
}

export interface Assessment {
  id: string;
  driverNumber: number;
  title: string;
  narrative: string;
  impact: ImpactTone;
  status: FindingState;
  confidence?: number | null;
  calibrationStatus?: string;
  forecast: string;
  alternative: string;
  evidence: string[];
  changedAt: string;
  driverRadio?: string | null;
  version?: number;
  supersedesId?: string | null;
}

export interface StrategyOption {
  label: string;
  action: string;
  score: number;
  delta: string;
  tone: ImpactTone;
  note: string;
}

export interface TrackSector {
  id: string;
  label: string;
  condition: string;
  tone: 'dry' | 'damp' | 'wet' | 'neutral';
  confidence: number;
}

export interface PulseSnapshot {
  mode: DataMode;
  sessionName: string;
  sessionType: string;
  lap: number;
  totalLaps: number;
  status: string;
  elapsed: string;
  activeEvent: string;
  sourceLabel: string;
  lastUpdated: string;
  drivers: Driver[];
  timeline: RaceEvent[];
  assessments: Assessment[];
  strategies: StrategyOption[];
  sectors: TrackSector[];
}
