import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { extractErrorMessage } from '../../utils/extractErrorMessage';
import { useToast } from '../../contexts/ToastContext';
import { useListResource } from '../../hooks/useListResource';
import { useModalForm } from '../../hooks/useModalForm';
import { DeviceType } from '../../types';

const DEFAULT_FORM_DATA = { name: '', slug: '', description: '', icon: 'router' };

// Self-contained, same as VendorsTab — device types were always loaded/
// managed independently of the shared systemSettings.get() payload.
const DeviceTypesTab: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);

  const { items: deviceTypes, reload: loadDeviceTypes } = useListResource<DeviceType>(
    () => apiService.deviceTypes.list()
  );

  // No edit flow exists for device types (only add/delete), so openEdit
  // is never called here — openCreate/close cover the one modal this tab has.
  const {
    showModal: showDeviceTypeModal, formData: deviceTypeForm, setFormData: setDeviceTypeForm,
    openCreate: handleAddDeviceType, close: closeModal,
  } = useModalForm<DeviceType, typeof DEFAULT_FORM_DATA>(DEFAULT_FORM_DATA, () => DEFAULT_FORM_DATA);

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
      toast.success(t('systemSettings.device_types.created'));
      closeModal();
      await loadDeviceTypes();
    } catch (error) {
      logger.error('Error creating device type:', error);
      toast.error(extractErrorMessage(error, t('systemSettings.device_types.failed_create')));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteDeviceType = async (deviceType: DeviceType) => {
    if (!window.confirm(t('systemSettings.device_types.confirm_delete', { name: deviceType.name }))) {
      return;
    }

    try {
      await apiService.deviceTypes.delete(deviceType.id);
      toast.success(t('systemSettings.device_types.deleted'));
      await loadDeviceTypes();
    } catch (error) {
      logger.error('Error deleting device type:', error);
      toast.error(t('systemSettings.device_types.failed_delete'));
    }
  };

  return (
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

      {/* Add Device Type Modal */}
      {showDeviceTypeModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div className="modal-header">
              <h2>{t('systemSettings.device_types.add_type')}</h2>
              <button onClick={closeModal} className="btn-close">✕</button>
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
              <button onClick={closeModal} className="btn-secondary">
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

export default DeviceTypesTab;
