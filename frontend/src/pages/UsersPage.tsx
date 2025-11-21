import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import apiService from '../services/api.service';
import '../styles/Devices.css';

interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  is_ldap_user: boolean;
  two_factor_enabled: boolean;
  date_joined: string;
  last_login: string | null;
}

const UsersPage: React.FC = () => {
  const { t } = useTranslation();
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    first_name: '',
    last_name: '',
    role: 'viewer',
    password: '',
    is_active: true
  });

  // Check if current user is administrator
  const isAdmin = currentUser?.role === 'administrator';

  useEffect(() => {
    if (isAdmin) {
      loadUsers();
    }
  }, [isAdmin]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const data = await apiService.users.list();
      // Handle both paginated and non-paginated responses
      setUsers(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      console.error('Error loading users:', error);
      alert(t('common.error') + ': ' + t('users.failed_load'));
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = () => {
    setEditingUser(null);
    setFormData({
      email: '',
      username: '',
      first_name: '',
      last_name: '',
      role: 'viewer',
      password: '',
      is_active: true
    });
    setShowModal(true);
  };

  const handleEditUser = (user: User) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      username: user.username,
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      password: '',
      is_active: user.is_active
    });
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      if (editingUser) {
        // Update user
        const updateData: any = {
          first_name: formData.first_name,
          last_name: formData.last_name,
          role: formData.role,
          is_active: formData.is_active
        };
        if (formData.password) {
          updateData.password = formData.password;
        }
        await apiService.users.update(editingUser.id, updateData);
        alert(t('common.success') + ': ' + t('users.user_updated'));
      } else {
        // Create user
        if (!formData.password) {
          alert(t('users.password_required'));
          return;
        }
        await apiService.users.create(formData);
        alert(t('common.success') + ': ' + t('users.user_created'));
      }

      setShowModal(false);
      loadUsers();
    } catch (error: any) {
      console.error('Error saving user:', error);
      alert(t('common.error') + ': ' + (error.response?.data?.detail || t('users.failed_save')));
    }
  };

  const handleDeleteUser = async (user: User) => {
    if (user.id === currentUser?.id) {
      alert(t('users.cannot_delete_self'));
      return;
    }

    if (!window.confirm(`${t('users.confirm_delete')} ${user.email}?`)) {
      return;
    }

    try {
      await apiService.users.delete(user.id);
      alert(t('common.success') + ': ' + t('users.user_deleted'));
      loadUsers();
    } catch (error) {
      console.error('Error deleting user:', error);
      alert(t('common.error') + ': ' + t('users.failed_delete'));
    }
  };

  const getRoleBadgeClass = (role: string) => {
    switch (role) {
      case 'administrator': return 'badge-danger';
      case 'operator': return 'badge-primary';
      case 'auditor': return 'badge-warning';
      default: return 'badge-secondary';
    }
  };

  if (!isAdmin) {
    return (
      <div className="devices-page">
        <div className="empty-state">
          <h3>{t('users.access_denied')}</h3>
          <p>{t('users.no_permission')}</p>
        </div>
      </div>
    );
  }

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
        <h1>👥 {t('users.management')}</h1>
        <button onClick={handleCreateUser} className="btn-primary">
          ➕ {t('users.create_user')}
        </button>
      </div>

      <div className="devices-grid">
        {users.map((user) => (
          <div key={user.id} className="device-card">
            <div className="device-header">
              <div>
                <h3 className="device-name">
                  {user.first_name} {user.last_name}
                  {user.is_ldap_user && <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: 'var(--info-color)' }}>🔗 LDAP</span>}
                  {user.two_factor_enabled && <span style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: 'var(--success-color)' }}>🔒 2FA</span>}
                </h3>
                <p className="device-ip">{user.email}</p>
              </div>
              <span className={`badge ${getRoleBadgeClass(user.role)}`}>
                {user.role}
              </span>
            </div>

            <div className="device-body">
              <div className="device-info">
                <div className="info-row">
                  <span className="info-label">{t('users.username')}:</span>
                  <span className="info-value">{user.username}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">{t('users.status')}:</span>
                  <span className={`badge ${user.is_active ? 'badge-success' : 'badge-secondary'}`} style={{ marginLeft: '4px' }}>
                    {user.is_active ? t('users.active') : t('users.inactive')}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">{t('users.joined')}:</span>
                  <span className="info-value">{new Date(user.date_joined).toLocaleDateString()}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">{t('users.last_login')}:</span>
                  <span className="info-value">
                    {user.last_login ? new Date(user.last_login).toLocaleString() : t('users.never')}
                  </span>
                </div>
              </div>
            </div>

            <div className="device-footer">
              <button
                onClick={() => handleEditUser(user)}
                className="btn-sm btn-primary"
                disabled={user.is_ldap_user}
                title={user.is_ldap_user ? t('users.ldap_managed') : ''}
              >
                ✏️ {t('common.edit')}
              </button>
              <button
                onClick={() => handleDeleteUser(user)}
                className="btn-sm btn-danger"
                disabled={user.id === currentUser?.id || user.is_ldap_user}
              >
                🗑️ {t('common.delete')}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Create/Edit User Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingUser ? t('users.edit_user') : t('users.create_user')}</h2>
              <button onClick={() => setShowModal(false)} className="btn-close">✕</button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-row">
                  <div className="form-group">
                    <label>{t('users.email')} *</label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({...formData, email: e.target.value})}
                      required
                      disabled={!!editingUser}
                    />
                  </div>

                  <div className="form-group">
                    <label>{t('users.username')} *</label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => setFormData({...formData, username: e.target.value})}
                      required
                      disabled={!!editingUser}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>{t('users.first_name')}</label>
                    <input
                      type="text"
                      value={formData.first_name}
                      onChange={(e) => setFormData({...formData, first_name: e.target.value})}
                    />
                  </div>

                  <div className="form-group">
                    <label>{t('users.last_name')}</label>
                    <input
                      type="text"
                      value={formData.last_name}
                      onChange={(e) => setFormData({...formData, last_name: e.target.value})}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>{t('users.role')} *</label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({...formData, role: e.target.value})}
                    required
                  >
                    <option value="viewer">{t('users.role_viewer')}</option>
                    <option value="operator">{t('users.role_operator')}</option>
                    <option value="auditor">{t('users.role_auditor')}</option>
                    <option value="administrator">{t('users.role_administrator')}</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>{t('users.password')} {editingUser && t('users.password_optional')}</label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    required={!editingUser}
                    minLength={8}
                    placeholder={editingUser ? t('users.password_placeholder') : ''}
                  />
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({...formData, is_active: e.target.checked})}
                    />
                    {t('users.active')}
                  </label>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                  {t('common.cancel')}
                </button>
                <button type="submit" className="btn-primary">
                  {editingUser ? t('common.edit') : t('common.add')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UsersPage;
