import React from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import { extractErrorMessage } from '../utils/extractErrorMessage';
import { useToast } from '../contexts/ToastContext';
import { useListResource } from '../hooks/useListResource';
import { useModalForm } from '../hooks/useModalForm';
import DeviceFiltersEditor from './DeviceFiltersEditor';
import { CompliancePolicy, ComplianceRule, ComplianceSeverity, DeviceFilters } from '../types';
import '../styles/Devices.css';

const SEVERITIES: ComplianceSeverity[] = ['low', 'medium', 'high', 'critical'];

const EMPTY_RULE: ComplianceRule = { type: 'must_not_contain', pattern: '', is_regex: false, description: '' };

const DEFAULT_FORM_DATA = {
  name: '',
  description: '',
  is_active: true,
  severity: 'medium' as ComplianceSeverity,
  device_filters: {} as DeviceFilters,
  rules: [{ ...EMPTY_RULE }] as ComplianceRule[],
};

const SEVERITY_BADGE: Record<ComplianceSeverity, string> = {
  low: 'badge-secondary',
  medium: 'badge-info',
  high: 'badge-warning',
  critical: 'badge-danger',
};

const CompliancePolicies: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();

  const { items: policies, loading, reload } = useListResource<CompliancePolicy>(
    () => apiService.compliancePolicies.list(),
    () => toast.error(t('compliance.failed_load'))
  );

  const {
    showModal, editing, formData, setFormData, openCreate, openEdit, close,
  } = useModalForm<CompliancePolicy, typeof DEFAULT_FORM_DATA>(DEFAULT_FORM_DATA, (policy) => ({
    name: policy.name,
    description: policy.description,
    is_active: policy.is_active,
    severity: policy.severity,
    device_filters: policy.device_filters || {},
    rules: policy.rules && policy.rules.length ? policy.rules : [{ ...EMPTY_RULE }],
  }));

  const updateRule = (index: number, patch: Partial<ComplianceRule>) => {
    const rules = formData.rules.map((r, i) => (i === index ? { ...r, ...patch } : r));
    setFormData({ ...formData, rules });
  };

  const addRule = () => setFormData({ ...formData, rules: [...formData.rules, { ...EMPTY_RULE }] });
  const removeRule = (index: number) => {
    if (formData.rules.length <= 1) return;
    setFormData({ ...formData, rules: formData.rules.filter((_, i) => i !== index) });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        rules: formData.rules.filter((r) => r.pattern.trim() !== ''),
      };
      if (editing) {
        await apiService.compliancePolicies.update(editing.id, payload);
        toast.success(t('compliance.policy_updated'));
      } else {
        await apiService.compliancePolicies.create(payload);
        toast.success(t('compliance.policy_created'));
      }
      close();
      reload();
    } catch (error) {
      logger.error('Error saving compliance policy:', error);
      toast.error(extractErrorMessage(error, t('compliance.failed_save')));
    }
  };

  const handleDelete = async (policy: CompliancePolicy) => {
    if (!window.confirm(`${t('compliance.confirm_delete')} "${policy.name}"?`)) return;
    try {
      await apiService.compliancePolicies.delete(policy.id);
      toast.success(t('compliance.policy_deleted'));
      reload();
    } catch (error) {
      logger.error('Error deleting compliance policy:', error);
      toast.error(t('compliance.failed_delete'));
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>{t('common.loading')}</p>
      </div>
    );
  }

  return (
    <div className="schedules-section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2>✅ {t('compliance.policies_title')}</h2>
        <button onClick={openCreate} className="btn-primary">
          ➕ {t('compliance.create')}
        </button>
      </div>

      {policies.length === 0 ? (
        <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="empty-icon">✅</div>
          <h3>{t('compliance.no_policies')}</h3>
          <p>{t('compliance.create_first')}</p>
        </div>
      ) : (
        <div className="devices-grid">
          {policies.map((policy) => (
            <div key={policy.id} className="device-card">
              <div className="device-header">
                <div>
                  <h3 className="device-name">{policy.name}</h3>
                  {policy.description && (
                    <p className="device-ip" style={{ fontSize: '0.875rem' }}>{policy.description}</p>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <span className={`badge ${SEVERITY_BADGE[policy.severity]}`}>
                    {t(`compliance.severities.${policy.severity}`)}
                  </span>
                  <span className={`badge ${policy.is_active ? 'badge-success' : 'badge-secondary'}`}>
                    {policy.is_active ? t('notificationRules.is_active') : t('notificationRules.inactive')}
                  </span>
                  {policy.open_violation_count > 0 && (
                    <span className="badge badge-danger">
                      {t('compliance.open_count', { count: policy.open_violation_count })}
                    </span>
                  )}
                </div>
              </div>

              <div className="device-body">
                <div className="device-info">
                  <div className="info-row">
                    <span className="info-label">{t('compliance.rules_count')}:</span>
                    <span className="info-value">{policy.rules?.length || 0}</span>
                  </div>
                  {policy.rules?.slice(0, 3).map((rule, i) => (
                    <div key={i} className="info-row">
                      <span className="info-label">{t(`compliance.rule_types.${rule.type}`)}:</span>
                      <span className="info-value" style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{rule.pattern}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="device-footer">
                <button onClick={() => openEdit(policy)} className="btn-sm btn-primary" title={t('common.edit')}>✏️</button>
                <button onClick={() => handleDelete(policy)} className="btn-sm btn-danger" title={t('common.delete')}>🗑️</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => close()}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
            <div className="modal-header">
              <h2>{editing ? t('compliance.edit') : t('compliance.create')}</h2>
              <button onClick={() => close()} className="btn-close">✕</button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label>{t('compliance.name')} *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>{t('compliance.description')}</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={2}
                  />
                </div>

                <div className="form-group">
                  <label>{t('compliance.severity')}</label>
                  <select
                    value={formData.severity}
                    onChange={(e) => setFormData({ ...formData, severity: e.target.value as ComplianceSeverity })}
                  >
                    {SEVERITIES.map((s) => (
                      <option key={s} value={s}>{t(`compliance.severities.${s}`)}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label>{t('compliance.rules_title')} *</label>
                  {formData.rules.map((rule, i) => (
                    <div
                      key={i}
                      style={{
                        border: '1px solid var(--border-color)', borderRadius: '8px',
                        padding: '0.75rem', marginBottom: '0.75rem',
                      }}
                    >
                      <div className="form-row">
                        <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                          <label>{t('compliance.rule_type')}</label>
                          <select
                            value={rule.type}
                            onChange={(e) => updateRule(i, { type: e.target.value as ComplianceRule['type'] })}
                          >
                            <option value="must_not_contain">{t('compliance.rule_types.must_not_contain')}</option>
                            <option value="must_contain">{t('compliance.rule_types.must_contain')}</option>
                          </select>
                        </div>
                        <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <input
                              type="checkbox"
                              checked={!!rule.is_regex}
                              onChange={(e) => updateRule(i, { is_regex: e.target.checked })}
                            />
                            {t('compliance.is_regex')}
                          </label>
                        </div>
                      </div>
                      <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                        <label>{t('compliance.pattern')} *</label>
                        <input
                          type="text"
                          value={rule.pattern}
                          onChange={(e) => updateRule(i, { pattern: e.target.value })}
                          placeholder={rule.is_regex ? 'community\\s+public' : 'transport input telnet'}
                          style={{ fontFamily: 'monospace' }}
                          required
                        />
                      </div>
                      <div className="form-group" style={{ marginBottom: 0 }}>
                        <label>{t('compliance.rule_description')}</label>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <input
                            type="text"
                            value={rule.description || ''}
                            onChange={(e) => updateRule(i, { description: e.target.value })}
                            placeholder={t('compliance.rule_description_placeholder')}
                            style={{ flex: 1 }}
                          />
                          <button
                            type="button"
                            onClick={() => removeRule(i)}
                            className="btn-sm btn-danger"
                            disabled={formData.rules.length <= 1}
                            title={t('common.delete')}
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                  <button type="button" onClick={addRule} className="btn-secondary btn-sm">
                    ➕ {t('compliance.add_rule')}
                  </button>
                </div>

                <div className="form-group">
                  <label>{t('notificationRules.device_filters')}</label>
                  <DeviceFiltersEditor
                    value={formData.device_filters}
                    onChange={(v) => setFormData({ ...formData, device_filters: v })}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    />
                    {t('notificationRules.is_active')}
                  </label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => close()} className="btn-secondary">
                  {t('common.cancel')}
                </button>
                <button type="submit" className="btn-primary">
                  {editing ? t('common.edit') : t('common.add')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CompliancePolicies;
