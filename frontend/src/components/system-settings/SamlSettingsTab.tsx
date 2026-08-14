import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { extractErrorMessage } from '../../utils/extractErrorMessage';
import { useToast } from '../../contexts/ToastContext';
import { SAMLSettingsResponse } from '../../types';

const DEFAULT_SAML_SETTINGS: SAMLSettingsResponse = {
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
};

// Self-contained (unlike EmailSettingsTab/etc.) — SAML settings were never
// part of the shared systemSettings.get() payload the other tabs slice
// from; the original component loaded them via a separate request too.
const SamlSettingsTab: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [samlSettings, setSamlSettings] = useState(DEFAULT_SAML_SETTINGS);

  useEffect(() => {
    loadSamlSettings();
  }, []);

  const loadSamlSettings = async () => {
    try {
      const response = await apiService.saml.getSettings();
      setSamlSettings(response);
    } catch (error) {
      logger.error('Error loading SAML settings:', error);
    }
  };

  const handleSaveSaml = async () => {
    try {
      setSaving(true);
      await apiService.saml.updateSettings(samlSettings);
      toast.success(t('systemSettings.saml.saved'));
    } catch (error) {
      logger.error('Error saving SAML settings:', error);
      toast.error(extractErrorMessage(error, t('systemSettings.saml.failed')));
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
          onChange={(e) => setSamlSettings({ ...samlSettings, default_role: e.target.value as SAMLSettingsResponse['default_role'] })}
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
  );
};

export default SamlSettingsTab;
