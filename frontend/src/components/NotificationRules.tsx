import React from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import { extractErrorMessage } from '../utils/extractErrorMessage';
import { useToast } from '../contexts/ToastContext';
import { useListResource } from '../hooks/useListResource';
import { useModalForm } from '../hooks/useModalForm';
import DeviceFiltersEditor from './DeviceFiltersEditor';
import { NotificationRule, NotificationTrigger, NotificationChannel, DeviceFilters } from '../types';
import '../styles/Devices.css';

const TRIGGERS: NotificationTrigger[] = [
  'backup_failed', 'backup_success', 'device_offline', 'config_changed', 'critical_change',
];
const CHANNELS: NotificationChannel[] = ['email', 'telegram', 'webhook'];

const DEFAULT_FORM_DATA = {
  name: '',
  description: '',
  trigger: 'backup_failed' as NotificationTrigger,
  channel: 'email' as NotificationChannel,
  is_active: true,
  email_recipients: [] as string[],
  telegram_chat_ids: [] as string[],
  webhook_url: '',
  device_filters: {} as DeviceFilters,
};

const NotificationRules: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();

  const { items: rules, loading, reload } = useListResource<NotificationRule>(
    () => apiService.notificationRules.list(),
    () => toast.error(t('notificationRules.failed_load'))
  );

  const {
    showModal, editing, formData, setFormData, openCreate, openEdit, close,
  } = useModalForm<NotificationRule, typeof DEFAULT_FORM_DATA>(DEFAULT_FORM_DATA, (rule) => ({
    name: rule.name,
    description: rule.description,
    trigger: rule.trigger,
    channel: rule.channel,
    is_active: rule.is_active,
    email_recipients: rule.email_recipients || [],
    telegram_chat_ids: rule.telegram_chat_ids || [],
    webhook_url: rule.webhook_url || '',
    device_filters: rule.device_filters || {},
  }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = { ...formData };
      if (editing) {
        await apiService.notificationRules.update(editing.id, payload);
        toast.success(t('notificationRules.rule_updated'));
      } else {
        await apiService.notificationRules.create(payload);
        toast.success(t('notificationRules.rule_created'));
      }
      close();
      reload();
    } catch (error) {
      logger.error('Error saving notification rule:', error);
      toast.error(extractErrorMessage(error, t('notificationRules.failed_save')));
    }
  };

  const handleDelete = async (rule: NotificationRule) => {
    if (!window.confirm(`${t('notificationRules.confirm_delete')} "${rule.name}"?`)) return;
    try {
      await apiService.notificationRules.delete(rule.id);
      toast.success(t('notificationRules.rule_deleted'));
      reload();
    } catch (error) {
      logger.error('Error deleting notification rule:', error);
      toast.error(t('notificationRules.failed_delete'));
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
        <h2>🔔 {t('notificationRules.title')}</h2>
        <button onClick={openCreate} className="btn-primary">
          ➕ {t('notificationRules.create')}
        </button>
      </div>

      {rules.length === 0 ? (
        <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="empty-icon">🔔</div>
          <h3>{t('notificationRules.no_rules')}</h3>
          <p>{t('notificationRules.create_first')}</p>
        </div>
      ) : (
        <div className="devices-grid">
          {rules.map((rule) => (
            <div key={rule.id} className="device-card">
              <div className="device-header">
                <div>
                  <h3 className="device-name">{rule.name}</h3>
                  {rule.description && (
                    <p className="device-ip" style={{ fontSize: '0.875rem' }}>{rule.description}</p>
                  )}
                </div>
                <span className={`badge ${rule.is_active ? 'badge-success' : 'badge-secondary'}`}>
                  {rule.is_active ? t('notificationRules.is_active') : t('notificationRules.inactive')}
                </span>
              </div>

              <div className="device-body">
                <div className="device-info">
                  <div className="info-row">
                    <span className="info-label">{t('notificationRules.trigger')}:</span>
                    <span className="info-value">{t(`notificationRules.triggers.${rule.trigger}`)}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('notificationRules.channel')}:</span>
                    <span className="info-value">{t(`notificationRules.channels.${rule.channel}`)}</span>
                  </div>
                  {rule.channel === 'webhook' && rule.webhook_url && (
                    <div className="info-row">
                      <span className="info-label">URL:</span>
                      <span className="info-value" style={{ wordBreak: 'break-all' }}>{rule.webhook_url}</span>
                    </div>
                  )}
                  {Object.keys(rule.device_filters || {}).length > 0 && (
                    <div className="info-row">
                      <span className="info-label">{t('notificationRules.scoped')}:</span>
                      <span className="info-value">{JSON.stringify(rule.device_filters)}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="device-footer">
                <button onClick={() => openEdit(rule)} className="btn-sm btn-primary" title={t('common.edit')}>✏️</button>
                <button onClick={() => handleDelete(rule)} className="btn-sm btn-danger" title={t('common.delete')}>🗑️</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => close()}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <h2>{editing ? t('notificationRules.edit') : t('notificationRules.create')}</h2>
              <button onClick={() => close()} className="btn-close">✕</button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label>{t('notificationRules.name')} *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>{t('notificationRules.description')}</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={2}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>{t('notificationRules.trigger')} *</label>
                    <select
                      value={formData.trigger}
                      onChange={(e) => setFormData({ ...formData, trigger: e.target.value as NotificationTrigger })}
                    >
                      {TRIGGERS.map((tr) => (
                        <option key={tr} value={tr}>{t(`notificationRules.triggers.${tr}`)}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>{t('notificationRules.channel')} *</label>
                    <select
                      value={formData.channel}
                      onChange={(e) => setFormData({ ...formData, channel: e.target.value as NotificationChannel })}
                    >
                      {CHANNELS.map((ch) => (
                        <option key={ch} value={ch}>{t(`notificationRules.channels.${ch}`)}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {formData.channel === 'email' && (
                  <div className="form-group">
                    <label>{t('notificationRules.email_recipients')}</label>
                    <input
                      type="text"
                      value={formData.email_recipients.join(', ')}
                      onChange={(e) => setFormData({
                        ...formData,
                        email_recipients: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                      })}
                      placeholder="ops@example.com, noc@example.com"
                    />
                    <small style={{ color: 'var(--text-secondary)' }}>{t('notificationRules.email_recipients_help')}</small>
                  </div>
                )}

                {formData.channel === 'telegram' && (
                  <div className="form-group">
                    <label>{t('notificationRules.telegram_chat_ids')}</label>
                    <input
                      type="text"
                      value={formData.telegram_chat_ids.join(', ')}
                      onChange={(e) => setFormData({
                        ...formData,
                        telegram_chat_ids: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                      })}
                      placeholder="123456789, -100987654321"
                    />
                    <small style={{ color: 'var(--text-secondary)' }}>{t('notificationRules.telegram_chat_ids_help')}</small>
                  </div>
                )}

                {formData.channel === 'webhook' && (
                  <div className="form-group">
                    <label>{t('notificationRules.webhook_url')} *</label>
                    <input
                      type="url"
                      value={formData.webhook_url}
                      onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
                      placeholder="https://hooks.example.com/..."
                      required
                    />
                  </div>
                )}

                <div className="form-group">
                  <label>{t('notificationRules.device_filters')}</label>
                  <DeviceFiltersEditor
                    value={formData.device_filters}
                    onChange={(v) => setFormData({ ...formData, device_filters: v })}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    />
                    {t('notificationRules.is_active')}
                  </label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => close()} className="btn-secondary">
                  {t('common.cancel')}
                </button>
                <button type="submit" className="btn-primary">
                  {editing ? t('common.edit') : t('common.add')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationRules;
