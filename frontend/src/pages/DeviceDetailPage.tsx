import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import ConfigViewer from '../components/ConfigViewer';
import { getConfigLanguage } from '../utils/configLanguage';
import logger from '../utils/logger';
import '../styles/Devices.css';

interface DeviceDetail {
  id: number;
  name: string;
  ip_address: string;
  description: string;
  vendor: any;
  device_type: any;
  protocol: string;
  port: number;
  username: string;
  location: string;
  criticality: string;
  status: string;
  backup_enabled: boolean;
  last_backup: string | null;
  backup_count: number;
  created_at: string;
}

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
  changes_summary: string;
}

const DeviceDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [device, setDevice] = useState<DeviceDetail | null>(null);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBackup, setSelectedBackup] = useState<Backup | null>(null);
  const [configContent, setConfigContent] = useState<string>('');
  const [showViewer, setShowViewer] = useState(false);
  const [compareMode, setCompareMode] = useState(false);
  const [compareBackup1, setCompareBackup1] = useState<Backup | null>(null);
  const [compareBackup2, setCompareBackup2] = useState<Backup | null>(null);
  const [diffContent, setDiffContent] = useState<string>('');

  // Ref to store interval ID for cleanup
  const pollIntervalRef = React.useRef<NodeJS.Timeout | null>(null);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      if (id) {
        try {
          const [deviceData] = await Promise.all([
            apiService.devices.get(parseInt(id)),
          ]);
          if (isMounted) {
            setDevice(deviceData);
            // Load backups separately
            const response = await apiService.backups.list({ device: id, ordering: '-created_at' });
            const backupsList = Array.isArray(response) ? response : response.results || [];
            if (isMounted) setBackups(backupsList);
          }
        } catch (error) {
          if (isMounted) {
            logger.error('Error loading device:', error);
            alert(t('common.error') + ': Failed to load device');
          }
        } finally {
          if (isMounted) setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      isMounted = false;
    };
  }, [id, t]);

  const loadDeviceBackups = async () => {
    try {
      const response = await apiService.backups.list({
        device: id,
        ordering: '-created_at'
      });
      const backupsList = Array.isArray(response) ? response : response.results || [];
      setBackups(backupsList);
    } catch (error) {
      logger.error('Error loading backups:', error);
    }
  };

  const handleBackupNow = async () => {
    if (!device) return;

    try {
      // Queue backup task - WebSocket in Layout will show real-time progress
      await apiService.devices.backupNow(device.id);

      // Clear any existing poll interval
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }

      // Reload backups every 2 seconds for up to 30 seconds to catch the new backup
      let attempts = 0;
      const maxAttempts = 15;
      pollIntervalRef.current = setInterval(async () => {
        attempts++;
        await loadDeviceBackups();
        if (attempts >= maxAttempts && pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }, 2000);
    } catch (error: any) {
      logger.error('Error initiating backup:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.error || 'Failed to queue backup task'));
    }
  };

  const handleTestConnection = async () => {
    if (!device) return;

    try {
      const result = await apiService.devices.testConnection(device.id);
      if (result.success) {
        alert(`${t('common.success')}: ${result.message}`);
      } else {
        alert(`${t('common.error')}: ${result.message}`);
      }
    } catch (error: any) {
      logger.error('Error testing connection:', error);
      alert(t('common.error') + ': Connection test failed');
    }
  };

  const viewBackupConfig = async (backup: Backup) => {
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

  const downloadBackupConfig = async (backup: Backup) => {
    try {
      const blob = await apiService.backups.download(backup.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${device?.name}_${backup.created_at}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      logger.error('Error downloading configuration:', error);
      alert(t('backups.failed_download'));
    }
  };

  const deleteBackup = async (backup: Backup) => {
    if (!window.confirm(`Delete backup from ${new Date(backup.created_at).toLocaleString()}?`)) {
      return;
    }

    try {
      await apiService.backups.delete(backup.id);
      alert(t('backups.delete_success'));
      loadDeviceBackups();
    } catch (error) {
      logger.error('Error deleting backup:', error);
      alert(t('backups.failed_delete'));
    }
  };

  const handleCompareSelect = (backup: Backup) => {
    if (!compareBackup1) {
      setCompareBackup1(backup);
    } else if (!compareBackup2) {
      setCompareBackup2(backup);
    } else {
      // Reset and start fresh
      setCompareBackup1(backup);
      setCompareBackup2(null);
    }
  };

  const executeCompare = async () => {
    if (!compareBackup1 || !compareBackup2) {
      alert('Please select two backups to compare');
      return;
    }

    try {
      const result = await apiService.backups.compare(compareBackup1.id, compareBackup2.id);
      setDiffContent(result.diff);
      setShowViewer(true);
    } catch (error) {
      logger.error('Error comparing backups:', error);
      alert('Failed to compare backups');
    }
  };

  const cancelCompare = () => {
    setCompareMode(false);
    setCompareBackup1(null);
    setCompareBackup2(null);
    setDiffContent('');
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

  if (!device) {
    return (
      <div className="devices-page">
        <div className="empty-state">
          <h3>{t('devices.device_not_found')}</h3>
          <button onClick={() => navigate('/devices')} className="btn-primary">
            {t('common.close')}
          </button>
        </div>
      </div>
    );
  }

  if (showViewer && (selectedBackup || diffContent)) {
    const handleClose = () => {
      setShowViewer(false);
      setDiffContent('');
      setCompareMode(false);
      setCompareBackup1(null);
      setCompareBackup2(null);
    };

    return (
      <div className="devices-page">
        <div className="page-header">
          <button onClick={handleClose} className="btn-back">
            ← {t('common.close')}
          </button>
          <h1>
            {diffContent ?
              `${device.name} - Comparison` :
              `${device.name} - ${new Date(selectedBackup!.created_at).toLocaleString()}`
            }
          </h1>
        </div>
        <ConfigViewer
          config={diffContent || configContent}
          language={getConfigLanguage(device.vendor.slug)}
          title={diffContent ?
            `Configuration Comparison - ${device.name}` :
            `${t('backups.view_config')} - ${device.name}`
          }
        />
      </div>
    );
  }

  return (
    <div className="devices-page">
      <div className="page-header">
        <button onClick={() => navigate('/devices')} className="btn-back">
          ← {t('devices.back_to_devices')}
        </button>
        <h1>{device.name}</h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button onClick={handleTestConnection} className="btn-secondary">
            🔌 {t('devices.test_connection')}
          </button>
          <button onClick={handleBackupNow} className="btn-primary">
            💾 {t('devices.backup_now')}
          </button>
        </div>
      </div>

      {/* Device Info Card */}
      <div className="device-card" style={{ marginBottom: '2rem' }}>
        <div className="device-header">
          <div>
            <h3 className="device-name">{device.name}</h3>
            <p className="device-ip">{device.ip_address}</p>
          </div>
          <span className={`status-badge status-${device.status}`}>
            {device.status}
          </span>
        </div>

        <div className="device-body">
          <div className="device-info" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', display: 'grid', gap: '1rem' }}>
            <div className="info-row">
              <span className="info-label">{t('devices.vendor')}:</span>
              <span className="info-value">{device.vendor?.name || 'N/A'}</span>
            </div>
            <div className="info-row">
              <span className="info-label">{t('devices.device_type')}:</span>
              <span className="info-value">{device.device_type?.name || 'N/A'}</span>
            </div>
            <div className="info-row">
              <span className="info-label">{t('devices.protocol')}:</span>
              <span className="info-value">{device.protocol?.toUpperCase()}:{device.port}</span>
            </div>
            <div className="info-row">
              <span className="info-label">Criticality:</span>
              <span className={`criticality-badge criticality-${device.criticality}`}>
                {device.criticality}
              </span>
            </div>
            <div className="info-row">
              <span className="info-label">Location:</span>
              <span className="info-value">{device.location || 'N/A'}</span>
            </div>
            <div className="info-row">
              <span className="info-label">{t('devices.last_backup')}:</span>
              <span className="info-value">
                {device.last_backup ? new Date(device.last_backup).toLocaleString() : t('devices.never')}
              </span>
            </div>
          </div>

          {device.description && (
            <p className="device-description" style={{ marginTop: '1rem' }}>{device.description}</p>
          )}
        </div>
      </div>

      {/* Backups History */}
      <div className="page-header" style={{ marginTop: '2rem' }}>
        <h2>{t('backups.title')} ({backups.length})</h2>
        <div style={{ display: 'flex', gap: '1rem' }}>
          {compareMode && (
            <>
              <button onClick={executeCompare} className="btn-success" disabled={!compareBackup1 || !compareBackup2}>
                ⚖️ Compare Selected ({compareBackup1 ? '1' : '0'}/{compareBackup2 ? '2' : compareBackup1 ? '1' : '0'})
              </button>
              <button onClick={cancelCompare} className="btn-secondary">
                ✖ Cancel
              </button>
            </>
          )}
          <button
            onClick={() => setCompareMode(!compareMode)}
            className={compareMode ? "btn-secondary" : "btn-primary"}
          >
            {compareMode ? '👁️ View Mode' : '⚖️ Compare Mode'}
          </button>
          <button onClick={loadDeviceBackups} className="btn-primary">
            🔄 {t('common.refresh')}
          </button>
        </div>
      </div>

      {backups.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">💾</div>
          <h3>{t('backups.no_backups')}</h3>
          <p>{t('backups.no_backups_hint')}</p>
        </div>
      ) : (
        <div className="devices-grid">
          {backups.map((backup) => {
            const isSelected = compareBackup1?.id === backup.id || compareBackup2?.id === backup.id;

            return (
            <div
              key={backup.id}
              className="backup-card device-card"
              style={{
                border: isSelected ? '2px solid var(--primary-color)' : undefined,
                backgroundColor: isSelected ? 'var(--hover-bg)' : undefined
              }}
            >
              <div className="device-header">
                <div>
                  <h3 style={{ fontSize: '1rem', margin: 0 }}>
                    {new Date(backup.created_at).toLocaleString()}
                    {isSelected && <span style={{ marginLeft: '0.5rem', color: 'var(--primary-color)' }}>✓</span>}
                  </h3>
                  <p style={{ fontSize: '0.75rem', margin: '0.25rem 0 0', color: 'var(--text-secondary)' }}>
                    {t(`backups.${backup.backup_type}`)}
                  </p>
                </div>
                <span className={`badge ${getStatusBadgeClass(backup.status)}`}>
                  {getStatusText(backup.status)}
                </span>
              </div>

              <div className="device-body">
                <div className="device-info">
                  <div className="info-row">
                    <span className="info-label">{t('backups.size')}:</span>
                    <span className="info-value">{formatBytes(backup.size_bytes)}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('backups.duration')}:</span>
                    <span className="info-value">{formatDuration(backup.duration_seconds)}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('backups.has_changes')}:</span>
                    <span className={`info-value ${backup.has_changes ? 'text-warning' : 'text-success'}`}>
                      {backup.has_changes ? t('backups.changes_detected') : t('backups.no_changes')}
                    </span>
                  </div>
                </div>
                {backup.changes_summary && (
                  <p style={{ fontSize: '0.875rem', margin: '0.75rem 0 0', color: 'var(--text-secondary)' }}>
                    {backup.changes_summary}
                  </p>
                )}
              </div>

              <div className="device-footer">
                {compareMode ? (
                  <button
                    onClick={() => handleCompareSelect(backup)}
                    className={`btn-sm ${isSelected ? 'btn-success' : 'btn-primary'}`}
                    disabled={backup.status !== 'success'}
                  >
                    {isSelected ? '✓ Selected' : '⚖️ Select for Compare'}
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => viewBackupConfig(backup)}
                      className="btn-sm btn-primary"
                      disabled={backup.status !== 'success'}
                    >
                      👁️ {t('backups.view_config')}
                    </button>
                    <button
                      onClick={() => downloadBackupConfig(backup)}
                      className="btn-sm btn-success"
                      disabled={backup.status !== 'success'}
                    >
                      ⬇️ {t('backups.download')}
                    </button>
                    <button
                      onClick={() => deleteBackup(backup)}
                      className="btn-sm btn-danger"
                    >
                      🗑️ {t('common.delete')}
                    </button>
                  </>
                )}
              </div>
            </div>
          );
          })}
        </div>
      )}
    </div>
  );
};

export default DeviceDetailPage;
