import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useTranslation } from 'react-i18next';
import UserProfileModal from './UserProfileModal';
import TaskTerminal from './TaskTerminal';
import '../styles/Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

interface LogEntry {
  type: string;
  text: string;
  device_name: string;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [showProfileModal, setShowProfileModal] = useState(false);

  // ===== Real-time Terminal State =====
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showTerminal, setShowTerminal] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const autoCloseTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  const isActive = (path: string) => {
    return location.pathname === path ? 'active' : '';
  };

  // ===== WebSocket Connection Logic =====
  useEffect(() => {
    if (!user) return;

    let isUnmounting = false; // Flag to prevent reconnections during unmount

    const connectWebSocket = () => {
      if (isUnmounting) return; // Don't reconnect if unmounting

      try {
        // Determine WebSocket URL (token will be sent via cookie, not URL)
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Use actual hostname and port (same as current page, nginx will proxy)
        const wsHost = window.location.host; // includes port if non-standard
        const wsUrl = `${wsProtocol}//${wsHost}/ws/backup_logs/`;

        // Create WebSocket connection
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('WebSocket connected');
          setIsConnected(true);
          reconnectAttemptsRef.current = 0; // Reset reconnect attempts
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data) {
              // Add new log with limit of 100
              setLogs((prevLogs) => {
                const newLogs = [...prevLogs, data];
                return newLogs.slice(-100); // Keep only last 100 logs
              });

              // Show terminal when log arrives
              setShowTerminal(true);

              // Reset auto-close timer (close terminal 30 sec after last log)
              if (autoCloseTimeoutRef.current) {
                clearTimeout(autoCloseTimeoutRef.current);
              }
              autoCloseTimeoutRef.current = setTimeout(() => {
                setShowTerminal(false);
                setLogs([]); // Clear logs when auto-closing
              }, 30000); // 30 seconds
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        ws.onclose = (event) => {
          console.log('WebSocket disconnected', event.code, event.reason);
          setIsConnected(false);
          wsRef.current = null;

          // Don't reconnect if component is unmounting
          if (isUnmounting) return;

          // Attempt to reconnect (with exponential backoff)
          if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
            console.log(`Reconnecting in ${delay}ms... (attempt ${reconnectAttemptsRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`);

            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptsRef.current++;
              connectWebSocket();
            }, delay);
          } else {
            console.error('Max WebSocket reconnection attempts reached');
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
        };
      } catch (error) {
        console.error('Failed to establish WebSocket connection:', error);
      }
    };

    // Connect on mount
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      isUnmounting = true; // Set flag to prevent reconnections

      // Clear all timeouts
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (autoCloseTimeoutRef.current) {
        clearTimeout(autoCloseTimeoutRef.current);
      }

      // Close WebSocket if it exists and is open/connecting
      if (wsRef.current) {
        const ws = wsRef.current;
        // Only close if WebSocket is in CONNECTING or OPEN state
        if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
        wsRef.current = null;
      }
    };
  }, [user]);

  // Handle terminal close
  const handleTerminalClose = () => {
    setShowTerminal(false);
    setLogs([]);
    if (autoCloseTimeoutRef.current) {
      clearTimeout(autoCloseTimeoutRef.current);
    }
  };

  // Handle log clear
  const handleClearLogs = () => {
    setLogs([]);
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

          <Link to="/groups" className={`nav-item ${isActive('/groups')}`}>
            <span className="nav-icon">📁</span>
            <span className="nav-text">{t('groups.title')}</span>
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
      <main className="main-content" style={{ paddingBottom: showTerminal ? '170px' : '0' }}>
        {children}
      </main>

      {/* Real-time Task Terminal */}
      {showTerminal && (
        <TaskTerminal
          logs={logs}
          onClose={handleTerminalClose}
          isConnected={isConnected}
          onClear={handleClearLogs}
        />
      )}
    </div>
  );
};

export default Layout;
