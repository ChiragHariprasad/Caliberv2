import React, { useState } from 'react';
import { parseTaggedHash } from '../../types/calibre';

interface MonoHashProps {
  hash: string | null | undefined;
  className?: string;
  truncateLength?: number;
  label?: string;
  showCopy?: boolean;
}

export const MonoHash: React.FC<MonoHashProps> = ({
  hash,
  className = '',
  truncateLength = 12,
  label,
  showCopy = true,
}) => {
  const [copied, setCopied] = useState(false);
  const parsed = parseTaggedHash(hash);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!parsed.raw) return;
    try {
      await navigator.clipboard.writeText(parsed.raw);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore clipboard error
    }
  };

  const displayHash =
    parsed.hash.length > truncateLength
      ? `${parsed.hash.slice(0, Math.floor(truncateLength / 2))}…${parsed.hash.slice(-Math.floor(truncateLength / 2))}`
      : parsed.hash;

  return (
    <span
      className={`mono-hash-container ${className}`}
      title={`Algorithm: ${parsed.algorithm.toUpperCase()} · Full digest: ${parsed.raw}`}
    >
      {label && <span className="mono-hash__label">{label}:</span>}
      <span className={`mono-hash__algo-tag mono-hash__algo-tag--${parsed.algorithm}`}>
        {parsed.algorithm.toUpperCase()}
      </span>
      <code className="mono-hash__value">{displayHash || '—'}</code>
      {showCopy && parsed.raw && (
        <button
          type="button"
          className="mono-hash__copy-btn"
          onClick={handleCopy}
          aria-label="Copy hash to clipboard"
          title="Copy digest"
        >
          {copied ? (
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )}
        </button>
      )}
    </span>
  );
};

