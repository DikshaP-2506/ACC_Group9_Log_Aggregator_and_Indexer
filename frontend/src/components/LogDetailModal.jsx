import React, { useState } from 'react';

export default function LogDetailModal({ log, onClose }) {
  const [copiedId, setCopiedId] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);

  if (!log) return null;

  const handleCopyId = () => {
    if (log.id) {
      navigator.clipboard.writeText(log.id);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const handleCopyJson = () => {
    const jsonStr = JSON.stringify(log, null, 2);
    navigator.clipboard.writeText(jsonStr);
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  const metadataJson = JSON.stringify(log.metadata || {}, null, 2);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-header-title">
            <span className="modal-tag">Document Inspector</span>
            <h3>Structured Log Entry</h3>
          </div>
          <button
            type="button"
            className="btn-modal-close"
            onClick={onClose}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {/* Document ID row */}
          <div className="doc-id-banner">
            <div>
              <span className="doc-id-label">Deterministic Document ID:</span>
              <code className="doc-id-code">{log.id}</code>
            </div>
            <button
              type="button"
              className="btn-copy-chip"
              onClick={handleCopyId}
            >
              {copiedId ? '✓ Copied' : 'Copy ID'}
            </button>
          </div>

          {/* Key Attributes Grid */}
          <div className="detail-meta-grid">
            <div className="meta-box">
              <span className="meta-label">Severity Level</span>
              <span className={`badge-level ${log.level?.toLowerCase() || 'info'}`}>
                {log.level}
              </span>
            </div>

            <div className="meta-box">
              <span className="meta-label">Originating Source</span>
              <span className="badge-source">{log.source}</span>
            </div>

            <div className="meta-box">
              <span className="meta-label">Assigned Partition</span>
              <span className="badge-partition">
                <span className="partition-dot" />
                {log.partition || 'partition-0'}
              </span>
            </div>

            <div className="meta-box">
              <span className="meta-label">Timestamp (UTC)</span>
              <span className="meta-value-mono">{log.timestamp}</span>
            </div>
          </div>

          {/* Log Message */}
          <div className="detail-section">
            <span className="detail-section-title">Log Message Payload:</span>
            <div className="message-box">
              {log.message}
            </div>
          </div>

          {/* Metadata JSON */}
          <div className="detail-section">
            <div className="json-header-row">
              <span className="detail-section-title">Context Metadata (JSON):</span>
              <button
                type="button"
                className="btn-copy-chip"
                onClick={handleCopyJson}
              >
                {copiedJson ? '✓ Copied Full JSON' : 'Copy JSON'}
              </button>
            </div>
            <pre className="code-box">
              <code>{metadataJson}</code>
            </pre>
          </div>

          {/* Routing Details note */}
          <div className="routing-proof-note">
            <span className="proof-icon">ℹ</span>
            <span>
              <strong>Routing Partition:</strong> Source service <code>{log.source}</code> routes deterministically to <code>{log.partition || 'partition-0'}</code>.
            </span>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="modal-footer">
          <button type="button" className="btn-action btn-secondary" onClick={onClose}>
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
