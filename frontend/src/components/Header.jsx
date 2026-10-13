import React from 'react';

export default function Header({
  health,
  autoRefresh,
  setAutoRefresh,
  onRefresh,
  loading,
  onOpenTestModal,
  stats
}) {
  const isHealthy = health?.status === 'healthy' && health?.elasticsearch?.connected;
  const clusterName = health?.elasticsearch?.cluster_name || 'docker-cluster';
  const clusterStatus = health?.elasticsearch?.cluster_status || (isHealthy ? 'green' : 'degraded');
  const totalCount = stats?.total ?? 0;

  return (
    <header className="header-card">
      <div className="header-brand-block">
        <div className="brand-logo-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
        </div>
        <div className="header-title-group">
          <div className="brand-title-row">
            <h1>Group 9 Log Aggregator</h1>
            <span className="brand-tag">Distributed</span>
          </div>
          <p>
            Real-time telemetry ingestion, consistent-hash routing &amp; inverted-index search
          </p>
        </div>
      </div>

      <div className="header-actions">
        {/* Clean Cluster Health Badge */}
        <div
          className={`health-badge ${isHealthy ? 'online' : 'degraded'}`}
          title={`Elasticsearch: ${clusterName} (${clusterStatus})`}
        >
          <span className="pulse-dot" />
          <span className="cluster-label">
            {isHealthy ? 'Cluster Online' : 'Cluster Offline'}
          </span>
          {isHealthy && (
            <span className="doc-count-pill">
              {totalCount.toLocaleString()} logs
            </span>
          )}
        </div>

        {/* Live Stream Auto-Refresh Toggle */}
        <button
          type="button"
          className={`btn-action btn-refresh-toggle ${autoRefresh ? 'active' : ''}`}
          onClick={() => setAutoRefresh(!autoRefresh)}
          title="Toggle live stream auto-refresh"
        >
          <span className={`live-beacon ${autoRefresh ? 'pulsing' : ''}`} />
          <span>{autoRefresh ? 'Live (5s)' : 'Paused'}</span>
        </button>

        {/* Ingest Log Button */}
        <button
          type="button"
          className="btn-action btn-primary"
          onClick={onOpenTestModal}
          title="Inject a log entry into the aggregator pipeline"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          <span>Ingest Log</span>
        </button>

        {/* Refresh Button */}
        <button
          type="button"
          className="btn-action btn-icon-only"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh logs from Elasticsearch"
          aria-label="Refresh logs"
        >
          <span className={`refresh-icon ${loading ? 'spinning' : ''}`}>↻</span>
        </button>
      </div>
    </header>
  );
}
