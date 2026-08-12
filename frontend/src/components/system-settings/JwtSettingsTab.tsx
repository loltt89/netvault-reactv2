import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { useToast } from '../../contexts/ToastContext';

export interface JwtSettingsData {
  access_token_lifetime: number;
  refresh_token_lifetime: number;
}

interface JwtSettingsTabProps {
  initial: JwtSettingsData;
  onSaved: () => void;
}

const JwtSettingsTab: React.FC<JwtSettingsTabProps> = ({ initial, onSaved }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [jwtSettings, setJwtSettings] = useState(initial);

  useEffect(() => {
    setJwtSettings(initial);
  }, [initial]);

  const handleSaveJWT = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ jwt: jwtSettings });
      toast.success(t('systemSettings.jwt.saved'));
      onSaved();
    } catch (error) {
      logger.error('Error saving JWT settings:', error);
      toast.error(t('systemSettings.jwt.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-tab-content">
      <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>
          <strong>{t('systemSettings.jwt.title')}</strong><br />
          {t('systemSettings.jwt.description')}
        </p>
      </div>

      <div className="form-group">
        <label>{t('systemSettings.jwt.access_lifetime')} *</label>
        <input
          type="number"
          value={jwtSettings.access_token_lifetime}
          onChange={(e) => setJwtSettings({ ...jwtSettings, access_token_lifetime: parseInt(e.target.value) })}
          min="5"
          max="1440"
        />
        <small style={{ color: 'var(--text-secondary)' }}>
          {t('systemSettings.jwt.access_lifetime_help')}
        </small>
      </div>

      <div className="form-group">
        <label>{t('systemSettings.jwt.refresh_lifetime')} *</label>
        <input
          type="number"
          value={jwtSettings.refresh_token_lifetime}
          onChange={(e) => setJwtSettings({ ...jwtSettings, refresh_token_lifetime: parseInt(e.target.value) })}
          min="60"
          max="43200"
        />
        <small style={{ color: 'var(--text-secondary)' }}>
          {t('systemSettings.jwt.refresh_lifetime_help')}
        </small>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <button onClick={handleSaveJWT} className="btn-primary" disabled={saving}>
          {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
        </button>
      </div>
    </div>
  );
};

export default JwtSettingsTab;
