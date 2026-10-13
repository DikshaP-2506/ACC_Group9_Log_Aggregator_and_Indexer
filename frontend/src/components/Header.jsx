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
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
        </div>
        <div className="header-title-group">
          <div className="brand-title-row">
            <h1>LogSphere // Group 9</h1>
            <span className="brand-tag">Enterprise Observability</span>
          </div>
          <p>
            Elasticsearch Inverted Index &bull; Consistent Hash Routing &bull; Resilient Microservice Shippers
          </p>
        </div>
      </div>

      <div className="header-actions">
        {/* Dynamic Cluster Health Badge */}
        <div
          className={`health-badge ${isHealthy ? clusterStatus : 'degraded'}`}
          title={`Elasticsearch Cluster: ${clusterName} (${clusterStatus}). Total documents: ${totalCount}`}
        >
          <span className="pulse-dot" />
          <span className="cluster-label">
            {isHealthy
              ? `ES: ${clusterName} (${clusterStatus})`
              : 'ES: Offline'}
          </span>
          {isHealthy && totalCount > 0 && (
            <span className="doc-count-pill">{totalCount.toLocaleString()} docs</span>
          )}
        </div>

        {/* Dynamic Auto-Refresh Toggle */}
        <button
          type="button"
          className={`btn-action btn-refresh-toggle ${autoRefresh ? 'active' : ''}`}
          onClick={() => setAutoRefresh(!autoRefresh)}
          title="Toggle live log stream auto-polling"
        >
          <span className={`live-beacon ${autoRefresh ? 'pulsing' : ''}`} />
          <span>Stream {autoRefresh ? 'Live (5s)' : 'Paused'}</span>
        </button>

        {/* Ingest Log Button */}
        <button
          type="button"
          className="btn-action btn-primary"
          onClick={onOpenTestModal}
          title="Inject a log event into the aggregator pipeline"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          <span>Ingest Log</span>
        </button>

        {/* Refresh Button */}
        <button
          type="button"
          className="btn-action btn-secondary"
          onClick={onRefresh}
          disabled={loading}
          title="Perform immediate search refresh"
        >
          <span className={`refresh-icon ${loading ? 'spinning' : ''}`}>↻</span>
          <span>Refresh</span>
        </button>
      </div>
    </header>
  );
}
