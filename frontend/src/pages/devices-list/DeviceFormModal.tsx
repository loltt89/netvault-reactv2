import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { extractErrorMessage } from '../../utils/extractErrorMessage';
import { useToast } from '../../contexts/ToastContext';
import { Device } from '../../types';

interface Vendor { id: number; name: string; }
interface DeviceType { id: number; name: string; }

interface DeviceFormData {
  name: string;
  ip_address: string;
  description: string;
  vendor: string;
  device_type: string;
  protocol: string;
  port: string;
  username: string;
  password: string;
  enable_password: string;
  location: string;
  criticality: string;
  backup_enabled: boolean;
}

const EMPTY_FORM: DeviceFormData = {
  name: '',
  ip_address: '',
  description: '',
  vendor: '',
  device_type: '',
  protocol: 'ssh',
  port: '22',
  username: '',
  password: '',
  enable_password: '',
  location: '',
  criticality: 'medium',
  backup_enabled: true,
};

interface DeviceFormModalProps {
  isOpen: boolean;
  editingDevice: Device | null;
  vendors: Vendor[];
  deviceTypes: DeviceType[];
  onClose: () => void;
  onSaved: () => void;
}

const DeviceFormModal: React.FC<DeviceFormModalProps> = ({
  isOpen, editingDevice, vendors, deviceTypes, onClose, onSaved,
}) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [formData, setFormData] = useState<DeviceFormData>(EMPTY_FORM);
  // Track if mousedown started on the overlay itself (for proper close
  // behavior — a drag that starts inside the modal and releases over the
  // overlay shouldn't close it).
  const mouseDownOnOverlay = useRef(false);

  useEffect(() => {
    if (!isOpen) return;
    if (editingDevice) {
      setFormData({
        name: editingDevice.name,
        ip_address: editingDevice.ip_address,
        description: editingDevice.description,
        vendor: String(editingDevice.vendor),
        device_type: String(editingDevice.device_type),
        protocol: editingDevice.protocol,
        port: String(editingDevice.port),
        username: editingDevice.username,
        password: '*****', // Router-style: show ***** as actual value
        enable_password: '*****',
        location: editingDevice.location,
        criticality: editingDevice.criticality,
        backup_enabled: editingDevice.backup_enabled,
      });
    } else {
      setFormData({
        ...EMPTY_FORM,
        vendor: vendors.length > 0 ? String(vendors[0].id) : '',
        device_type: deviceTypes.length > 0 ? String(deviceTypes[0].id) : '',
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, editingDevice]);

  const handleProtocolChange = (protocol: string) => {
    setFormData({
      ...formData,
      protocol,
      port: protocol === 'ssh' ? '22' : '23',
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const payload: any = {
        name: formData.name,
        ip_address: formData.ip_address,
        description: formData.description,
        vendor: parseInt(formData.vendor),
        device_type: parseInt(formData.device_type),
        protocol: formData.protocol,
        port: parseInt(formData.port),
        username: formData.username,
        location: formData.location,
        criticality: formData.criticality,
        backup_enabled: formData.backup_enabled,
      };

      if (editingDevice) {
        // Router-style password handling for edit mode:
        // - If password is '*****' (unchanged placeholder), don't send it
        // - If password was changed to something else, send the new value
        // - If the field was focused (clearing the placeholder) but left
        //   empty, we still send '' — the backend now treats an empty
        //   string as "leave unchanged" for both fields, not "clear the
        //   credential" (see DeviceCreateSerializer.update): an accidental
        //   Tab-through blanks the placeholder via onFocus below just as
        //   easily as a deliberate edit does, so '' alone is never treated
        //   as an explicit clear request.
        if (formData.password !== '*****') {
          payload.password = formData.password;
        }
        if (formData.enable_password !== '*****') {
          payload.enable_password = formData.enable_password;
        }
        await apiService.devices.update(editingDevice.id, payload);
        toast.success(t('devices.device_updated'));
      } else {
        // For new devices, always send password (can be empty)
        payload.password = formData.password;
        if (formData.enable_password) {
          payload.enable_password = formData.enable_password;
        }
        await apiService.devices.create(payload);
        toast.success(t('devices.device_created'));
      }

      onSaved();
    } catch (error: any) {
      logger.error('Error saving device:', error);
      toast.error(extractErrorMessage(error, t('devices.failed_save')));
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onMouseDown={() => { mouseDownOnOverlay.current = true; }}
      onClick={() => { if (mouseDownOnOverlay.current) onClose(); }}
    >
      <div className="modal-content" onMouseDown={(e) => { e.stopPropagation(); mouseDownOnOverlay.current = false; }}>
        <div className="modal-header">
          <h2>{editingDevice ? t('devices.edit_device') : t('devices.add_device')}</h2>
          <button onClick={onClose} className="btn-close">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label>{t('devices.device_name')} *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>{t('devices.ip_address')} *</label>
                <input
                  type="text"
                  value={formData.ip_address}
                  onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label>Location</label>
                <input
                  type="text"
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>{t('devices.vendor')} *</label>
                <select
                  value={formData.vendor}
                  onChange={(e) => setFormData({ ...formData, vendor: e.target.value })}
                  required
                >
                  <option value="">Select vendor</option>
                  {vendors.map((vendor) => (
                    <option key={vendor.id} value={vendor.id}>
                      {vendor.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>{t('devices.device_type')} *</label>
                <select
                  value={formData.device_type}
                  onChange={(e) => setFormData({ ...formData, device_type: e.target.value })}
                  required
                >
                  <option value="">Select type</option>
                  {deviceTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>{t('devices.protocol')} *</label>
                <select
                  value={formData.protocol}
                  onChange={(e) => handleProtocolChange(e.target.value)}
                  required
                >
                  <option value="ssh">SSH</option>
                  <option value="telnet">Telnet</option>
                </select>
                {formData.protocol === 'telnet' && (
                  <div style={{ color: 'var(--warning-color)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
                    ⚠️ {t('devices.telnet_warning')}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label>{t('devices.port')} *</label>
                <input
                  type="number"
                  value={formData.port}
                  onChange={(e) => setFormData({ ...formData, port: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label>Username *</label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                required
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => {
                    setFormData({ ...formData, password: e.target.value });
                  }}
                  onFocus={() => {
                    // Router-style: clear ***** on focus to allow new input
                    if (editingDevice && formData.password === '*****') {
                      setFormData({ ...formData, password: '' });
                    }
                  }}
                  placeholder={!editingDevice ? t('devices.password_optional') : undefined}
                />
                {editingDevice && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                    {formData.password === '*****'
                      ? t('devices.password_unchanged')
                      : (formData.password ? t('devices.password_will_change') : t('devices.password_kept_if_empty'))}
                  </div>
                )}
              </div>

              <div className="form-group">
                <label>Enable Password</label>
                <input
                  type="password"
                  value={formData.enable_password}
                  onChange={(e) => {
                    setFormData({ ...formData, enable_password: e.target.value });
                  }}
                  onFocus={() => {
                    // Router-style: clear ***** on focus to allow new input
                    if (editingDevice && formData.enable_password === '*****') {
                      setFormData({ ...formData, enable_password: '' });
                    }
                  }}
                  placeholder={!editingDevice ? t('devices.enable_password_optional') : undefined}
                />
                {editingDevice && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                    {formData.enable_password === '*****'
                      ? t('devices.password_unchanged')
                      : (formData.enable_password ? t('devices.password_will_change') : t('devices.password_kept_if_empty'))}
                  </div>
                )}
              </div>
            </div>

            <div className="form-group">
              <label>Criticality</label>
              <select
                value={formData.criticality}
                onChange={(e) => setFormData({ ...formData, criticality: e.target.value })}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div className="form-group">
              <label>Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
              />
            </div>

            <div className="form-group">
              <div className="checkbox-group">
                <input
                  type="checkbox"
                  id="backup_enabled"
                  checked={formData.backup_enabled}
                  onChange={(e) => setFormData({ ...formData, backup_enabled: e.target.checked })}
                />
                <label htmlFor="backup_enabled">{t('devices.backup_enabled')}</label>
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" onClick={onClose} className="btn-secondary">
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn-primary">
              {t('common.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DeviceFormModal;
