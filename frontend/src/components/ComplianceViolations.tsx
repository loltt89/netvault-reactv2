import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import { extractErrorMessage } from '../utils/extractErrorMessage';
import { useToast } from '../contexts/ToastContext';
import { useListResource } from '../hooks/useListResource';
import { ComplianceViolation, ComplianceStatistics, ComplianceSeverity } from '../types';
import '../styles/Devices.css';

const SEVERITY_BADGE: Record<ComplianceSeverity, string> = {
  low: 'badge-secondary',
  medium: 'badge-info',
  high: 'badge-warning',
  critical: 'badge-danger',
};

const ComplianceViolations: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState<'open' | 'resolved' | ''>('open');
  const [stats, setStats] = useState<ComplianceStatistics | null>(null);

  const { items: violations, loading, reload } = useListResource<ComplianceViolation>(
    () => apiService.complianceViolations.list(statusFilter ? { status: statusFilter } : undefined),
    () => toast.error(t('compliance.failed_load'))
  );

  // useListResource only fetches on mount — its `load` is memoized with an
  // empty dep array, so a statusFilter change alone wouldn't trigger a
  // refetch without this explicit reload().
  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  const loadStats = useCallback(async () => {
    try {
      const data = await apiService.complianceViolations.statistics();
      setStats(data);
    } catch (error) {
      logger.error('Error loading compliance statistics:', error);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats, violations.length]);

  const handleAcknowledge = async (violation: ComplianceViolation) => {
    try {
      await apiService.complianceViolations.acknowledge(violation.id);
      toast.success(t('compliance.acknowledged'));
      reload();
      loadStats();
    } catch (error) {
      logger.error('Error acknowledging violation:', error);
      toast.error(extractErrorMessage(error, t('compliance.failed_acknowledge')));
    }
  };

  return (
    <div className="schedules-section">
      <h2 style={{ marginBottom: '1rem' }}>⚠️ {t('compliance.violations_title')}</h2>

      {stats && (
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
          <div className="info-card" style={{ padding: '1rem', minWidth: '140px' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{stats.open_total}</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{t('compliance.open_total')}</div>
          </div>
          <div className="info-card" style={{ padding: '1rem', minWidth: '140px' }}>
            <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{stats.affected_devices}</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{t('compliance.affected_devices')}</div>
          </div>
          {(['critical', 'high', 'medium', 'low'] as ComplianceSeverity[]).map((sev) => (
            stats.by_severity[sev] > 0 && (
              <div key={sev} className="info-card" style={{ padding: '1rem', minWidth: '140px' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{stats.by_severity[sev]}</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  <span className={`badge ${SEVERITY_BADGE[sev]}`}>{t(`compliance.severities.${sev}`)}</span>
                </div>
              </div>
            )
          ))}
        </div>
      )}

      <div className="form-group" style={{ maxWidth: '250px', marginBottom: '1rem' }}>
        <label>{t('compliance.filter_status')}</label>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as 'open' | 'resolved' | '')}>
          <option value="open">{t('compliance.status_open')}</option>
          <option value="resolved">{t('compliance.status_resolved')}</option>
          <option value="">{t('compliance.status_all')}</option>
        </select>
      </div>

      {loading ? (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      ) : violations.length === 0 ? (
        <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="empty-icon">✅</div>
          <h3>{t('compliance.no_violations')}</h3>
        </div>
      ) : (
        <div className="table-container" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--hover-bg)', borderBottom: '2px solid var(--border-color)' }}>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('compliance.device')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('compliance.policies_title')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('compliance.rule_description')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('compliance.severity')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('compliance.detected_at')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('compliance.status')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}></th>
              </tr>
            </thead>
            <tbody>
              {violations.map((v) => (
                <tr key={v.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '1rem' }}>
                    <div style={{ fontWeight: 500 }}>{v.device_name}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{v.device_ip}</div>
                  </td>
                  <td style={{ padding: '1rem' }}>{v.policy_name}</td>
                  <td style={{ padding: '1rem' }}>{v.rule_description}</td>
                  <td style={{ padding: '1rem' }}>
                    <span className={`badge ${SEVERITY_BADGE[v.policy_severity]}`}>
                      {t(`compliance.severities.${v.policy_severity}`)}
                    </span>
                  </td>
                  <td style={{ padding: '1rem', fontSize: '0.85rem' }}>{new Date(v.detected_at).toLocaleString()}</td>
                  <td style={{ padding: '1rem' }}>
                    <span className={`badge ${v.status === 'open' ? 'badge-danger' : 'badge-success'}`}>
                      {t(`compliance.status_${v.status}`)}
                    </span>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    {v.status === 'open' && (
                      <button onClick={() => handleAcknowledge(v)} className="btn-sm btn-secondary">
                        {t('compliance.acknowledge')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ComplianceViolations;
