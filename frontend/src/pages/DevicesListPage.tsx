import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import { extractErrorMessage } from '../utils/extractErrorMessage';
import { unwrapList } from '../utils/unwrapList';
import { Device } from '../types';
import DevicesFilters from './devices-list/DevicesFilters';
import DevicesTable from './devices-list/DevicesTable';
import DevicesPagination from './devices-list/DevicesPagination';
import DeviceFormModal from './devices-list/DeviceFormModal';
import ImportCsvModal from './devices-list/ImportCsvModal';
import BulkTagEditModal from './devices-list/BulkTagEditModal';
import '../styles/Devices.css';

// This used to be one ~1300-line component doing the job of five: list
// rendering, client-side filter/sort, pagination, the add/edit form, CSV
// import, and per-row actions. Split into devices-list/ — this container
// now only owns what's genuinely shared across those pieces: the device
// list itself, the filter/sort/pagination state that drives what's shown,
// and the handlers (delete/backup-now/test-connection/bulk-delete) that
// need to trigger a reload here after they run.
interface Vendor { id: number; name: string; }
interface DeviceType { id: number; name: string; }

const DevicesListPage: React.FC = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const toast = useToast();
  const [devices, setDevices] = useState<Device[]>([]);
  const [filteredDevices, setFilteredDevices] = useState<Device[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [deviceTypes, setDeviceTypes] = useState<DeviceType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [selectedDevices, setSelectedDevices] = useState<Set<number>>(new Set());
  const [bulkDeleteLoading, setBulkDeleteLoading] = useState(false);
  const [bulkBackupLoading, setBulkBackupLoading] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showBulkTagModal, setShowBulkTagModal] = useState(false);
  const [bulkTagSaving, setBulkTagSaving] = useState(false);

  const isAdmin = user?.role === 'administrator';
  // bulk_backup_now/bulk_tag_edit are Operator+Admin on the backend
  // (CanManageDevices allows POST for operator) — bulk_delete stays
  // admin-only, matching its own dedicated permission_classes.
  const canBulkAct = isAdmin || user?.role === 'operator';

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [filterVendor, setFilterVendor] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterLocation, setFilterLocation] = useState('');
  const [filterTags, setFilterTags] = useState('');
  const [sortField, setSortField] = useState<string>('ip_address');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(user?.page_size || 50);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    loadVendors();
    loadDeviceTypes();
  }, []);

  // Reload devices when pagination changes. Filter changes are handled by
  // the two effects below instead of being lumped in here: search/vendor/
  // type/status/location/tags all need to reset back to page 1 (a filter
  // applied while sitting on, say, page 3 of the unfiltered list must not
  // silently keep querying page 3 of the filtered one — it may not exist),
  // and the search/location text boxes need debouncing so every keystroke
  // doesn't fire its own request.
  useEffect(() => {
    loadDevices();
  }, [currentPage, pageSize]);

  // A filter change invalidates whatever page we were on. If we're not
  // already on page 1, jump there — that alone triggers the effect above.
  // If we're already on page 1, that effect won't fire (no dep changed),
  // so the debounced effect below is what actually reloads in that case.
  useEffect(() => {
    if (currentPage !== 1) {
      setCurrentPage(1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm, filterVendor, filterType, filterStatus, filterLocation, filterTags]);

  // Debounced reload for filter changes. Search/location are free text —
  // this keeps a keystroke from firing a request per character. Vendor/
  // type/status are discrete dropdown picks, cheap to also fold into the
  // same short debounce rather than special-case them separately.
  // clearTimeout on cleanup collapses the extra render this causes when
  // currentPage also resets to 1 above into a single actual request.
  useEffect(() => {
    const timer = setTimeout(() => {
      loadDevices();
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm, filterVendor, filterType, filterStatus, filterLocation, filterTags]);

  useEffect(() => {
    applySort();
  }, [devices, sortField, sortDirection]);

  // Update pageSize when user preference loads
  useEffect(() => {
    if (user?.page_size && user.page_size !== pageSize) {
      setPageSize(user.page_size);
    }
  }, [user?.page_size]);

  const loadDevices = async () => {
    try {
      setLoading(true);
      const response = await apiService.devices.list({
        ordering: 'name',
        page: currentPage,
        page_size: pageSize,
        // Sent to the server (DeviceViewSet.get_queryset) rather than
        // filtered client-side against the one already-fetched page —
        // this list is paginated (up to page_size=100), so a client-side
        // filter used to only ever search/filter within whatever page
        // happened to be loaded, silently missing matches sitting on any
        // other page.
        search: searchTerm || undefined,
        vendor: filterVendor || undefined,
        device_type: filterType || undefined,
        status: filterStatus || undefined,
        location: filterLocation || undefined,
        tags: filterTags || undefined,
      });
      const devicesList = unwrapList<Device>(response);
      setDevices(devicesList);
      // Paginated response carries the real total; a plain-array fallback
      // (non-paginated response) has no separate total, so its own
      // length is the best available count.
      setTotalCount('count' in response ? response.count : devicesList.length);
    } catch (error) {
      logger.error('Error loading devices:', error);
      // Don't show alert for empty device list - this is normal on fresh install
      setDevices([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  };

  const loadVendors = async () => {
    try {
      const response = await apiService.vendors.list();
      setVendors(unwrapList<Vendor>(response));
    } catch (error) {
      logger.error('Error loading vendors:', error);
    }
  };

  const loadDeviceTypes = async () => {
    try {
      const response = await apiService.deviceTypes.list();
      setDeviceTypes(unwrapList<DeviceType>(response));
    } catch (error) {
      logger.error('Error loading device types:', error);
    }
  };

  // Search/vendor/type/status/location/tags are now applied server-side
  // (loadDevices sends them as query params — see the comment there), so
  // all that's left to do client-side is order the page that came back.
  // This still only sorts within the current page rather than across the
  // whole filtered result set, same as before this fix — a smaller,
  // separate limitation of pagination+sort interaction that filtering
  // alone doesn't touch.
  const applySort = () => {
    const filtered = devices.slice();

    filtered.sort((a, b) => {
      // The only array-valued Device field ('tags') is handled by its own
      // early-return branch above, so by this point the dynamic-keyed
      // read is always one of Device's remaining, genuinely comparable
      // field types — never string[].
      let aVal: string | number | boolean | null = a[sortField as keyof Device] as string | number | boolean | null;
      let bVal: string | number | boolean | null = b[sortField as keyof Device] as string | number | boolean | null;

      // Tags is a string[] — sort by its joined, lowercased text rather
      // than relying on array's implicit toString() coercion below.
      if (sortField === 'tags') {
        const aTags = (a.tags || []).slice().sort().join(',').toLowerCase();
        const bTags = (b.tags || []).slice().sort().join(',').toLowerCase();
        if (aTags < bTags) return sortDirection === 'asc' ? -1 : 1;
        if (aTags > bTags) return sortDirection === 'asc' ? 1 : -1;
        return 0;
      }

      // Handle IP address sorting naturally
      if (sortField === 'ip_address') {
        const parseIP = (ip: string) => ip.split('.').map(n => parseInt(n, 10));
        // sortField === 'ip_address' guarantees these came from Device's
        // own ip_address field, which is always a string.
        const aIP = parseIP((aVal as string) || '0.0.0.0');
        const bIP = parseIP((bVal as string) || '0.0.0.0');
        for (let i = 0; i < 4; i++) {
          if (aIP[i] !== bIP[i]) {
            return sortDirection === 'asc' ? aIP[i] - bIP[i] : bIP[i] - aIP[i];
          }
        }
        return 0;
      }

      if (aVal == null) aVal = '';
      if (bVal == null) bVal = '';

      if (typeof aVal === 'string' && typeof bVal === 'string') {
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
    setFilterTags('');
  };

  const hasActiveFilters = Boolean(
    searchTerm || filterVendor || filterType || filterStatus || filterLocation || filterTags
  );

  const totalPages = Math.ceil(totalCount / pageSize);

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };

  const handlePageSizeChange = async (newSize: number) => {
    setPageSize(newSize);
    setCurrentPage(1); // Reset to first page when changing page size
    try {
      await apiService.users.updateProfile({ page_size: newSize });
    } catch (error) {
      logger.error('Failed to save page size preference:', error);
    }
  };

  const handleAddDevice = () => {
    setEditingDevice(null);
    setShowModal(true);
  };

  const handleEditDevice = (device: Device) => {
    setEditingDevice(device);
    setShowModal(true);
  };

  const handleDeviceSaved = () => {
    setShowModal(false);
    loadDevices();
  };

  const handleDeleteDevice = async (device: Device, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Delete device "${device.name}"?`)) {
      return;
    }

    try {
      await apiService.devices.delete(device.id);
      toast.success(t('devices.device_deleted'));
      loadDevices();
    } catch (error) {
      logger.error('Error deleting device:', error);
      toast.error(t('devices.failed_delete'));
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
      toast.success(t('devices.bulk_delete_success', { count: result.deleted_count }));
      setSelectedDevices(new Set());
      loadDevices();
    } catch (error) {
      logger.error('Error bulk deleting devices:', error);
      toast.error(extractErrorMessage(error, t('devices.bulk_delete_failed')));
    } finally {
      setBulkDeleteLoading(false);
    }
  };

  const handleBulkBackupNow = async () => {
    if (selectedDevices.size === 0) return;

    setBulkBackupLoading(true);
    try {
      const result = await apiService.devices.bulkBackupNow(Array.from(selectedDevices));
      toast.success(t('devices.bulk_backup_success', { count: result.triggered_count }));
      setSelectedDevices(new Set());
    } catch (error) {
      logger.error('Error bulk-triggering backups:', error);
      toast.error(extractErrorMessage(error, t('devices.bulk_backup_failed')));
    } finally {
      setBulkBackupLoading(false);
    }
  };

  const handleBulkTagEdit = async (action: 'add' | 'remove' | 'set', tags: string[]) => {
    setBulkTagSaving(true);
    try {
      const result = await apiService.devices.bulkTagEdit(Array.from(selectedDevices), action, tags);
      toast.success(t('devices.bulk_tag_success', { count: result.updated_count }));
      setShowBulkTagModal(false);
      setSelectedDevices(new Set());
      loadDevices();
    } catch (error) {
      logger.error('Error bulk-editing tags:', error);
      toast.error(extractErrorMessage(error, t('devices.bulk_tag_failed')));
    } finally {
      setBulkTagSaving(false);
    }
  };

  const handleBackupNow = async (device: Device, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      // Queue backup task - real-time progress will be shown in TaskTerminal
      await apiService.devices.backupNow(device.id);
      // No toast - logs will appear in TaskTerminal
    } catch (error) {
      logger.error('Error initiating backup:', error);
      toast.error(extractErrorMessage(error, 'Failed to queue backup task'));
    }
  };

  const handleTestConnection = async (device: Device, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const result = await apiService.devices.testConnection(device.id);
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
      // Reload devices to update status
      loadDevices();
    } catch (error) {
      logger.error('Error testing connection:', error);
      toast.error('Connection test failed');
    }
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
          {canBulkAct && selectedDevices.size > 0 && (
            <>
              <button
                onClick={handleBulkBackupNow}
                className="btn-secondary"
                disabled={bulkBackupLoading}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                💾 {bulkBackupLoading ? t('common.loading') : t('devices.bulk_backup_now', { count: selectedDevices.size })}
              </button>
              <button
                onClick={() => setShowBulkTagModal(true)}
                className="btn-secondary"
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                🏷️ {t('devices.bulk_tag_edit', { count: selectedDevices.size })}
              </button>
            </>
          )}
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
          <button onClick={() => setShowImportModal(true)} className="btn-primary">
            📥 {t('devices.import.button')}
          </button>
          <button onClick={handleAddDevice} className="btn-primary">
            ➕ {t('devices.add_device')}
          </button>
        </div>
      </div>

      <DevicesFilters
        searchTerm={searchTerm}
        filterVendor={filterVendor}
        filterType={filterType}
        filterStatus={filterStatus}
        filterLocation={filterLocation}
        filterTags={filterTags}
        vendors={vendors}
        deviceTypes={deviceTypes}
        onSearchTermChange={setSearchTerm}
        onFilterVendorChange={setFilterVendor}
        onFilterTypeChange={setFilterType}
        onFilterStatusChange={setFilterStatus}
        onFilterLocationChange={setFilterLocation}
        onFilterTagsChange={setFilterTags}
        onClearFilters={clearFilters}
      />

      {filteredDevices.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🖥️</div>
          <h3>{t('devices.no_devices')}</h3>
          {/* devices is now the server-filtered result itself (see
              loadDevices), so an empty list here can mean either "no
              devices at all" or "none match the current filters" —
              hasActiveFilters is what tells those two apart. */}
          <p>{hasActiveFilters ? t('devices.adjust_filters') : t('devices.add_first_device')}</p>
          {!hasActiveFilters && (
            <button onClick={handleAddDevice} className="btn-primary">
              {t('devices.add_device')}
            </button>
          )}
        </div>
      ) : (
        <DevicesTable
          devices={filteredDevices}
          isAdmin={isAdmin}
          selectedDevices={selectedDevices}
          sortField={sortField}
          sortDirection={sortDirection}
          onSort={handleSort}
          onSelectDevice={handleSelectDevice}
          onSelectAll={handleSelectAll}
          onBackupNow={handleBackupNow}
          onEditDevice={handleEditDevice}
          onTestConnection={handleTestConnection}
          onDeleteDevice={handleDeleteDevice}
        />
      )}

      <DevicesPagination
        currentPage={currentPage}
        totalPages={totalPages}
        pageSize={pageSize}
        totalCount={totalCount}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />

      <DeviceFormModal
        isOpen={showModal}
        editingDevice={editingDevice}
        vendors={vendors}
        deviceTypes={deviceTypes}
        onClose={() => setShowModal(false)}
        onSaved={handleDeviceSaved}
      />

      <ImportCsvModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onImported={loadDevices}
      />

      {showBulkTagModal && (
        <BulkTagEditModal
          deviceCount={selectedDevices.size}
          saving={bulkTagSaving}
          onClose={() => setShowBulkTagModal(false)}
          onSubmit={handleBulkTagEdit}
        />
      )}
    </div>
  );
};

export default DevicesListPage;
