export type DataMode = 'SIMULATED' | 'REPLAY' | 'LIVE';
export type PipelineStatus = 'CONNECTED' | 'PROCESSING' | 'DEGRADED' | 'FAILED';
export type ImpactTone = 'positive' | 'negative' | 'neutral';
export type FindingState = 'PROVISIONAL' | 'CONFIRMED' | 'UNRESOLVED' | 'SUPERSEDED' | 'WITHDRAWN';
export type DriverStatus = 'ACTIVE' | 'PIT_LANE' | 'RETIRED' | 'DNS' | 'INACTIVE';
export type PositionMode = 'MEASURED_GPS' | 'TIMING_ESTIMATED' | 'INTERPOLATED_DISPLAY';

export interface TelemetryChannel {
  value: number | string | null;
  unit: string;
  source: string;
  freshness_ms: number;
  quality: 'AVAILABLE' | 'UNAVAILABLE';
}

export interface TelemetryHistoryPoint {
  time_offset_s: number;
  speed: number;
  throttle: number;
  brake: number;
  gear: number;
  rpm: number;
  drs: number;
}

export interface Driver {
  number: number;
  initials: string;
  name: string;
  team: string;
  teamColor?: string;
  position: number;
  gap: string;
  interval: string;
  tyre: 'S' | 'M' | 'H' | 'I' | 'W';
  stint: number;
  tyreAge: number;
  lastLap: string;
  momentum: number;
  status?: DriverStatus;
  progress?: number;
  positionMode?: PositionMode;
  freshnessSeconds?: number;
  telemetry?: Record<string, TelemetryChannel>;
  history?: TelemetryHistoryPoint[];
  impact: {
    tone: ImpactTone;
    label: string;
  };
}

export interface Corner {
  number: number;
  name: string;
  x: number;
  y: number;
  sector: number;
  apex_speed_kmh?: number | null;
}

export interface DRSZone {
  zone_id: number;
  detection_point: [number, number];
  activation_point: [number, number];
  length_meters: number;
}

export interface PitLaneGeometry {
  entry_point: [number, number];
  exit_point: [number, number];
  path: [number, number][];
  speed_limit_kmh: number;
}

export interface SectorBoundary {
  sector_number: number;
  start_progress: number;
  end_progress: number;
  checkpoint: [number, number];
}

export interface CircuitGeometry {
  circuit_id: string;
  name: string;
  country: string;
  city: string;
  layout_id: string;
  layout_version: string;
  length_meters: number;
  track_direction: 'CLOCKWISE' | 'COUNTER_CLOCKWISE' | 'FIGURE_EIGHT';
  coordinate_reference_system: string;
  source_attribution: string;
  checksum_sha256: string;
  centreline: [number, number][];
  inner_boundary?: [number, number][];
  outer_boundary?: [number, number][];
  corners: Corner[];
  sectors: SectorBoundary[];
  pit_lane: PitLaneGeometry;
  start_finish_line: [[number, number], [number, number]];
  drs_zones: DRSZone[];
  view_box: {
    min_x: number;
    min_y: number;
    width: number;
    height: number;
  };
}

export interface OfficialNotice {
  notice_id: string;
  timestamp_utc: string;
  category: 'FLAG' | 'SAFETY_CAR' | 'INCIDENT' | 'INVESTIGATION' | 'DECISION' | 'PENALTY' | 'WEATHER' | 'GRID';
  flag: 'GREEN' | 'YELLOW' | 'RED' | 'CLEAR' | 'BLUE';
  title: string;
  detail: string;
  driver_numbers: number[];
  regulatory_reference: string;
  source: string;
  status: string;
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
  assumptions?: Record<string, any>;
  calculationVersion?: string;
}

export interface TrackSector {
  id: string;
  label: string;
  condition: string;
  tone: 'dry' | 'damp' | 'wet' | 'neutral';
  confidence: number;
}

export interface AgentTelemetry {
  agent_id: string;
  runtime_status: string;
  events_received: number;
  eligible_inputs: number;
  processed_inputs: number;
  findings_emitted: number;
  no_finding_count: number;
  insufficient_data_outcomes: number;
  filtered_count: number;
  failed_count: number;
  retry_pending_count: number;
  kafka_consumer_lag: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  last_event_timestamp?: string | null;
  model_version: string;
  output_finding_ids?: string[];
}

export interface AgentFinding {
  finding_id: string;
  finding_version: number;
  agent_id: string;
  finding_type: string;
  session_id: string;
  run_id: string;
  subject: {
    driver_number?: number;
    segment_id?: string;
  };
  trigger_event_id?: string;
  as_of_event_time: string;
  interpretation: 'OBSERVED' | 'DERIVED' | 'INFERRED' | 'PREDICTED';
  result: Record<string, any>;
  uncertainty: Record<string, any>;
  evidence_refs: string[];
  model_version: string;
  assessment_status: string;
  supersedes_finding_id?: string | null;
}

export interface PipelineStatusData {
  kafka: {
    connected: boolean;
    transport: string;
    processed_events: number;
    duplicate_events: number;
  };
  flink: {
    status: string;
    job_id: string | null;
    job_name?: string;
    checkpoints_completed: number;
    read_records?: number;
    write_records?: number;
  };
  agents: {
    total_registered: number;
    active_agents: string[];
    metrics: Record<string, AgentTelemetry>;
  };
  findings_count: number;
  assessments_count: number;
  last_event_time_utc?: string | null;
}

export interface VerificationRun {
  run_id: string;
  session_id: string;
  status: string;
  mode: string;
  timestamp: string;
  stages_passed: number;
  stages_count: number;
  total_latency_ms: number;
  report_file: string;
  stages?: Array<{
    stage_name: string;
    status: string;
    inputs_expected?: number | null;
    outputs_actual?: number | null;
    drops?: number;
    latency_ms?: number;
  }>;
}

export interface LineageTraceEvent {
  timestamp: string;
  stage: string;
  event: string;
  payload: Record<string, any>;
}

export interface PulseSnapshot {
  mode: DataMode;
  pipelineStatus: PipelineStatus;
  circuitId?: string;
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
  officialNotices?: OfficialNotice[];
}

export interface ReplayStatusData {
  sessionId: string;
  captureId: string;
  runId: string;
  status: 'READY' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'RESETTING' | 'FAILED' | string;
  runner_status?: string;
  mode: string;
  speed: number;
  allowedSpeeds: number[];
  currentIndex: number;
  totalEvents: number;
  publishedCount: number;
  dropCount: number;
  currentLap: number;
  totalLaps: number;
  elapsed: string;
  elapsedMs: number;
  lastEventTimeUtc?: string | null;
  progressPercent: number;
}

export interface SessionInfo {
  session_id: string;
  circuit_id: string;
  grand_prix_name: string;
  season: number;
  round_number?: number;
  session_type: string;
  availability_status: 'AVAILABLE_HISTORICAL' | 'AVAILABLE_SIMULATION' | 'NO_SESSION_DATA';
  total_laps: number;
  capture_id?: string;
  events_count: number;
}
