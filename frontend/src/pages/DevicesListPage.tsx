import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import '../styles/Devices.css';

interface ImportPreviewRow {
  row_number: number;
  data: Record<string, string>;
  errors: string[];
  warnings: string[];
  valid: boolean;
}

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
}

const DevicesListPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [devices, setDevices] = useState<Device[]>([]);
  const [filteredDevices, setFilteredDevices] = useState<Device[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [deviceTypes, setDeviceTypes] = useState<DeviceType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [selectedDevices, setSelectedDevices] = useState<Set<number>>(new Set());
  const [bulkDeleteLoading, setBulkDeleteLoading] = useState(false);

  // Check if user is admin
  const isAdmin = user?.role === 'administrator';

  // Import CSV state
  const [showImportModal, setShowImportModal] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<{
    total_rows: number;
    valid_rows: number;
    duplicate_rows: number;
    error_rows: number;
    rows: ImportPreviewRow[];
  } | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importOptions, setImportOptions] = useState({
    skip_duplicates: true,
    update_existing: false,
  });
  const [importResult, setImportResult] = useState<{
    created: number;
    updated: number;
    skipped: number;
    errors: string[];
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [filterVendor, setFilterVendor] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterLocation, setFilterLocation] = useState('');
  const [sortField, setSortField] = useState<string>('ip_address');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

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
  });

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [devices, searchTerm, filterVendor, filterType, filterStatus, filterLocation, sortField, sortDirection]);

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
      logger.error('Error loading devices:', error);
      // Don't show alert for empty device list - this is normal on fresh install
      setDevices([]);
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
      logger.error('Error loading vendors:', error);
    }
  };

  const loadDeviceTypes = async () => {
    try {
      const response = await apiService.deviceTypes.list();
      const typesList = Array.isArray(response) ? response : response.results || [];
      setDeviceTypes(typesList);
    } catch (error) {
      logger.error('Error loading device types:', error);
    }
  };

  const applyFilters = () => {
    let filtered = devices;

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(device =>
        device.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        device.ip_address.includes(searchTerm) ||
        (device.location && device.location.toLowerCase().includes(searchTerm.toLowerCase()))
      );
    }

    // Vendor filter
    if (filterVendor) {
      filtered = filtered.filter(device => String(device.vendor) === filterVendor);
    }

    // Type filter
    if (filterType) {
      filtered = filtered.filter(device => String(device.device_type) === filterType);
    }

    // Status filter
    if (filterStatus) {
      filtered = filtered.filter(device => device.status === filterStatus);
    }

    // Location filter
    if (filterLocation) {
      filtered = filtered.filter(device =>
        device.location && device.location.toLowerCase().includes(filterLocation.toLowerCase())
      );
    }

    // Sorting
    filtered.sort((a, b) => {
      let aVal: any = a[sortField as keyof Device];
      let bVal: any = b[sortField as keyof Device];

      // Handle IP address sorting naturally
      if (sortField === 'ip_address') {
        const parseIP = (ip: string) => ip.split('.').map(n => parseInt(n, 10));
        const aIP = parseIP(aVal || '0.0.0.0');
        const bIP = parseIP(bVal || '0.0.0.0');
        for (let i = 0; i < 4; i++) {
          if (aIP[i] !== bIP[i]) {
            return sortDirection === 'asc' ? aIP[i] - bIP[i] : bIP[i] - aIP[i];
          }
        }
        return 0;
      }

      // Handle null/undefined
      if (aVal == null) aVal = '';
      if (bVal == null) bVal = '';

      // String comparison
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = bVal.toLowerCase();
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    setFilteredDevices(filtered);
  };

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const clearFilters = () => {
    setSearchTerm('');
    setFilterVendor('');
    setFilterType('');
    setFilterStatus('');
    setFilterLocation('');
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
      password: '',
      enable_password: '',
      location: device.location,
      criticality: device.criticality,
      backup_enabled: device.backup_enabled,
    });
    setShowModal(true);
  };

  // Import CSV functions
  const handleOpenImport = () => {
    setShowImportModal(true);
    setImportFile(null);
    setImportPreview(null);
    setImportResult(null);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImportFile(file);
    setImportLoading(true);
    setImportResult(null);

    try {
      const preview = await apiService.devices.csvPreview(file);
      setImportPreview(preview);
    } catch (error: any) {
      alert(error.response?.data?.error || t('devices.import.preview_error'));
    } finally {
      setImportLoading(false);
    }
  };

  const handleImport = async () => {
    if (!importFile) return;

    setImportLoading(true);
    try {
      const result = await apiService.devices.csvImport(importFile, importOptions);
      setImportResult(result);
      if (result.created > 0 || result.updated > 0) {
        loadDevices();
      }
    } catch (error: any) {
      alert(error.response?.data?.error || t('devices.import.import_error'));
    } finally {
      setImportLoading(false);
    }
  };

  const getCurrentLanguage = () => {
    const lang = localStorage.getItem('language') || 'en';
    return ['en', 'ru', 'kk'].includes(lang) ? lang : 'en';
  };

  const handleDownloadTemplate = async () => {
    try {
      const lang = getCurrentLanguage();
      const response = await apiService.devices.csvTemplate(lang);
      const blob = response.data;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `devices_template_${lang}.csv`);
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(link);
      }, 100);
    } catch (error) {
      logger.error('Failed to download template:', error);
      alert(t('common.error') + ': ' + t('devices.import.template_download_error'));
    }
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

      if (formData.password) {
        payload.password = formData.password;
      }

      if (formData.enable_password) {
        payload.enable_password = formData.enable_password;
      }

      if (editingDevice) {
        await apiService.devices.update(editingDevice.id, payload);
        alert(t('devices.device_updated'));
      } else {
        if (!formData.password) {
          alert(t('devices.password_required'));
          return;
        }
        await apiService.devices.create(payload);
        alert(t('devices.device_created'));
      }

      setShowModal(false);
      loadDevices();
    } catch (error: any) {
      logger.error('Error saving device:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.message || t('devices.failed_save')));
    }
  };

  const handleDeleteDevice = async (device: Device, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Delete device "${device.name}"?`)) {
      return;
    }

    try {
      await apiService.devices.delete(device.id);
      alert(t('devices.device_deleted'));
      loadDevices();
    } catch (error) {
      logger.error('Error deleting device:', error);
      alert(t('devices.failed_delete'));
    }
  };

  // Bulk selection handlers
  const handleSelectDevice = (deviceId: number, e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    const newSelected = new Set(selectedDevices);
    if (e.target.checked) {
      newSelected.add(deviceId);
    } else {
      newSelected.delete(deviceId);
    }
    setSelectedDevices(newSelected);
  };

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedDevices(new Set(filteredDevices.map(d => d.id)));
    } else {
      setSelectedDevices(new Set());
    }
  };

  const handleBulkDelete = async () => {
    if (selectedDevices.size === 0) return;

    const selectedNames = devices
      .filter(d => selectedDevices.has(d.id))
      .map(d => d.name)
      .join(', ');

    if (!window.confirm(t('devices.bulk_delete_confirm', { count: selectedDevices.size, names: selectedNames }))) {
      return;
    }

    setBulkDeleteLoading(true);
    try {
      const result = await apiService.devices.bulkDelete(Array.from(selectedDevices));
      alert(t('devices.bulk_delete_success', { count: result.deleted_count }));
      setSelectedDevices(new Set());
      loadDevices();
    } catch (error: any) {
      logger.error('Error bulk deleting devices:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.detail || t('devices.bulk_delete_failed')));
    } finally {
      setBulkDeleteLoading(false);
    }
  };

  const handleBackupNow = async (device: Device, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      // Queue backup task - real-time progress will be shown in TaskTerminal
      await apiService.devices.backupNow(device.id);
      // No alert - logs will appear in TaskTerminal
    } catch (error: any) {
      logger.error('Error initiating backup:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.error || 'Failed to queue backup task'));
    }
  };

  const handleTestConnection = async (device: Device, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const result = await apiService.devices.testConnection(device.id);
      if (result.success) {
        alert(`${t('common.success')}: ${result.message}`);
      } else {
        alert(`${t('common.error')}: ${result.message}`);
      }
      // Reload devices to update status
      loadDevices();
    } catch (error: any) {
      logger.error('Error testing connection:', error);
      alert(t('common.error') + ': Connection test failed');
    }
  };

  const handleProtocolChange = (protocol: string) => {
    setFormData({
      ...formData,
      protocol,
      port: protocol === 'ssh' ? '22' : '23',
    });
  };

  const getUniqueLocations = () => {
    const locations = devices
      .map(d => d.location)
      .filter(l => l && l.trim() !== '');
    return Array.from(new Set(locations));
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
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {isAdmin && selectedDevices.size > 0 && (
            <button
              onClick={handleBulkDelete}
              className="btn-danger"
              disabled={bulkDeleteLoading}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              🗑️ {bulkDeleteLoading ? t('common.deleting') : t('devices.bulk_delete', { count: selectedDevices.size })}
            </button>
          )}
          <button onClick={() => loadDevices()} className="btn-primary">
            🔄 {t('common.refresh')}
          </button>
          <button onClick={handleOpenImport} className="btn-primary">
            📥 {t('devices.import.button')}
          </button>
          <button onClick={handleAddDevice} className="btn-primary">
            ➕ {t('devices.add_device')}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="filters-section">
        <div className="filters-row">
          <input
            type="text"
            placeholder={t('common.search') + ' (name, IP, location)...'}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
            style={{ flex: 2 }}
          />

          <select
            value={filterVendor}
            onChange={(e) => setFilterVendor(e.target.value)}
            className="filter-select"
          >
            <option value="">{t('devices.all_vendors')}</option>
            {vendors.map(vendor => (
              <option key={vendor.id} value={vendor.id}>{vendor.name}</option>
            ))}
          </select>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="filter-select"
          >
            <option value="">{t('devices.all_types')}</option>
            {deviceTypes.map(type => (
              <option key={type.id} value={type.id}>{type.name}</option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="filter-select"
          >
            <option value="">{t('devices.all_status')}</option>
            <option value="online">{t('devices.online')}</option>
            <option value="offline">{t('devices.offline')}</option>
            <option value="unknown">{t('devices.unknown')}</option>
          </select>

          <input
            type="text"
            placeholder={t('devices.location_placeholder')}
            value={filterLocation}
            onChange={(e) => setFilterLocation(e.target.value)}
            className="search-input"
          />

          <button onClick={clearFilters} className="btn-secondary">
            ✕ {t('devices.clear_filters')}
          </button>
        </div>
      </div>

      {/* Devices Table */}
      {filteredDevices.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🖥️</div>
          <h3>{t('devices.no_devices')}</h3>
          <p>{devices.length === 0 ? t('devices.add_first_device') : t('devices.adjust_filters')}</p>
          {devices.length === 0 && (
            <button onClick={handleAddDevice} className="btn-primary">
              {t('devices.add_device')}
            </button>
          )}
        </div>
      ) : (
        <div className="table-container">
          <table className="devices-table">
            <thead>
              <tr>
                {isAdmin && (
                  <th style={{ width: '40px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={selectedDevices.size === filteredDevices.length && filteredDevices.length > 0}
                      onChange={handleSelectAll}
                      title={t('devices.select_all')}
                    />
                  </th>
                )}
                <th onClick={() => handleSort('name')} className={`sortable ${sortField === 'name' ? 'active' : ''}`}>
                  {t('devices.name')}
                  <span className="sort-indicator">{sortField === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : '▲'}</span>
                </th>
                <th onClick={() => handleSort('ip_address')} className={`sortable ${sortField === 'ip_address' ? 'active' : ''}`}>
                  {t('devices.ip_address')}
                  <span className="sort-indicator">{sortField === 'ip_address' ? (sortDirection === 'asc' ? '▲' : '▼') : '▲'}</span>
                </th>
                <th onClick={() => handleSort('vendor')} className={`sortable ${sortField === 'vendor' ? 'active' : ''}`}>
                  {t('devices.vendor')}
                  <span className="sort-indicator">{sortField === 'vendor' ? (sortDirection === 'asc' ? '▲' : '▼') : '▲'}</span>
                </th>
                <th onClick={() => handleSort('device_type')} className={`sortable ${sortField === 'device_type' ? 'active' : ''}`}>
                  {t('devices.type')}
                  <span className="sort-indicator">{sortField === 'device_type' ? (sortDirection === 'asc' ? '▲' : '▼') : '▲'}</span>
                </th>
                <th onClick={() => handleSort('location')} className={`sortable ${sortField === 'location' ? 'active' : ''}`}>
                  {t('devices.location')}
                  <span className="sort-indicator">{sortField === 'location' ? (sortDirection === 'asc' ? '▲' : '▼') : '▲'}</span>
                </th>
                <th onClick={() => handleSort('status')} className={`sortable ${sortField === 'status' ? 'active' : ''}`}>
                  {t('devices.status')}
                  <span className="sort-indicator">{sortField === 'status' ? (sortDirection === 'asc' ? '▲' : '▼') : '▲'}</span>
                </th>
                <th onClick={() => handleSort('last_backup')} className={`sortable ${sortField === 'last_backup' ? 'active' : ''}`}>
                  {t('devices.last_backup')}
                  <span className="sort-indicator">{sortField === 'last_backup' ? (sortDirection === 'asc' ? '▲' : '▼') : '▲'}</span>
                </th>
                <th>{t('devices.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {filteredDevices.map((device) => (
                <tr
                  key={device.id}
                  onClick={() => navigate(`/devices/${device.id}`)}
                  style={{ cursor: 'pointer' }}
                  className={`table-row-hover ${selectedDevices.has(device.id) ? 'selected-row' : ''}`}
                >
                  {isAdmin && (
                    <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedDevices.has(device.id)}
                        onChange={(e) => handleSelectDevice(device.id, e)}
                      />
                    </td>
                  )}
                  <td>
                    <strong>
                      {device.name}
                      {device.backup_enabled && (
                        <span
                          style={{
                            marginLeft: '0.5rem',
                            fontSize: '0.875rem',
                            color: 'var(--success-color)',
                            cursor: 'help'
                          }}
                          title={t('devices.auto_backup_enabled')}
                        >
                          💾✓
                        </span>
                      )}
                    </strong>
                    {device.description && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                        {device.description.substring(0, 50)}
                        {device.description.length > 50 ? '...' : ''}
                      </div>
                    )}
                  </td>
                  <td style={{ fontFamily: 'monospace' }}>{device.ip_address}</td>
                  <td>{device.vendor_name}</td>
                  <td>{device.device_type_name}</td>
                  <td>{device.location || '-'}</td>
                  <td>
                    <span className={`status-badge status-${device.status}`}>
                      {device.status}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.875rem' }}>
                    {device.last_backup
                      ? new Date(device.last_backup).toLocaleString()
                      : t('devices.never')}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                      <button
                        onClick={(e) => handleBackupNow(device, e)}
                        className="btn-sm btn-success"
                        title={t('devices.backup_now')}
                      >
                        💾
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditDevice(device);
                        }}
                        className="btn-sm btn-secondary"
                        title={t('common.edit')}
                      >
                        ✏️
                      </button>
                      <button
                        onClick={(e) => handleTestConnection(device, e)}
                        className="btn-sm btn-primary"
                        title={t('devices.test_connection')}
                      >
                        🔌
                      </button>
                      <button
                        onClick={(e) => handleDeleteDevice(device, e)}
                        className="btn-sm btn-danger"
                        title={t('common.delete')}
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="footer-stats">
        Total: {devices.length} | Filtered: {filteredDevices.length}
      </div>

      {/* Add/Edit Device Modal - Same as before */}
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

      {/* Import CSV Modal */}
      {showImportModal && (
        <div className="modal-overlay" onClick={() => setShowImportModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px', maxHeight: '80vh', overflow: 'auto' }}>
            <div className="modal-header">
              <h2>{t('devices.import.title')}</h2>
              <button onClick={() => setShowImportModal(false)} className="close-btn">✕</button>
            </div>

            <div className="modal-body">
              {/* Download template */}
              <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: 'var(--hover-bg)', borderRadius: '8px' }}>
                <p style={{ margin: '0 0 0.5rem 0', fontWeight: 600 }}>{t('devices.import.download_template')}</p>
                <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                  {t('devices.import.template_hint')}
                </p>
                <button
                  onClick={handleDownloadTemplate}
                  className="btn-primary"
                  type="button"
                >
                  📄 {t('devices.import.download_button')}
                </button>
              </div>

              {/* File upload */}
              <div style={{ marginBottom: '1.5rem' }}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  style={{ display: 'none' }}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="btn-primary"
                  disabled={importLoading}
                  style={{ width: '100%', padding: '1rem' }}
                >
                  {importFile ? `📁 ${importFile.name}` : `📂 ${t('devices.import.select_file')}`}
                </button>
              </div>

              {/* Loading */}
              {importLoading && (
                <div style={{ textAlign: 'center', padding: '2rem' }}>
                  <p>{t('devices.import.processing')}</p>
                </div>
              )}

              {/* Preview */}
              {importPreview && !importResult && (
                <div>
                  <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ padding: '0.5rem 1rem', backgroundColor: 'var(--hover-bg)', borderRadius: '4px' }}>
                      {t('devices.import.total')}: <strong>{importPreview.total_rows}</strong>
                    </div>
                    <div style={{ padding: '0.5rem 1rem', backgroundColor: '#d4edda', borderRadius: '4px', color: '#155724' }}>
                      {t('devices.import.valid')}: <strong>{importPreview.valid_rows}</strong>
                    </div>
                    {importPreview.duplicate_rows > 0 && (
                      <div style={{ padding: '0.5rem 1rem', backgroundColor: '#fff3cd', borderRadius: '4px', color: '#856404' }}>
                        {t('devices.import.duplicates')}: <strong>{importPreview.duplicate_rows}</strong>
                      </div>
                    )}
                    {importPreview.error_rows > 0 && (
                      <div style={{ padding: '0.5rem 1rem', backgroundColor: '#f8d7da', borderRadius: '4px', color: '#721c24' }}>
                        {t('devices.import.errors')}: <strong>{importPreview.error_rows}</strong>
                      </div>
                    )}
                  </div>

                  {/* Options */}
                  <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)', borderRadius: '8px' }}>
                    <div className="checkbox-group" style={{ marginBottom: '0.5rem' }}>
                      <input
                        type="checkbox"
                        id="skip_duplicates"
                        checked={importOptions.skip_duplicates}
                        onChange={(e) => setImportOptions({ ...importOptions, skip_duplicates: e.target.checked })}
                      />
                      <label htmlFor="skip_duplicates">{t('devices.import.skip_duplicates')}</label>
                    </div>
                    <div className="checkbox-group">
                      <input
                        type="checkbox"
                        id="update_existing"
                        checked={importOptions.update_existing}
                        onChange={(e) => setImportOptions({ ...importOptions, update_existing: e.target.checked })}
                      />
                      <label htmlFor="update_existing">{t('devices.import.update_existing')}</label>
                    </div>
                  </div>

                  {/* Preview table */}
                  <div style={{ maxHeight: '300px', overflow: 'auto', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                      <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--card-bg)' }}>
                        <tr>
                          <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>#</th>
                          <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>{t('devices.name')}</th>
                          <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>IP</th>
                          <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>{t('devices.vendor')}</th>
                          <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>{t('devices.status')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importPreview.rows.map((row) => (
                          <tr key={row.row_number} style={{ backgroundColor: row.valid ? 'inherit' : '#fff3cd' }}>
                            <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>{row.row_number}</td>
                            <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>{row.data.name}</td>
                            <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>{row.data.ip_address}</td>
                            <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>{row.data.vendor}</td>
                            <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>
                              {row.valid ? (
                                <span style={{ color: '#28a745' }}>✓</span>
                              ) : (
                                <span style={{ color: '#dc3545' }} title={row.errors.join(', ')}>✗ {row.errors[0]}</span>
                              )}
                              {row.warnings.length > 0 && (
                                <span style={{ color: '#ffc107', marginLeft: '0.5rem' }} title={row.warnings.join(', ')}>⚠</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Import result */}
              {importResult && (
                <div style={{ padding: '1rem', backgroundColor: '#d4edda', borderRadius: '8px', color: '#155724' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0' }}>{t('devices.import.complete')}</h4>
                  <p style={{ margin: 0 }}>
                    {t('devices.import.created')}: {importResult.created},
                    {t('devices.import.updated_count')}: {importResult.updated},
                    {t('devices.import.skipped_count')}: {importResult.skipped}
                  </p>
                  {importResult.errors.length > 0 && (
                    <div style={{ marginTop: '0.5rem', color: '#721c24' }}>
                      <strong>{t('devices.import.errors')}:</strong>
                      <ul style={{ margin: '0.25rem 0 0 1rem', padding: 0 }}>
                        {importResult.errors.slice(0, 5).map((err, i) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowImportModal(false)} className="btn-secondary">
                {t('common.close')}
              </button>
              {importPreview && !importResult && importPreview.valid_rows > 0 && (
                <button onClick={handleImport} className="btn-primary" disabled={importLoading}>
                  {importLoading ? t('devices.import.importing') : t('devices.import.import_button')}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DevicesListPage;
