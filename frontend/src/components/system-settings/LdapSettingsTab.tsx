import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { useToast } from '../../contexts/ToastContext';

export interface LdapSettingsData {
  enabled: boolean;
  server_uri: string;
  bind_dn: string;
  user_search_base: string;
}

interface LdapSettingsTabProps {
  initial: LdapSettingsData;
  onSaved: () => void;
}

const LdapSettingsTab: React.FC<LdapSettingsTabProps> = ({ initial, onSaved }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [ldapSettings, setLdapSettings] = useState({ ...initial, bind_password: '' });

  useEffect(() => {
    setLdapSettings({ ...initial, bind_password: '' });
  }, [initial]);

  const handleSaveLDAP = async () => {
    try {
      setSaving(true);
      await apiService.systemSettings.update({ ldap: ldapSettings });
      toast.success(t('systemSettings.ldap.saved'));
      onSaved();
    } catch (error) {
      logger.error('Error saving LDAP settings:', error);
      toast.error(t('systemSettings.ldap.failed_save'));
    } finally {
      setSaving(false);
    }
  };

  return (
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
  );
};

export default LdapSettingsTab;
