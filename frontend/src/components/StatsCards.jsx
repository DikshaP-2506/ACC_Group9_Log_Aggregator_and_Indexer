import React from 'react';

export default function StatsCards({
  stats,
  totalFallback,
  errorCountFallback,
  warningCountFallback,
  activePartitionsCount,
  totalPartitionsCount
}) {
  const total = stats?.total ?? totalFallback ?? 0;
  const errors = stats?.error_count ?? errorCountFallback ?? 0;
  const warnings = stats?.warning_count ?? warningCountFallback ?? 0;
  const infoCount = stats?.info_count ?? Math.max(0, total - errors - warnings);
  const activePartitions = activePartitionsCount ?? 3;
  const totalPartitions = totalPartitionsCount ?? 3;

  const errorRate = total > 0 ? ((errors / total) * 100).toFixed(1) : '0.0';
  const warningRate = total > 0 ? ((warnings / total) * 100).toFixed(1) : '0.0';

  return (
    <div className="stats-grid">
      {/* 1. Total Indexed Logs */}
      <div className="stat-card total">
        <div className="stat-card-glow" />
        <div className="stat-header">
          <span className="stat-label">Total Indexed Logs</span>
          <span className="stat-icon-badge cyan">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
          </span>
        </div>
        <div className="stat-main-number">
          <h2>{total.toLocaleString()}</h2>
        </div>
        <div className="stat-sub-info">
          <span className="sub-badge cyan">{infoCount.toLocaleString()} Info</span>
          <span className="sub-caption">Persisted in Elasticsearch index</span>
        </div>
      </div>

      {/* 2. Critical Errors */}
      <div className="stat-card errors">
        <div className="stat-card-glow" />
        <div className="stat-header">
          <span className="stat-label">Critical Failures</span>
          <span className="stat-icon-badge danger">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </span>
        </div>
        <div className="stat-main-number">
          <h2>{errors.toLocaleString()}</h2>
        </div>
        <div className="stat-sub-info">
          <span className={`sub-badge danger ${errors > 0 ? 'pulse' : ''}`}>{errorRate}% rate</span>
          <span className="sub-caption">{errors > 0 ? 'Action required in pipelines' : 'No critical errors'}</span>
        </div>
      </div>

      {/* 3. Warnings */}
      <div className="stat-card warnings">
        <div className="stat-card-glow" />
        <div className="stat-header">
          <span className="stat-label">Warnings &amp; Alerts</span>
          <span className="stat-icon-badge warning">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
          </span>
        </div>
        <div className="stat-main-number">
          <h2>{warnings.toLocaleString()}</h2>
        </div>
        <div className="stat-sub-info">
          <span className="sub-badge warning">{warningRate}% volume</span>
          <span className="sub-caption">Operational warnings logged</span>
        </div>
      </div>

      {/* 4. Active Partitions */}
      <div className="stat-card partitions">
        <div className="stat-card-glow" />
        <div className="stat-header">
          <span className="stat-label">Hash Ring Partitions</span>
          <span className="stat-icon-badge purple">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="2" y1="12" x2="22" y2="12"></line>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
            </svg>
          </span>
        </div>
        <div className="stat-main-number">
          <h2>
            {activePartitions}
            <span className="number-sub-denom">/{totalPartitions}</span>
          </h2>
        </div>
        <div className="stat-sub-info">
          <span className={`sub-badge ${activePartitions === totalPartitions ? 'purple' : 'danger'}`}>
            {activePartitions === totalPartitions ? 'All Active' : 'Failover Mode'}
          </span>
          <span className="sub-caption">Deterministic SHA-256 router</span>
        </div>
      </div>
    </div>
  );
}
