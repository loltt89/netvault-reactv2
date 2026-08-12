import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { useToast } from '../../contexts/ToastContext';

export interface RedisSettingsData {
  url: string;
}

interface RedisSettingsTabProps {
  initial: RedisSettingsData;
  onSaved: () => void;
}

const RedisSettingsTab: React.FC<RedisSettingsTabProps> = ({ initial, onSaved }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [redisSettings, setRedisSettings] = useState(initial);

  useEffect(() => {
    setRedisSettings(initial);
  }, [initial]);

  const handleSaveRedis = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ redis: redisSettings });
      toast.success(t('systemSettings.redis.saved'));
      onSaved();
    } catch (error) {
      logger.error('Error saving Redis settings:', error);
      toast.error(t('systemSettings.redis.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-tab-content">
      <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>
          <strong>{t('systemSettings.redis.title')}</strong><br />
          {t('systemSettings.redis.description')}
        </p>
      </div>

      <div className="form-group">
        <label>{t('systemSettings.redis.url')} *</label>
        <input
          type="text"
          value={redisSettings.url}
          onChange={(e) => setRedisSettings({ ...redisSettings, url: e.target.value })}
          placeholder="redis://localhost:6379/0"
        />
        <small style={{ color: 'var(--text-secondary)' }}>
          {t('systemSettings.redis.url_help')}
        </small>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <button onClick={handleSaveRedis} className="btn-primary" disabled={saving}>
          {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
        </button>
      </div>
    </div>
  );
};

export default RedisSettingsTab;
