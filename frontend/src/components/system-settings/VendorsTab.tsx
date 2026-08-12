import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { extractErrorMessage } from '../../utils/extractErrorMessage';
import { useToast } from '../../contexts/ToastContext';
import { useListResource } from '../../hooks/useListResource';
import { Vendor } from '../../types';

// Self-contained: owns its own vendor list (via useListResource) instead of
// depending on the parent's shared systemSettings.get() payload — vendors
// were always loaded/managed independently of the other tabs.
//
// Two distinct interaction patterns live here on purpose, not one modal
// reused twice: editing an *existing* vendor's backup_commands happens
// inline in its card (editingVendor/vendorCommands), while creating a
// *new* vendor happens in a popup form (showVendorModal/vendorForm) that
// also collects name/slug/description. Forcing both through the same
// modal-form shape (like useModalForm, used elsewhere for schedules/
// retention policies) would have papered over that real difference.
const VendorsTab: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const [saving, setSaving] = useState(false);

  const { items: vendors, reload: loadVendors } = useListResource<Vendor>(() => apiService.vendors.list());

  const [editingVendor, setEditingVendor] = useState<Vendor | null>(null);
  const [vendorCommands, setVendorCommands] = useState('');
  const [showVendorModal, setShowVendorModal] = useState(false);
  const [vendorForm, setVendorForm] = useState({ name: '', slug: '', description: '', backup_commands: '' });

  const handleEditVendor = (vendor: Vendor) => {
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
          toast.warning(t('systemSettings.vendors.invalid_json'));
          setSaving(false);
          return;
        }
      }

      await apiService.vendors.update(editingVendor.id, {
        backup_commands: parsedCommands
      });

      toast.success(t('systemSettings.vendors.updated'));
      setEditingVendor(null);
      setVendorCommands('');
      await loadVendors();
    } catch (error) {
      logger.error('Error saving vendor commands:', error);
      toast.error(t('systemSettings.vendors.failed_save'));
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
          toast.warning(t('systemSettings.vendors.invalid_json_commands'));
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
      toast.success(t('systemSettings.vendors.created'));
      setShowVendorModal(false);
      await loadVendors();
    } catch (error: any) {
      logger.error('Error creating vendor:', error);
      toast.error(extractErrorMessage(error, t('systemSettings.vendors.failed_create')));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteVendor = async (vendor: Vendor) => {
    if (!window.confirm(t('systemSettings.vendors.confirm_delete', { name: vendor.name }))) {
      return;
    }

    try {
      await apiService.vendors.delete(vendor.id);
      toast.success(t('systemSettings.vendors.deleted'));
      await loadVendors();
    } catch (error) {
      logger.error('Error deleting vendor:', error);
      toast.error(t('systemSettings.vendors.failed_delete'));
    }
  };

  return (
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
        {vendors.map((vendor: any) => (
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
    </div>
  );
};

export default VendorsTab;
