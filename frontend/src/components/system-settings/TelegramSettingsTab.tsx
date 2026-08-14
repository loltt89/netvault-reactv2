import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { extractErrorMessage } from '../../utils/extractErrorMessage';
import { useToast } from '../../contexts/ToastContext';

export interface TelegramSettingsData {
  enabled: boolean;
  bot_token: string;
  chat_id: string;
}

interface TelegramSettingsTabProps {
  initial: TelegramSettingsData;
  onSaved: () => void;
}

const TelegramSettingsTab: React.FC<TelegramSettingsTabProps> = ({ initial, onSaved }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [telegramSettings, setTelegramSettings] = useState(initial);

  useEffect(() => {
    setTelegramSettings(initial);
  }, [initial]);

  const handleSaveTelegram = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ telegram: telegramSettings });
      toast.success(t('systemSettings.telegram.saved'));
      onSaved();
    } catch (error) {
      logger.error('Error saving telegram settings:', error);
      toast.error(t('systemSettings.telegram.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleTestTelegram = async () => {
    try {
      const result = await apiService.systemSettings.testTelegram(
        telegramSettings.bot_token,
        telegramSettings.chat_id
      );
      toast.success(result.message);
    } catch (error) {
      toast.error(extractErrorMessage(error, t('systemSettings.telegram.failed_test')));
    }
  };

  return (
    <div className="settings-tab-content">
      <div className="form-group">
        <div className="checkbox-group">
          <input
            type="checkbox"
            id="telegram_enabled"
            checked={telegramSettings.enabled}
            onChange={(e) => setTelegramSettings({ ...telegramSettings, enabled: e.target.checked })}
          />
          <label htmlFor="telegram_enabled" style={{ fontWeight: 600, fontSize: '1rem' }}>
            {t('systemSettings.telegram.enable')}
          </label>
        </div>
      </div>

      <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>
          <strong>{t('systemSettings.telegram.how_to_bot')}</strong><br />
          {t('systemSettings.telegram.step1')}<br />
          {t('systemSettings.telegram.step2')}<br />
          {t('systemSettings.telegram.step3')}<br />
          <br />
          <strong>{t('systemSettings.telegram.how_to_chat')}</strong><br />
          {t('systemSettings.telegram.step4')}<br />
          {t('systemSettings.telegram.step5')}<br />
          {t('systemSettings.telegram.step6')}
        </p>
      </div>

      <div className="form-group">
        <label>{t('systemSettings.telegram.bot_token')} *</label>
        <input
          type="text"
          value={telegramSettings.bot_token}
          onChange={(e) => setTelegramSettings({ ...telegramSettings, bot_token: e.target.value })}
          placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
          disabled={!telegramSettings.enabled}
        />
      </div>

      <div className="form-group">
        <label>{t('systemSettings.telegram.chat_id')} *</label>
        <input
          type="text"
          value={telegramSettings.chat_id}
          onChange={(e) => setTelegramSettings({ ...telegramSettings, chat_id: e.target.value })}
          placeholder="-1001234567890"
          disabled={!telegramSettings.enabled}
        />
      </div>

      <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
        <button onClick={handleSaveTelegram} className="btn-primary" disabled={saving}>
          {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
        </button>
        <button onClick={handleTestTelegram} className="btn-secondary" disabled={!telegramSettings.enabled}>
          {t('systemSettings.telegram.test_telegram')}
        </button>
      </div>
    </div>
  );
};

export default TelegramSettingsTab;
