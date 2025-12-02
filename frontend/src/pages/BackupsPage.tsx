import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import ConfigViewer from '../components/ConfigViewer';
import { getConfigLanguage } from '../utils/configLanguage';
import logger from '../utils/logger';
import '../styles/Backups.css';

interface Backup {
  id: number;
  device: any;
  status: string;
  created_at: string;
  size_bytes: number;
  duration_seconds: number;
  success: boolean;
  has_changes: boolean;
  backup_type: string;
}

interface BackupGroup {
  group: string;
  count: number;
  backups: Backup[];
  total_size: number;
}

type GroupByType = 'date' | 'vendor' | 'device_type';

type DateFilterType = 'all' | 'today' | 'yesterday' | 'last7days' | 'last30days' | 'custom';

const BackupsPage: React.FC = () => {
  const { t } = useTranslation();
  const [groups, setGroups] = useState<BackupGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBackup, setSelectedBackup] = useState<Backup | null>(null);
  const [configContent, setConfigContent] = useState<string>('');
  const [showViewer, setShowViewer] = useState(false);
  const [groupBy, setGroupBy] = useState<GroupByType>('date');
  const [selectedBackups, setSelectedBackups] = useState<Set<number>>(new Set());
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [downloading, setDownloading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Filters
  const [dateFilter, setDateFilter] = useState<DateFilterType>('all');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [vendorFilter, setVendorFilter] = useState<string>('');
  const [deviceTypeFilter, setDeviceTypeFilter] = useState<string>('');
  const [vendors, setVendors] = useState<any[]>([]);
  const [deviceTypes, setDeviceTypes] = useState<any[]>([]);

  useEffect(() => {
    loadVendorsAndTypes();
  }, []);

  useEffect(() => {
    loadBackups();
  }, [groupBy, dateFilter, dateFrom, dateTo, vendorFilter, deviceTypeFilter]);

  const loadVendorsAndTypes = async () => {
    try {
      const [vendorsData, typesData] = await Promise.all([
        apiService.vendors.list(),
        apiService.deviceTypes.list()
      ]);
      setVendors(vendorsData);
      setDeviceTypes(typesData);
    } catch (error) {
      logger.error('Error loading vendors and types:', error);
    }
  };

  const getDateRange = (filter: DateFilterType): { date_from?: string; date_to?: string } => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    switch (filter) {
      case 'today':
        return { date_from: today.toISOString() };
      case 'yesterday':
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const dayBeforeYesterday = new Date(yesterday);
        dayBeforeYesterday.setDate(dayBeforeYesterday.getDate() - 1);
        return {
          date_from: dayBeforeYesterday.toISOString(),
          date_to: yesterday.toISOString()
        };
      case 'last7days':
        const last7 = new Date(today);
        last7.setDate(last7.getDate() - 7);
        return { date_from: last7.toISOString() };
      case 'last30days':
        const last30 = new Date(today);
        last30.setDate(last30.getDate() - 30);
        return { date_from: last30.toISOString() };
      case 'custom':
        return {
          date_from: dateFrom ? new Date(dateFrom).toISOString() : undefined,
          date_to: dateTo ? new Date(dateTo).toISOString() : undefined
        };
      default:
        return {};
    }
  };

  const loadBackups = async () => {
    try {
      setLoading(true);
      const dateRange = getDateRange(dateFilter);
      const params: any = {
        ...dateRange,
      };

      if (vendorFilter) {
        params.vendor = vendorFilter;
      }
      if (deviceTypeFilter) {
        params.device_type = deviceTypeFilter;
      }

      const response = await apiService.backups.getGrouped(groupBy, params);
      setGroups(response.groups || []);
      // Expand first group by default
      if (response.groups && response.groups.length > 0) {
        setExpandedGroups(new Set([response.groups[0].group]));
      }
    } catch (error) {
      logger.error('Error loading backups:', error);
      setGroups([]);
    } finally {
      setLoading(false);
    }
  };

  const clearFilters = () => {
    setDateFilter('all');
    setDateFrom('');
    setDateTo('');
    setVendorFilter('');
    setDeviceTypeFilter('');
  };

  const hasActiveFilters = () => {
    return dateFilter !== 'all' || vendorFilter !== '' || deviceTypeFilter !== '';
  };

  const viewConfig = async (backup: Backup) => {
    try {
      const response = await apiService.backups.getConfiguration(backup.id);
      setConfigContent(response.configuration);
      setSelectedBackup(backup);
      setShowViewer(true);
    } catch (error) {
      logger.error('Error loading configuration:', error);
      alert(t('backups.failed_load_config'));
    }
  };

  const downloadConfig = async (backup: Backup) => {
    try {
      const blob = await apiService.backups.download(backup.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${backup.device.name}_${backup.created_at}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      logger.error('Error downloading configuration:', error);
      alert(t('backups.failed_download'));
    }
  };

  const downloadSelectedBackups = async () => {
    try {
      setDownloading(true);
      const backupIds = Array.from(selectedBackups);
      const blob = await apiService.backups.downloadMultiple(backupIds);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `backups_${new Date().toISOString().split('T')[0]}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      // No alert - browser will show download progress
    } catch (error) {
      logger.error('Error downloading multiple backups:', error);
      alert(t('backups.failed_download_multiple'));
    } finally {
      setDownloading(false);
    }
  };

  const deleteSelectedBackups = async () => {
    setShowDeleteConfirm(false);

    try {
      setDeleting(true);
      const backupIds = Array.from(selectedBackups);
      let deleted = 0;
      let failed = 0;

      for (const backupId of backupIds) {
        try {
          await apiService.backups.delete(backupId);
          deleted++;
        } catch (error) {
          logger.error(`Error deleting backup ${backupId}:`, error);
          failed++;
        }
      }

      setSelectedBackups(new Set());
      loadBackups();

      if (failed === 0) {
        alert(t('backups.delete_multiple_success', { count: deleted }));
      } else {
        alert(t('backups.delete_multiple_partial', { deleted, failed }));
      }
    } catch (error) {
      logger.error('Error deleting backups:', error);
      alert(t('backups.failed_delete_multiple'));
    } finally {
      setDeleting(false);
    }
  };

  const deleteBackup = async (backup: Backup) => {
    if (!window.confirm(`Delete backup from ${new Date(backup.created_at).toLocaleString()}?`)) {
      return;
    }

    try {
      await apiService.backups.delete(backup.id);
      alert(t('backups.delete_success'));
      loadBackups();
    } catch (error) {
      logger.error('Error deleting backup:', error);
      alert(t('backups.failed_delete'));
    }
  };

  const toggleBackupSelection = (backupId: number) => {
    const newSelected = new Set(selectedBackups);
    if (newSelected.has(backupId)) {
      newSelected.delete(backupId);
    } else {
      newSelected.add(backupId);
    }
    setSelectedBackups(newSelected);
  };

  const toggleGroupSelection = (group: BackupGroup) => {
    const newSelected = new Set(selectedBackups);
    const groupBackupIds = group.backups.map(b => b.id);
    const allSelected = groupBackupIds.every(id => newSelected.has(id));

    if (allSelected) {
      // Deselect all in group
      groupBackupIds.forEach(id => newSelected.delete(id));
    } else {
      // Select all in group
      groupBackupIds.forEach(id => newSelected.add(id));
    }
    setSelectedBackups(newSelected);
  };

  const toggleGroupExpand = (groupName: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupName)) {
      newExpanded.delete(groupName);
    } else {
      newExpanded.add(groupName);
    }
    setExpandedGroups(newExpanded);
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null || seconds === undefined) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}m ${secs}s`;
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'success':
        return 'badge-success';
      case 'failed':
        return 'badge-danger';
      case 'running':
      case 'pending':
        return 'badge-warning';
      default:
        return 'badge-secondary';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'success':
        return t('backups.status_success');
      case 'failed':
        return t('backups.status_failed');
      case 'running':
        return t('backups.status_running');
      case 'pending':
        return t('backups.status_pending');
      default:
        return status;
    }
  };

  const isGroupSelected = (group: BackupGroup) => {
    const groupBackupIds = group.backups.map(b => b.id);
    return groupBackupIds.length > 0 && groupBackupIds.every(id => selectedBackups.has(id));
  };

  const isGroupPartiallySelected = (group: BackupGroup) => {
    const groupBackupIds = group.backups.map(b => b.id);
    const selectedCount = groupBackupIds.filter(id => selectedBackups.has(id)).length;
    return selectedCount > 0 && selectedCount < groupBackupIds.length;
  };

  if (loading) {
    return (
      <div className="backups-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (showViewer && selectedBackup) {
    return (
      <div className="backups-page">
        <div className="page-header">
          <button onClick={() => setShowViewer(false)} className="btn-back">
            ← {t('common.close')}
          </button>
          <h1>{selectedBackup.device.name} - {new Date(selectedBackup.created_at).toLocaleString()}</h1>
        </div>
        <ConfigViewer
          config={configContent}
          language={getConfigLanguage(selectedBackup.device.vendor.slug)}
          title={`${t('backups.view_config')} - ${selectedBackup.device.name}`}
        />
      </div>
    );
  }

  return (
    <div className="backups-page">
      <div className="page-header">
        <h1>{t('backups.title')}</h1>
        <div className="header-actions">
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as GroupByType)}
            className="group-by-select"
          >
            <option value="date">{t('backups.group_by_date')}</option>
            <option value="vendor">{t('backups.group_by_vendor')}</option>
            <option value="device_type">{t('backups.group_by_device_type')}</option>
          </select>

          <button onClick={loadBackups} className="btn-primary">
            🔄 {t('common.refresh')}
          </button>
        </div>
      </div>

      {/* Filters Panel */}
      <div className="filters-panel">
        <div className="filters-row">
          {/* Date Filter */}
          <div className="filter-group">
            <label>{t('backups.filter_date')}:</label>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value as DateFilterType)}
              className="filter-select"
            >
              <option value="all">{t('backups.filter_all_time')}</option>
              <option value="today">{t('backups.filter_today')}</option>
              <option value="yesterday">{t('backups.filter_yesterday')}</option>
              <option value="last7days">{t('backups.filter_last_7_days')}</option>
              <option value="last30days">{t('backups.filter_last_30_days')}</option>
              <option value="custom">{t('backups.filter_custom')}</option>
            </select>
          </div>

          {/* Custom Date Range */}
          {dateFilter === 'custom' && (
            <>
              <div className="filter-group">
                <label>{t('backups.filter_from')}:</label>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="filter-input"
                />
              </div>
              <div className="filter-group">
                <label>{t('backups.filter_to')}:</label>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="filter-input"
                />
              </div>
            </>
          )}

          {/* Vendor Filter */}
          <div className="filter-group">
            <label>{t('backups.filter_vendor')}:</label>
            <select
              value={vendorFilter}
              onChange={(e) => setVendorFilter(e.target.value)}
              className="filter-select"
            >
              <option value="">{t('backups.filter_all_vendors')}</option>
              {vendors.map(vendor => (
                <option key={vendor.id} value={vendor.id}>{vendor.name}</option>
              ))}
            </select>
          </div>

          {/* Device Type Filter */}
          <div className="filter-group">
            <label>{t('backups.filter_device_type')}:</label>
            <select
              value={deviceTypeFilter}
              onChange={(e) => setDeviceTypeFilter(e.target.value)}
              className="filter-select"
            >
              <option value="">{t('backups.filter_all_types')}</option>
              {deviceTypes.map(type => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </select>
          </div>

          {/* Clear Filters */}
          {hasActiveFilters() && (
            <button onClick={clearFilters} className="btn-secondary">
              ✕ {t('backups.clear_filters')}
            </button>
          )}

          {/* Download Selected - Always visible, disabled when nothing selected */}
          <button
            onClick={downloadSelectedBackups}
            className="btn-primary"
            disabled={selectedBackups.size === 0 || downloading || deleting}
            style={{ marginLeft: 'auto' }}
          >
            {downloading ? '⏳' : '📦'} {t('backups.download_selected')} ({selectedBackups.size})
          </button>

          {/* Delete Selected - Always visible, disabled when nothing selected */}
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="btn-danger"
            disabled={selectedBackups.size === 0 || downloading || deleting}
          >
            {deleting ? '⏳' : '🗑️'} {t('backups.delete_selected')} ({selectedBackups.size})
          </button>
        </div>
      </div>

      <div className="backups-grouped">
        {groups.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">💾</div>
            <h3>{t('backups.no_backups')}</h3>
            <p>{t('backups.no_backups_hint')}</p>
          </div>
        ) : (
          groups.map((group) => (
            <div key={group.group} className="backup-group">
              <div className="group-header" onClick={() => toggleGroupExpand(group.group)}>
                <div className="group-title">
                  <input
                    type="checkbox"
                    checked={isGroupSelected(group)}
                    ref={input => {
                      if (input) {
                        input.indeterminate = isGroupPartiallySelected(group);
                      }
                    }}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleGroupSelection(group);
                    }}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <span className="expand-icon">
                    {expandedGroups.has(group.group) ? '▼' : '▶'}
                  </span>
                  <h2>{group.group}</h2>
                  <span className="group-stats">
                    {group.count} {t('backups.backups')} • {formatBytes(group.total_size)}
                  </span>
                </div>
              </div>

              {expandedGroups.has(group.group) && (
                <div className="backups-grid">
                  {group.backups.map((backup) => (
                    <div
                      key={backup.id}
                      className={`backup-card ${selectedBackups.has(backup.id) ? 'selected' : ''}`}
                    >
                      <div className="backup-header">
                        <div>
                          <input
                            type="checkbox"
                            checked={selectedBackups.has(backup.id)}
                            onChange={() => toggleBackupSelection(backup.id)}
                          />
                          <h3>{backup.device?.name || t('devices.unknown_device')}</h3>
                          <p className="backup-date">
                            {new Date(backup.created_at).toLocaleString()}
                          </p>
                        </div>
                        <span className={`badge ${getStatusBadgeClass(backup.status)}`}>
                          {getStatusText(backup.status)}
                        </span>
                      </div>

                      <div className="backup-info">
                        <div className="info-item">
                          <span className="info-label">{t('backups.size')}:</span>
                          <span className="info-value">{formatBytes(backup.size_bytes)}</span>
                        </div>
                        <div className="info-item">
                          <span className="info-label">{t('backups.duration')}:</span>
                          <span className="info-value">{formatDuration(backup.duration_seconds)}</span>
                        </div>
                        <div className="info-item">
                          <span className="info-label">{t('backups.backup_type')}:</span>
                          <span className="info-value">{t(`backups.${backup.backup_type}`)}</span>
                        </div>
                        <div className="info-item">
                          <span className="info-label">{t('backups.has_changes')}:</span>
                          <span className={`info-value ${backup.has_changes ? 'text-warning' : 'text-success'}`}>
                            {backup.has_changes ? t('backups.changes_detected') : t('backups.no_changes')}
                          </span>
                        </div>
                      </div>

                      <div className="backup-actions">
                        <button
                          onClick={() => viewConfig(backup)}
                          className="btn-primary btn-sm"
                          disabled={backup.status !== 'success'}
                        >
                          👁️ {t('backups.view_config')}
                        </button>
                        <button
                          onClick={() => downloadConfig(backup)}
                          className="btn-success btn-sm"
                          disabled={backup.status !== 'success'}
                        >
                          ⬇️ {t('backups.download')}
                        </button>
                        <button
                          onClick={() => deleteBackup(backup)}
                          className="btn-danger btn-sm"
                        >
                          🗑️ {t('common.delete')}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay" onClick={() => setShowDeleteConfirm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div className="modal-header">
              <h2>⚠️ {t('backups.confirm_delete_title')}</h2>
              <button onClick={() => setShowDeleteConfirm(false)} className="btn-close">✕</button>
            </div>

            <div className="modal-body">
              <p>{t('backups.confirm_delete_message', { count: selectedBackups.size })}</p>
              <div style={{
                marginTop: '1rem',
                padding: '1rem',
                backgroundColor: '#fff3cd',
                border: '1px solid #ffc107',
                borderRadius: '4px',
                color: '#856404'
              }}>
                <strong>⚠️ {t('common.warning')}:</strong> {t('backups.delete_warning')}
              </div>
            </div>

            <div className="modal-footer">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="btn-secondary"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={deleteSelectedBackups}
                className="btn-danger"
                disabled={deleting}
              >
                {deleting ? '⏳ ' : '🗑️ '}{t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BackupsPage;
