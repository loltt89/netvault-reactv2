import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';

interface SystemSettings {
  email: {
    backend: string;
    host: string;
    port: number;
    use_tls: boolean;
    host_user: string;
    from_email: string;
  };
  telegram: {
    bot_token: string;
    chat_id: string;
    enabled: boolean;
  };
  ldap: {
    enabled: boolean;
    server_uri: string;
    bind_dn: string;
    user_search_base: string;
  };
  redis: {
    url: string;
  };
  backup: {
    retention_days: number;
    parallel_workers: number;
  };
  device_check: {
    interval_minutes: number;
    tcp_timeout: number;
    ssh_timeout: number;
  };
  jwt: {
    access_token_lifetime: number;
    refresh_token_lifetime: number;
  };
  security: {
    session_cookie_secure: boolean;
    csrf_cookie_secure: boolean;
    secure_ssl_redirect: boolean;
  };
}

const SystemSettings: React.FC = () => {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'email' | 'telegram' | 'ldap' | 'saml' | 'backup' | 'device_check' | 'jwt' | 'redis' | 'vendors' | 'devicetypes'>('email');

  // Form states
  const [emailSettings, setEmailSettings] = useState({
    host: '',
    port: 587,
    use_tls: true,
    host_user: '',
    host_password: '',
  });

  const [telegramSettings, setTelegramSettings] = useState({
    enabled: false,
    bot_token: '',
    chat_id: '',
  });

  const [ldapSettings, setLdapSettings] = useState({
    enabled: false,
    server_uri: '',
    bind_dn: '',
    bind_password: '',
    user_search_base: '',
  });

  const [samlSettings, setSamlSettings] = useState({
    enabled: false,
    sp_entity_id: '',
    sp_acs_url: '',
    sp_sls_url: '',
    sp_metadata_url: '',
    idp_entity_id: '',
    idp_sso_url: '',
    idp_slo_url: '',
    idp_x509_cert: '',
    attr_username: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name',
    attr_email: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
    attr_first_name: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname',
    attr_last_name: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname',
    auto_create_users: true,
    default_role: 'viewer',
    want_assertions_signed: true,
    want_messages_signed: false,
  });

  const [backupSettings, setBackupSettings] = useState({
    retention_days: 90,
    parallel_workers: 5,
  });

  const [deviceCheckSettings, setDeviceCheckSettings] = useState({
    interval_minutes: 5,
    tcp_timeout: 2,
    ssh_timeout: 5,
  });

  const [jwtSettings, setJwtSettings] = useState({
    access_token_lifetime: 60,
    refresh_token_lifetime: 1440,
  });

  const [redisSettings, setRedisSettings] = useState({
    url: 'redis://localhost:6379/0',
  });

  const [vendors, setVendors] = useState<any[]>([]);
  const [editingVendor, setEditingVendor] = useState<any>(null);
  const [vendorCommands, setVendorCommands] = useState('');
  const [showVendorModal, setShowVendorModal] = useState(false);
  const [vendorForm, setVendorForm] = useState({ name: '', slug: '', description: '', backup_commands: '' });

  const [deviceTypes, setDeviceTypes] = useState<any[]>([]);
  const [showDeviceTypeModal, setShowDeviceTypeModal] = useState(false);
  const [deviceTypeForm, setDeviceTypeForm] = useState({ name: '', slug: '', description: '', icon: 'router' });

  useEffect(() => {
    loadSettings();
    loadVendors();
    loadDeviceTypes();
    loadSamlSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await apiService.systemSettings.get();
      setSettings(data);

      // Populate form fields
      setEmailSettings({
        host: data.email.host,
        port: data.email.port,
        use_tls: data.email.use_tls,
        host_user: data.email.host_user,
        host_password: '',
      });

      setTelegramSettings({
        enabled: data.telegram.enabled,
        bot_token: data.telegram.bot_token,
        chat_id: data.telegram.chat_id,
      });

      setLdapSettings({
        enabled: data.ldap.enabled,
        server_uri: data.ldap.server_uri,
        bind_dn: data.ldap.bind_dn,
        bind_password: '',
        user_search_base: data.ldap.user_search_base,
      });

      setBackupSettings({
        retention_days: data.backup.retention_days,
        parallel_workers: data.backup.parallel_workers,
      });

      setDeviceCheckSettings({
        interval_minutes: data.device_check.interval_minutes,
        tcp_timeout: data.device_check.tcp_timeout,
        ssh_timeout: data.device_check.ssh_timeout,
      });

      setJwtSettings({
        access_token_lifetime: data.jwt.access_token_lifetime,
        refresh_token_lifetime: data.jwt.refresh_token_lifetime,
      });

      setRedisSettings({
        url: data.redis.url,
      });
    } catch (error: any) {
      console.error('Error loading system settings:', error);
      if (error.response?.status === 403) {
        alert(t('systemSettings.access_denied'));
      } else {
        alert(t('systemSettings.failed_load'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEmail = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ email: emailSettings });
      alert(t('systemSettings.email.saved'));
      await loadSettings();
    } catch (error) {
      console.error('Error saving email settings:', error);
      alert(t('systemSettings.email.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleTestEmail = async () => {
    const testEmail = prompt(t('systemSettings.email.enter_email'));
    if (!testEmail) return;

    try {
      const result = await apiService.systemSettings.testEmail(testEmail);
      alert(result.message);
    } catch (error: any) {
      alert(error.response?.data?.error || t('systemSettings.email.failed_test'));
    }
  };

  const handleSaveTelegram = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ telegram: telegramSettings });
      alert(t('systemSettings.telegram.saved'));
      await loadSettings();
    } catch (error) {
      console.error('Error saving telegram settings:', error);
      alert(t('systemSettings.telegram.failed_save'));
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
      alert(result.message);
    } catch (error: any) {
      alert(error.response?.data?.error || t('systemSettings.telegram.failed_test'));
    }
  };

  const handleSaveLDAP = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ ldap: ldapSettings });
      alert(t('systemSettings.ldap.saved'));
      await loadSettings();
    } catch (error) {
      console.error('Error saving LDAP settings:', error);
      alert(t('systemSettings.ldap.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveBackup = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ backup: backupSettings });
      alert(t('systemSettings.backup.saved'));
      await loadSettings();
    } catch (error) {
      console.error('Error saving backup settings:', error);
      alert(t('systemSettings.backup.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveDeviceCheck = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ device_check: deviceCheckSettings });
      alert(t('systemSettings.device_check.saved'));
      await loadSettings();
    } catch (error) {
      console.error('Error saving device check settings:', error);
      alert(t('systemSettings.device_check.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveJWT = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ jwt: jwtSettings });
      alert(t('systemSettings.jwt.saved'));
      await loadSettings();
    } catch (error) {
      console.error('Error saving JWT settings:', error);
      alert(t('systemSettings.jwt.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveRedis = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ redis: redisSettings });
      alert(t('systemSettings.redis.saved'));
      await loadSettings();
    } catch (error) {
      console.error('Error saving Redis settings:', error);
      alert(t('systemSettings.redis.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const loadVendors = async () => {
    try {
      const response = await apiService.vendors.list();
      const vendorsList = Array.isArray(response) ? response : response.results || [];
      setVendors(vendorsList);
    } catch (error) {
      console.error('Error loading vendors:', error);
    }
  };

  const handleEditVendor = (vendor: any) => {
    setEditingVendor(vendor);
    setVendorCommands(vendor.backup_commands ? JSON.stringify(vendor.backup_commands, null, 2) : '');
  };

  const handleSaveVendorCommands = async () => {
    if (!editingVendor) return;

    try {
      setSaving(true);
      let parsedCommands = {};

      if (vendorCommands.trim()) {
        try {
          parsedCommands = JSON.parse(vendorCommands);
        } catch (e) {
          alert(t('systemSettings.vendors.invalid_json'));
          setSaving(false);
          return;
        }
      }

      await apiService.vendors.update(editingVendor.id, {
        backup_commands: parsedCommands
      });

      alert(t('systemSettings.vendors.updated'));
      setEditingVendor(null);
      setVendorCommands('');
      await loadVendors();
    } catch (error) {
      console.error('Error saving vendor commands:', error);
      alert(t('systemSettings.vendors.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  const handleAddVendor = () => {
    setVendorForm({ name: '', slug: '', description: '', backup_commands: '' });
    setShowVendorModal(true);
  };

  const handleSaveVendor = async () => {
    try {
      setSaving(true);

      let parsedCommands = {};
      if (vendorForm.backup_commands.trim()) {
        try {
          parsedCommands = JSON.parse(vendorForm.backup_commands);
        } catch (e) {
          alert(t('systemSettings.vendors.invalid_json_commands'));
          setSaving(false);
          return;
        }
      }

      const payload = {
        name: vendorForm.name,
        slug: vendorForm.slug,
        description: vendorForm.description,
        backup_commands: parsedCommands,
      };

      await apiService.vendors.create(payload);
      alert(t('systemSettings.vendors.created'));
      setShowVendorModal(false);
      await loadVendors();
    } catch (error: any) {
      console.error('Error creating vendor:', error);
      alert(error.response?.data?.slug?.[0] || error.response?.data?.name?.[0] || t('systemSettings.vendors.failed_create'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteVendor = async (vendor: any) => {
    if (!window.confirm(t('systemSettings.vendors.confirm_delete', { name: vendor.name }))) {
      return;
    }

    try {
      await apiService.vendors.delete(vendor.id);
      alert(t('systemSettings.vendors.deleted'));
      await loadVendors();
    } catch (error) {
      console.error('Error deleting vendor:', error);
      alert(t('systemSettings.vendors.failed_delete'));
    }
  };

  const loadDeviceTypes = async () => {
    try {
      const response = await apiService.deviceTypes.list();
      const typesList = Array.isArray(response) ? response : response.results || [];
      setDeviceTypes(typesList);
    } catch (error) {
      console.error('Error loading device types:', error);
    }
  };

  const loadSamlSettings = async () => {
    try {
      const response = await apiService.request('GET', '/saml/settings/');
      setSamlSettings(response);
    } catch (error) {
      console.error('Error loading SAML settings:', error);
    }
  };

  const handleSaveSaml = async () => {
    try {
      setSaving(true);
      await apiService.request('POST', '/saml/settings/', samlSettings);
      alert(t('systemSettings.saml.saved'));
    } catch (error: any) {
      console.error('Error saving SAML settings:', error);
      alert(error.response?.data?.error || t('systemSettings.saml.failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleAddDeviceType = () => {
    setDeviceTypeForm({ name: '', slug: '', description: '', icon: 'router' });
    setShowDeviceTypeModal(true);
  };

  const handleSaveDeviceType = async () => {
    try {
      setSaving(true);

      const payload = {
        name: deviceTypeForm.name,
        slug: deviceTypeForm.slug,
        description: deviceTypeForm.description,
        icon: deviceTypeForm.icon,
      };

      await apiService.deviceTypes.create(payload);
      alert(t('systemSettings.device_types.created'));
      setShowDeviceTypeModal(false);
      await loadDeviceTypes();
    } catch (error: any) {
      console.error('Error creating device type:', error);
      alert(error.response?.data?.slug?.[0] || error.response?.data?.name?.[0] || t('systemSettings.device_types.failed_create'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteDeviceType = async (deviceType: any) => {
    if (!window.confirm(t('systemSettings.device_types.confirm_delete', { name: deviceType.name }))) {
      return;
    }

    try {
      await apiService.deviceTypes.delete(deviceType.id);
      alert(t('systemSettings.device_types.deleted'));
      await loadDeviceTypes();
    } catch (error) {
      console.error('Error deleting device type:', error);
      alert(t('systemSettings.device_types.failed_delete'));
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
        <button
          className={`tab-btn ${activeTab === 'email' ? 'active' : ''}`}
          onClick={() => setActiveTab('email')}
        >
          📧 {t('systemSettings.tabs.email')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'telegram' ? 'active' : ''}`}
          onClick={() => setActiveTab('telegram')}
        >
          📱 {t('systemSettings.tabs.telegram')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'ldap' ? 'active' : ''}`}
          onClick={() => setActiveTab('ldap')}
        >
          🔐 {t('systemSettings.tabs.ldap')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'saml' ? 'active' : ''}`}
          onClick={() => setActiveTab('saml')}
        >
          🔑 SAML SSO
        </button>
        <button
          className={`tab-btn ${activeTab === 'backup' ? 'active' : ''}`}
          onClick={() => setActiveTab('backup')}
        >
          💾 {t('systemSettings.tabs.backup')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'device_check' ? 'active' : ''}`}
          onClick={() => setActiveTab('device_check')}
        >
          🔍 {t('systemSettings.tabs.device_check')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'jwt' ? 'active' : ''}`}
          onClick={() => setActiveTab('jwt')}
        >
          🔑 {t('systemSettings.tabs.jwt')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'redis' ? 'active' : ''}`}
          onClick={() => setActiveTab('redis')}
        >
          🗄️ {t('systemSettings.tabs.redis')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'vendors' ? 'active' : ''}`}
          onClick={() => setActiveTab('vendors')}
        >
          🏭 {t('systemSettings.tabs.vendors')}
        </button>
        <button
          className={`tab-btn ${activeTab === 'devicetypes' ? 'active' : ''}`}
          onClick={() => setActiveTab('devicetypes')}
        >
          📦 {t('systemSettings.tabs.device_types')}
        </button>
      </div>

      {/* Email Settings */}
      {activeTab === 'email' && (
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
      )}

      {/* Telegram Settings */}
      {activeTab === 'telegram' && (
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
      )}

      {/* LDAP Settings */}
      {activeTab === 'ldap' && (
        <div className="settings-tab-content">
          <div className="form-group">
            <div className="checkbox-group">
              <input
                type="checkbox"
                id="ldap_enabled"
                checked={ldapSettings.enabled}
                onChange={(e) => setLdapSettings({ ...ldapSettings, enabled: e.target.checked })}
              />
              <label htmlFor="ldap_enabled" style={{ fontWeight: 600, fontSize: '1rem' }}>
                {t('systemSettings.ldap.enable')}
              </label>
            </div>
          </div>

          <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>
              <strong>{t('systemSettings.ldap.title')}</strong><br />
              {t('systemSettings.ldap.description')}
            </p>
          </div>

          <div className="form-group">
            <label>{t('systemSettings.ldap.server_uri')} *</label>
            <input
              type="text"
              value={ldapSettings.server_uri}
              onChange={(e) => setLdapSettings({ ...ldapSettings, server_uri: e.target.value })}
              placeholder="ldap://ldap.example.com:389"
              disabled={!ldapSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.ldap.bind_dn')} *</label>
            <input
              type="text"
              value={ldapSettings.bind_dn}
              onChange={(e) => setLdapSettings({ ...ldapSettings, bind_dn: e.target.value })}
              placeholder="CN=admin,DC=example,DC=com"
              disabled={!ldapSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.ldap.bind_password')}</label>
            <input
              type="password"
              value={ldapSettings.bind_password}
              onChange={(e) => setLdapSettings({ ...ldapSettings, bind_password: e.target.value })}
              placeholder={t('systemSettings.leave_empty')}
              disabled={!ldapSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.ldap.user_search_base')} *</label>
            <input
              type="text"
              value={ldapSettings.user_search_base}
              onChange={(e) => setLdapSettings({ ...ldapSettings, user_search_base: e.target.value })}
              placeholder="OU=Users,DC=example,DC=com"
              disabled={!ldapSettings.enabled}
            />
          </div>

          <div style={{ marginTop: '1.5rem' }}>
            <button onClick={handleSaveLDAP} className="btn-primary" disabled={saving}>
              {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
            </button>
          </div>
        </div>
      )}

      {/* SAML SSO Settings */}
      {activeTab === 'saml' && (
        <div className="settings-tab-content">
          <div className="form-group">
            <div className="checkbox-group">
              <input
                type="checkbox"
                id="saml_enabled"
                checked={samlSettings.enabled}
                onChange={(e) => setSamlSettings({ ...samlSettings, enabled: e.target.checked })}
              />
              <label htmlFor="saml_enabled" style={{ fontWeight: 600, fontSize: '1rem' }}>
                {t('systemSettings.saml.enable')}
              </label>
            </div>
          </div>

          <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>
              <strong>{t('systemSettings.saml.sp_info')}</strong><br />
              {t('systemSettings.saml.sp_info_desc')}
            </p>
          </div>

          {/* SP Information (Read-only) */}
          <h4 style={{ marginTop: '1.5rem', marginBottom: '1rem' }}>{t('systemSettings.saml.sp_info')}</h4>
          <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--bg-tertiary)' }}>
            <p style={{ margin: '0.25rem 0', fontSize: '0.85rem' }}>
              <strong>{t('systemSettings.saml.metadata_url')}:</strong> <code>{samlSettings.sp_metadata_url || `${window.location.origin}/api/v1/saml/metadata/`}</code>
            </p>
            <p style={{ margin: '0.25rem 0', fontSize: '0.85rem' }}>
              <strong>{t('systemSettings.saml.acs_url')}:</strong> <code>{samlSettings.sp_acs_url || `${window.location.origin}/api/v1/saml/acs/`}</code>
            </p>
            <p style={{ margin: '0.25rem 0', fontSize: '0.85rem' }}>
              <strong>{t('systemSettings.saml.entity_id')}:</strong> <code>{samlSettings.sp_entity_id || `${window.location.origin}/api/v1/saml/metadata/`}</code>
            </p>
          </div>

          <div className="form-group">
            <label>{t('systemSettings.saml.entity_id')} (optional)</label>
            <input
              type="text"
              value={samlSettings.sp_entity_id}
              onChange={(e) => setSamlSettings({ ...samlSettings, sp_entity_id: e.target.value })}
              placeholder={`${window.location.origin}/api/v1/saml/metadata/`}
              disabled={!samlSettings.enabled}
            />
          </div>

          {/* IdP Configuration */}
          <h4 style={{ marginTop: '1.5rem', marginBottom: '1rem' }}>{t('systemSettings.saml.idp_config')}</h4>

          <div className="form-group">
            <label>{t('systemSettings.saml.idp_entity_id')} *</label>
            <input
              type="text"
              value={samlSettings.idp_entity_id}
              onChange={(e) => setSamlSettings({ ...samlSettings, idp_entity_id: e.target.value })}
              placeholder="https://sts.windows.net/xxxxx/"
              disabled={!samlSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.saml.idp_sso_url')} *</label>
            <input
              type="text"
              value={samlSettings.idp_sso_url}
              onChange={(e) => setSamlSettings({ ...samlSettings, idp_sso_url: e.target.value })}
              placeholder="https://login.microsoftonline.com/xxxxx/saml2"
              disabled={!samlSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.saml.idp_slo_url')}</label>
            <input
              type="text"
              value={samlSettings.idp_slo_url}
              onChange={(e) => setSamlSettings({ ...samlSettings, idp_slo_url: e.target.value })}
              placeholder="https://login.microsoftonline.com/xxxxx/saml2"
              disabled={!samlSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.saml.idp_x509_cert')} *</label>
            <textarea
              value={samlSettings.idp_x509_cert}
              onChange={(e) => setSamlSettings({ ...samlSettings, idp_x509_cert: e.target.value })}
              placeholder={t('systemSettings.saml.idp_x509_cert_placeholder')}
              rows={6}
              disabled={!samlSettings.enabled}
              style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
            />
          </div>

          {/* Attribute Mapping */}
          <h4 style={{ marginTop: '1.5rem', marginBottom: '1rem' }}>{t('systemSettings.saml.attr_mapping')}</h4>

          <div className="form-group">
            <label>{t('systemSettings.saml.attr_username')}</label>
            <input
              type="text"
              value={samlSettings.attr_username}
              onChange={(e) => setSamlSettings({ ...samlSettings, attr_username: e.target.value })}
              disabled={!samlSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.saml.attr_email')}</label>
            <input
              type="text"
              value={samlSettings.attr_email}
              onChange={(e) => setSamlSettings({ ...samlSettings, attr_email: e.target.value })}
              disabled={!samlSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.saml.attr_first_name')}</label>
            <input
              type="text"
              value={samlSettings.attr_first_name}
              onChange={(e) => setSamlSettings({ ...samlSettings, attr_first_name: e.target.value })}
              disabled={!samlSettings.enabled}
            />
          </div>

          <div className="form-group">
            <label>{t('systemSettings.saml.attr_last_name')}</label>
            <input
              type="text"
              value={samlSettings.attr_last_name}
              onChange={(e) => setSamlSettings({ ...samlSettings, attr_last_name: e.target.value })}
              disabled={!samlSettings.enabled}
            />
          </div>

          {/* User Provisioning */}
          <h4 style={{ marginTop: '1.5rem', marginBottom: '1rem' }}>{t('systemSettings.saml.user_provisioning')}</h4>

          <div className="form-group">
            <div className="checkbox-group">
              <input
                type="checkbox"
                id="saml_auto_create"
                checked={samlSettings.auto_create_users}
                onChange={(e) => setSamlSettings({ ...samlSettings, auto_create_users: e.target.checked })}
                disabled={!samlSettings.enabled}
              />
              <label htmlFor="saml_auto_create">
                {t('systemSettings.saml.auto_create_users')}
              </label>
            </div>
          </div>

          <div className="form-group">
            <label>{t('systemSettings.saml.default_role')}</label>
            <select
              value={samlSettings.default_role}
              onChange={(e) => setSamlSettings({ ...samlSettings, default_role: e.target.value })}
              disabled={!samlSettings.enabled}
            >
              <option value="viewer">{t('systemSettings.saml.role_viewer')}</option>
              <option value="operator">{t('systemSettings.saml.role_operator')}</option>
              <option value="auditor">Auditor</option>
              <option value="administrator">{t('systemSettings.saml.role_admin')}</option>
            </select>
          </div>

          {/* Security */}
          <h4 style={{ marginTop: '1.5rem', marginBottom: '1rem' }}>{t('systemSettings.saml.security_options')}</h4>

          <div className="form-group">
            <div className="checkbox-group">
              <input
                type="checkbox"
                id="saml_want_assertions_signed"
                checked={samlSettings.want_assertions_signed}
                onChange={(e) => setSamlSettings({ ...samlSettings, want_assertions_signed: e.target.checked })}
                disabled={!samlSettings.enabled}
              />
              <label htmlFor="saml_want_assertions_signed">
                {t('systemSettings.saml.want_assertions_signed')}
              </label>
            </div>
          </div>

          <div className="form-group">
            <div className="checkbox-group">
              <input
                type="checkbox"
                id="saml_want_messages_signed"
                checked={samlSettings.want_messages_signed}
                onChange={(e) => setSamlSettings({ ...samlSettings, want_messages_signed: e.target.checked })}
                disabled={!samlSettings.enabled}
              />
              <label htmlFor="saml_want_messages_signed">
                {t('systemSettings.saml.want_messages_signed')}
              </label>
            </div>
          </div>

          <div style={{ marginTop: '1.5rem' }}>
            <button onClick={handleSaveSaml} className="btn-primary" disabled={saving}>
              {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
            </button>
          </div>
        </div>
      )}

      {/* Vendors Settings */}
      {activeTab === 'vendors' && (
        <div className="settings-tab-content">
          <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>
              <strong>{t('systemSettings.vendors.title')}</strong><br />
              {t('systemSettings.vendors.description')}<br />
              <br />
              <strong>{t('systemSettings.vendors.format')}</strong><br />
              {t('systemSettings.vendors.format_setup')}<br />
              {t('systemSettings.vendors.format_backup')}<br />
              {t('systemSettings.vendors.format_enable')}
            </p>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <button onClick={handleAddVendor} className="btn-primary">
              ➕ {t('systemSettings.vendors.add_vendor')}
            </button>
          </div>

          <div style={{ display: 'grid', gap: '1rem' }}>
            {vendors.map((vendor) => (
              <div key={vendor.id} style={{
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '1rem',
                backgroundColor: editingVendor?.id === vendor.id ? 'var(--hover-bg)' : 'transparent'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <div>
                    <h3 style={{ margin: 0 }}>{vendor.name}</h3>
                    <small style={{ color: 'var(--text-secondary)' }}>Slug: {vendor.slug}</small>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      onClick={() => editingVendor?.id === vendor.id ? setEditingVendor(null) : handleEditVendor(vendor)}
                      className="btn-secondary"
                      style={{ fontSize: '0.9rem', padding: '0.25rem 0.75rem' }}
                    >
                      {editingVendor?.id === vendor.id ? t('common.cancel') : t('systemSettings.vendors.edit_commands')}
                    </button>
                    {!vendor.is_predefined && (
                      <button
                        onClick={() => handleDeleteVendor(vendor)}
                        className="btn-danger"
                        style={{ fontSize: '0.9rem', padding: '0.25rem 0.75rem' }}
                        title={t('common.delete')}
                      >
                        🗑️
                      </button>
                    )}
                  </div>
                </div>

                {editingVendor?.id === vendor.id ? (
                  <div>
                    <div className="form-group" style={{ marginTop: '1rem' }}>
                      <label>{t('systemSettings.vendors.backup_commands')}</label>
                      <textarea
                        value={vendorCommands}
                        onChange={(e) => setVendorCommands(e.target.value)}
                        rows={8}
                        style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
                        placeholder={`{\n  "setup": ["terminal length 0"],\n  "backup": "show running-config",\n  "enable_mode": true\n}`}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                      <button onClick={handleSaveVendorCommands} className="btn-primary" disabled={saving}>
                        {saving ? t('systemSettings.saving') : t('systemSettings.vendors.save_commands')}
                      </button>
                      <button onClick={() => setEditingVendor(null)} className="btn-secondary">
                        {t('common.cancel')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{
                    backgroundColor: 'var(--bg-color)',
                    padding: '0.75rem',
                    borderRadius: '4px',
                    fontFamily: 'monospace',
                    fontSize: '0.85rem',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word'
                  }}>
                    {vendor.backup_commands && Object.keys(vendor.backup_commands).length > 0
                      ? JSON.stringify(vendor.backup_commands, null, 2)
                      : t('systemSettings.vendors.no_commands')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Device Types Settings */}
      {activeTab === 'devicetypes' && (
        <div className="settings-tab-content">
          <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>
              <strong>{t('systemSettings.device_types.title')}</strong><br />
              {t('systemSettings.device_types.description')}
            </p>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <button onClick={handleAddDeviceType} className="btn-primary">
              ➕ {t('systemSettings.device_types.add_type')}
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1rem' }}>
            {deviceTypes.map((deviceType) => (
              <div key={deviceType.id} style={{
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                padding: '1rem',
                backgroundColor: 'transparent'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>
                      {deviceType.icon === 'router' && '🔀'}
                      {deviceType.icon === 'switch' && '🔗'}
                      {deviceType.icon === 'firewall' && '🛡️'}
                      {deviceType.icon === 'server' && '🖥️'}
                      {deviceType.icon === 'ap' && '📡'}
                      {!['router', 'switch', 'firewall', 'server', 'ap'].includes(deviceType.icon) && '📦'}
                    </div>
                    <h4 style={{ margin: '0 0 0.25rem 0' }}>{deviceType.name}</h4>
                    <small style={{ color: 'var(--text-secondary)' }}>Slug: {deviceType.slug}</small>
                    {deviceType.description && (
                      <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {deviceType.description}
                      </p>
                    )}
                  </div>
                  {!deviceType.is_predefined && (
                    <button
                      onClick={() => handleDeleteDeviceType(deviceType)}
                      className="btn-danger"
                      style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
                      title={t('common.delete')}
                    >
                      🗑️
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Backup Settings */}
      {activeTab === 'backup' && (
        <div className="settings-tab-content">
          <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>
              <strong>{t('systemSettings.backup.title')}</strong><br />
              {t('systemSettings.backup.description')}
            </p>
          </div>

          <div className="form-group">
            <label>{t('systemSettings.backup.retention_days')} *</label>
            <input
              type="number"
              value={backupSettings.retention_days}
              onChange={(e) => setBackupSettings({ ...backupSettings, retention_days: parseInt(e.target.value) })}
              min="1"
              max="3650"
            />
            <small style={{ color: 'var(--text-secondary)' }}>
              {t('systemSettings.backup.retention_help')}
            </small>
          </div>

          <div className="form-group">
            <label>{t('systemSettings.backup.parallel_workers')} *</label>
            <input
              type="number"
              value={backupSettings.parallel_workers}
              onChange={(e) => setBackupSettings({ ...backupSettings, parallel_workers: parseInt(e.target.value) })}
              min="1"
              max="20"
            />
            <small style={{ color: 'var(--text-secondary)' }}>
              {t('systemSettings.backup.workers_help')}
            </small>
          </div>

          <div style={{ marginTop: '1.5rem' }}>
            <button onClick={handleSaveBackup} className="btn-primary" disabled={saving}>
              {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
            </button>
          </div>
        </div>
      )}

      {/* Device Check Settings */}
      {activeTab === 'device_check' && (
        <div className="settings-tab-content">
          <div className="info-card" style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>
              <strong>{t('systemSettings.device_check.title')}</strong><br />
              {t('systemSettings.device_check.description')}<br />
              <br />
              <strong>{t('systemSettings.device_check.hybrid_mode')}</strong><br />
              {t('systemSettings.device_check.hybrid_description')}
            </p>
          </div>

          <div className="form-group">
            <label>{t('systemSettings.device_check.interval')} *</label>
            <input
              type="number"
              value={deviceCheckSettings.interval_minutes}
              onChange={(e) => setDeviceCheckSettings({ ...deviceCheckSettings, interval_minutes: parseInt(e.target.value) })}
              min="1"
              max="60"
            />
            <small style={{ color: 'var(--text-secondary)' }}>
              {t('systemSettings.device_check.interval_help')}
            </small>
          </div>

          <div className="form-group">
            <label>{t('systemSettings.device_check.tcp_timeout')} *</label>
            <input
              type="number"
              value={deviceCheckSettings.tcp_timeout}
              onChange={(e) => setDeviceCheckSettings({ ...deviceCheckSettings, tcp_timeout: parseInt(e.target.value) })}
              min="1"
              max="10"
            />
            <small style={{ color: 'var(--text-secondary)' }}>
              {t('systemSettings.device_check.tcp_timeout_help')}
            </small>
          </div>

          <div className="form-group">
            <label>{t('systemSettings.device_check.ssh_timeout')} *</label>
            <input
              type="number"
              value={deviceCheckSettings.ssh_timeout}
              onChange={(e) => setDeviceCheckSettings({ ...deviceCheckSettings, ssh_timeout: parseInt(e.target.value) })}
              min="1"
              max="30"
            />
            <small style={{ color: 'var(--text-secondary)' }}>
              {t('systemSettings.device_check.ssh_timeout_help')}
            </small>
          </div>

          <div style={{ marginTop: '1.5rem' }}>
            <button onClick={handleSaveDeviceCheck} className="btn-primary" disabled={saving}>
              {saving ? t('systemSettings.saving') : t('systemSettings.save_settings')}
            </button>
          </div>
        </div>
      )}

      {/* JWT Session Settings */}
      {activeTab === 'jwt' && (
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
      )}

      {/* Redis Settings */}
      {activeTab === 'redis' && (
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
      )}

      {/* Add Vendor Modal */}
      {showVendorModal && (
        <div className="modal-overlay" onClick={() => setShowVendorModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <h2>{t('systemSettings.vendors.add_vendor')}</h2>
              <button onClick={() => setShowVendorModal(false)} className="btn-close">✕</button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label>{t('systemSettings.vendors.vendor_name')} *</label>
                <input
                  type="text"
                  value={vendorForm.name}
                  onChange={(e) => setVendorForm({ ...vendorForm, name: e.target.value })}
                  placeholder="e.g., My Custom Vendor"
                  required
                />
              </div>

              <div className="form-group">
                <label>{t('systemSettings.vendors.slug')} *</label>
                <input
                  type="text"
                  value={vendorForm.slug}
                  onChange={(e) => setVendorForm({ ...vendorForm, slug: e.target.value })}
                  placeholder="e.g., my-custom-vendor (lowercase, no spaces)"
                  required
                />
                <small style={{ color: 'var(--text-secondary)' }}>
                  {t('systemSettings.vendors.slug_help')}
                </small>
              </div>

              <div className="form-group">
                <label>{t('systemSettings.vendors.description')}</label>
                <textarea
                  value={vendorForm.description}
                  onChange={(e) => setVendorForm({ ...vendorForm, description: e.target.value })}
                  rows={3}
                  placeholder="Optional description"
                />
              </div>

              <div className="form-group">
                <label>{t('systemSettings.vendors.backup_commands')}</label>
                <textarea
                  value={vendorForm.backup_commands}
                  onChange={(e) => setVendorForm({ ...vendorForm, backup_commands: e.target.value })}
                  rows={8}
                  placeholder={`{\n  "setup": ["terminal length 0"],\n  "backup": "show running-config",\n  "enable_mode": true\n}`}
                  style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowVendorModal(false)} className="btn-secondary">
                {t('common.cancel')}
              </button>
              <button onClick={handleSaveVendor} className="btn-primary" disabled={saving || !vendorForm.name || !vendorForm.slug}>
                {saving ? t('systemSettings.vendors.creating') : t('systemSettings.vendors.create_vendor')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Device Type Modal */}
      {showDeviceTypeModal && (
        <div className="modal-overlay" onClick={() => setShowDeviceTypeModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div className="modal-header">
              <h2>{t('systemSettings.device_types.add_type')}</h2>
              <button onClick={() => setShowDeviceTypeModal(false)} className="btn-close">✕</button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label>{t('systemSettings.device_types.type_name')} *</label>
                <input
                  type="text"
                  value={deviceTypeForm.name}
                  onChange={(e) => setDeviceTypeForm({ ...deviceTypeForm, name: e.target.value })}
                  placeholder="e.g., Custom Firewall"
                  required
                />
              </div>

              <div className="form-group">
                <label>{t('systemSettings.device_types.slug')} *</label>
                <input
                  type="text"
                  value={deviceTypeForm.slug}
                  onChange={(e) => setDeviceTypeForm({ ...deviceTypeForm, slug: e.target.value })}
                  placeholder="e.g., custom-firewall (lowercase, no spaces)"
                  required
                />
                <small style={{ color: 'var(--text-secondary)' }}>
                  {t('systemSettings.vendors.slug_help')}
                </small>
              </div>

              <div className="form-group">
                <label>{t('systemSettings.device_types.icon')}</label>
                <select
                  value={deviceTypeForm.icon}
                  onChange={(e) => setDeviceTypeForm({ ...deviceTypeForm, icon: e.target.value })}
                >
                  <option value="router">🔀 {t('systemSettings.device_types.icon_router')}</option>
                  <option value="switch">🔗 {t('systemSettings.device_types.icon_switch')}</option>
                  <option value="firewall">🛡️ {t('systemSettings.device_types.icon_firewall')}</option>
                  <option value="server">🖥️ {t('systemSettings.device_types.icon_server')}</option>
                  <option value="ap">📡 {t('systemSettings.device_types.icon_ap')}</option>
                  <option value="other">📦 {t('systemSettings.device_types.icon_other')}</option>
                </select>
              </div>

              <div className="form-group">
                <label>{t('systemSettings.vendors.description')}</label>
                <textarea
                  value={deviceTypeForm.description}
                  onChange={(e) => setDeviceTypeForm({ ...deviceTypeForm, description: e.target.value })}
                  rows={3}
                  placeholder="Optional description"
                />
              </div>
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowDeviceTypeModal(false)} className="btn-secondary">
                {t('common.cancel')}
              </button>
              <button onClick={handleSaveDeviceType} className="btn-primary" disabled={saving || !deviceTypeForm.name || !deviceTypeForm.slug}>
                {saving ? t('systemSettings.vendors.creating') : t('systemSettings.device_types.create_type')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SystemSettings;
