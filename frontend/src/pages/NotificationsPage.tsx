import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import NotificationRules from '../components/NotificationRules';
import NotificationLog from '../components/NotificationLog';
import '../styles/Settings.css';

const NotificationsPage: React.FC = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'rules' | 'log'>('rules');

  return (
    <div className="devices-page">
      <div className="page-header">
        <h1>🔔 {t('notificationRules.nav_title')}</h1>
        <p className="page-subtitle">{t('notificationRules.subtitle')}</p>
      </div>

      <div className="settings-container">
        <div className="tabs">
          <button
            className={`tab-btn ${activeTab === 'rules' ? 'active' : ''}`}
            onClick={() => setActiveTab('rules')}
          >
            🔔 {t('notificationRules.tabs.rules')}
          </button>
          <button
            className={`tab-btn ${activeTab === 'log' ? 'active' : ''}`}
            onClick={() => setActiveTab('log')}
          >
            📜 {t('notificationRules.tabs.log')}
          </button>
        </div>

        {activeTab === 'rules' && (
          <div className="settings-tab-content">
            <NotificationRules />
          </div>
        )}

        {activeTab === 'log' && (
          <div className="settings-tab-content">
            <NotificationLog />
          </div>
        )}
      </div>
    </div>
  );
};

export default NotificationsPage;
