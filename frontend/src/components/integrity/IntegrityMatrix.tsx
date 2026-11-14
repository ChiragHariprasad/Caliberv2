import React, { useMemo, useState } from 'react';
import type { Driver } from '../../types';
import type {
  ContractDefinition,
  DecisionInstance,
  IntegrityState,
  SIAAssessment,
} from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  CircleDotIcon,
  FilterIcon,
  SearchIcon,
  ShieldIcon,
} from '../icons';

interface IntegrityMatrixProps {
  drivers: Driver[];
  contracts: ContractDefinition[];
  decisions: DecisionInstance[];
  verdicts: SIAAssessment[];
  onSelectDecision: (instanceId: string) => void;
  selectedInstanceId?: string | null;
  sessionId?: string;
  sessionName?: string;
  className?: string;
}

// 13 Full Library Specification Contracts (Reference catalogue)
const LIBRARY_CONTRACTS = [
  { id: 'C01_lap_time_consistency', name: 'C01 Lap Time', scope: 'DRIVER_LAP', desc: 'Lap Time Consistency' },
  { id: 'C02_sector_sum_consistency', name: 'C02 Sector Sum', scope: 'SECTOR', desc: 'Sector Sum Consistency' },
  { id: 'C03_pit_speed_integrity', name: 'C03 Pit Speed', scope: 'SECTOR', desc: 'Pit-Lane Speed Limit' },
  { id: 'C04_vehicle_kinematics', name: 'C04 Kinematics', scope: 'DRIVER_LAP', desc: 'Kinematic Acceleration Bounds' },
  { id: 'C05_telemetry_alignment', name: 'C05 Time Align', scope: 'DRIVER_LAP', desc: 'Telemetry Time Alignment' },
  { id: 'C06_position_track_consistency', name: 'C06 Position', scope: 'DRIVER_LAP', desc: 'Track Position Consistency' },
  { id: 'C07_session_status_integrity', name: 'C07 Session Status', scope: 'SESSION', desc: 'Session Flag Status Integrity' },
  { id: 'C08_incident_timing', name: 'C08 Incident Timing', scope: 'SESSION', desc: 'Race Incident Timestamp Audit' },
  { id: 'C09_weather_reporting', name: 'C09 Weather', scope: 'SESSION', desc: 'Weather Reporting Correlation' },
  { id: 'C10_weather_advisory', name: 'C10 Weather Adv', scope: 'SESSION', desc: 'Track Condition Advisory' },
  { id: 'C11_feed_source_integrity', name: 'C11 Feed Integrity', scope: 'SESSION', desc: 'Multi-Source Feed Provenance' },
  { id: 'C12_monitor_health', name: 'C12 Monitor Health', scope: 'SESSION', desc: 'Normalizer & Flink Heartbeat' },
  { id: 'C13_rule_regime_consistency', name: 'C13 Rule Regime', scope: 'SESSION', desc: 'FIA Sporting Regime Verification' },
];

export const IntegrityMatrix: React.FC<IntegrityMatrixProps> = ({
  drivers,
  contracts,
  decisions,
  verdicts,
  onSelectDecision,
  selectedInstanceId,
  sessionId = 'f1-2026-monaco-sim',
  sessionName = 'Monaco Grand Prix (Simulation)',
  className = '',
}) => {
  const [contractMode, setContractMode] = useState<'ACTIVE' | 'ALL_13'>('ACTIVE');
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [teamFilter, setTeamFilter] = useState<string>('ALL');
  const [contractFilter, setContractFilter] = useState<string>('ALL');
  const [search, setSearch] = useState<string>('');
  const [sortBy, setSortBy] = useState<'POS' | 'NUM' | 'NAME' | 'TEAM' | 'ALERTS'>('POS');
  const [hoveredCell, setHoveredCell] = useState<{
    driverName: string;
    contractName: string;
    state: string;
    x: number;
    y: number;
  } | null>(null);

  // Map of instance_id -> verdict
  const verdictMap = useMemo(() => {
    const map = new Map<string, SIAAssessment>();
    for (const v of verdicts) {
      if (v.decision_instance_id) {
        map.set(v.decision_instance_id, v);
      }
    }
    return map;
  }, [verdicts]);

  // Lookup helper matching canonical SIA IDs and friendly aliases
  const findVerdict = (contractId: string, driverNumber: number): SIAAssessment | null => {
    const cid = contractId.toLowerCase().replace(/[^a-z0-9]/g, '_');
    const directKey = `dec-${cid}-d${driverNumber}`;
    if (verdictMap.has(directKey)) return verdictMap.get(directKey)!;

    for (const v of verdicts) {
      const vId = v.decision_instance_id.toLowerCase();
      const matchContract = vId.includes(cid) || (v.contract?.id && v.contract.id.toLowerCase().includes(cid));
      const matchDriver =
        vId.includes(`d${driverNumber}`) ||
        vId.includes(`driver:${driverNumber}`) ||
        vId.includes(`|${driverNumber}|`) ||
        v.scope?.driver === `#${driverNumber}` ||
        v.scope?.driver === String(driverNumber) ||
        v.scope?.driver_id === String(driverNumber);
      if (matchContract && matchDriver) {
        return v;
      }
    }
    return null;
  };

  // Active contracts from backend or library reference
  const displayedContracts = useMemo(() => {
    if (contractMode === 'ACTIVE') {
      if (contracts.length > 0) {
        return contracts.map((c) => ({
          id: c.contract_id,
          name: c.contract_id.replace(/_/g, ' ').toUpperCase(),
          scope: c.scope_class || (c as any).decision_scope?.scope_class || 'STREAM',
          desc: `${c.contract_id.replace(/_/g, ' ')} verification`,
        }));
      }
      return [
        { id: 'lap_time', name: 'C01 LAP TIME', scope: 'DRIVER_LAP', desc: 'Lap Time Consistency' },
        { id: 'pit_speed', name: 'C03 PIT SPEED', scope: 'SECTOR', desc: 'Pit Lane Speed Limit' },
        { id: 'sector_time', name: 'C02 SECTOR SUM', scope: 'SECTOR', desc: 'Sector Sum Consistency' },
        { id: 'driver_position', name: 'C06 POSITION', scope: 'DRIVER_LAP', desc: 'Track Position Invariant' },
        { id: 'weather_observation', name: 'C09 WEATHER', scope: 'SESSION', desc: 'Weather Reporting Correlation' },
      ];
    }
    return LIBRARY_CONTRACTS;
  }, [contractMode, contracts]);

  // Extract unique teams for dropdown
  const uniqueTeams = useMemo(() => {
    const teams = new Set<string>();
    for (const d of drivers) {
      if (d.team) teams.add(d.team);
    }
    return Array.from(teams).sort();
  }, [drivers]);

  // Dynamic Overview Statistics
  const stats = useMemo(() => {
    let total = 0;
    let healthy = 0;
    let suspect = 0;
    let unknown = 0;
    let degraded = 0;
    let voided = 0;

    for (const d of drivers) {
      for (const c of displayedContracts) {
        total++;
        const v = findVerdict(c.id, d.number);
        if (v?.disposition === 'VOIDED') {
          voided++;
        } else {
          const st = v?.integrity_state || 'UNKNOWN';
          if (st === 'HEALTHY') healthy++;
          else if (st === 'SUSPECT') suspect++;
          else if (st === 'UNKNOWN') unknown++;
          else if (st === 'DEGRADED') degraded++;
        }
      }
    }

    return { total, healthy, suspect, unknown, degraded, voided };
  }, [drivers, displayedContracts, verdictMap]);

  // Filtered & Sorted Drivers
  const processedDrivers = useMemo(() => {
    let list = drivers.filter((d) => {
      // Search
      if (search.trim()) {
        const q = search.toLowerCase();
        const matchesText =
          d.name.toLowerCase().includes(q) ||
          d.team.toLowerCase().includes(q) ||
          d.number.toString().includes(q);
        if (!matchesText) return false;
      }

      // Team filter
      if (teamFilter !== 'ALL' && d.team !== teamFilter) {
        return false;
      }

      return true;
    });

    // Sorting
    list = [...list].sort((a, b) => {
      if (sortBy === 'POS') return a.position - b.position;
      if (sortBy === 'NUM') return a.number - b.number;
      if (sortBy === 'NAME') return a.name.localeCompare(b.name);
      if (sortBy === 'TEAM') return a.team.localeCompare(b.team);
      if (sortBy === 'ALERTS') {
        const countAlerts = (drv: Driver) => {
          let alerts = 0;
          for (const c of displayedContracts) {
            const v = findVerdict(c.id, drv.number);
            if (v?.integrity_state === 'DEGRADED' || v?.integrity_state === 'SUSPECT') {
              alerts++;
            }
          }
          return alerts;
        };
        return countAlerts(b) - countAlerts(a);
      }
      return 0;
    });

    return list;
  }, [drivers, search, teamFilter, sortBy, displayedContracts, verdictMap]);

  const hasActiveFilters =
    stateFilter !== 'ALL' ||
    teamFilter !== 'ALL' ||
    contractFilter !== 'ALL' ||
    search.trim() !== '' ||
    sortBy !== 'POS';

  const resetFilters = () => {
    setStateFilter('ALL');
    setTeamFilter('ALL');
    setContractFilter('ALL');
    setSearch('');
    setSortBy('POS');
  };

  return (
    <div className={`integrity-board-root ${className}`}>
      {/* 1. Page Header */}
      <header className="integrity-page-header">
        <div className="integrity-page-header-left">
          <div className="integrity-section-eyebrow">
            <span className="eyebrow-accent-dot" />
            <span>EVIDENCE VERIFICATION &amp; INTEGRITY</span>
          </div>
          <h1 className="integrity-main-heading">Session Evidence Integrity</h1>
          <p className="integrity-session-description">
            Active Session: <strong>{sessionName}</strong> &bull; Session ID: <code>{sessionId}</code> &bull; Multi-contract deterministic SIA Core v3 invariant evaluation
          </p>
        </div>

        <div className="integrity-page-header-right">
          <div className="header-meta-pill">
            <span className="meta-label">ACTIVE CONTRACTS:</span>
            <span className="meta-value">{displayedContracts.length} / 13</span>
          </div>
          <div className="header-meta-pill">
            <span className="meta-label">STREAM STATUS:</span>
            <span className="meta-value text-emerald-400">
              <span className="pulse-indicator-dot" /> Live (500ms sync)
            </span>
          </div>
          <div className="header-mode-toggle">
            <button
              type="button"
              className={`mode-toggle-btn ${contractMode === 'ACTIVE' ? 'is-active' : ''}`}
              onClick={() => setContractMode('ACTIVE')}
            >
              Active Stream ({contracts.length || 5})
            </button>
            <button
              type="button"
              className={`mode-toggle-btn ${contractMode === 'ALL_13' ? 'is-active' : ''}`}
              onClick={() => setContractMode('ALL_13')}
            >
              All 13 Specification
            </button>
          </div>
        </div>
      </header>

      {/* 2. Summary Metrics: Horizontal KPI Strip (6 prominent, perfectly spaced cards) */}
      <section className="integrity-kpi-strip" aria-label="Integrity verdict metrics">
        {/* Total Decisions */}
        <div
          className={`kpi-metric-card ${stateFilter === 'ALL' ? 'is-active-filter' : ''}`}
          onClick={() => setStateFilter('ALL')}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-metric-header">
            <span className="kpi-metric-label">TOTAL DECISIONS</span>
            <CircleDotIcon size={14} className="text-slate-400" />
          </div>
          <div className="kpi-metric-value-box">
            <span className="kpi-metric-number">{stats.total}</span>
          </div>
          <div className="kpi-metric-footer">
            <span className="kpi-metric-subtext">Active instances tracked</span>
          </div>
          <div className="kpi-metric-accent-line" style={{ background: '#3b82f6' }} />
        </div>

        {/* Healthy */}
        <div
          className={`kpi-metric-card kpi-metric-card--healthy ${stateFilter === 'HEALTHY' ? 'is-active-filter' : ''}`}
          onClick={() => setStateFilter(stateFilter === 'HEALTHY' ? 'ALL' : 'HEALTHY')}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-metric-header">
            <span className="kpi-metric-label text-emerald-400">HEALTHY</span>
            <CheckCircleIcon size={14} className="text-emerald-400" />
          </div>
          <div className="kpi-metric-value-box">
            <span className="kpi-metric-number text-emerald-400">{stats.healthy}</span>
          </div>
          <div className="kpi-metric-footer">
            <span className="kpi-metric-subtext">
              {stats.total > 0 ? `${((stats.healthy / stats.total) * 100).toFixed(0)}% of matrix` : '0%'}
            </span>
          </div>
          <div className="kpi-metric-accent-line" style={{ background: '#00ff88' }} />
        </div>

        {/* Suspect */}
        <div
          className={`kpi-metric-card kpi-metric-card--suspect ${stateFilter === 'SUSPECT' ? 'is-active-filter' : ''}`}
          onClick={() => setStateFilter(stateFilter === 'SUSPECT' ? 'ALL' : 'SUSPECT')}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-metric-header">
            <span className="kpi-metric-label text-amber-400">SUSPECT</span>
            <AlertTriangleIcon size={14} className="text-amber-400" />
          </div>
          <div className="kpi-metric-value-box">
            <span className="kpi-metric-number text-amber-400">{stats.suspect}</span>
          </div>
          <div className="kpi-metric-footer">
            <span className="kpi-metric-subtext">
              {stats.total > 0 ? `${((stats.suspect / stats.total) * 100).toFixed(0)}% anomalies` : '0%'}
            </span>
          </div>
          <div className="kpi-metric-accent-line" style={{ background: '#ffd000' }} />
        </div>

        {/* Unknown */}
        <div
          className={`kpi-metric-card kpi-metric-card--unknown ${stateFilter === 'UNKNOWN' ? 'is-active-filter' : ''}`}
          onClick={() => setStateFilter(stateFilter === 'UNKNOWN' ? 'ALL' : 'UNKNOWN')}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-metric-header">
            <span className="kpi-metric-label text-slate-400">UNKNOWN</span>
            <CircleDotIcon size={14} className="text-slate-400" />
          </div>
          <div className="kpi-metric-value-box">
            <span className="kpi-metric-number text-slate-300">{stats.unknown}</span>
          </div>
          <div className="kpi-metric-footer">
            <span className="kpi-metric-subtext">
              {stats.total > 0 ? `${((stats.unknown / stats.total) * 100).toFixed(0)}% awaiting tick` : '0%'}
            </span>
          </div>
          <div className="kpi-metric-accent-line" style={{ background: '#64748b' }} />
        </div>

        {/* Degraded */}
        <div
          className={`kpi-metric-card kpi-metric-card--degraded ${stateFilter === 'DEGRADED' ? 'is-active-filter' : ''}`}
          onClick={() => setStateFilter(stateFilter === 'DEGRADED' ? 'ALL' : 'DEGRADED')}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-metric-header">
            <span className="kpi-metric-label text-rose-500">DEGRADED</span>
            <ShieldIcon size={14} className="text-rose-500" />
          </div>
          <div className="kpi-metric-value-box">
            <span className="kpi-metric-number text-rose-500">{stats.degraded}</span>
          </div>
          <div className="kpi-metric-footer">
            <span className="kpi-metric-subtext">
              {stats.total > 0 ? `${((stats.degraded / stats.total) * 100).toFixed(0)}% breaches` : '0 breaches'}
            </span>
          </div>
          <div className="kpi-metric-accent-line" style={{ background: '#ff4d4f' }} />
        </div>

        {/* Voided */}
        <div
          className={`kpi-metric-card kpi-metric-card--voided ${stateFilter === 'VOIDED' ? 'is-active-filter' : ''}`}
          onClick={() => setStateFilter(stateFilter === 'VOIDED' ? 'ALL' : 'VOIDED')}
          role="button"
          tabIndex={0}
        >
          <div className="kpi-metric-header">
            <span className="kpi-metric-label text-purple-400">VOIDED</span>
            <span style={{ fontSize: '12px', color: '#c084fc', fontWeight: 'bold' }}>&empty;</span>
          </div>
          <div className="kpi-metric-value-box">
            <span className="kpi-metric-number text-purple-400">{stats.voided}</span>
          </div>
          <div className="kpi-metric-footer">
            <span className="kpi-metric-subtext">Administrative exclusion</span>
          </div>
          <div className="kpi-metric-accent-line" style={{ background: '#a855f7' }} />
        </div>
      </section>

      {/* 3. Filter and Search Toolbar */}
      <section className="integrity-filter-toolbar" aria-label="Matrix filters">
        <div className="filter-toolbar-controls">
          {/* Team Selector */}
          <div className="filter-group">
            <label htmlFor="team-select" className="filter-label">TEAM:</label>
            <select
              id="team-select"
              className="filter-select"
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
            >
              <option value="ALL">All Teams ({uniqueTeams.length})</option>
              {uniqueTeams.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Contract Selector */}
          <div className="filter-group">
            <label htmlFor="contract-select" className="filter-label">CONTRACT:</label>
            <select
              id="contract-select"
              className="filter-select"
              value={contractFilter}
              onChange={(e) => setContractFilter(e.target.value)}
            >
              <option value="ALL">All Contracts ({displayedContracts.length})</option>
              {displayedContracts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Verdict Selector */}
          <div className="filter-group">
            <label htmlFor="verdict-select" className="filter-label">VERDICT:</label>
            <select
              id="verdict-select"
              className="filter-select"
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
            >
              <option value="ALL">All Verdicts</option>
              <option value="HEALTHY">Healthy Only</option>
              <option value="SUSPECT">Suspect Only</option>
              <option value="UNKNOWN">Unknown Only</option>
              <option value="DEGRADED">Degraded Only</option>
              <option value="VOIDED">Voided Only</option>
            </select>
          </div>

          {/* Sort Selector */}
          <div className="filter-group">
            <label htmlFor="sort-select" className="filter-label">SORT:</label>
            <select
              id="sort-select"
              className="filter-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
            >
              <option value="POS">Track Position (P1–P20)</option>
              <option value="ALERTS">Alerts First (Suspect / Degraded)</option>
              <option value="NUM">Car Number (#1–#99)</option>
              <option value="NAME">Driver Name (A–Z)</option>
              <option value="TEAM">Constructor Name (A–Z)</option>
            </select>
          </div>

          {hasActiveFilters && (
            <button type="button" className="filter-reset-button" onClick={resetFilters}>
              Reset Filters
            </button>
          )}
        </div>

        {/* Participant Search */}
        <div className="filter-toolbar-search">
          <div className="search-bar-wrapper">
            <SearchIcon size={14} className="search-bar-icon" />
            <input
              type="search"
              className="search-bar-input"
              placeholder="Search driver, team, or car #..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Filter matrix participants"
            />
            {search && (
              <button
                type="button"
                className="search-bar-clear"
                onClick={() => setSearch('')}
                aria-label="Clear search"
              >
                &times;
              </button>
            )}
          </div>
        </div>
      </section>

      {/* 4. Main Integrity Matrix: Full-Width Professional Data Table */}
      <section className="integrity-matrix-container" aria-label="Integrity evaluation matrix">
        <div className="matrix-table-wrapper">
          <table className="integrity-data-table">
            <thead>
              <tr>
                <th className="th-participant-col">PARTICIPANT / CONSTRUCTOR</th>
                {displayedContracts
                  .filter((c) => contractFilter === 'ALL' || c.id === contractFilter)
                  .map((c) => (
                    <th key={c.id} className="th-contract-col">
                      <div className="contract-col-header">
                        <span className="contract-col-scope">{c.scope}</span>
                        <strong className="contract-col-name">{c.name}</strong>
                      </div>
                    </th>
                  ))}
              </tr>
            </thead>
            <tbody>
              {processedDrivers.length === 0 ? (
                <tr>
                  <td colSpan={displayedContracts.length + 1} className="matrix-empty-cell">
                    <div className="matrix-empty-content">
                      <FilterIcon size={24} className="text-slate-500 mb-2" />
                      <h4>No participants match current filter criteria</h4>
                      <p>Adjust your search query or reset the verdict state and constructor filters.</p>
                      <button type="button" className="btn-clear-matrix-filters" onClick={resetFilters}>
                        Clear All Filters
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                processedDrivers.map((driver) => {
                  const teamColor = driver.teamColor || '#E80020';

                  return (
                    <tr key={driver.number} className="matrix-data-row">
                      {/* Driver Identity Sticky Column */}
                      <td className="matrix-participant-cell" style={{ borderLeftColor: teamColor }}>
                        <div className="participant-ident-wrap">
                          <div className="participant-badges">
                            <span className="p-pos-badge" style={{ backgroundColor: teamColor }}>
                              P{driver.position}
                            </span>
                            <span className="p-num-badge">#{driver.number}</span>
                          </div>
                          <div className="participant-text">
                            <span className="p-driver-name">{driver.name}</span>
                            <span className="p-team-name">{driver.team}</span>
                          </div>
                        </div>
                      </td>

                      {/* Contract Verdict Cells */}
                      {displayedContracts
                        .filter((c) => contractFilter === 'ALL' || c.id === contractFilter)
                        .map((contract) => {
                          const verdict = findVerdict(contract.id, driver.number);
                          const instId =
                            verdict?.decision_instance_id ||
                            `dec-${contract.id.toLowerCase().replace(/[^a-z0-9]/g, '_')}-d${driver.number}`;

                          const cellState: IntegrityState = verdict?.integrity_state || 'UNKNOWN';
                          const disposition = verdict?.disposition || 'NORMAL';
                          const isVoided = disposition === 'VOIDED';

                          // Apply state filter if set
                          if (stateFilter !== 'ALL') {
                            if (stateFilter === 'VOIDED' && !isVoided) {
                              return <td key={contract.id} className="matrix-verdict-cell is-filtered-out" />;
                            }
                            if (stateFilter !== 'VOIDED' && (cellState !== stateFilter || isVoided)) {
                              return <td key={contract.id} className="matrix-verdict-cell is-filtered-out" />;
                            }
                          }

                          const isSelected = selectedInstanceId === instId;
                          const isAlert = cellState === 'SUSPECT' || cellState === 'DEGRADED';

                          return (
                            <td
                              key={contract.id}
                              className={`matrix-verdict-cell ${isSelected ? 'is-selected-cell' : ''} ${
                                isAlert ? 'is-alert-cell' : ''
                              }`}
                              onClick={() => onSelectDecision(instId)}
                              onMouseEnter={(e) => {
                                const rect = e.currentTarget.getBoundingClientRect();
                                setHoveredCell({
                                  driverName: driver.name,
                                  contractName: contract.name,
                                  state: isVoided ? 'VOIDED' : cellState,
                                  x: rect.left + rect.width / 2,
                                  y: rect.top - 8,
                                });
                              }}
                              onMouseLeave={() => setHoveredCell(null)}
                              role="button"
                              tabIndex={0}
                            >
                              <div className="verdict-cell-content">
                                <StateBadge
                                  state={cellState}
                                  disposition={disposition}
                                  size="sm"
                                  className="verdict-pill-badge"
                                />
                                {isAlert && <span className="alert-pulse-dot" />}
                              </div>
                            </td>
                          );
                        })}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Compact Hover Tooltip */}
        {hoveredCell && (
          <div
            className="matrix-hover-tooltip"
            style={{
              position: 'fixed',
              left: `${hoveredCell.x}px`,
              top: `${hoveredCell.y}px`,
              transform: 'translate(-50%, -100%)',
              pointerEvents: 'none',
              zIndex: 1100,
            }}
          >
            <div className="tooltip-title">{hoveredCell.driverName}</div>
            <div className="tooltip-sub">
              {hoveredCell.contractName}: <strong className="tooltip-state">{hoveredCell.state}</strong>
            </div>
            <div className="tooltip-hint">Click to inspect decision</div>
          </div>
        )}

        {/* 5. Matrix Provenance & Invariant Footer */}
        <footer className="integrity-matrix-footer">
          <div className="footer-left-info">
            <span className="footer-pulse-dot" />
            <span>
              All matrix verdicts are deterministically evaluated by <strong>SIA Core v3</strong> from calibrated
              optical loops, ECU CAN-bus transponders, and regulatory AST contracts.
            </span>
          </div>
          <div className="footer-right-info">
            <span>Click any matrix cell to open the Decision Inspector Drawer</span>
          </div>
        </footer>
      </section>
    </div>
  );
};
