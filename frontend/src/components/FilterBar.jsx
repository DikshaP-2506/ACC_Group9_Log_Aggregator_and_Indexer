import React from 'react';

export default function FilterBar({
  query,
  setQuery,
  level,
  setLevel,
  source,
  setSource,
  partition,
  setPartition,
  timeRange,
  setTimeRange,
  limit,
  setLimit,
  availableSources,
  availablePartitions,
  onReset,
  totalResults
}) {
  const activeFiltersCount = [
    query.trim(),
    level,
    source,
    partition,
    timeRange !== 'all' ? timeRange : ''
  ].filter(Boolean).length;

  return (
    <div className="filter-card">
      <div className="filter-top-row">
        {/* Search input with live clear button */}
        <div className="search-input-wrapper">
          <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            className="search-input"
            placeholder="Search keywords across inverted index (e.g. timeout, order, error, failed)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button
              type="button"
              className="btn-clear-search"
              onClick={() => setQuery('')}
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>

        {/* Severity filter */}
        <div className="select-wrapper">
          <label className="select-label">Severity</label>
          <select
            className={`select-control ${level ? 'has-value' : ''}`}
            value={level}
            onChange={(e) => setLevel(e.target.value)}
          >
            <option value="">All Severities</option>
            <option value="ERROR">● ERROR</option>
            <option value="WARNING">● WARNING</option>
            <option value="INFO">● INFO</option>
            <option value="DEBUG">● DEBUG</option>
          </select>
        </div>

        {/* Source filter - 100% dynamic from backend */}
        <div className="select-wrapper">
          <label className="select-label">Source Service</label>
          <select
            className={`select-control ${source ? 'has-value' : ''}`}
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="">All Sources ({availableSources.length})</option>
            {availableSources.map((src) => (
              <option key={src} value={src}>{src}</option>
            ))}
          </select>
        </div>

        {/* Partition filter - 100% dynamic */}
        <div className="select-wrapper">
          <label className="select-label">Hash Partition</label>
          <select
            className={`select-control ${partition ? 'has-value' : ''}`}
            value={partition}
            onChange={(e) => setPartition(e.target.value)}
          >
            <option value="">All Partitions ({availablePartitions.length})</option>
            {availablePartitions.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        {/* Limit selector */}
        <div className="select-wrapper" style={{ minWidth: '95px' }}>
          <label className="select-label">Page Size</label>
          <select
            className="select-control"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            <option value={10}>10 / page</option>
            <option value={25}>25 / page</option>
            <option value={50}>50 / page</option>
            <option value={100}>100 / page</option>
          </select>
        </div>
      </div>

      <div className="filter-bottom-row">
        {/* Time range toggle group */}
        <div className="filter-bottom-left">
          <span className="filter-meta-label">Time Window:</span>
          <div className="btn-time-group">
            <button
              type="button"
              className={`btn-time ${timeRange === 'all' ? 'active' : ''}`}
              onClick={() => setTimeRange('all')}
            >
              All Time
            </button>
            <button
              type="button"
              className={`btn-time ${timeRange === '15m' ? 'active' : ''}`}
              onClick={() => setTimeRange('15m')}
            >
              Last 15m
            </button>
            <button
              type="button"
              className={`btn-time ${timeRange === '1h' ? 'active' : ''}`}
              onClick={() => setTimeRange('1h')}
            >
              Last 1h
            </button>
            <button
              type="button"
              className={`btn-time ${timeRange === '24h' ? 'active' : ''}`}
              onClick={() => setTimeRange('24h')}
            >
              Last 24h
            </button>
          </div>

          {activeFiltersCount > 0 && (
            <span className="badge-active-filters">
              {activeFiltersCount} filter{activeFiltersCount > 1 ? 's' : ''} applied
            </span>
          )}
        </div>

        <div className="filter-bottom-right">
          <span className="results-counter">
            Matches: <strong>{totalResults.toLocaleString()}</strong> records
          </span>

          {activeFiltersCount > 0 && (
            <button
              type="button"
              className="btn-reset-filters"
              onClick={onReset}
              title="Reset all active search and filter constraints"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
              <span>Reset All</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
