import React from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import SystemSettings from '../components/SystemSettings';
import '../styles/Settings.css';

const SettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const { user } = useAuth();

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>⚙️ {t('settings.system_settings')}</h1>
        <p className="page-subtitle">{t('systemSettings.subtitle')}</p>
      </div>

      <div className="settings-container">
        {/* System Settings - Only for Administrator */}
        {user?.role === 'administrator' ? (
          <div className="settings-section">
            <SystemSettings />
          </div>
        ) : (
          <div className="empty-state" style={{ padding: '3rem', textAlign: 'center' }}>
            <div className="empty-icon">🔒</div>
            <h3>{t('systemSettings.access_denied')}</h3>
          </div>
        )}
      </div>
    </div>
  );
};

export default SettingsPage;
