import { useState } from 'react';
import type { Assessment, OfficialNotice, RaceEvent } from '../types';
import { BrainIcon, CheckCircleIcon, ScaleIcon } from './icons';

interface RaceControlViewProps {
  notices: OfficialNotice[];
  timeline: RaceEvent[];
  assessments: Assessment[];
}

export function RaceControlView({ notices, timeline, assessments }: RaceControlViewProps) {
  const [activeTab, setActiveTab] = useState<'OFFICIAL' | 'PULSE_AI' | 'ALL'>('OFFICIAL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  const filteredNotices = notices.filter((n) => {
    if (categoryFilter === 'ALL') return true;
    return n.category === categoryFilter;
  });

  return (
    <div className="race-control-view">
      <div className="view-intro-bar">
        <div>
          <span className="eyebrow">FIA Official Regulatory Feed & Stewarding Audit</span>
          <h2>Race Control, Track Status & Regulatory Decisions</h2>
        </div>
        <div className="domain-tabs">
          <button
            type="button"
            className={`domain-tab ${activeTab === 'OFFICIAL' ? 'active' : ''}`}
            onClick={() => setActiveTab('OFFICIAL')}
          >
            <ScaleIcon size={14} className="tab-icon mr-1" />
            Official FIA Domain ({notices.length})
          </button>
          <button
            type="button"
            className={`domain-tab ${activeTab === 'PULSE_AI' ? 'active' : ''}`}
            onClick={() => setActiveTab('PULSE_AI')}
          >
            <BrainIcon size={14} className="tab-icon mr-1" />
            PULSE Analytics Domain ({assessments.length})
          </button>
          <button
            type="button"
            className={`domain-tab ${activeTab === 'ALL' ? 'active' : ''}`}
            onClick={() => setActiveTab('ALL')}
          >
            Merged Lineage ({notices.length + assessments.length})
          </button>
        </div>
      </div>

      {/* Official Domain View */}
      {(activeTab === 'OFFICIAL' || activeTab === 'ALL') && (
        <section className="panel official-stewarding-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Official FIA Communications</p>
              <h3>Official Race Director Notices & Stewards' Decisions</h3>
            </div>
            <div className="category-chips">
              {['ALL', 'SAFETY_CAR', 'FLAG', 'INCIDENT', 'INVESTIGATION', 'WEATHER'].map((cat) => (
                <button
                  type="button"
                  key={cat}
                  className={`chip-filter ${categoryFilter === cat ? 'active' : ''}`}
                  onClick={() => setCategoryFilter(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          <div className="notices-table-container">
            <table className="official-notices-table">
              <thead>
                <tr>
                  <th>NOTICE ID</th>
                  <th>TIMESTAMP (UTC)</th>
                  <th>FLAG / CAT</th>
                  <th>OFFICIAL TITLE & DIRECTIVE</th>
                  <th>CARS</th>
                  <th>REGULATORY BASIS</th>
                  <th>SOURCE & STATUS</th>
                </tr>
              </thead>
              <tbody>
                {filteredNotices.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '1.5rem', color: '#8899a6' }}>
                      No official FIA race control notices issued in current session window.
                    </td>
                  </tr>
                ) : (
                  filteredNotices.map((notice) => (
                    <tr key={notice.notice_id} className={`notice-row flag-${notice.flag.toLowerCase()}`}>
                      <td className="col-notice-id">
                        <code>{notice.notice_id}</code>
                      </td>
                      <td className="col-time">
                        {new Date(notice.timestamp_utc).toLocaleTimeString()}
                      </td>
                      <td className="col-flag">
                        <span className={`flag-badge flag-${notice.flag.toLowerCase()}`}>
                          {notice.flag}
                        </span>
                      </td>
                      <td className="col-directive">
                        <strong>{notice.title}</strong>
                        <p className="directive-detail">{notice.detail}</p>
                      </td>
                      <td className="col-cars">
                        {notice.driver_numbers.length > 0 ? (
                          <div className="driver-chips">
                            {notice.driver_numbers.map((dn) => (
                              <span key={dn} className="driver-mini-chip">#{dn}</span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-muted">ALL</span>
                        )}
                      </td>
                      <td className="col-reg">
                        <span className="reg-code" title={notice.regulatory_reference}>
                          {notice.regulatory_reference}
                        </span>
                      </td>
                      <td className="col-source">
                        <span className="source-tag">{notice.source}</span>
                        <span className="status-verified">
                          <CheckCircleIcon size={12} className="inline mr-1" />
                          {notice.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <p className="panel-note">Official records are ingested verbatim from the FIA Race Director feed and published stewards bulletins. PULSE never generates artificial stewarding decisions.</p>
        </section>
      )}

      {/* PULSE Consequence Domain View */}
      {(activeTab === 'PULSE_AI' || activeTab === 'ALL') && (
        <section className="panel pulse-correlation-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">PULSE Multi-Agent Synthesis</p>
              <h3>Tactical Consequences & Correlated Race Context</h3>
            </div>
            <span className="subtle-chip">Deterministic Consequence Fusion</span>
          </div>

          <div className="pulse-assessment-cards-grid">
            {assessments.map((a) => (
              <div key={a.id} className={`assessment-audit-card tone-${a.impact}`}>
                <div className="audit-card-top">
                  <span className="audit-driver">Car #{a.driverNumber}</span>
                  <span className={`audit-status status-${a.status.toLowerCase()}`}>
                    {a.status} (v{a.version ?? 1})
                  </span>
                  {a.supersedesId && (
                    <span className="supersedes-tag">Supersedes {a.supersedesId}</span>
                  )}
                </div>

                <h4>{a.title}</h4>
                <p className="narrative-text">{a.narrative}</p>

                <div className="audit-forecast-box">
                  <strong>2-Lap Forecast:</strong> {a.forecast}
                </div>

                <div className="audit-evidence-section">
                  <span className="evidence-title">Supporting Findings Lineage:</span>
                  <ul>
                    {a.evidence.map((ev, i) => (
                      <li key={i}>{ev}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

