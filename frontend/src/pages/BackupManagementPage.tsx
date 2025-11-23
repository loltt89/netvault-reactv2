import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import BackupSchedules from '../components/BackupSchedules';
import apiService from '../services/api.service';
import '../styles/Settings.css';

const BackupManagementPage: React.FC = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'schedules' | 'retention'>('schedules');
  const [retentionDays, setRetentionDays] = useState(90);
  const [parallelWorkers, setParallelWorkers] = useState(5);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await apiService.systemSettings.get();

      if (data.backup) {
        setRetentionDays(data.backup.retention_days || 90);
        setParallelWorkers(data.backup.parallel_workers || 5);
      }
    } catch (error) {
      console.error('Error loading backup settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveRetention = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({
        backup: {
          retention_days: retentionDays,
          parallel_workers: parallelWorkers
        }
      });
      alert(t('systemSettings.backup.saved'));
    } catch (error) {
      console.error('Error saving backup settings:', error);
      alert(t('systemSettings.backup.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="page-header">
          <h1>📅 {t('backup_management.title')}</h1>
        </div>
        <div className="loading-container">
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>📅 {t('backup_management.title')}</h1>
        <p className="page-subtitle">{t('backup_management.subtitle')}</p>
      </div>

      <div className="settings-container">
        <div className="settings-tabs">
          <button
            className={`tab-btn ${activeTab === 'schedules' ? 'active' : ''}`}
            onClick={() => setActiveTab('schedules')}
          >
            🕐 {t('backup_management.tabs.schedules')}
          </button>
          <button
            className={`tab-btn ${activeTab === 'retention' ? 'active' : ''}`}
            onClick={() => setActiveTab('retention')}
          >
            🗄️ {t('backup_management.tabs.retention')}
          </button>
        </div>

        {/* Schedules Tab */}
        {activeTab === 'schedules' && (
          <div className="settings-tab-content">
            <BackupSchedules />
          </div>
        )}

        {/* Retention Policy Tab */}
        {activeTab === 'retention' && (
          <div className="settings-tab-content">
            <div className="info-card" style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
              <p style={{ margin: 0, fontSize: '0.9rem' }}>
                <strong>{t('backup_management.retention.description_title')}</strong><br />
                {t('backup_management.retention.description')}
              </p>
            </div>

            <div className="form-group">
              <label>{t('systemSettings.backup.retention_days')}</label>
              <input
                type="number"
                min="1"
                max="3650"
                value={retentionDays}
                onChange={(e) => setRetentionDays(Number(e.target.value))}
              />
              <small style={{ color: 'var(--text-secondary)', marginTop: '0.25rem', display: 'block' }}>
                {t('systemSettings.backup.retention_help')}
              </small>
            </div>

            <div className="form-group">
              <label>{t('systemSettings.backup.parallel_workers')}</label>
              <input
                type="number"
                min="1"
                max="20"
                value={parallelWorkers}
                onChange={(e) => setParallelWorkers(Number(e.target.value))}
              />
              <small style={{ color: 'var(--text-secondary)', marginTop: '0.25rem', display: 'block' }}>
                {t('systemSettings.backup.workers_help')}
              </small>
            </div>

            <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: 'var(--card-bg)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <h3 style={{ marginTop: 0, fontSize: '1rem' }}>{t('backup_management.retention.current_settings')}</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{t('backup_management.retention.retention_days')}:</span>
                  <strong>{retentionDays} {t('backup_management.retention.days')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{t('backup_management.retention.parallel_workers')}:</span>
                  <strong>{parallelWorkers} {t('backup_management.retention.workers')}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '0.5rem', borderTop: '1px solid var(--border-color)' }}>
                  <span>{t('backup_management.retention.estimated_cleanup')}:</span>
                  <strong>{t('backup_management.retention.automatic')}</strong>
                </div>
              </div>
            </div>

            <div style={{ marginTop: '1.5rem' }}>
              <button onClick={handleSaveRetention} className="btn-primary" disabled={saving}>
                {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
              </button>
            </div>

            <div className="info-card" style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#fff3cd', border: '1px solid #ffc107', color: '#856404' }}>
              <p style={{ margin: 0, fontSize: '0.9rem' }}>
                <strong>⚠️ {t('backup_management.retention.warning_title')}</strong><br />
                {t('backup_management.retention.warning_text')}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BackupManagementPage;
