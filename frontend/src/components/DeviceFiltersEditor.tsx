import React from 'react';
import { useTranslation } from 'react-i18next';
import { Criticality, DeviceFilters } from '../types';

const CRITICALITY_OPTIONS: Criticality[] = ['low', 'medium', 'high', 'critical'];

interface Props {
  value: DeviceFilters;
  onChange: (value: DeviceFilters) => void;
}

/**
 * Editor for the {"tags": [...], "criticality": [...], ...} device_filters
 * shape shared by NotificationRule, CompliancePolicy, and User.device_scope
 * (see backend/core/device_filters.py) — one widget, since all three mean
 * exactly the same thing: "which devices does this apply to".
 *
 * Covers the two most commonly used keys (tags, criticality) directly;
 * vendor_id/device_type_id/location are supported by the backend but not
 * exposed here yet — still settable via the API directly if needed.
 */
const DeviceFiltersEditor: React.FC<Props> = ({ value, onChange }) => {
  const { t } = useTranslation();

  const tags: string[] = Array.isArray(value.tags) ? value.tags : [];
  const criticality: string[] = Array.isArray(value.criticality)
    ? value.criticality
    : value.criticality ? [value.criticality] : [];

  const updateTags = (raw: string) => {
    const next = { ...value };
    const parsed = raw.split(',').map((s) => s.trim()).filter(Boolean);
    if (parsed.length) {
      next.tags = parsed;
    } else {
      delete next.tags;
    }
    onChange(next);
  };

  const toggleCriticality = (level: string, checked: boolean) => {
    const next = { ...value };
    const current = new Set(criticality);
    if (checked) {
      current.add(level);
    } else {
      current.delete(level);
    }
    if (current.size) {
      next.criticality = Array.from(current);
    } else {
      delete next.criticality;
    }
    onChange(next);
  };

  const isEmpty = Object.keys(value || {}).length === 0;

  return (
    <div className="device-filters-editor">
      <div className="form-group">
        <label>{t('deviceFilters.tags')}</label>
        <input
          type="text"
          value={tags.join(', ')}
          onChange={(e) => updateTags(e.target.value)}
          placeholder={t('deviceFilters.tags_placeholder')}
        />
      </div>

      <div className="form-group">
        <label>{t('deviceFilters.criticality')}</label>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          {CRITICALITY_OPTIONS.map((level) => (
            <label key={level} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 400 }}>
              <input
                type="checkbox"
                checked={criticality.includes(level)}
                onChange={(e) => toggleCriticality(level, e.target.checked)}
              />
              {t(`devices.criticality_${level}`, level)}
            </label>
          ))}
        </div>
      </div>

      <small style={{ color: 'var(--text-secondary)', display: 'block' }}>
        {isEmpty ? t('deviceFilters.empty_means_all') : t('deviceFilters.and_combined')}
      </small>
    </div>
  );
};

export default DeviceFiltersEditor;
