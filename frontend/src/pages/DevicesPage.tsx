import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import '../styles/Devices.css';

interface Device {
  id: number;
  name: string;
  ip_address: string;
  description: string;
  vendor: number;
  vendor_name: string;
  device_type: number;
  device_type_name: string;
  protocol: string;
  port: number;
  username: string;
  location: string;
  criticality: string;
  status: string;
  backup_enabled: boolean;
  last_backup: string | null;
  custom_commands: any;
}

interface Vendor {
  id: number;
  name: string;
}

interface DeviceType {
  id: number;
  name: string;
}

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
  custom_commands: string;
}

const DevicesPage: React.FC = () => {
  const { t } = useTranslation();
  const [devices, setDevices] = useState<Device[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [deviceTypes, setDeviceTypes] = useState<DeviceType[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [formData, setFormData] = useState<DeviceFormData>({
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
    custom_commands: '',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    await Promise.all([loadDevices(), loadVendors(), loadDeviceTypes()]);
  };

  const loadDevices = async () => {
    try {
      setLoading(true);
      const response = await apiService.devices.list({ ordering: 'name' });
      const devicesList = Array.isArray(response) ? response : response.results || [];
      setDevices(devicesList);
    } catch (error) {
      console.error('Error loading devices:', error);
      alert(t('common.error') + ': Failed to load devices');
    } finally {
      setLoading(false);
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

  const loadDeviceTypes = async () => {
    try {
      const response = await apiService.deviceTypes.list();
      const typesList = Array.isArray(response) ? response : response.results || [];
      setDeviceTypes(typesList);
    } catch (error) {
      console.error('Error loading device types:', error);
    }
  };

  const handleAddDevice = () => {
    setEditingDevice(null);
    setFormData({
      name: '',
      ip_address: '',
      description: '',
      vendor: vendors.length > 0 ? String(vendors[0].id) : '',
      device_type: deviceTypes.length > 0 ? String(deviceTypes[0].id) : '',
      protocol: 'ssh',
      port: '22',
      username: '',
      password: '',
      enable_password: '',
      location: '',
      criticality: 'medium',
      backup_enabled: true,
      custom_commands: '',
    });
    setShowModal(true);
  };

  const handleEditDevice = async (device: Device) => {
    setEditingDevice(device);
    setFormData({
      name: device.name,
      ip_address: device.ip_address,
      description: device.description,
      vendor: String(device.vendor),
      device_type: String(device.device_type),
      protocol: device.protocol,
      port: String(device.port),
      username: device.username,
      password: '', // Don't populate password for security
      enable_password: '',
      location: device.location,
      criticality: device.criticality,
      backup_enabled: device.backup_enabled,
      custom_commands: device.custom_commands ? JSON.stringify(device.custom_commands, null, 2) : '',
    });
    setShowModal(true);
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

      // Only include password if provided
      if (formData.password) {
        payload.password = formData.password;
      }

      if (formData.enable_password) {
        payload.enable_password = formData.enable_password;
      }

      // Parse custom commands JSON if provided
      if (formData.custom_commands && formData.custom_commands.trim()) {
        try {
          payload.custom_commands = JSON.parse(formData.custom_commands);
        } catch (jsonError) {
          alert('Invalid JSON format for custom commands');
          return;
        }
      } else {
        payload.custom_commands = [];
      }

      if (editingDevice) {
        await apiService.devices.update(editingDevice.id, payload);
        alert(t('common.success') + ': Device updated');
      } else {
        if (!formData.password) {
          alert('Password is required for new devices');
          return;
        }
        await apiService.devices.create(payload);
        alert(t('common.success') + ': Device created');
      }

      setShowModal(false);
      loadDevices();
    } catch (error: any) {
      console.error('Error saving device:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.message || 'Failed to save device'));
    }
  };

  const handleDeleteDevice = async (device: Device) => {
    if (!window.confirm(`Delete device "${device.name}"?`)) {
      return;
    }

    try {
      await apiService.devices.delete(device.id);
      alert(t('common.success') + ': Device deleted');
      loadDevices();
    } catch (error) {
      console.error('Error deleting device:', error);
      alert(t('common.error') + ': Failed to delete device');
    }
  };

  const handleTestConnection = async (device: Device) => {
    try {
      const result = await apiService.devices.testConnection(device.id);
      if (result.success) {
        alert(`${t('common.success')}: ${result.message}`);
      } else {
        alert(`${t('common.error')}: ${result.message}`);
      }
    } catch (error: any) {
      console.error('Error testing connection:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.message || 'Connection test failed'));
    }
  };

  const handleBackupNow = async (device: Device) => {
    try {
      const result = await apiService.devices.backupNow(device.id);
      alert(`${t('common.success')}: ${result.message}`);
    } catch (error: any) {
      console.error('Error initiating backup:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.error || 'Backup failed'));
    }
  };

  const handleProtocolChange = (protocol: string) => {
    setFormData({
      ...formData,
      protocol,
      port: protocol === 'ssh' ? '22' : '23',
    });
  };

  const filteredDevices = devices.filter(device =>
    device.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    device.ip_address.includes(searchTerm) ||
    (device.location && device.location.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const getStatusClass = (status: string) => {
    return `status-${status}`;
  };

  const getCriticalityClass = (criticality: string) => {
    return `criticality-${criticality}`;
  };

  if (loading) {
    return (
      <div className="devices-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="devices-page">
      <div className="page-header">
        <h1>{t('devices.title')}</h1>
        <button onClick={loadDevices} className="btn-primary">
          🔄 {t('common.refresh')}
        </button>
      </div>

      <div className="toolbar">
        <input
          type="text"
          placeholder={t('common.search') + '...'}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        <button onClick={handleAddDevice} className="btn-primary">
          ➕ {t('devices.add_device')}
        </button>
      </div>

      {filteredDevices.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🖥️</div>
          <h3>{t('devices.title')}</h3>
          <p>No devices found</p>
          <button onClick={handleAddDevice} className="btn-primary">
            {t('devices.add_device')}
          </button>
        </div>
      ) : (
        <div className="devices-grid">
          {filteredDevices.map((device) => (
            <div key={device.id} className="device-card">
              <div className="device-header">
                <div>
                  <h3 className="device-name">
                    {device.name}
                    {device.backup_enabled && (
                      <span
                        style={{
                          marginLeft: '0.5rem',
                          fontSize: '1rem',
                          color: 'var(--success-color)',
                          cursor: 'help'
                        }}
                        title={t('devices.auto_backup_enabled')}
                      >
                        💾✓
                      </span>
                    )}
                  </h3>
                  <p className="device-ip">{device.ip_address}</p>
                </div>
                <span className={`status-badge ${getStatusClass(device.status)}`}>
                  {device.status}
                </span>
              </div>

              <div className="device-body">
                <div className="device-info">
                  <div className="info-row">
                    <span className="info-label">{t('devices.vendor')}:</span>
                    <span className="info-value">{device.vendor_name || 'N/A'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('devices.device_type')}:</span>
                    <span className="info-value">{device.device_type_name || 'N/A'}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('devices.protocol')}:</span>
                    <span className="info-value">{device.protocol?.toUpperCase()}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Criticality:</span>
                    <span className={`criticality-badge ${getCriticalityClass(device.criticality)}`}>
                      {device.criticality}
                    </span>
                  </div>
                </div>

                {device.description && (
                  <p className="device-description">{device.description}</p>
                )}

                {device.location && (
                  <div className="location-row">
                    <span>📍</span>
                    <span>{device.location}</span>
                  </div>
                )}
              </div>

              <div className="device-footer">
                <button
                  onClick={() => handleBackupNow(device)}
                  className="btn-sm btn-success"
                  title={t('devices.backup_now')}
                >
                  💾
                </button>
                <button
                  onClick={() => handleEditDevice(device)}
                  className="btn-sm btn-secondary"
                  title={t('common.edit')}
                >
                  ✏️
                </button>
                <button
                  onClick={() => handleTestConnection(device)}
                  className="btn-sm btn-primary"
                  title={t('devices.test_connection')}
                >
                  🔌
                </button>
                <button
                  onClick={() => handleDeleteDevice(device)}
                  className="btn-sm btn-danger"
                  title={t('common.delete')}
                >
                  🗑️
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="footer-stats">
        {t('devices.title')}: {devices.length} | Shown: {filteredDevices.length}
      </div>

      {/* Add/Edit Device Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingDevice ? t('devices.edit_device') : t('devices.add_device')}</h2>
              <button onClick={() => setShowModal(false)} className="btn-close">
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
                    <label>Password {!editingDevice && '*'}</label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      required={!editingDevice}
                      placeholder={editingDevice ? 'Leave empty to keep current' : ''}
                    />
                  </div>

                  <div className="form-group">
                    <label>Enable Password</label>
                    <input
                      type="password"
                      value={formData.enable_password}
                      onChange={(e) => setFormData({ ...formData, enable_password: e.target.value })}
                      placeholder="For Cisco devices"
                    />
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

                <div className="form-group">
                  <label>Custom Backup Commands (JSON, optional)</label>
                  <textarea
                    value={formData.custom_commands}
                    onChange={(e) => setFormData({ ...formData, custom_commands: e.target.value })}
                    rows={6}
                    placeholder={`{\n  "setup": ["terminal length 0"],\n  "backup": "show running-config",\n  "enable_mode": true\n}`}
                    style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
                  />
                  <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
                    Leave empty to use vendor defaults. Override vendor commands for this specific device.
                    <br />
                    💡 To edit vendor defaults, go to Settings → Vendors tab
                  </small>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                  {t('common.cancel')}
                </button>
                <button type="submit" className="btn-primary">
                  {t('common.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default DevicesPage;
