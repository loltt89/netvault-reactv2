import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Device } from '../../types';

type SortDirection = 'asc' | 'desc';

interface DevicesTableProps {
  devices: Device[];
  isAdmin: boolean;
  selectedDevices: Set<number>;
  sortField: string;
  sortDirection: SortDirection;
  onSort: (field: string) => void;
  onSelectDevice: (deviceId: number, e: React.ChangeEvent<HTMLInputElement>) => void;
  onSelectAll: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onBackupNow: (device: Device, e: React.MouseEvent) => void;
  onEditDevice: (device: Device) => void;
  onTestConnection: (device: Device, e: React.MouseEvent) => void;
  onDeleteDevice: (device: Device, e: React.MouseEvent) => void;
}

const SortHeader: React.FC<{
  field: string;
  label: string;
  sortField: string;
  sortDirection: SortDirection;
  onSort: (field: string) => void;
}> = ({ field, label, sortField, sortDirection, onSort }) => (
  <th onClick={() => onSort(field)} className={`sortable ${sortField === field ? 'active' : ''}`}>
    {label}
    <span className="sort-indicator">{sortField === field ? (sortDirection === 'asc' ? '▲' : '▼') : '▲'}</span>
  </th>
);

const DevicesTable: React.FC<DevicesTableProps> = ({
  devices, isAdmin, selectedDevices, sortField, sortDirection, onSort,
  onSelectDevice, onSelectAll, onBackupNow, onEditDevice, onTestConnection, onDeleteDevice,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  if (devices.length === 0) {
    return null;
  }

  return (
    <div className="table-container">
      <table className="devices-table">
        <thead>
          <tr>
            {isAdmin && (
              <th style={{ width: '40px', textAlign: 'center' }}>
                <input
                  type="checkbox"
                  checked={selectedDevices.size === devices.length && devices.length > 0}
                  onChange={onSelectAll}
                  title={t('devices.select_all')}
                />
              </th>
            )}
            <SortHeader field="name" label={t('devices.name')} sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
            <SortHeader field="ip_address" label={t('devices.ip_address')} sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
            <SortHeader field="vendor" label={t('devices.vendor')} sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
            <SortHeader field="device_type" label={t('devices.type')} sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
            <SortHeader field="location" label={t('devices.location')} sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
            <SortHeader field="tags" label={t('devices.tags')} sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
            <SortHeader field="status" label={t('devices.status')} sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
            <SortHeader field="last_backup" label={t('devices.last_backup')} sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
            <th>{t('devices.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => (
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
                    onChange={(e) => onSelectDevice(device.id, e)}
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
                {device.tags && device.tags.length > 0 ? (
                  <div className="tag-chips">
                    {device.tags.map((tag) => (
                      <span key={tag} className="tag-chip">{tag}</span>
                    ))}
                  </div>
                ) : '-'}
              </td>
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
                    onClick={(e) => onBackupNow(device, e)}
                    className="btn-sm btn-success"
                    title={t('devices.backup_now')}
                  >
                    💾
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onEditDevice(device);
                    }}
                    className="btn-sm btn-secondary"
                    title={t('common.edit')}
                  >
                    ✏️
                  </button>
                  <button
                    onClick={(e) => onTestConnection(device, e)}
                    className="btn-sm btn-primary"
                    title={t('devices.test_connection')}
                  >
                    🔌
                  </button>
                  <button
                    onClick={(e) => onDeleteDevice(device, e)}
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
  );
};

export default DevicesTable;
