const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Searches logs from the Elasticsearch backend aggregator.
 * @param {Object} filters
 * @returns {Promise<{total: number, page: number, limit: number, logs: Array}>}
 */
export async function fetchLogs({
  query = '',
  level = '',
  source = '',
  partition = '',
  startTime = '',
  endTime = '',
  page = 1,
  limit = 25
} = {}) {
  const params = new URLSearchParams();

  if (query.trim()) params.append('query', query.trim());
  if (level.trim()) params.append('level', level.trim());
  if (source.trim()) params.append('source', source.trim());
  if (partition.trim()) params.append('partition', partition.trim());
  if (startTime) params.append('start_time', startTime);
  if (endTime) params.append('end_time', endTime);
  params.append('page', page);
  params.append('limit', limit);

  const url = `${API_BASE_URL}/logs/search?${params.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.message || errorBody.error || `HTTP error ${response.status}`);
  }

  return response.json();
}

/**
 * Fetches application health and Elasticsearch cluster status.
 */
export async function fetchHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.message || errorBody.error || `Health check failed (${response.status})`);
  }
  return response.json();
}

/**
 * Fetches logical partition routing engine status.
 */
export async function fetchPartitions() {
  const response = await fetch(`${API_BASE_URL}/routing/partitions`);
  if (!response.ok) {
    throw new Error(`Failed to fetch partitions status (${response.status})`);
  }
  return response.json();
}

/**
 * Fetches aggregated log statistics, level distributions, and real dynamic sources.
 */
export async function fetchLogStats() {
  const response = await fetch(`${API_BASE_URL}/logs/stats`);
  if (!response.ok) {
    throw new Error(`Failed to fetch log statistics (${response.status})`);
  }
  return response.json();
}

/**
 * Ingests a new log entry into the aggregator.
 */
export async function ingestTestLog(payload) {
  const response = await fetch(`${API_BASE_URL}/logs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.message || data.error || `Ingestion failed (${response.status})`);
  }
  return data;
}

/**
 * Resolves deterministic routing destination for a given log source key.
 */
export async function resolveRoute(source) {
  const response = await fetch(`${API_BASE_URL}/routing/resolve?source=${encodeURIComponent(source)}`);
  if (!response.ok) {
    throw new Error(`Failed to resolve route (${response.status})`);
  }
  return response.json();
}

/**
 * Toggles a partition active/unavailable to test dynamic failover.
 */
export async function togglePartition(nodeId) {
  const response = await fetch(`${API_BASE_URL}/routing/partitions/${encodeURIComponent(nodeId)}/toggle`, {
    method: 'POST'
  });
  if (!response.ok) {
    throw new Error(`Failed to toggle partition (${response.status})`);
  }
  return response.json();
}

export { API_BASE_URL };

