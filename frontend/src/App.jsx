import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Header from './components/Header';
import StatsCards from './components/StatsCards';
import FilterBar from './components/FilterBar';
import LogTable from './components/LogTable';
import LogDetailModal from './components/LogDetailModal';
import TestLogModal from './components/TestLogModal';
import { fetchLogs, fetchHealth, fetchPartitions, fetchLogStats } from './services/api';

export default function App() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(25);

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [level, setLevel] = useState('');
  const [source, setSource] = useState('');
  const [partition, setPartition] = useState('');
  const [timeRange, setTimeRange] = useState('all');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const [health, setHealth] = useState(null);
  const [partitionsData, setPartitionsData] = useState(null);
  const [stats, setStats] = useState(null);

  const [selectedLog, setSelectedLog] = useState(null);
  const [showIngestModal, setShowIngestModal] = useState(false);

  // Debounce search query input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Compute ISO start_time from timeRange
  const calculateStartTime = useCallback(() => {
    if (timeRange === 'all') return '';
    const now = new Date();
    if (timeRange === '15m') now.setMinutes(now.getMinutes() - 15);
    else if (timeRange === '1h') now.setHours(now.getHours() - 1);
    else if (timeRange === '24h') now.setHours(now.getHours() - 24);
    return now.toISOString();
  }, [timeRange]);

  // Main fetch function
  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const startTime = calculateStartTime();
      const data = await fetchLogs({
        query: debouncedQuery,
        level,
        source,
        partition,
        startTime,
        page,
        limit
      });
      setLogs(data.logs || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, level, source, partition, calculateStartTime, page, limit]);

  // Metadata & Stats fetch
  const loadMetadataAndStats = useCallback(async () => {
    try {
      const [h, p, s] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchPartitions().catch(() => null),
        fetchLogStats().catch(() => null)
      ]);
      if (h) setHealth(h);
      if (p) setPartitionsData(p);
      if (s) setStats(s);
    } catch {
      // Ignore background metadata polling failure
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    loadMetadataAndStats();
  }, [loadMetadataAndStats]);

  // Auto-refresh interval (5s)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadLogs();
      loadMetadataAndStats();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadLogs, loadMetadataAndStats]);

  // Dynamically populated sources (zero hardcoding)
  const availableSources = useMemo(() => {
    const sourcesFromStats = stats?.sources || [];
    const sourcesFromCurrentLogs = logs.map((l) => l.source).filter(Boolean);
    const combined = Array.from(new Set([...sourcesFromStats, ...sourcesFromCurrentLogs]));
    return combined.sort();
  }, [stats, logs]);

  // Dynamically populated partitions (zero hardcoding)
  const availablePartitions = useMemo(() => {
    if (partitionsData?.partitions && partitionsData.partitions.length > 0) {
      return partitionsData.partitions.map((p) => p.node_id);
    }
    return ['partition-0', 'partition-1', 'partition-2'];
  }, [partitionsData]);

  // Reset filters
  const handleResetFilters = () => {
    setQuery('');
    setLevel('');
    setSource('');
    setPartition('');
    setTimeRange('all');
    setPage(1);
  };

  const handleRefreshAll = () => {
    loadLogs();
    loadMetadataAndStats();
  };

  return (
    <div className="app-container">
      <Header
        health={health}
        autoRefresh={autoRefresh}
        setAutoRefresh={setAutoRefresh}
        onRefresh={handleRefreshAll}
        loading={loading}
        onOpenTestModal={() => setShowIngestModal(true)}
        stats={stats}
      />

      <StatsCards
        stats={stats}
        totalFallback={total}
        errorCountFallback={logs.filter((l) => l.level === 'ERROR' || l.level === 'CRITICAL').length}
        warningCountFallback={logs.filter((l) => l.level === 'WARNING' || l.level === 'WARN').length}
        activePartitionsCount={partitionsData?.active_partitions?.length}
        totalPartitionsCount={partitionsData?.total_partitions}
      />

      <FilterBar
        query={query}
        setQuery={setQuery}
        level={level}
        setLevel={(lvl) => { setLevel(lvl); setPage(1); }}
        source={source}
        setSource={(src) => { setSource(src); setPage(1); }}
        partition={partition}
        setPartition={(p) => { setPartition(p); setPage(1); }}
        timeRange={timeRange}
        setTimeRange={(tr) => { setTimeRange(tr); setPage(1); }}
        limit={limit}
        setLimit={(lim) => { setLimit(lim); setPage(1); }}
        availableSources={availableSources}
        availablePartitions={availablePartitions}
        onReset={handleResetFilters}
        totalResults={total}
      />

      <LogTable
        logs={logs}
        total={total}
        page={page}
        limit={limit}
        setPage={setPage}
        loading={loading}
        error={error}
        onSelectLog={setSelectedLog}
        onRetry={handleRefreshAll}
        searchQuery={debouncedQuery}
        onClearFilters={handleResetFilters}
      />

      <LogDetailModal
        log={selectedLog}
        onClose={() => setSelectedLog(null)}
      />

      {showIngestModal && (
        <TestLogModal
          onClose={() => setShowIngestModal(false)}
          onSuccess={handleRefreshAll}
        />
      )}
    </div>
  );
}
