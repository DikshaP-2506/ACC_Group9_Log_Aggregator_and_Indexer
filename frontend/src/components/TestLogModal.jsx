import React, { useState, useEffect } from 'react';
import { ingestTestLog, resolveRoute } from '../services/api';

const PRESETS = [
  {
    name: '🚨 Payment Gateway Timeout',
    level: 'ERROR',
    source: 'payment-service',
    message: 'Payment gateway rejected transaction: Connection timeout to Stripe API host',
    metadata: {
      gateway: 'stripe',
      timeout_ms: 5000,
      order_id: 'ord-8831',
      attempt: 3
    }
  },
  {
    name: '🔒 User Session Auth',
    level: 'INFO',
    source: 'auth-service',
    message: 'User authentication successful and JWT access token issued',
    metadata: {
      user_id: 418,
      auth_method: 'oauth2_google',
      ip: '192.168.1.104'
    }
  },
  {
    name: '⚠️ DB Connection Warning',
    level: 'WARNING',
    source: 'db-replica-01',
    message: 'Database connection pool near capacity (18/20 active connections)',
    metadata: {
      pool: 'postgres',
      active_connections: 18,
      max_connections: 20
    }
  },
  {
    name: '📦 Inventory Stock Sync',
    level: 'INFO',
    source: 'inventory-service',
    message: 'Warehouse stock level updated and cached in Redis buffer',
    metadata: {
      sku: 'SKU-7721',
      quantity_delta: -1,
      warehouse: 'us-east-1'
    }
  }
];

export default function TestLogModal({ onClose, onSuccess }) {
  const [level, setLevel] = useState('INFO');
  const [source, setSource] = useState('payment-service');
  const [message, setMessage] = useState('Payment transaction verified and cleared');
  const [metadataJson, setMetadataJson] = useState('{\n  "environment": "production",\n  "trace_id": "trc_9012"\n}');
  const [predictedPartition, setPredictedPartition] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  // Live resolve destination as user types source
  useEffect(() => {
    if (!source.trim()) {
      setPredictedPartition(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await resolveRoute(source.trim());
        setPredictedPartition(res.assigned_partition);
      } catch {
        setPredictedPartition(null);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [source]);

  const applyPreset = (preset) => {
    setLevel(preset.level);
    setSource(preset.source);
    setMessage(preset.message);
    setMetadataJson(JSON.stringify(preset.metadata, null, 2));
    setStatusMsg(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message.trim() || !source.trim()) return;

    let parsedMeta = {};
    if (metadataJson.trim()) {
      try {
        parsedMeta = JSON.parse(metadataJson);
      } catch (err) {
        setStatusMsg({
          type: 'error',
          text: `Invalid Metadata JSON: ${err.message}`
        });
        return;
      }
    }

    setSubmitting(true);
    setStatusMsg(null);

    try {
      const payload = {
        level,
        source: source.trim(),
        message: message.trim(),
        metadata: parsedMeta
      };

      const res = await ingestTestLog(payload);
      setStatusMsg({
        type: 'success',
        text: `Log ingested! ID: ${res.id.substring(0, 16)}... -> Partition: ${res.partition}`
      });
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1200);
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '580px' }}>
        <div className="modal-header">
          <div className="modal-header-title">
            <span className="modal-tag">Pipeline Ingestion Console</span>
            <h3>Inject Structured Log Event</h3>
          </div>
          <button type="button" className="btn-modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Quick Presets row */}
            <div>
              <span className="meta-label" style={{ marginBottom: '8px', display: 'block' }}>
                Quick Presets:
              </span>
              <div className="preset-chips-row">
                {PRESETS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="preset-chip"
                    onClick={() => applyPreset(p)}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>

            {statusMsg && (
              <div className={`status-banner ${statusMsg.type}`}>
                <span className="status-banner-icon">
                  {statusMsg.type === 'success' ? '✓' : '⚠'}
                </span>
                <span>{statusMsg.text}</span>
              </div>
            )}

            <div className="form-two-col">
              <div>
                <label className="input-label">Severity Level:</label>
                <select
                  className="select-control"
                  style={{ width: '100%' }}
                  value={level}
                  onChange={(e) => setLevel(e.target.value)}
                >
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                  <option value="DEBUG">DEBUG</option>
                </select>
              </div>

              <div>
                <label className="input-label">
                  Originating Source:
                  {predictedPartition && (
                    <span className="predicted-tag">➔ {predictedPartition}</span>
                  )}
                </label>
                <input
                  type="text"
                  className="text-input"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  placeholder="e.g. payment-service, auth-service"
                  required
                />
              </div>
            </div>

            <div>
              <label className="input-label">Log Message Payload:</label>
              <textarea
                className="text-input"
                style={{ height: '70px', resize: 'vertical' }}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Descriptive log message event..."
                required
              />
            </div>

            <div>
              <label className="input-label">Context Metadata (JSON Object):</label>
              <textarea
                className="text-input font-mono"
                style={{ height: '90px', resize: 'vertical', fontSize: '0.8rem' }}
                value={metadataJson}
                onChange={(e) => setMetadataJson(e.target.value)}
                placeholder='{\n  "key": "value"\n}'
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-action btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn-action btn-primary" disabled={submitting}>
              {submitting ? 'Ingesting into Pipeline...' : 'Ingest to Aggregator'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
