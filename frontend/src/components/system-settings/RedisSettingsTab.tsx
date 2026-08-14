import React from 'react';
import { useTranslation } from 'react-i18next';

export interface RedisSettingsData {
  url: string;
}

interface RedisSettingsTabProps {
  initial: RedisSettingsData;
}

// Read-only: backend/core/system_settings_views.py explicitly documents
// this as "read from Django settings, not editable via UI" — the GET
// response includes it, but update_system_settings has no handler for a
// 'redis' key at all, so a previous version of this tab that POSTed
// { redis: ... } and showed a "saved" toast was a no-op the whole time:
// nothing was ever persisted, and the toast lied. Celery/Channels are
// also both configured from REDIS_URL at process start, before this UI
// could ever run, so even a real DB-backed write here couldn't take
// effect without a restart regardless — .env + restart is the only way
// to actually change this, which is what the note below says.
const RedisSettingsTab: React.FC<RedisSettingsTabProps> = ({ initial }) => {
  const { t } = useTranslation();

  return (
    <div className="settings-tab-content">
      <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
        <p style={{ margin: 0, fontSize: '0.9rem' }}>
          <strong>{t('systemSettings.redis.title')}</strong><br />
          {t('systemSettings.redis.description')}
        </p>
      </div>

      <div className="form-group">
        <label>{t('systemSettings.redis.url')}</label>
        <input type="text" value={initial.url} readOnly disabled />
        <small style={{ color: 'var(--text-secondary)' }}>
          {t('systemSettings.redis.read_only_note')}
        </small>
      </div>
    </div>
  );
};

export default RedisSettingsTab;
