import React from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import { useToast } from '../contexts/ToastContext';
import { useListResource } from '../hooks/useListResource';
import { Notification } from '../types';
import '../styles/Devices.css';

const STATUS_BADGE: Record<string, string> = {
  sent: 'badge-success',
  failed: 'badge-danger',
  pending: 'badge-secondary',
};

const NotificationLog: React.FC = () => {
  const { t } = useTranslation();
  const toast = useToast();

  const { items: log, loading } = useListResource<Notification>(
    () => apiService.notificationLog.list(),
    () => toast.error(t('notificationRules.log.failed_load'))
  );

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
      <h2 style={{ marginBottom: '1.5rem' }}>📜 {t('notificationRules.log.title')}</h2>

      {log.length === 0 ? (
        <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="empty-icon">📜</div>
          <h3>{t('notificationRules.log.empty')}</h3>
        </div>
      ) : (
        <div className="table-container" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--hover-bg)', borderBottom: '2px solid var(--border-color)' }}>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('notificationRules.log.rule')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('notificationRules.channel')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('notificationRules.log.recipient')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('notificationRules.log.status')}</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>{t('notificationRules.log.sent_at')}</th>
              </tr>
            </thead>
            <tbody>
              {log.map((entry) => (
                <tr key={entry.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '1rem' }}>
                    {entry.rule_name || '—'}<br /><small style={{ color: 'var(--text-secondary)' }}>{entry.title}</small>
                  </td>
                  <td style={{ padding: '1rem' }}>{t(`notificationRules.channels.${entry.channel}`, entry.channel)}</td>
                  <td style={{ padding: '1rem', wordBreak: 'break-all' }}>{entry.recipient}</td>
                  <td style={{ padding: '1rem' }}>
                    <span className={`badge ${STATUS_BADGE[entry.status] || 'badge-secondary'}`}>
                      {t(`notificationRules.log.statuses.${entry.status}`, entry.status)}
                    </span>
                    {entry.status === 'failed' && entry.error_message && (
                      <div><small style={{ color: 'var(--danger)' }}>{entry.error_message}</small></div>
                    )}
                  </td>
                  <td style={{ padding: '1rem' }}>
                    {entry.sent_at ? new Date(entry.sent_at).toLocaleString() : new Date(entry.created_at).toLocaleString()}
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

export default NotificationLog;
