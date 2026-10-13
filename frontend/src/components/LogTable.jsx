import React from 'react';

function formatTimestamp(isoString) {
  if (!isoString) return '-';
  try {
    const d = new Date(isoString);
    const datePart = d.toISOString().substring(0, 10);
    const timePart = d.toISOString().substring(11, 19);
    return { datePart, timePart, full: `${datePart} ${timePart} UTC` };
  } catch {
    return { datePart: isoString, timePart: '', full: isoString };
  }
}

function HighlightMessage({ text, query }) {
  if (!query || !query.trim() || !text) {
    return <span>{text}</span>;
  }

  const trimmed = query.trim();
  const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'));

  return (
    <span>
      {parts.map((part, i) =>
        part.toLowerCase() === trimmed.toLowerCase() ? (
          <mark key={i} className="search-highlight">
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </span>
  );
}

export default function LogTable({
  logs,
  total,
  page,
  limit,
  setPage,
  loading,
  error,
  onSelectLog,
  onRetry,
  searchQuery,
  onClearFilters
}) {
  const totalPages = Math.max(1, Math.ceil(total / limit));

  const getLevelClass = (lvl) => {
    switch (lvl?.toUpperCase()) {
      case 'ERROR':
      case 'CRITICAL':
        return 'error';
      case 'WARN':
      case 'WARNING':
        return 'warning';
      case 'INFO':
        return 'info';
      case 'DEBUG':
        return 'debug';
      default:
        return 'info';
    }
  };

  return (
    <div className="table-card">
      {error ? (
        <div className="state-container error">
          <div className="state-icon-circle danger">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"></polygon>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </div>
          <h3>Aggregator Connection Issue</h3>
          <p className="state-msg">{error}</p>
          <button type="button" className="btn-action btn-primary" onClick={onRetry}>
            ↻ Retry Connection
          </button>
        </div>
      ) : loading && logs.length === 0 ? (
        /* Shimmer loading skeleton rows */
        <div className="table-skeleton-container">
          <div className="skeleton-header" />
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton-row" />
          ))}
        </div>
      ) : logs.length === 0 ? (
        <div className="state-container">
          <div className="state-icon-circle neutral">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="9" y1="15" x2="15" y2="15"></line>
            </svg>
          </div>
          <h3>No matching log documents found</h3>
          <p className="state-msg">
            No events match your current keyword, severity, partition, or time filters.
          </p>
          {onClearFilters && (
            <button type="button" className="btn-action btn-secondary" onClick={onClearFilters}>
              Reset Filters
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="table-responsive">
            <table className="log-table">
              <thead>
                <tr>
                  <th style={{ width: '175px' }}>Timestamp (UTC)</th>
                  <th style={{ width: '100px' }}>Level</th>
                  <th style={{ width: '140px' }}>Source Service</th>
                  <th style={{ width: '130px' }}>Hash Partition</th>
                  <th>Log Message Payload</th>
                  <th style={{ width: '90px', textAlign: 'center' }}>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const ts = formatTimestamp(log.timestamp);
                  const lvlClass = getLevelClass(log.level);

                  return (
                    <tr
                      key={log.id}
                      onClick={() => onSelectLog(log)}
                      className={`log-row row-level-${lvlClass}`}
                    >
                      <td className="cell-timestamp">
                        <span className="ts-time">{ts.timePart}</span>
                        <span className="ts-date">{ts.datePart}</span>
                      </td>
                      <td>
                        <span className={`badge-level ${lvlClass}`}>
                          <span className="level-dot" />
                          {log.level}
                        </span>
                      </td>
                      <td>
                        <span className="badge-source" title={`Originating host: ${log.source}`}>
                          {log.source}
                        </span>
                      </td>
                      <td>
                        <span className="badge-partition" title={`Consistent hash node: ${log.partition}`}>
                          <span className="partition-dot" />
                          {log.partition || 'partition-0'}
                        </span>
                      </td>
                      <td>
                        <div className="message-text" title={log.message}>
                          <HighlightMessage text={log.message} query={searchQuery} />
                        </div>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <button
                          type="button"
                          className="btn-inspect-row"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectLog(log);
                          }}
                          title="Open structured document inspection modal"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination bar */}
          <div className="pagination-bar">
            <div className="pagination-records-info">
              Showing <strong>{(page - 1) * limit + 1}</strong>–<strong>{Math.min(page * limit, total)}</strong> of <strong>{total.toLocaleString()}</strong> events
            </div>

            <div className="pagination-controls">
              <button
                type="button"
                className="btn-page"
                disabled={page <= 1}
                onClick={() => setPage(1)}
                title="First page"
              >
                ⇤ First
              </button>
              <button
                type="button"
                className="btn-page"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                ◀ Prev
              </button>

              <span className="page-indicator">
                Page <strong>{page}</strong> of <strong>{totalPages}</strong>
              </span>

              <button
                type="button"
                className="btn-page"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next ▶
              </button>
              <button
                type="button"
                className="btn-page"
                disabled={page >= totalPages}
                onClick={() => setPage(totalPages)}
                title="Last page"
              >
                Last ⇥
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
