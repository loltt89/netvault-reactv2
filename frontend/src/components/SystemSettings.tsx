import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import { useToast } from '../contexts/ToastContext';
import { SystemSettingsResponse } from '../types';
import EmailSettingsTab from './system-settings/EmailSettingsTab';
import TelegramSettingsTab from './system-settings/TelegramSettingsTab';
import NotificationsSettingsTab from './system-settings/NotificationsSettingsTab';
import LdapSettingsTab from './system-settings/LdapSettingsTab';
import SamlSettingsTab from './system-settings/SamlSettingsTab';
import JwtSettingsTab from './system-settings/JwtSettingsTab';
import RedisSettingsTab from './system-settings/RedisSettingsTab';
import VendorsTab from './system-settings/VendorsTab';
import DeviceTypesTab from './system-settings/DeviceTypesTab';

// This used to be a single ~1400-line component owning nine unrelated
// settings domains' state/handlers/JSX in one file. Split into one file
// per tab under system-settings/ — this container now only owns what's
// genuinely shared: the tab switcher and the systemSettings.get() payload
// that email/telegram/notifications/ldap/jwt/redis all slice from (SAML/
// vendors/device-types were always independently loaded, so those three
// tabs are fully self-contained — see their own files).
type TabId = 'email' | 'telegram' | 'notifications' | 'ldap' | 'saml' | 'jwt' | 'redis' | 'vendors' | 'devicetypes';

// Matches the original per-tab useState defaults exactly — if
// loadSettings() fails, the tabs render with these instead of getting
// stuck behind the loading spinner forever (the toast in the catch block
// below already tells the admin the load failed).
const DEFAULT_SETTINGS: SystemSettingsResponse = {
  email: { host: '', port: 587, use_tls: true, host_user: '', from_email: '' },
  telegram: { enabled: false, bot_token: '', chat_id: '' },
  notifications: { notify_on_success: false, notify_on_failure: true, notify_schedule_summary: false },
  ldap: { enabled: false, server_uri: '', bind_dn: '', user_search_base: '', user_search_filter: '' },
  backup: { retention_days: 90, parallel_workers: 5 },
  redis: { url: 'redis://localhost:6379/0' },
  jwt: { access_token_lifetime: 60, refresh_token_lifetime: 1440 },
};

const SystemSettings: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const [settings, setSettings] = useState<SystemSettingsResponse>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('email');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await apiService.systemSettings.get();
      setSettings(data);
    } catch (error) {
      logger.error('Error loading system settings:', error);
      if (axios.isAxiosError(error) && error.response?.status === 403) {
        toast.error(t('systemSettings.access_denied'));
      } else {
        toast.error(t('systemSettings.failed_load'));
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem' }}>
        <div className="spinner"></div>
        <p>{t('systemSettings.loading')}</p>
      </div>
    );
  }

  return (
    <div className="system-settings">
      <h2>⚙️ {t('systemSettings.title')}</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
        {t('systemSettings.subtitle')}
      </p>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: '1.5rem' }}>
        <button className={`tab-btn ${activeTab === 'email' ? 'active' : ''}`} onClick={() => setActiveTab('email')}>
          📧 {t('systemSettings.tabs.email')}
        </button>
        <button className={`tab-btn ${activeTab === 'telegram' ? 'active' : ''}`} onClick={() => setActiveTab('telegram')}>
          📱 {t('systemSettings.tabs.telegram')}
        </button>
        <button className={`tab-btn ${activeTab === 'notifications' ? 'active' : ''}`} onClick={() => setActiveTab('notifications')}>
          🔔 {t('systemSettings.tabs.notifications')}
        </button>
        <button className={`tab-btn ${activeTab === 'ldap' ? 'active' : ''}`} onClick={() => setActiveTab('ldap')}>
          🔐 {t('systemSettings.tabs.ldap')}
        </button>
        <button className={`tab-btn ${activeTab === 'saml' ? 'active' : ''}`} onClick={() => setActiveTab('saml')}>
          🔑 SAML SSO
        </button>
        <button className={`tab-btn ${activeTab === 'jwt' ? 'active' : ''}`} onClick={() => setActiveTab('jwt')}>
          🔑 {t('systemSettings.tabs.jwt')}
        </button>
        <button className={`tab-btn ${activeTab === 'redis' ? 'active' : ''}`} onClick={() => setActiveTab('redis')}>
          🗄️ {t('systemSettings.tabs.redis')}
        </button>
        <button className={`tab-btn ${activeTab === 'vendors' ? 'active' : ''}`} onClick={() => setActiveTab('vendors')}>
          🏭 {t('systemSettings.tabs.vendors')}
        </button>
        <button className={`tab-btn ${activeTab === 'devicetypes' ? 'active' : ''}`} onClick={() => setActiveTab('devicetypes')}>
          📦 {t('systemSettings.tabs.device_types')}
        </button>
      </div>

      {activeTab === 'email' && <EmailSettingsTab initial={settings.email} onSaved={loadSettings} />}
      {activeTab === 'telegram' && <TelegramSettingsTab initial={settings.telegram} onSaved={loadSettings} />}
      {activeTab === 'notifications' && <NotificationsSettingsTab initial={settings.notifications} onSaved={loadSettings} />}
      {activeTab === 'ldap' && <LdapSettingsTab initial={settings.ldap} onSaved={loadSettings} />}
      {activeTab === 'saml' && <SamlSettingsTab />}
      {activeTab === 'jwt' && <JwtSettingsTab initial={settings.jwt} onSaved={loadSettings} />}
      {activeTab === 'redis' && <RedisSettingsTab initial={settings.redis} />}
      {activeTab === 'vendors' && <VendorsTab />}
      {activeTab === 'devicetypes' && <DeviceTypesTab />}
    </div>
  );
};

export default SystemSettings;
