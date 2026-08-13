import React from 'react';
import { useTranslation } from 'react-i18next';

interface Vendor { id: number; name: string; }
interface DeviceType { id: number; name: string; }

interface DevicesFiltersProps {
  searchTerm: string;
  filterVendor: string;
  filterType: string;
  filterStatus: string;
  filterLocation: string;
  filterTags: string;
  vendors: Vendor[];
  deviceTypes: DeviceType[];
  onSearchTermChange: (value: string) => void;
  onFilterVendorChange: (value: string) => void;
  onFilterTypeChange: (value: string) => void;
  onFilterStatusChange: (value: string) => void;
  onFilterLocationChange: (value: string) => void;
  onFilterTagsChange: (value: string) => void;
  onClearFilters: () => void;
}

const DevicesFilters: React.FC<DevicesFiltersProps> = ({
  searchTerm, filterVendor, filterType, filterStatus, filterLocation, filterTags, vendors, deviceTypes,
  onSearchTermChange, onFilterVendorChange, onFilterTypeChange, onFilterStatusChange,
  onFilterLocationChange, onFilterTagsChange, onClearFilters,
}) => {
  const { t } = useTranslation();

  return (
    <div className="filters-section">
      <div className="filters-row">
        <input
          type="text"
          placeholder={t('common.search') + ' (name, IP, location)...'}
          value={searchTerm}
          onChange={(e) => onSearchTermChange(e.target.value)}
          className="search-input"
          style={{ flex: 2 }}
        />

        <select
          value={filterVendor}
          onChange={(e) => onFilterVendorChange(e.target.value)}
          className="filter-select"
        >
          <option value="">{t('devices.all_vendors')}</option>
          {vendors.map(vendor => (
            <option key={vendor.id} value={vendor.id}>{vendor.name}</option>
          ))}
        </select>

        <select
          value={filterType}
          onChange={(e) => onFilterTypeChange(e.target.value)}
          className="filter-select"
        >
          <option value="">{t('devices.all_types')}</option>
          {deviceTypes.map(type => (
            <option key={type.id} value={type.id}>{type.name}</option>
          ))}
        </select>

        <select
          value={filterStatus}
          onChange={(e) => onFilterStatusChange(e.target.value)}
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
          onChange={(e) => onFilterLocationChange(e.target.value)}
          className="search-input"
        />

        <input
          type="text"
          placeholder={t('devices.tags_filter_placeholder')}
          value={filterTags}
          onChange={(e) => onFilterTagsChange(e.target.value)}
          className="search-input"
        />

        <button onClick={onClearFilters} className="btn-secondary">
          ✕ {t('devices.clear_filters')}
        </button>
      </div>
    </div>
  );
};

export default DevicesFilters;
