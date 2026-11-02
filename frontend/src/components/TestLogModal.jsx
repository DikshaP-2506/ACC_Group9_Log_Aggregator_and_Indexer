import React, { useState, useEffect } from 'react';
import { ingestTestLog, resolveRoute } from '../services/api';

const PRESETS = [
  {
    name: '💳 FinTech: Payment Timeout',
    level: 'ERROR',
    domain: 'fintech',
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
    name: '🏥 Healthcare: ICU Vitals Alert',
    level: 'ERROR',
    domain: 'healthcare',
    source: 'patient-vitals-monitor',
    message: 'Critical ICU telemetry alert: Cardiac arrhythmia detected on patient_412 (Ward 4B)',
    metadata: {
      patient_id: 'PT-412',
      vital_sign: 'VTach',
      ward: 'ICU-North',
      code_blue: false,
      standard: 'FHIR_R4'
    }
  },
  {
    name: '🛒 E-Commerce: Stock Delta',
    level: 'INFO',
    domain: 'ecommerce',
    source: 'inventory-service',
    message: 'Warehouse stock level updated and cached in Redis buffer for SKU-7721',
    metadata: {
      sku: 'SKU-7721',
      quantity_delta: -1,
      warehouse: 'us-east-1',
      carrier: 'FedEx'
    }
  },
  {
    name: '🛡️ CyberSec: WAF SQLi Block',
    level: 'ERROR',
    domain: 'cybersecurity',
    source: 'waf-edge-proxy',
    message: 'WAF blocked malicious SQL injection pattern in query param "user_id"',
    metadata: {
      vector: 'SQLi',
      client_ip: '198.51.100.24',
      blocked: true,
      rule_id: 'OWASP-CRS-942100'
    }
  },
  {
    name: '⚙️ DevOps: DB Pool Warning',
    level: 'WARNING',
    domain: 'devops',
    source: 'db-replica-01',
    message: 'Database connection pool near capacity (18/20 active connections)',
    metadata: {
      pool: 'postgres',
      active_connections: 18,
      max_connections: 20,
      host: 'pg-replica-01'
    }
  },
  {
    name: '📡 IoT: Smart Meter Beacon',
    level: 'INFO',
    domain: 'iot',
    source: 'sensor-node-hub',
    message: 'Smart electricity meter telemetry beacon ingested: 3.42 kWh reported',
    metadata: {
      meter_id: 'meter-8821',
      voltage: 230.1,
      protocol: 'MQTT_v5',
      qos: 1
    }
  },
  {
    name: '🎬 Streaming: CDN Miss Spike',
    level: 'WARNING',
    domain: 'streaming',
    source: 'hls-segmenter',
    message: 'Adaptive bitrate throttling: Client switched to 720p due to buffer underflow',
    metadata: {
      stream_id: 'live-4912',
      resolution: '720p',
      bitrate_kbps: 2400,
      dropped_frames: 12
    }
  }
];

export default function TestLogModal({ onClose, onSuccess }) {
  const [level, setLevel] = useState('ERROR');
  const [domain, setDomain] = useState('fintech');
  const [source, setSource] = useState('payment-service');
  const [message, setMessage] = useState('Payment gateway rejected transaction: Connection timeout to Stripe API host');
  const [metadataJson, setMetadataJson] = useState('{\n  "gateway": "stripe",\n  "timeout_ms": 5000,\n  "order_id": "ord-8831"\n}');
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
    setDomain(preset.domain || 'general');
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
        domain: domain.trim(),
        source: source.trim(),
        message: message.trim(),
        metadata: parsedMeta
      };

      const res = await ingestTestLog(payload);
      setStatusMsg({
        type: 'success',
        text: `Log ingested! [${res.log?.domain || domain}] ID: ${res.id.substring(0, 16)}... -> Partition: ${res.partition}`
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
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '620px' }}>
        <div className="modal-header">
          <div className="modal-header-title">
            <span className="modal-tag">Multi-Domain Ingestion Console</span>
            <h3>Inject Structured Enterprise Log</h3>
          </div>
          <button type="button" className="btn-modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* Quick Multi-Domain Presets row */}
            <div>
              <span className="meta-label" style={{ marginBottom: '8px', display: 'block' }}>
                Multi-Domain Presets:
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
                <label className="input-label">Enterprise Domain:</label>
                <select
                  className="select-control"
                  style={{ width: '100%' }}
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                >
                  <option value="fintech">💳 FinTech &amp; Payments</option>
                  <option value="healthcare">🏥 Healthcare &amp; MedTech</option>
                  <option value="ecommerce">🛒 E-Commerce &amp; Retail</option>
                  <option value="cybersecurity">🛡️ Cybersecurity &amp; SecOps</option>
                  <option value="devops">⚙️ DevOps &amp; Cloud Infra</option>
                  <option value="iot">📡 IoT &amp; Edge Telemetry</option>
                  <option value="streaming">🎬 Streaming &amp; Media</option>
                  <option value="general">🌐 General Microservice</option>
                </select>
              </div>

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
            </div>

            <div>
              <label className="input-label">
                Originating Source Service:
                {predictedPartition && (
                  <span className="predicted-tag">➔ Routes to {predictedPartition}</span>
                )}
              </label>
              <input
                type="text"
                className="text-input"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="e.g. payment-service, ehr-service, auth-service, db-replica-01"
                required
              />
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
