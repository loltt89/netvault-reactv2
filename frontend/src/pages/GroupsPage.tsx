import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../services/api.service';
import '../styles/GroupsPage.css';

interface DeviceGroup {
  id: number;
  name: string;
  description: string;
  color: string;
  device_count: number;
}

const COLOR_OPTIONS = [
  { value: '#6366f1', name: 'Indigo' },
  { value: '#8b5cf6', name: 'Violet' },
  { value: '#ec4899', name: 'Pink' },
  { value: '#ef4444', name: 'Red' },
  { value: '#f97316', name: 'Orange' },
  { value: '#eab308', name: 'Yellow' },
  { value: '#22c55e', name: 'Green' },
  { value: '#14b8a6', name: 'Teal' },
  { value: '#3b82f6', name: 'Blue' },
  { value: '#64748b', name: 'Slate' },
];

const GroupsPage: React.FC = () => {
  const { t } = useTranslation();
  const [groups, setGroups] = useState<DeviceGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingGroup, setEditingGroup] = useState<DeviceGroup | null>(null);
  const [formData, setFormData] = useState({ name: '', description: '', color: '#6366f1' });

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      const response = await apiService.deviceGroups.list();
      setGroups(response.data.results || response.data);
    } catch (error) {
      console.error('Failed to load groups:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingGroup) {
        await apiService.deviceGroups.update(editingGroup.id, formData);
      } else {
        await apiService.deviceGroups.create(formData);
      }
      setShowModal(false);
      setEditingGroup(null);
      setFormData({ name: '', description: '', color: '#6366f1' });
      loadGroups();
    } catch (error) {
      console.error('Failed to save group:', error);
    }
  };

  const handleEdit = (group: DeviceGroup) => {
    setEditingGroup(group);
    setFormData({ name: group.name, description: group.description || '', color: group.color });
    setShowModal(true);
  };

  const handleDelete = async (group: DeviceGroup) => {
    if (group.device_count > 0) {
      alert(t('groups.has_devices'));
      return;
    }
    if (window.confirm(t('groups.confirm_delete'))) {
      try {
        await apiService.deviceGroups.delete(group.id);
        loadGroups();
      } catch (error) {
        console.error('Failed to delete group:', error);
      }
    }
  };

  const openCreateModal = () => {
    setEditingGroup(null);
    setFormData({ name: '', description: '', color: '#6366f1' });
    setShowModal(true);
  };

  if (loading) {
    return <div className="loading">{t('common.loading')}</div>;
  }

  return (
    <div className="groups-page">
      <div className="page-header">
        <h1>{t('groups.title')}</h1>
        <button className="btn btn-primary" onClick={openCreateModal}>
          {t('groups.add_group')}
        </button>
      </div>

      <div className="groups-grid">
        {groups.map((group) => (
          <div key={group.id} className="group-card">
            <div className="group-color" style={{ backgroundColor: group.color }} />
            <div className="group-info">
              <h3>{group.name}</h3>
              {group.description && <p>{group.description}</p>}
              <span className="device-count">
                {group.device_count} {t('groups.devices')}
              </span>
            </div>
            <div className="group-actions">
              <button className="btn btn-sm" onClick={() => handleEdit(group)}>
                {t('common.edit')}
              </button>
              <button
                className="btn btn-sm btn-danger"
                onClick={() => handleDelete(group)}
                disabled={group.device_count > 0}
              >
                {t('common.delete')}
              </button>
            </div>
          </div>
        ))}
        {groups.length === 0 && (
          <div className="no-groups">
            <p>{t('groups.no_groups')}</p>
          </div>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingGroup ? t('groups.edit_group') : t('groups.add_group')}</h2>
              <button className="close-btn" onClick={() => setShowModal(false)}>&times;</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>{t('groups.name')} *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>{t('groups.description')}</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="form-group">
                <label>{t('groups.color')}</label>
                <div className="color-picker">
                  {COLOR_OPTIONS.map((color) => (
                    <button
                      key={color.value}
                      type="button"
                      className={`color-option ${formData.color === color.value ? 'selected' : ''}`}
                      style={{ backgroundColor: color.value }}
                      onClick={() => setFormData({ ...formData, color: color.value })}
                      title={color.name}
                    />
                  ))}
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn" onClick={() => setShowModal(false)}>
                  {t('common.cancel')}
                </button>
                <button type="submit" className="btn btn-primary">
                  {t('common.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default GroupsPage;
