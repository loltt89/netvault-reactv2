import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import './TasksTable.css';

interface Device {
  id: number;
  name: string;
  ip_address: string;
  vendor: {
    id: number;
    name: string;
    slug: string;
  } | null;
}

interface Task {
  id: number;
  device: Device;
  status: 'pending' | 'running' | 'success' | 'failed' | 'partial';
  backup_type: 'manual' | 'scheduled' | 'automatic';
  size_bytes: number;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  success: boolean;
  error_message: string;
  has_changes: boolean;
  changes_summary: string;
  triggered_by_email: string | null;
  created_at: string;
}

interface TaskDetail extends Task {
  output_log: string;
  configuration: string | null;
}

interface TasksTableProps {
  onToggle: () => void;
  isMinimized: boolean;
  isConnected: boolean;
}

type StatusFilter = 'all' | 'running' | 'completed' | 'failed';
type SortField = 'started_at' | 'device' | 'status' | 'duration_seconds';
type SortOrder = 'asc' | 'desc';

const TasksTable: React.FC<TasksTableProps> = ({ onToggle, isMinimized, isConnected }) => {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [selectedTask, setSelectedTask] = useState<TaskDetail | null>(null);
  const [sortField, setSortField] = useState<SortField>('started_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const tasksRef = useRef<Task[]>([]);

  const fetchTasks = useCallback(async () => {
    try {
      setLoading(true);

      // Build filter params
      const params: any = {
        page,
        page_size: 50,
        ordering: sortOrder === 'desc' ? `-${sortField}` : sortField,
      };

      // Apply status filter
      if (statusFilter === 'running') {
        params.status = 'running';
      } else if (statusFilter === 'completed') {
        params.status__in = 'success,partial';
      } else if (statusFilter === 'failed') {
        params.status = 'failed';
      }

      const response = await apiService.backups.list(params);
      const newTasks = response.results || response;
      setTasks(newTasks);
      tasksRef.current = newTasks;

      // Handle pagination
      if (response.count) {
        setTotalPages(Math.ceil(response.count / 50));
      }
    } catch (error) {
      logger.error('Failed to fetch tasks:', error);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, sortField, sortOrder]);

  useEffect(() => {
    fetchTasks();

    // Auto-refresh: faster if there are running tasks, slower if all completed
    const interval = setInterval(() => {
      const hasRunningTasks = tasksRef.current.some(t => t.status === 'running' || t.status === 'pending');

      // Always refresh, but with different intervals based on task status
      // This ensures new tasks are picked up even when table is empty/completed
      fetchTasks();
    }, 1000); // Check every 1 second (60 req/min = 3.6% of rate limit)

    return () => clearInterval(interval);
  }, [fetchTasks]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
      case 'pending':
        return '🔄';
      case 'success':
        return '✅';
      case 'failed':
        return '❌';
      case 'partial':
        return '⚠️';
      default:
        return '❓';
    }
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'running':
      case 'pending':
        return 'status-running';
      case 'success':
        return 'status-success';
      case 'failed':
        return 'status-failed';
      case 'partial':
        return 'status-warning';
      default:
        return '';
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const handleRowClick = async (task: Task) => {
    try {
      const response = await apiService.backups.getDetails(task.id);
      setSelectedTask(response);
    } catch (error) {
      logger.error('Failed to fetch task details:', error);
    }
  };

  const getTaskName = (backupType: string) => {
    return t(`tasks.task_types.${backupType}`, { defaultValue: t('tasks.task_types.manual') });
  };

  const getRunningTasks = () => tasks.filter(t => t.status === 'running' || t.status === 'pending').length;
  const getCompletedTasks = () => tasks.filter(t => t.status === 'success' || t.status === 'partial').length;
  const getFailedTasks = () => tasks.filter(t => t.status === 'failed').length;

  return (
    <div className={`tasks-panel ${isMinimized ? 'minimized' : ''}`}>
      <div className="tasks-header" onClick={isMinimized ? onToggle : undefined} style={{ cursor: isMinimized ? 'pointer' : 'default' }}>
        <div className="tasks-title">
          <h2>{t('tasks.title')}</h2>
          <span className={`connection-badge ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? `🟢 ${t('tasks.live')}` : `🔴 ${t('tasks.offline')}`}
          </span>
        </div>
        <button onClick={onToggle} className="tasks-toggle-btn" title={isMinimized ? t('tasks.maximize') : t('tasks.minimize')}>
          {isMinimized ? '▲' : '▼'}
        </button>
      </div>

      {/* Status Filter Tabs */}
      <div className="tasks-filters">
        <button
          className={`filter-tab ${statusFilter === 'all' ? 'active' : ''}`}
          onClick={() => setStatusFilter('all')}
        >
          {t('tasks.all')} ({tasks.length})
        </button>
        <button
          className={`filter-tab ${statusFilter === 'running' ? 'active' : ''}`}
          onClick={() => setStatusFilter('running')}
        >
          {t('tasks.running')} ({getRunningTasks()})
        </button>
        <button
          className={`filter-tab ${statusFilter === 'completed' ? 'active' : ''}`}
          onClick={() => setStatusFilter('completed')}
        >
          {t('tasks.completed')} ({getCompletedTasks()})
        </button>
        <button
          className={`filter-tab ${statusFilter === 'failed' ? 'active' : ''}`}
          onClick={() => setStatusFilter('failed')}
        >
          {t('tasks.failed')} ({getFailedTasks()})
        </button>
        <button onClick={fetchTasks} className="refresh-btn" title={t('tasks.refresh')}>
          🔄 {t('tasks.refresh')}
        </button>
      </div>

      {/* Tasks Table */}
      <div className="tasks-table-container">
        <table className="tasks-table">
          <thead>
            <tr>
              <th className="col-status">{t('tasks.status')}</th>
              <th className="col-task">{t('tasks.task')}</th>
              <th className="col-target" onClick={() => handleSort('device')}>
                {t('tasks.target')} {sortField === 'device' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th className="col-progress">{t('tasks.progress')}</th>
              <th className="col-initiator">{t('tasks.initiator')}</th>
              <th className="col-time" onClick={() => handleSort('started_at')}>
                {t('tasks.start_time')} {sortField === 'started_at' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th className="col-duration" onClick={() => handleSort('duration_seconds')}>
                {t('tasks.duration')} {sortField === 'duration_seconds' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
            </tr>
          </thead>
          <tbody>
            {loading && tasks.length === 0 ? (
              <tr>
                <td colSpan={7} className="loading-row">{t('tasks.loading_tasks')}</td>
              </tr>
            ) : tasks.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-row">{t('tasks.no_tasks')}</td>
              </tr>
            ) : (
              tasks.map(task => (
                <tr
                  key={task.id}
                  className={`task-row ${getStatusClass(task.status)}`}
                  onClick={() => handleRowClick(task)}
                >
                  <td className="col-status">
                    <span className={`status-icon ${getStatusClass(task.status)}`}>
                      {getStatusIcon(task.status)}
                    </span>
                  </td>
                  <td className="col-task">
                    <div className="task-name">{getTaskName(task.backup_type)}</div>
                    {task.has_changes && <span className="changes-badge">{t('tasks.changes_badge')}</span>}
                  </td>
                  <td className="col-target">
                    <div className="target-device">
                      <strong>{task.device.name}</strong>
                      <small>{task.device.ip_address}</small>
                    </div>
                  </td>
                  <td className="col-progress">
                    {task.status === 'running' || task.status === 'pending' ? (
                      <div className="progress-bar">
                        <div className="progress-fill animating"></div>
                      </div>
                    ) : task.status === 'success' || task.status === 'partial' ? (
                      <span className="progress-text">✓ {formatBytes(task.size_bytes)}</span>
                    ) : (
                      <span className="progress-text">-</span>
                    )}
                  </td>
                  <td className="col-initiator">
                    {task.triggered_by_email || <em>{t('tasks.system')}</em>}
                  </td>
                  <td className="col-time">
                    {formatTimestamp(task.started_at)}
                  </td>
                  <td className="col-duration">
                    {task.status === 'running' || task.status === 'pending' ? (
                      <span className="running-duration">{t('tasks.running_status')}</span>
                    ) : (
                      formatDuration(task.duration_seconds)
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="tasks-pagination">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            {t('tasks.previous')}
          </button>
          <span className="page-info">{t('tasks.page_info', { current: page, total: totalPages })}</span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            {t('tasks.next')}
          </button>
        </div>
      )}

      {/* Task Detail Modal */}
      {selectedTask && (
        <div className="task-modal-overlay" onClick={() => setSelectedTask(null)}>
          <div className="task-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{t('tasks.details.title', { name: getTaskName(selectedTask.backup_type) })}</h3>
              <button onClick={() => setSelectedTask(null)}>✕</button>
            </div>
            <div className="modal-content">
              <div className="detail-section">
                <h4>{t('tasks.details.general')}</h4>
                <table className="detail-table">
                  <tbody>
                    <tr>
                      <td>{t('tasks.details.device')}</td>
                      <td><strong>{selectedTask.device.name}</strong> ({selectedTask.device.ip_address})</td>
                    </tr>
                    <tr>
                      <td>{t('tasks.details.status')}</td>
                      <td className={getStatusClass(selectedTask.status)}>
                        {getStatusIcon(selectedTask.status)} {t(`tasks.status_labels.${selectedTask.status}`)}
                      </td>
                    </tr>
                    <tr>
                      <td>{t('tasks.details.type')}</td>
                      <td>{selectedTask.backup_type}</td>
                    </tr>
                    <tr>
                      <td>{t('tasks.details.size')}</td>
                      <td>{formatBytes(selectedTask.size_bytes)}</td>
                    </tr>
                    <tr>
                      <td>{t('tasks.details.changes')}</td>
                      <td>{selectedTask.has_changes ? t('tasks.details.has_changes', { summary: selectedTask.changes_summary }) : t('tasks.details.no_changes')}</td>
                    </tr>
                    <tr>
                      <td>{t('tasks.details.started')}</td>
                      <td>{formatTimestamp(selectedTask.started_at)}</td>
                    </tr>
                    <tr>
                      <td>{t('tasks.details.completed')}</td>
                      <td>{selectedTask.completed_at ? formatTimestamp(selectedTask.completed_at) : '-'}</td>
                    </tr>
                    <tr>
                      <td>{t('tasks.details.duration')}</td>
                      <td>{formatDuration(selectedTask.duration_seconds)}</td>
                    </tr>
                    <tr>
                      <td>{t('tasks.details.initiator')}</td>
                      <td>{selectedTask.triggered_by_email || t('tasks.system')}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {selectedTask.error_message && (
                <div className="detail-section error-section">
                  <h4>{t('tasks.details.error_message')}</h4>
                  <pre className="error-message">{selectedTask.error_message}</pre>
                </div>
              )}

              {selectedTask.output_log && (
                <div className="detail-section">
                  <h4>{t('tasks.details.output_log')}</h4>
                  <pre className="output-log">{selectedTask.output_log}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TasksTable;
