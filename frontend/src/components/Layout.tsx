import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import UserProfileModal from './UserProfileModal';
import TasksTable from './TasksTable';
import { useTaskSocket } from '../hooks/useTaskSocket';
import logger from '../utils/logger';
import '../styles/Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [isTasksPanelMinimized, setIsTasksPanelMinimized] = useState(true); // Start minimized

  // Real-time backup-log WebSocket connection (reconnect/backoff logic lives
  // in the hook — see hooks/useTaskSocket.ts). Only isConnected is rendered
  // today (passed to TasksTable); logs/showTerminal are tracked by the hook
  // for whenever the terminal UI they were meant to feed gets built.
  const { isConnected } = useTaskSocket();

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      logger.error('Logout error:', error);
    }
  };

  const isActive = (path: string) => {
    return location.pathname === path ? 'active' : '';
  };

  // Handle tasks panel minimize/maximize toggle
  const handleToggleTasksPanel = () => {
    setIsTasksPanelMinimized(!isTasksPanelMinimized);
  };

  return (
    <div className="layout">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>🔒 {t('app.name')}</h2>
        </div>

        <nav className="sidebar-nav">
          <Link to="/dashboard" className={`nav-item ${isActive('/dashboard')}`}>
            <span className="nav-icon">📊</span>
            <span className="nav-text">{t('dashboard.title')}</span>
          </Link>

          <Link to="/devices" className={`nav-item ${isActive('/devices')}`}>
            <span className="nav-icon">🖥️</span>
            <span className="nav-text">{t('devices.title')}</span>
          </Link>

          <Link to="/backups" className={`nav-item ${isActive('/backups')}`}>
            <span className="nav-icon">💾</span>
            <span className="nav-text">{t('backups.title')}</span>
          </Link>

          <Link to="/config-search" className={`nav-item ${isActive('/config-search')}`}>
            <span className="nav-icon">🔍</span>
            <span className="nav-text">{t('config_search.nav_title')}</span>
          </Link>

          <Link to="/backup-management" className={`nav-item ${isActive('/backup-management')}`}>
            <span className="nav-icon">📅</span>
            <span className="nav-text">{t('backup_management.nav_title')}</span>
          </Link>

          {/* Admin-only: Users Management */}
          {user?.role === 'administrator' && (
            <Link to="/users" className={`nav-item ${isActive('/users')}`}>
              <span className="nav-icon">👥</span>
              <span className="nav-text">{t('users.title')}</span>
            </Link>
          )}

          {/* Admin and Auditor: Audit Logs */}
          {(user?.role === 'administrator' || user?.role === 'auditor') && (
            <Link to="/audit-logs" className={`nav-item ${isActive('/audit-logs')}`}>
              <span className="nav-icon">📋</span>
              <span className="nav-text">{t('auditLogs.title')}</span>
            </Link>
          )}

          {/* System Settings - Admin Only */}
          {user?.role === 'administrator' && (
            <Link to="/settings" className={`nav-item ${isActive('/settings')}`}>
              <span className="nav-icon">🔧</span>
              <span className="nav-text">{t('settings.system_settings')}</span>
            </Link>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">
              {user?.first_name?.charAt(0) || user?.email?.charAt(0) || 'U'}
            </div>
            <div className="user-details">
              <div className="user-name">{user?.full_name || user?.email}</div>
              <div className="user-role">{user?.role}</div>
            </div>
            <button
              onClick={() => setShowProfileModal(true)}
              className="btn-settings"
              title={t('profile.title')}
            >
              ⚙️
            </button>
          </div>
          <button onClick={handleLogout} className="btn-logout">
            🚪 {t('auth.logout')}
          </button>
        </div>
      </aside>

      {/* User Profile Modal */}
      <UserProfileModal
        isOpen={showProfileModal}
        onClose={() => setShowProfileModal(false)}
      />

      {/* Main Content */}
      <main className="main-content" style={{ paddingBottom: isTasksPanelMinimized ? '50px' : '33vh' }}>
        {children}
      </main>

      {/* Tasks Panel (VMware-style) - Always visible */}
      <TasksTable
        onToggle={handleToggleTasksPanel}
        isMinimized={isTasksPanelMinimized}
        isConnected={isConnected}
      />
    </div>
  );
};

export default Layout;
