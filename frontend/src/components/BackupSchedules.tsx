import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import '../styles/Devices.css';

interface BackupSchedule {
  id: number;
  name: string;
  description: string;
  frequency: string;
  run_time: string | null;
  run_days: string;
  is_active: boolean;
  last_run: string | null;
  next_run: string | null;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
}

const BackupSchedulesComponent: React.FC = () => {
  const { t } = useTranslation();
  const [schedules, setSchedules] = useState<BackupSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<BackupSchedule | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    frequency: 'daily',
    run_time: '02:00',
    run_days: '',
    is_active: true
  });

  useEffect(() => {
    loadSchedules();
  }, []);

  const loadSchedules = async () => {
    try {
      setLoading(true);
      const data = await apiService.backupSchedules.list();
      setSchedules(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      logger.error('Error loading schedules:', error);
      alert(t('common.error') + ': ' + t('schedules.failed_load'));
    } finally {
      setLoading(false);
    }
  };


  const handleCreate = () => {
    setEditingSchedule(null);
    setFormData({
      name: '',
      description: '',
      frequency: 'daily',
      run_time: '02:00',
      run_days: '',
      is_active: true
    });
    setShowModal(true);
  };

  const handleEdit = (schedule: BackupSchedule) => {
    setEditingSchedule(schedule);
    setFormData({
      name: schedule.name,
      description: schedule.description,
      frequency: schedule.frequency,
      run_time: schedule.run_time || '02:00',
      run_days: schedule.run_days || '',
      is_active: schedule.is_active
    });
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const scheduleData: any = {
        name: formData.name,
        description: formData.description,
        frequency: formData.frequency,
        is_active: formData.is_active
      };

      if (formData.frequency !== 'hourly') {
        if (!formData.run_time) {
          alert(t('schedules.time_required'));
          return;
        }
        scheduleData.run_time = formData.run_time;
      }

      if (formData.frequency === 'weekly' && formData.run_days) {
        scheduleData.run_days = formData.run_days;
      }

      if (editingSchedule) {
        await apiService.backupSchedules.update(editingSchedule.id, scheduleData);
        alert(t('common.success') + ': ' + t('schedules.schedule_updated'));
      } else {
        await apiService.backupSchedules.create(scheduleData);
        alert(t('common.success') + ': ' + t('schedules.schedule_created'));
      }

      setShowModal(false);
      loadSchedules();
    } catch (error: any) {
      logger.error('Error saving schedule:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.detail || t('schedules.failed_save')));
    }
  };

  const handleDelete = async (schedule: BackupSchedule) => {
    if (!window.confirm(`${t('schedules.confirm_delete')} "${schedule.name}"?`)) {
      return;
    }

    try {
      await apiService.backupSchedules.delete(schedule.id);
      alert(t('common.success') + ': ' + t('schedules.schedule_deleted'));
      loadSchedules();
    } catch (error) {
      logger.error('Error deleting schedule:', error);
      alert(t('common.error') + ': ' + t('schedules.failed_delete'));
    }
  };

  const handleToggleActive = async (schedule: BackupSchedule) => {
    try {
      await apiService.backupSchedules.toggleActive(schedule.id);
      alert(t('common.success') + ': ' + t('schedules.schedule_toggled'));
      loadSchedules();
    } catch (error) {
      logger.error('Error toggling schedule:', error);
      alert(t('common.error') + ': ' + t('schedules.failed_toggle'));
    }
  };

  const handleRunNow = async (schedule: BackupSchedule) => {
    try {
      await apiService.backupSchedules.runNow(schedule.id);
      alert(t('common.success') + ': ' + t('schedules.schedule_running'));
    } catch (error) {
      logger.error('Error running schedule:', error);
      alert(t('common.error') + ': ' + t('schedules.failed_run'));
    }
  };

  const getFrequencyBadgeClass = (frequency: string) => {
    switch (frequency) {
      case 'hourly': return 'badge-info';
      case 'daily': return 'badge-primary';
      case 'weekly': return 'badge-success';
      case 'monthly': return 'badge-warning';
      default: return 'badge-secondary';
    }
  };

  const weekDays = [
    { value: '0', label: t('schedules.monday') },
    { value: '1', label: t('schedules.tuesday') },
    { value: '2', label: t('schedules.wednesday') },
    { value: '3', label: t('schedules.thursday') },
    { value: '4', label: t('schedules.friday') },
    { value: '5', label: t('schedules.saturday') },
    { value: '6', label: t('schedules.sunday') },
  ];

  const handleDayToggle = (dayValue: string) => {
    const days = formData.run_days ? formData.run_days.split(',') : [];
    if (days.includes(dayValue)) {
      setFormData({
        ...formData,
        run_days: days.filter(d => d !== dayValue).join(',')
      });
    } else {
      setFormData({
        ...formData,
        run_days: [...days, dayValue].sort().join(',')
      });
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
        <h2>📅 {t('schedules.title')}</h2>
        <button onClick={handleCreate} className="btn-primary">
          ➕ {t('schedules.create')}
        </button>
      </div>

      {schedules.length === 0 ? (
        <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="empty-icon">📅</div>
          <h3>{t('schedules.no_schedules')}</h3>
          <p>{t('schedules.create_first')}</p>
        </div>
      ) : (
        <div className="devices-grid">
          {schedules.map((schedule) => (
            <div key={schedule.id} className="device-card">
              <div className="device-header">
                <div>
                  <h3 className="device-name">{schedule.name}</h3>
                  {schedule.description && (
                    <p className="device-ip" style={{ fontSize: '0.875rem' }}>{schedule.description}</p>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span className={`badge ${getFrequencyBadgeClass(schedule.frequency)}`}>
                    {t(`schedules.frequency_${schedule.frequency}`)}
                  </span>
                  <span className={`badge ${schedule.is_active ? 'badge-success' : 'badge-secondary'}`}>
                    {schedule.is_active ? t('schedules.is_active') : 'Inactive'}
                  </span>
                </div>
              </div>

              <div className="device-body">
                <div className="device-info">
                  {schedule.run_time && (
                    <div className="info-row">
                      <span className="info-label">{t('schedules.run_time')}:</span>
                      <span className="info-value">{schedule.run_time}</span>
                    </div>
                  )}
                  <div className="info-row">
                    <span className="info-label">{t('schedules.last_run')}:</span>
                    <span className="info-value">
                      {schedule.last_run ? new Date(schedule.last_run).toLocaleString() : t('users.never')}
                    </span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">{t('schedules.total_runs')}:</span>
                    <span className="info-value">
                      {schedule.total_runs} ({schedule.successful_runs} / {schedule.failed_runs})
                    </span>
                  </div>
                </div>
              </div>

              <div className="device-footer">
                <button
                  onClick={() => handleEdit(schedule)}
                  className="btn-sm btn-primary"
                  title={t('common.edit')}
                >
                  ✏️
                </button>
                <button
                  onClick={() => handleToggleActive(schedule)}
                  className={`btn-sm ${schedule.is_active ? 'btn-warning' : 'btn-success'}`}
                  title={t('schedules.toggle_status')}
                >
                  {schedule.is_active ? '⏸️' : '▶️'}
                </button>
                <button
                  onClick={() => handleRunNow(schedule)}
                  className="btn-sm btn-info"
                  title={t('schedules.run_now')}
                >
                  ▶️
                </button>
                <button
                  onClick={() => handleDelete(schedule)}
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

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <h2>{editingSchedule ? t('schedules.edit') : t('schedules.create')}</h2>
              <button onClick={() => setShowModal(false)} className="btn-close">✕</button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label>{t('schedules.name')} *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>{t('schedules.description')}</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                    rows={2}
                  />
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>{t('schedules.frequency')} *</label>
                    <select
                      value={formData.frequency}
                      onChange={(e) => setFormData({...formData, frequency: e.target.value})}
                      required
                    >
                      <option value="hourly">{t('schedules.frequency_hourly')}</option>
                      <option value="daily">{t('schedules.frequency_daily')}</option>
                      <option value="weekly">{t('schedules.frequency_weekly')}</option>
                      <option value="monthly">{t('schedules.frequency_monthly')}</option>
                    </select>
                  </div>

                  {formData.frequency !== 'hourly' && (
                    <div className="form-group">
                      <label>{t('schedules.run_time')} *</label>
                      <input
                        type="time"
                        value={formData.run_time}
                        onChange={(e) => setFormData({...formData, run_time: e.target.value})}
                        required
                      />
                    </div>
                  )}
                </div>

                {formData.frequency === 'weekly' && (
                  <div className="form-group">
                    <label>{t('schedules.run_days')}</label>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
                      {weekDays.map((day) => {
                        const isSelected = formData.run_days.split(',').includes(day.value);
                        return (
                          <button
                            key={day.value}
                            type="button"
                            onClick={() => handleDayToggle(day.value)}
                            className={`btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                            style={{ minWidth: '80px' }}
                          >
                            {day.label.substring(0, 3)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="form-group">
                  <div style={{
                    padding: '1rem',
                    backgroundColor: 'var(--card-bg)',
                    borderRadius: '4px',
                    border: '1px solid var(--border-color)'
                  }}>
                    <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                      ℹ️ {t('schedules.auto_backup_info')}
                    </p>
                  </div>
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                    />
                    {t('schedules.is_active')}
                  </label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                  {t('common.cancel')}
                </button>
                <button type="submit" className="btn-primary">
                  {editingSchedule ? t('common.edit') : t('common.add')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default BackupSchedulesComponent;
