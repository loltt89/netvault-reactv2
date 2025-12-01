import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import '../styles/Devices.css';

interface AuditLog {
  id: number;
  user: string;
  action: string;
  resource_type: string;
  resource_id: number | null;
  resource_name: string;
  description: string;
  ip_address: string;
  timestamp: string;
  success: boolean;
  error_message: string;
}

const AuditLogsPage: React.FC = () => {
  const { t } = useTranslation();
  const { user: currentUser } = useAuth();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    action: '',
    resource_type: '',
    user: '',
    success: '',
    search: ''
  });

  // Check if current user can view all logs
  const canViewAll = currentUser?.role === 'administrator' || currentUser?.role === 'auditor';

  const loadLogs = React.useCallback(async (currentFilters = filters) => {
    try {
      setLoading(true);
      const data = await apiService.auditLogs.list(currentFilters);
      // Handle both paginated and non-paginated responses
      setLogs(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      logger.error('Error loading audit logs:', error);
      alert(t('common.error') + ': ' + t('auditLogs.failed_load'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadLogs(filters);
  }, []); // Load only on mount

  const applyFilters = () => {
    loadLogs(filters);
  };

  const clearFilters = () => {
    const emptyFilters = {
      action: '',
      resource_type: '',
      user: '',
      success: '',
      search: ''
    };
    setFilters(emptyFilters);
    // Load with empty filters immediately
    loadLogs(emptyFilters);
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'login': return '🔑';
      case 'logout': return '🚪';
      case 'create': return '➕';
      case 'update': return '✏️';
      case 'delete': return '🗑️';
      case 'backup': return '💾';
      case 'restore': return '♻️';
      case 'download': return '⬇️';
      case 'view': return '👁️';
      default: return '📝';
    }
  };

  const getActionColor = (action: string) => {
    switch (action) {
      case 'create': return 'var(--success-color)';
      case 'delete': return 'var(--danger-color)';
      case 'update': return 'var(--primary-color)';
      case 'login': return 'var(--info-color)';
      default: return 'var(--text-secondary)';
    }
  };

  if (loading) {
    return (
      <div className="devices-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="devices-page">
      <div className="page-header">
        <h1>📋 {t('auditLogs.title')}</h1>
        <button onClick={() => loadLogs()} className="btn-primary">
          🔄 {t('common.refresh')}
        </button>
      </div>

      {/* Filters */}
      <div className="filters-card" style={{ marginBottom: '2rem', padding: '1.5rem', background: 'var(--card-bg)', borderRadius: '8px' }}>
        <div className="filters-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
          <div className="form-group">
            <label>{t('auditLogs.action')}</label>
            <select
              value={filters.action}
              onChange={(e) => setFilters({...filters, action: e.target.value})}
            >
              <option value="">{t('auditLogs.all_actions')}</option>
              <option value="login">{t('auditLogs.actions.login')}</option>
              <option value="logout">{t('auditLogs.actions.logout')}</option>
              <option value="create">{t('auditLogs.actions.create')}</option>
              <option value="update">{t('auditLogs.actions.update')}</option>
              <option value="delete">{t('auditLogs.actions.delete')}</option>
              <option value="backup">{t('auditLogs.actions.backup')}</option>
              <option value="restore">{t('auditLogs.actions.restore')}</option>
              <option value="download">{t('auditLogs.actions.download')}</option>
              <option value="view">{t('auditLogs.actions.view')}</option>
            </select>
          </div>

          <div className="form-group">
            <label>{t('auditLogs.resource_type')}</label>
            <select
              value={filters.resource_type}
              onChange={(e) => setFilters({...filters, resource_type: e.target.value})}
            >
              <option value="">{t('auditLogs.all_types')}</option>
              <option value="Device">{t('devices.title')}</option>
              <option value="Backup">{t('backups.title')}</option>
              <option value="User">{t('users.title')}</option>
              <option value="Vendor">Vendor</option>
            </select>
          </div>

          <div className="form-group">
            <label>{t('auditLogs.status')}</label>
            <select
              value={filters.success}
              onChange={(e) => setFilters({...filters, success: e.target.value})}
            >
              <option value="">{t('common.filter')}</option>
              <option value="true">{t('auditLogs.success')}</option>
              <option value="false">{t('auditLogs.failed')}</option>
            </select>
          </div>

          <div className="form-group">
            <label>{t('auditLogs.search')}</label>
            <input
              type="text"
              placeholder={t('auditLogs.search_placeholder')}
              value={filters.search}
              onChange={(e) => setFilters({...filters, search: e.target.value})}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <button onClick={applyFilters} className="btn-primary">
            {t('auditLogs.apply_filters')}
          </button>
          <button onClick={clearFilters} className="btn-secondary">
            {t('auditLogs.clear_filters')}
          </button>
        </div>
      </div>

      {/* Logs Table */}
      {logs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>{t('auditLogs.no_logs')}</h3>
          <p>{t('auditLogs.no_logs_hint')}</p>
        </div>
      ) : (
        <div className="table-container" style={{ overflowX: 'auto' }}>
          <table className="audit-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--hover-bg)', borderBottom: '2px solid var(--border-color)' }}>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('auditLogs.timestamp')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('auditLogs.user')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('auditLogs.action')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('auditLogs.resource')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('auditLogs.description')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('auditLogs.ip_address')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('auditLogs.status')}</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '1rem', fontSize: '0.875rem' }}>
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <strong>{log.user || t('auditLogs.system')}</strong>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <span style={{ color: getActionColor(log.action) }}>
                      {getActionIcon(log.action)} {log.action}
                    </span>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <div>
                      <div style={{ fontWeight: 500 }}>{log.resource_type}</div>
                      {log.resource_name && (
                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                          {log.resource_name}
                        </div>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: '1rem', fontSize: '0.875rem', maxWidth: '300px' }}>
                    {log.description}
                    {!log.success && log.error_message && (
                      <div style={{ color: 'var(--danger-color)', marginTop: '0.25rem' }}>
                        {t('auditLogs.error_prefix')} {log.error_message}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '1rem', fontSize: '0.875rem', fontFamily: 'monospace' }}>
                    {log.ip_address || '-'}
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <span className={`badge ${log.success ? 'badge-success' : 'badge-danger'}`}>
                      {log.success ? `✓ ${t('auditLogs.success')}` : `✗ ${t('auditLogs.failed')}`}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Info box for non-admin users */}
      {!canViewAll && (
        <div style={{
          marginTop: '2rem',
          padding: '1rem',
          backgroundColor: 'var(--info-bg)',
          borderLeft: '4px solid var(--info-color)',
          borderRadius: '4px'
        }}>
          <strong>ℹ️ {t('auditLogs.note')}</strong> {t('auditLogs.view_own_logs')}
        </div>
      )}
    </div>
  );
};

export default AuditLogsPage;
