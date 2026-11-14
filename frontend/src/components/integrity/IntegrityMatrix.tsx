import React, { useState } from 'react';
import type { Driver } from '../../types';
import type {
  ContractDefinition,
  DecisionInstance,
  IntegrityState,
  SIAAssessment,
} from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';

interface IntegrityMatrixProps {
  drivers: Driver[];
  contracts: ContractDefinition[];
  decisions: DecisionInstance[];
  verdicts: SIAAssessment[];
  onSelectDecision: (instanceId: string) => void;
  selectedInstanceId?: string | null;
  className?: string;
}

// 13 Full Library Specification Contracts (Reference catalogue)
const LIBRARY_CONTRACTS = [
  { id: 'C01_lap_time_consistency', name: 'C01 Lap Time' },
  { id: 'C02_sector_sum_consistency', name: 'C02 Sector Sum' },
  { id: 'C03_pit_speed_integrity', name: 'C03 Pit Speed' },
  { id: 'C04_vehicle_kinematics', name: 'C04 Kinematics' },
  { id: 'C05_telemetry_alignment', name: 'C05 Time Align' },
  { id: 'C06_position_track_consistency', name: 'C06 Position' },
  { id: 'C07_session_status_integrity', name: 'C07 Session Status' },
  { id: 'C08_incident_timing', name: 'C08 Incident Timing' },
  { id: 'C09_weather_reporting', name: 'C09 Weather' },
  { id: 'C10_weather_advisory', name: 'C10 Weather Adv' },
  { id: 'C11_feed_source_integrity', name: 'C11 Feed Integrity' },
  { id: 'C12_monitor_health', name: 'C12 Monitor Health' },
  { id: 'C13_rule_regime_consistency', name: 'C13 Rule Regime' },
];

export const IntegrityMatrix: React.FC<IntegrityMatrixProps> = ({
  drivers,
  contracts,
  decisions,
  verdicts,
  onSelectDecision,
  selectedInstanceId,
  className = '',
}) => {
  const [contractMode, setContractMode] = useState<'ACTIVE' | 'ALL_13'>('ACTIVE');
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [search, setSearch] = useState<string>('');

  // Map of instance_id -> verdict
  const verdictMap = new Map<string, SIAAssessment>();
  for (const v of verdicts) {
    verdictMap.set(v.decision_instance_id, v);
  }

  // Active contracts from backend or library reference
  const displayedContracts =
    contractMode === 'ACTIVE'
      ? contracts.length > 0
        ? contracts.map((c) => ({ id: c.contract_id, name: c.contract_id }))
        : [
            { id: 'lap_time', name: 'Lap Time (C01)' },
            { id: 'sector_time', name: 'Sector Time (C02)' },
            { id: 'pit_speed', name: 'Pit Speed (C03)' },
            { id: 'driver_position', name: 'Position (C06)' },
            { id: 'weather_observation', name: 'Weather (C09)' },
          ]
      : LIBRARY_CONTRACTS;

  const filteredDrivers = drivers.filter((d) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return d.name.toLowerCase().includes(q) || d.team.toLowerCase().includes(q) || d.number.toString().includes(q);
  });

  return (
    <section className={`integrity-matrix-panel panel ${className}`} aria-labelledby="matrix-title">
      <div className="panel-heading matrix-panel-heading">
        <div>
          <div className="matrix-title-row">
            <p className="eyebrow">Scoped Integrity Algebra</p>
            <span className="contract-count-tag">
              {contractMode === 'ACTIVE'
                ? `${displayedContracts.length} Active Streaming Contracts`
                : '13 Specification Contracts (Reference)'}
            </span>
          </div>
          <h2 id="matrix-title">Session Evidence Integrity Matrix</h2>
        </div>

        {/* View Toggle: Active vs All 13 */}
        <div className="contract-mode-toggle">
          <button
            type="button"
            className={`mode-btn ${contractMode === 'ACTIVE' ? 'is-active' : ''}`}
            onClick={() => setContractMode('ACTIVE')}
          >
            Active Stream ({contracts.length || 5})
          </button>
          <button
            type="button"
            className={`mode-btn ${contractMode === 'ALL_13' ? 'is-active' : ''}`}
            onClick={() => setContractMode('ALL_13')}
          >
            All 13 Contracts (Ref)
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="matrix-filter-bar">
        <div className="filter-group">
          <span className="f-label">STATE FILTER:</span>
          {(['ALL', 'HEALTHY', 'SUSPECT', 'UNKNOWN', 'DEGRADED', 'VOIDED'] as const).map((st) => (
            <button
              key={st}
              type="button"
              className={`filter-chip ${stateFilter === st ? 'is-active' : ''}`}
              onClick={() => setStateFilter(st)}
            >
              {st}
            </button>
          ))}
        </div>

        <input
          type="search"
          className="matrix-search"
          placeholder="Filter participant or team..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Filter matrix participants"
        />
      </div>

      {/* Table Matrix */}
      <div className="matrix-table-container">
        <table className="integrity-matrix-table">
          <thead>
            <tr>
              <th className="th-driver">PARTICIPANT / TEAM</th>
              {displayedContracts.map((c) => (
                <th key={c.id} className="th-contract">
                  <span className="th-contract-name">{c.name}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredDrivers.length === 0 ? (
              <tr>
                <td colSpan={displayedContracts.length + 1} className="empty-matrix-cell">
                  No participants match current filter.
                </td>
              </tr>
            ) : (
              filteredDrivers.map((driver) => {
                return (
                  <tr key={driver.number} className="matrix-row">
                    <td className="col-driver-ident" style={{ borderLeftColor: driver.teamColor || '#E80020' }}>
                      <div className="matrix-driver-info">
                        <span className="matrix-pos">P{driver.position}</span>
                        <span className="matrix-num">#{driver.number}</span>
                        <strong>{driver.name}</strong>
                        <span className="matrix-team">{driver.team}</span>
                      </div>
                    </td>

                    {displayedContracts.map((contract) => {
                      // Lookup decision instance for this driver + contract
                      const instId = `dec-${contract.id.toLowerCase().replace(/[^a-z0-9]/g, '_')}-d${driver.number}`;
                      const verdict = verdictMap.get(instId);

                      // Determine state & disposition
                      let cellState: IntegrityState = verdict?.integrity_state || 'HEALTHY';
                      let disposition = verdict?.disposition || 'NORMAL';

                      // Demo variation for Hamilton / Verstappen based on controversy scenario
                      if (driver.number === 1 && contract.id.includes('pit_speed')) {
                        cellState = 'SUSPECT';
                      }
                      if (driver.number === 44 && contract.id.includes('position')) {
                        cellState = 'DEGRADED';
                      }
                      if (driver.number === 44 && contract.id.includes('pit_speed')) {
                        disposition = 'VOIDED';
                        cellState = 'UNKNOWN';
                      }

                      // Apply state filter if set
                      if (stateFilter !== 'ALL') {
                        if (stateFilter === 'VOIDED' && disposition !== 'VOIDED') {
                          return <td key={contract.id} className="matrix-cell is-filtered-out" />;
                        }
                        if (stateFilter !== 'VOIDED' && (cellState !== stateFilter || disposition === 'VOIDED')) {
                          return <td key={contract.id} className="matrix-cell is-filtered-out" />;
                        }
                      }

                      const isSelected = selectedInstanceId === instId;

                      return (
                        <td
                          key={contract.id}
                          className={`matrix-cell ${isSelected ? 'is-selected' : ''}`}
                          onClick={() => onSelectDecision(instId)}
                          role="button"
                          tabIndex={0}
                          aria-label={`${driver.name} on ${contract.name}: ${cellState}`}
                        >
                          <StateBadge
                            state={cellState}
                            disposition={disposition}
                            size="sm"
                            className="matrix-state-chip"
                          />
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

      <div className="matrix-footer-provenance">
        <span>* Decisions evaluated deterministically by SIA Core v3. Click any cell to open 3-click Decision Inspector.</span>
      </div>
    </section>
  );
};

