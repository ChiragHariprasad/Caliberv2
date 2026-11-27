import React, { useState } from 'react';
import type { EvidenceAtom } from '../../types/calibre';
import { MonoHash } from '../shared/MonoHash';
import { StateBadge } from '../shared/StateBadge';

interface AtomViewerProps {
  atom: EvidenceAtom | null | undefined;
  rawSpanAvailable?: boolean;
  rawSpanHex?: string;
  rawSpanOffset?: string;
  bundleReference?: string;
  className?: string;
}

export const AtomViewer: React.FC<AtomViewerProps> = ({
  atom,
  rawSpanAvailable = false,
  rawSpanHex = '00 4a 2f 18 20 44 89 a2 7b 3c e1 90 ff 00 24 10',
  rawSpanOffset = '0x004A2F',
  bundleReference = 'captures/f1-2023-silverstone-race/bundle.tar.zst',
  className = '',
}) => {
  const [viewTab, setViewTab] = useState<'CANONICAL' | 'ORIGINS' | 'RAW_SPAN'>('CANONICAL');

  if (!atom) {
    return (
      <div className={`atom-viewer-empty ${className}`}>
        <p>Select an evidence role above to inspect its underlying Evidence Atom.</p>
      </div>
    );
  }

  return (
    <div className={`atom-viewer-card ${className}`}>
      <div className="atom-viewer__header">
        <div className="atom-id-row">
          <span className="atom-label">EVIDENCE ATOM</span>
          <MonoHash hash={atom.atom_id} label="ID" />
          <StateBadge state={atom.quality_grade} size="sm" />
        </div>

        <div className="atom-nav-tabs">
          <button
            type="button"
            className={`atom-tab ${viewTab === 'CANONICAL' ? 'active' : ''}`}
            onClick={() => setViewTab('CANONICAL')}
          >
            Canonical Payload (RFC 8785)
          </button>
          <button
            type="button"
            className={`atom-tab ${viewTab === 'ORIGINS' ? 'active' : ''}`}
            onClick={() => setViewTab('ORIGINS')}
          >
            Two-Axis Provenance
          </button>
          <button
            type="button"
            className={`atom-tab ${viewTab === 'RAW_SPAN' ? 'active' : ''}`}
            onClick={() => setViewTab('RAW_SPAN')}
          >
            Raw Span Reference {rawSpanAvailable ? '(In Buffer)' : '(Archived)'}
          </button>
        </div>
      </div>

      <div className="atom-viewer__body">
        {viewTab === 'CANONICAL' && (
          <div className="tab-pane canonical-pane">
            <div className="atom-kv-grid">
              <div className="kv-item">
                <span className="kv-key">Role:</span>
                <code className="kv-val">{atom.role_id}</code>
              </div>
              <div className="kv-item">
                <span className="kv-key">Value:</span>
                <strong className="kv-val">{String(atom.value)} {atom.unit}</strong>
              </div>
              <div className="kv-item">
                <span className="kv-key">Observed Instant:</span>
                <span className="kv-val">{atom.observed_at}</span>
              </div>
              <div className="kv-item">
                <span className="kv-key">Typed Time:</span>
                <span className="kv-val">
                  {atom.time.class} ({atom.time.value} µs · unc: ±{atom.time.unc} µs)
                </span>
              </div>
              <div className="kv-item">
                <span className="kv-key">Scope:</span>
                <code className="kv-val">{JSON.stringify(atom.scope)}</code>
              </div>
              <div className="kv-item">
                <span className="kv-key">Processor:</span>
                <span className="kv-val">{atom.processor_family_id} (v{atom.transform_version})</span>
              </div>
            </div>

            <div className="canonical-json-box">
              <span className="box-title">RFC 8785 Canonical JSON Representation:</span>
              <pre className="json-pre">
                {JSON.stringify(
                  {
                    role_id: atom.role_id,
                    value: atom.value,
                    unit: atom.unit,
                    observed_at: atom.observed_at,
                    time: atom.time,
                    scope: atom.scope,
                    source_origins: atom.source_origins,
                    processing_origins: atom.processing_origins,
                    processor_family_id: atom.processor_family_id,
                    transform_version: atom.transform_version,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          </div>
        )}

        {viewTab === 'ORIGINS' && (
          <div className="tab-pane origins-pane">
            <div className="provenance-axes-grid">
              <div className="axis-card">
                <h5>Source Origin Axis (Physical Hardware / Provider)</h5>
                <ul className="origin-list">
                  {atom.source_origins.map((src, i) => (
                    <li key={i} className="origin-item">
                      <span className="origin-badge badge--source">{src}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="axis-card">
                <h5>Processing Origin Axis (Software Transformation / Adapter)</h5>
                <ul className="origin-list">
                  {atom.processing_origins.map((proc, i) => (
                    <li key={i} className="origin-item">
                      <span className="origin-badge badge--proc">{proc}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {viewTab === 'RAW_SPAN' && (
          <div className="tab-pane raw-span-pane">
            {rawSpanAvailable ? (
              <div className="raw-span-buffer-view">
                <div className="span-meta">
                  <span>Status: <strong className="text-emerald-400">AVAILABLE IN ACTIVE BUFFER</strong></span>
                  <span>Offset: <code>{rawSpanOffset}</code></span>
                </div>
                <div className="hex-dump-box">
                  <code>{rawSpanHex}</code>
                </div>
              </div>
            ) : (
              <div className="raw-span-archived-view">
                <p className="notice-text">
                  Raw span byte slice has migrated to durable cold storage bundle.
                </p>
                <div className="bundle-meta-card">
                  <span className="b-label">Archive Bundle:</span>
                  <code className="b-val">{bundleReference}</code>
                  <span className="b-label">Byte Offset:</span>
                  <code className="b-val">{rawSpanOffset}</code>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

