import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import '../styles/Devices.css';

interface RetentionPolicy {
  id: number;
  name: string;
  description: string;
  keep_last_n: number;
  keep_daily: number;
  keep_weekly: number;
  keep_monthly: number;
  is_active: boolean;
  auto_delete: boolean;
  created_at: string;
  updated_at: string;
  devices: number[];
}

interface Device {
  id: number;
  name: string;
}

const BackupRetentionPoliciesComponent: React.FC = () => {
  const { t } = useTranslation();
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<RetentionPolicy | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    keep_last_n: 10,
    keep_daily: 7,
    keep_weekly: 4,
    keep_monthly: 12,
    is_active: true,
    auto_delete: false,
    devices: [] as number[]
  });

  useEffect(() => {
    loadPolicies();
    loadDevices();
  }, []);

  const loadPolicies = async () => {
    try {
      setLoading(true);
      const data = await apiService.retentionPolicies.list();
      setPolicies(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      logger.error('Error loading retention policies:', error);
      alert(t('common.error') + ': ' + t('retention.failed_load'));
    } finally {
      setLoading(false);
    }
  };

  const loadDevices = async () => {
    try {
      const data = await apiService.devices.list();
      const devicesList = Array.isArray(data) ? data : data.results || [];
      setDevices(devicesList);
    } catch (error) {
      logger.error('Error loading devices:', error);
    }
  };

  const handleCreate = () => {
    setEditingPolicy(null);
    setFormData({
      name: '',
      description: '',
      keep_last_n: 10,
      keep_daily: 7,
      keep_weekly: 4,
      keep_monthly: 12,
      is_active: true,
      auto_delete: false,
      devices: []
    });
    setShowModal(true);
  };

  const handleEdit = (policy: RetentionPolicy) => {
    setEditingPolicy(policy);
    setFormData({
      name: policy.name,
      description: policy.description,
      keep_last_n: policy.keep_last_n,
      keep_daily: policy.keep_daily,
      keep_weekly: policy.keep_weekly,
      keep_monthly: policy.keep_monthly,
      is_active: policy.is_active,
      auto_delete: policy.auto_delete,
      devices: policy.devices || []
    });
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const policyData = {
        name: formData.name,
        description: formData.description,
        keep_last_n: formData.keep_last_n,
        keep_daily: formData.keep_daily,
        keep_weekly: formData.keep_weekly,
        keep_monthly: formData.keep_monthly,
        is_active: formData.is_active,
        auto_delete: formData.auto_delete,
        devices: formData.devices
      };

      if (editingPolicy) {
        await apiService.retentionPolicies.update(editingPolicy.id, policyData);
        alert(t('common.success') + ': ' + t('retention.policy_updated'));
      } else {
        await apiService.retentionPolicies.create(policyData);
        alert(t('common.success') + ': ' + t('retention.policy_created'));
      }

      setShowModal(false);
      loadPolicies();
    } catch (error: any) {
      logger.error('Error saving retention policy:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.detail || t('retention.failed_save')));
    }
  };

  const handleDelete = async (policy: RetentionPolicy) => {
    if (!window.confirm(`${t('retention.confirm_delete')} "${policy.name}"?`)) {
      return;
    }

    try {
      await apiService.retentionPolicies.delete(policy.id);
      alert(t('common.success') + ': ' + t('retention.policy_deleted'));
      loadPolicies();
    } catch (error) {
      logger.error('Error deleting retention policy:', error);
      alert(t('common.error') + ': ' + t('retention.failed_delete'));
    }
  };

  const handleApplyNow = async (policy: RetentionPolicy) => {
    try {
      await apiService.retentionPolicies.applyNow(policy.id);
      alert(t('common.success') + ': ' + t('retention.policy_applied'));
    } catch (error) {
      logger.error('Error applying retention policy:', error);
      alert(t('common.error') + ': ' + t('retention.failed_apply'));
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div className="schedules-section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2>🗄️ {t('retention.title')}</h2>
        <button onClick={handleCreate} className="btn-primary">
          ➕ {t('retention.create')}
        </button>
      </div>

      {policies.length === 0 ? (
        <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="empty-icon">🗄️</div>
          <h3>{t('retention.no_policies')}</h3>
          <p>{t('retention.create_first')}</p>
        </div>
      ) : (
        <div className="devices-grid">
          {policies.map((policy) => (
            <div key={policy.id} className="device-card">
              <div className="device-header">
                <div>
                  <h3 className="device-name">{policy.name}</h3>
                  {policy.description && (
                    <p className="device-ip" style={{ fontSize: '0.875rem' }}>{policy.description}</p>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span className={`badge ${policy.is_active ? 'badge-success' : 'badge-secondary'}`}>
                    {policy.is_active ? t('retention.is_active') : 'Inactive'}
                  </span>
                  {policy.auto_delete && (
                    <span className="badge badge-warning">
                      {t('retention.auto_delete')}
                    </span>
                  )}
                </div>
              </div>

              <div className="device-body">
                <div className="device-info">
                  <div className="info-row">
                    <span className="info-label">{t('retention.keep_last_n')}:</span>
                    <span className="info-value">{policy.keep_last_n}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('retention.keep_daily')}:</span>
                    <span className="info-value">{policy.keep_daily} {t('common.days') || 'days'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('retention.keep_weekly')}:</span>
                    <span className="info-value">{policy.keep_weekly} {t('common.weeks') || 'weeks'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('retention.keep_monthly')}:</span>
                    <span className="info-value">{policy.keep_monthly} {t('common.months') || 'months'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('retention.devices_assigned')}:</span>
                    <span className="info-value">{policy.devices?.length || 0}</span>
                  </div>
                </div>
              </div>

              <div className="device-footer">
                <button
                  onClick={() => handleEdit(policy)}
                  className="btn-sm btn-primary"
                  title={t('common.edit')}
                >
                  ✏️
                </button>
                <button
                  onClick={() => handleApplyNow(policy)}
                  className="btn-sm btn-info"
                  disabled={!policy.is_active}
                  title={t('retention.apply_now')}
                >
                  ▶️
                </button>
                <button
                  onClick={() => handleDelete(policy)}
                  className="btn-sm btn-danger"
                  title={t('common.delete')}
                >
                  🗑️
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <h2>{editingPolicy ? t('retention.edit') : t('retention.create')}</h2>
              <button onClick={() => setShowModal(false)} className="btn-close">✕</button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label>{t('retention.name')} *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>{t('retention.description')}</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                    rows={2}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>
                      {t('retention.keep_last_n')} *
                      <small style={{ display: 'block', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                        {t('retention.keep_last_n_help')}
                      </small>
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={formData.keep_last_n}
                      onChange={(e) => setFormData({...formData, keep_last_n: parseInt(e.target.value)})}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label>
                      {t('retention.keep_daily')} *
                      <small style={{ display: 'block', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                        {t('retention.keep_daily_help')}
                      </small>
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={formData.keep_daily}
                      onChange={(e) => setFormData({...formData, keep_daily: parseInt(e.target.value)})}
                      required
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>
                      {t('retention.keep_weekly')} *
                      <small style={{ display: 'block', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                        {t('retention.keep_weekly_help')}
                      </small>
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={formData.keep_weekly}
                      onChange={(e) => setFormData({...formData, keep_weekly: parseInt(e.target.value)})}
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label>
                      {t('retention.keep_monthly')} *
                      <small style={{ display: 'block', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                        {t('retention.keep_monthly_help')}
                      </small>
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={formData.keep_monthly}
                      onChange={(e) => setFormData({...formData, keep_monthly: parseInt(e.target.value)})}
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>{t('retention.devices_assigned')}</label>
                  <select
                    multiple
                    value={formData.devices.map(String)}
                    onChange={(e) => {
                      const selected = Array.from(e.target.selectedOptions).map(opt => parseInt(opt.value));
                      setFormData({...formData, devices: selected});
                    }}
                    style={{ minHeight: '150px' }}
                  >
                    {devices.map((device) => (
                      <option key={device.id} value={device.id}>
                        {device.name}
                      </option>
                    ))}
                  </select>
                  <small style={{ color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                    Hold Ctrl/Cmd to select multiple devices
                  </small>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      checked={formData.auto_delete}
                      onChange={(e) => setFormData({...formData, auto_delete: e.target.checked})}
                    />
                    {t('retention.auto_delete')}
                  </label>
                  {formData.auto_delete && (
                    <small style={{ display: 'block', color: 'var(--danger)', marginTop: '0.5rem' }}>
                      ⚠️ {t('retention.auto_delete_warning')}
                    </small>
                  )}
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                    />
                    {t('retention.is_active')}
                  </label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                  {t('common.cancel')}
                </button>
                <button type="submit" className="btn-primary">
                  {editingPolicy ? t('common.edit') : t('common.add')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default BackupRetentionPoliciesComponent;
