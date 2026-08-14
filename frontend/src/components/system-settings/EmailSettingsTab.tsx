import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { extractErrorMessage } from '../../utils/extractErrorMessage';
import { useToast } from '../../contexts/ToastContext';

export interface EmailSettingsData {
  host: string;
  port: number;
  use_tls: boolean;
  host_user: string;
}

interface EmailSettingsTabProps {
  initial: EmailSettingsData;
  onSaved: () => void;
}

const EmailSettingsTab: React.FC<EmailSettingsTabProps> = ({ initial, onSaved }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [emailSettings, setEmailSettings] = useState({ ...initial, host_password: '' });

  // Re-sync local form state whenever the parent refetches (e.g. right
  // after this tab's own successful save) — matches the original
  // single-component behavior where the form reset to server-confirmed
  // values without requiring a tab switch to remount.
  useEffect(() => {
    setEmailSettings({ ...initial, host_password: '' });
  }, [initial]);

  const handleSaveEmail = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ email: emailSettings });
      toast.success(t('systemSettings.email.saved'));
      onSaved();
    } catch (error) {
      logger.error('Error saving email settings:', error);
      toast.error(t('systemSettings.email.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleTestEmail = async () => {
    const testEmail = prompt(t('systemSettings.email.enter_email'));
    if (!testEmail) return;

    try {
      const result = await apiService.systemSettings.testEmail(testEmail);
      toast.success(result.message);
    } catch (error) {
      toast.error(extractErrorMessage(error, t('systemSettings.email.failed_test')));
    }
  };

  return (
    <div className="settings-tab-content">
      <div className="form-group">
        <label>{t('systemSettings.email.smtp_host')} *</label>
        <input
          type="text"
          value={emailSettings.host}
          onChange={(e) => setEmailSettings({ ...emailSettings, host: e.target.value })}
          placeholder="smtp.gmail.com"
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>{t('systemSettings.email.port')} *</label>
          <input
            type="number"
            value={emailSettings.port}
            onChange={(e) => setEmailSettings({ ...emailSettings, port: parseInt(e.target.value) })}
          />
        </div>

        <div className="form-group" style={{ display: 'flex', alignItems: 'center', marginTop: '1.75rem' }}>
          <div className="checkbox-group">
            <input
              type="checkbox"
              id="use_tls"
              checked={emailSettings.use_tls}
              onChange={(e) => setEmailSettings({ ...emailSettings, use_tls: e.target.checked })}
            />
            <label htmlFor="use_tls">{t('systemSettings.email.use_tls')}</label>
          </div>
        </div>
      </div>

      <div className="form-group">
        <label>{t('systemSettings.email.smtp_username')}</label>
        <input
          type="text"
          value={emailSettings.host_user}
          onChange={(e) => setEmailSettings({ ...emailSettings, host_user: e.target.value })}
          placeholder="your-email@gmail.com"
        />
      </div>

      <div className="form-group">
        <label>{t('systemSettings.email.smtp_password')}</label>
        <input
          type="password"
          value={emailSettings.host_password}
          onChange={(e) => setEmailSettings({ ...emailSettings, host_password: e.target.value })}
          placeholder={t('systemSettings.leave_empty')}
        />
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
        <button onClick={handleSaveEmail} className="btn-primary" disabled={saving}>
          {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
        </button>
        <button onClick={handleTestEmail} className="btn-secondary">
          {t('systemSettings.email.test_email')}
        </button>
      </div>
    </div>
  );
};

export default EmailSettingsTab;
