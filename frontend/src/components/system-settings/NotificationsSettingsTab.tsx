import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { useToast } from '../../contexts/ToastContext';

export interface NotificationSettingsData {
  notify_on_success: boolean;
  notify_on_failure: boolean;
  notify_schedule_summary: boolean;
}

interface NotificationsSettingsTabProps {
  initial: NotificationSettingsData;
  onSaved: () => void;
}

const NotificationsSettingsTab: React.FC<NotificationsSettingsTabProps> = ({ initial, onSaved }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [notificationSettings, setNotificationSettings] = useState(initial);

  useEffect(() => {
    setNotificationSettings(initial);
  }, [initial]);

  const handleSaveNotifications = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ notifications: notificationSettings });
      toast.success(t('systemSettings.notifications.saved'));
      onSaved();
    } catch (error) {
      logger.error('Error saving notification settings:', error);
      toast.error(t('systemSettings.notifications.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-tab-content">
      <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>
          <strong>{t('systemSettings.notifications.title')}</strong><br />
          {t('systemSettings.notifications.description')}
        </p>
      </div>

      <div className="form-group">
        <div className="checkbox-group">
          <input
            type="checkbox"
            id="notify_on_success"
            checked={notificationSettings.notify_on_success}
            onChange={(e) => setNotificationSettings({ ...notificationSettings, notify_on_success: e.target.checked })}
          />
          <label htmlFor="notify_on_success" style={{ fontWeight: 600, fontSize: '1rem' }}>
            {t('systemSettings.notifications.notify_on_success')}
          </label>
        </div>
        <small style={{ color: 'var(--text-secondary)', marginLeft: '1.75rem', display: 'block', marginTop: '0.25rem' }}>
          {t('systemSettings.notifications.notify_on_success_help')}
        </small>
      </div>

      <div className="form-group">
        <div className="checkbox-group">
          <input
            type="checkbox"
            id="notify_on_failure"
            checked={notificationSettings.notify_on_failure}
            onChange={(e) => setNotificationSettings({ ...notificationSettings, notify_on_failure: e.target.checked })}
          />
          <label htmlFor="notify_on_failure" style={{ fontWeight: 600, fontSize: '1rem' }}>
            {t('systemSettings.notifications.notify_on_failure')}
          </label>
        </div>
        <small style={{ color: 'var(--text-secondary)', marginLeft: '1.75rem', display: 'block', marginTop: '0.25rem' }}>
          {t('systemSettings.notifications.notify_on_failure_help')}
        </small>
      </div>

      <div className="form-group">
        <div className="checkbox-group">
          <input
            type="checkbox"
            id="notify_schedule_summary"
            checked={notificationSettings.notify_schedule_summary}
            onChange={(e) => setNotificationSettings({ ...notificationSettings, notify_schedule_summary: e.target.checked })}
          />
          <label htmlFor="notify_schedule_summary" style={{ fontWeight: 600, fontSize: '1rem' }}>
            {t('systemSettings.notifications.notify_schedule_summary')}
          </label>
        </div>
        <small style={{ color: 'var(--text-secondary)', marginLeft: '1.75rem', display: 'block', marginTop: '0.25rem' }}>
          {t('systemSettings.notifications.notify_schedule_summary_help')}
        </small>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <button onClick={handleSaveNotifications} className="btn-primary" disabled={saving}>
          {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
        </button>
      </div>
    </div>
  );
};

export default NotificationsSettingsTab;
