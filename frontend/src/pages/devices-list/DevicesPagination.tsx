import React from 'react';
import { useTranslation } from 'react-i18next';

interface DevicesPaginationProps {
  currentPage: number;
  totalPages: number;
  pageSize: number;
  totalCount: number;
  filteredCount: number;
  totalDeviceCount: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

const DevicesPagination: React.FC<DevicesPaginationProps> = ({
  currentPage, totalPages, pageSize, totalCount, filteredCount, totalDeviceCount,
  onPageChange, onPageSizeChange,
}) => {
  const { t } = useTranslation();

  return (
    <div className="pagination-container" style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '1rem',
      backgroundColor: 'var(--card-bg)',
      borderRadius: '8px',
      marginTop: '1rem',
      flexWrap: 'wrap',
      gap: '1rem'
    }}>
      <div className="pagination-info" style={{ color: 'var(--text-secondary)' }}>
        {t('devices.showing')} {Math.min((currentPage - 1) * pageSize + 1, totalCount)}-{Math.min(currentPage * pageSize, totalCount)} {t('devices.of')} {totalCount}
        {filteredCount !== totalDeviceCount && ` (${t('devices.filtered')}: ${filteredCount})`}
      </div>

      <div className="pagination-controls" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          className="btn-sm btn-secondary"
          title={t('devices.first_page')}
        >
          ««
        </button>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="btn-sm btn-secondary"
          title={t('devices.prev_page')}
        >
          «
        </button>

        <span style={{ padding: '0 1rem', fontWeight: 500 }}>
          {currentPage} / {totalPages || 1}
        </span>

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="btn-sm btn-secondary"
          title={t('devices.next_page')}
        >
          »
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage >= totalPages}
          className="btn-sm btn-secondary"
          title={t('devices.last_page')}
        >
          »»
        </button>
      </div>

      <div className="page-size-selector" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <label style={{ color: 'var(--text-secondary)' }}>{t('devices.per_page')}:</label>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="filter-select"
          style={{ width: 'auto', minWidth: '70px' }}
        >
          <option value={20}>20</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
      </div>
    </div>
  );
};

export default DevicesPagination;
