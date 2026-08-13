import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { Link } from 'react-router-dom';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import { DashboardStats, StaleDevice } from '../types';
import '../styles/Dashboard.css';

interface BackupTrendData {
  date: string;
  successful: number;
  failed: number;
  total: number;
}

interface DeviceStatusData {
  name: string;
  value: number;
  [key: string]: string | number;
}

const DashboardPage: React.FC = () => {
  const { t } = useTranslation();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [backupTrend, setBackupTrend] = useState<BackupTrendData[]>([]);
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatusData[]>([]);
  const [staleDevices, setStaleDevices] = useState<StaleDevice[]>([]);
  const [loading, setLoading] = useState(true);

  // Format large numbers for display
  const formatNumber = (num: number): string => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [statsData, trendData, staleData] = await Promise.all([
        apiService.dashboard.getStatistics(),
        apiService.dashboard.getBackupTrend(7),
        apiService.staleBackups.list(3),
      ]);

      setStats(statsData);
      setBackupTrend(trendData || []);
      setStaleDevices(staleData?.devices || []);

      // Calculate device status data
      if (statsData) {
        const online = statsData.active_devices || 0;
        const total = statsData.total_devices || 0;
        const offline = total - online;

        setDeviceStatus([
          { name: 'Online', value: online },
          { name: 'Offline', value: offline },
        ]);
      }
    } catch (error) {
      logger.error('Error loading dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const COLORS = ['#10b981', '#ef4444', '#3b82f6', '#f59e0b'];

  if (loading) {
    return (
      <div className="dashboard-page">
        <div className="dashboard-loading">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h1>{t('dashboard.title')}</h1>
        <p className="dashboard-subtitle">{t('dashboard.welcome')}</p>
      </div>

      {/* Statistics Cards */}
      <div className="stats-grid">
        <div className="stat-card stat-primary">
          <div className="stat-icon">🖥️</div>
          <div className="stat-content">
            <h3 title={`${stats?.total_devices || 0}`}>{formatNumber(stats?.total_devices || 0)}</h3>
            <p>{t('dashboard.total_devices')}</p>
          </div>
        </div>

        <div className="stat-card stat-success">
          <div className="stat-icon">✅</div>
          <div className="stat-content">
            <h3 title={`${stats?.active_devices || 0}`}>{formatNumber(stats?.active_devices || 0)}</h3>
            <p>{t('dashboard.active_devices')}</p>
          </div>
        </div>

        <div className="stat-card stat-info">
          <div className="stat-icon">💾</div>
          <div className="stat-content">
            <h3 title={`${stats?.total_backups || 0}`}>{formatNumber(stats?.total_backups || 0)}</h3>
            <p>{t('dashboard.total_backups')}</p>
          </div>
        </div>

        <div className="stat-card stat-warning">
          <div className="stat-icon">📊</div>
          <div className="stat-content">
            <h3 title={`${stats?.last_24h_backups || 0}`}>{formatNumber(stats?.last_24h_backups || 0)}</h3>
            <p>{t('dashboard.last_24h')}</p>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="charts-grid">
        {/* Backup Trend Chart */}
        <div className="chart-card full-width">
          <h3 className="chart-title">{t('dashboard.backup_trend')}</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={backupTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="date" stroke="var(--text-secondary)" />
              <YAxis
                stroke="var(--text-secondary)"
                tickFormatter={(value) => formatNumber(value)}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--card-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  color: 'var(--text-primary)'
                }}
                formatter={(value: number) => [value, '']}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="successful"
                stroke="#10b981"
                strokeWidth={2}
                name={t('dashboard.successful_backups')}
                dot={{ fill: '#10b981' }}
                isAnimationActive={true}
                animationDuration={1000}
              />
              <Line
                type="monotone"
                dataKey="failed"
                stroke="#ef4444"
                strokeWidth={2}
                name={t('dashboard.failed_backups')}
                dot={{ fill: '#ef4444' }}
                isAnimationActive={true}
                animationDuration={1000}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Device Status Pie Chart */}
        <div className="chart-card">
          <h3 className="chart-title">{t('dashboard.device_status')}</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={deviceStatus}
                cx="50%"
                cy="50%"
                labelLine={true}
                label={(entry: any) => {
                  const percent = entry.percent as number;
                  // Short label with just percentage
                  return `${(percent * 100).toFixed(0)}%`;
                }}
                outerRadius={90}
                fill="#8884d8"
                dataKey="value"
                isAnimationActive={true}
                animationDuration={1000}
              >
                {deviceStatus.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--card-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  color: 'var(--text-primary)'
                }}
                formatter={(value: number, name: string) => [value, name]}
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                formatter={(value: string, entry: any) => {
                  const item = deviceStatus.find(d => d.name === value);
                  return `${value}: ${item?.value || 0}`;
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Backup Success Rate Chart */}
        <div className="chart-card">
          <h3 className="chart-title">Backup Success Rate</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={[
                {
                  name: 'Backups',
                  Successful: stats?.successful_backups || 0,
                  Failed: stats?.failed_backups || 0,
                },
              ]}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="name" stroke="var(--text-secondary)" />
              <YAxis
                stroke="var(--text-secondary)"
                tickFormatter={(value) => formatNumber(value)}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--card-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  color: 'var(--text-primary)'
                }}
                formatter={(value: number) => [value, '']}
              />
              <Legend />
              <Bar dataKey="Successful" fill="#10b981" name={t('dashboard.successful_backups')} isAnimationActive={true} animationDuration={1000} />
              <Bar dataKey="Failed" fill="#ef4444" name={t('dashboard.failed_backups')} isAnimationActive={true} animationDuration={1000} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Stale Backups — devices that haven't backed up in 3+ days, or ever.
          Always rendered, like the stat cards/charts above (which show 0s
          rather than disappearing on an empty system) — an empty state here
          reads as "nothing wrong to check", not "widget missing". */}
      <div className="chart-card full-width" style={{ marginTop: '1.5rem' }}>
        <h3 className="chart-title">
          ⏰ {t('staleBackups.title')} {staleDevices.length > 0 && `(${staleDevices.length})`}
        </h3>
        {staleDevices.length === 0 ? (
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            ✅ {t('staleBackups.all_good')}
          </p>
        ) : (
          <>
            <div className="table-container" style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--hover-bg)', borderBottom: '2px solid var(--border-color)' }}>
                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>{t('staleBackups.device')}</th>
                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>{t('staleBackups.ip_address')}</th>
                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>{t('staleBackups.last_backup')}</th>
                  </tr>
                </thead>
                <tbody>
                  {staleDevices.slice(0, 10).map((d) => (
                    <tr key={d.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '0.75rem' }}>
                        <Link to={`/devices/${d.id}`}>{d.name}</Link>
                      </td>
                      <td style={{ padding: '0.75rem' }}>{d.ip_address}</td>
                      <td style={{ padding: '0.75rem' }}>
                        {d.days_since_backup === null
                          ? t('staleBackups.never')
                          : t('staleBackups.days_ago', { count: d.days_since_backup })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {staleDevices.length > 10 && (
              <p style={{ marginTop: '0.75rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                {t('staleBackups.and_more', { count: staleDevices.length - 10 })}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;
