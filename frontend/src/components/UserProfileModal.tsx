import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useTheme, ThemeName } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { QRCodeSVG } from 'qrcode.react';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import { Language, Theme } from '../types';
import '../styles/UserProfileModal.css';

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const UserProfileModal: React.FC<UserProfileModalProps> = ({ isOpen, onClose }) => {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const { user, updateProfile, refreshUser } = useAuth();
  const [selectedLang, setSelectedLang] = useState(i18n.language);
  const [selectedTheme, setSelectedTheme] = useState(theme);
  const [activeTab, setActiveTab] = useState<'general' | 'security' | 'password'>('general');

  // 2FA states
  const [show2FASetup, setShow2FASetup] = useState(false);
  const [qrCodeUri, setQrCodeUri] = useState('');
  const [secret, setSecret] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [twoFAEnabled, setTwoFAEnabled] = useState(user?.two_factor_enabled || false);

  // Password change states
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    setTwoFAEnabled(user?.two_factor_enabled || false);
  }, [user]);

  const languages = [
    { code: 'en', name: 'English', flag: '🇬🇧' },
    { code: 'ru', name: 'Русский', flag: '🇷🇺' },
    { code: 'kk', name: 'Қазақша', flag: '🇰🇿' },
  ];

  const themes: { name: ThemeName; label: string; preview: string[] }[] = [
    {
      name: 'neumorphism',
      label: t('themes.neumorphism'),
      preview: ['#eef1f5', '#d1d9e6', '#4FD1C5', '#10b981']
    },
    {
      name: 'industrial',
      label: t('themes.industrial'),
      preview: ['#ffffff', '#f5f5f5', '#FF6400', '#10b981']
    },
    {
      name: 'isometric',
      label: t('themes.isometric'),
      preview: ['#090a0f', '#1e293b', '#00D9FF', '#34d399']
    },
    {
      name: 'glassmorphism',
      label: t('themes.glassmorphism'),
      preview: ['#0A1628', '#1d293b', '#00D9FF', '#34d399']
    },
    {
      name: 'blueprint',
      label: t('themes.blueprint'),
      preview: ['#1a202c', '#2d3748', '#FF6400', '#ffffff']
    },
  ];

  const handleLanguageChange = async (langCode: string) => {
    try {
      setSelectedLang(langCode);
      i18n.changeLanguage(langCode);
      localStorage.setItem('language', langCode);

      if (updateProfile) {
        await updateProfile({ preferred_language: langCode as Language });
      }
    } catch (error) {
      logger.error('Error updating language preference:', error);
    }
  };

  const handleThemeChange = async (themeName: ThemeName) => {
    try {
      setSelectedTheme(themeName);
      setTheme(themeName);

      if (updateProfile) {
        await updateProfile({ theme: themeName as Theme });
      }
    } catch (error) {
      logger.error('Error updating theme preference:', error);
    }
  };

  const handleEnable2FA = async () => {
    try {
      const response = await apiService.users.enable2FA();
      setQrCodeUri(response.uri);  // Backend returns 'uri', not 'qr_code_uri'
      setSecret(response.secret);
      setShow2FASetup(true);
    } catch (error) {
      logger.error('Error enabling 2FA:', error);
      alert(t('profile.failed_enable_2fa'));
    }
  };

  const handleVerify2FA = async () => {
    if (!verificationCode || verificationCode.length !== 6) {
      alert(t('profile.invalid_code'));
      return;
    }

    try {
      await apiService.users.verify2FA(verificationCode);
      setTwoFAEnabled(true);
      setShow2FASetup(false);
      setVerificationCode('');
      if (refreshUser) await refreshUser();
      alert(t('profile.2fa_enabled'));
    } catch (error: any) {
      logger.error('Error verifying 2FA:', error);
      alert(t('profile.invalid_verification'));
    }
  };

  const handleDisable2FA = async () => {
    const password = prompt(t('profile.enter_password_disable'));
    if (!password) return;

    try {
      await apiService.users.disable2FA(password);
      setTwoFAEnabled(false);
      if (refreshUser) await refreshUser();
      alert(t('profile.2fa_disabled'));
    } catch (error: any) {
      logger.error('Error disabling 2FA:', error);
      alert(t('profile.failed_disable_2fa'));
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      alert(t('profile.passwords_dont_match'));
      return;
    }

    if (newPassword.length < 8) {
      alert(t('profile.password_too_short'));
      return;
    }

    try {
      await apiService.users.changePassword(oldPassword, newPassword, confirmPassword);
      alert(t('profile.password_changed'));
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error: any) {
      logger.error('Error changing password:', error);
      alert(error.response?.data?.error || t('profile.failed_change_password'));
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content profile-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>⚙️ {t('profile.title')}</h2>
          <button onClick={onClose} className="btn-close">✕</button>
        </div>

        {/* User Info */}
        <div className="profile-user-info">
          <div className="profile-avatar-large">
            {user?.first_name?.charAt(0) || user?.email?.charAt(0) || 'U'}
          </div>
          <div>
            <h3>{user?.full_name || user?.email}</h3>
            <p>{user?.email}</p>
            <span className="role-badge">{user?.role}</span>
          </div>
        </div>

        {/* Tabs */}
        <div className="profile-tabs">
          <button
            className={`tab-button ${activeTab === 'general' ? 'active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            {t('profile.general')}
          </button>
          {!user?.is_ldap_user && (
            <>
              <button
                className={`tab-button ${activeTab === 'security' ? 'active' : ''}`}
                onClick={() => setActiveTab('security')}
              >
                {t('profile.security')}
              </button>
              <button
                className={`tab-button ${activeTab === 'password' ? 'active' : ''}`}
                onClick={() => setActiveTab('password')}
              >
                {t('profile.change_password')}
              </button>
            </>
          )}
        </div>

        <div className="profile-content">
          {/* General Tab */}
          {activeTab === 'general' && (
            <>
              {/* Language Settings */}
              <div className="settings-section">
                <h3>{t('settings.language')}</h3>
                <div className="language-grid">
                  {languages.map((lang) => (
                    <div
                      key={lang.code}
                      className={`language-card ${selectedLang === lang.code ? 'selected' : ''}`}
                      onClick={() => handleLanguageChange(lang.code)}
                    >
                      <div className="language-flag">{lang.flag}</div>
                      <div className="language-name">{lang.name}</div>
                      {selectedLang === lang.code && <div className="check-icon">✓</div>}
                    </div>
                  ))}
                </div>
              </div>

              {/* Theme Settings */}
              <div className="settings-section">
                <h3>{t('settings.theme')}</h3>
                <div className="theme-grid">
                  {themes.map((themeOption) => (
                    <div
                      key={themeOption.name}
                      className={`theme-card ${selectedTheme === themeOption.name ? 'selected' : ''}`}
                      onClick={() => handleThemeChange(themeOption.name)}
                    >
                      <div className="theme-preview">
                        {themeOption.preview.map((color, index) => (
                          <div
                            key={index}
                            className="theme-color"
                            style={{ backgroundColor: color }}
                          />
                        ))}
                      </div>
                      <div className="theme-name">{themeOption.label}</div>
                      {selectedTheme === themeOption.name && <div className="check-icon">✓</div>}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && !user?.is_ldap_user && (
            <div className="settings-section">
              <h3>🔒 {t('profile.two_factor')}</h3>
              <div className="info-card">
                <div className="info-item">
                  <span className="info-label">{t('profile.status')}:</span>
                  <span className={`badge ${twoFAEnabled ? 'badge-success' : 'badge-secondary'}`}>
                    {twoFAEnabled ? `✓ ${t('profile.enabled')}` : t('profile.disabled')}
                  </span>
                </div>
                <p style={{ margin: '1rem 0', color: 'var(--text-secondary)' }}>
                  {t('profile.2fa_description')}
                </p>

                {!twoFAEnabled ? (
                  <button onClick={handleEnable2FA} className="btn-primary">
                    {t('profile.enable_2fa')}
                  </button>
                ) : (
                  <button onClick={handleDisable2FA} className="btn-danger">
                    {t('profile.disable_2fa')}
                  </button>
                )}
              </div>

              {/* 2FA Setup */}
              {show2FASetup && (
                <div className="two-fa-setup">
                  <h4>{t('profile.scan_qr')}</h4>
                  <p>{t('profile.scan_description')}</p>

                  <div style={{ display: 'flex', justifyContent: 'center', margin: '1.5rem 0' }}>
                    {qrCodeUri && <QRCodeSVG value={qrCodeUri} size={200} />}
                  </div>

                  <div style={{ backgroundColor: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '6px', marginBottom: '1rem' }}>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', margin: '0 0 0.5rem 0' }}>
                      {t('profile.manual_entry')}:
                    </p>
                    <code style={{ fontSize: '0.875rem', wordBreak: 'break-all' }}>{secret}</code>
                  </div>

                  <h4>{t('profile.verify_code')}</h4>
                  <input
                    type="text"
                    placeholder={t('profile.enter_6_digit')}
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    maxLength={6}
                    className="form-input"
                    style={{ marginBottom: '1rem' }}
                  />

                  <button onClick={handleVerify2FA} className="btn-primary">
                    {t('profile.verify_enable')}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Password Tab */}
          {activeTab === 'password' && !user?.is_ldap_user && (
            <div className="settings-section">
              <h3>{t('profile.change_password')}</h3>
              <form onSubmit={handleChangePassword} className="password-form">
                <div className="form-group">
                  <label>{t('profile.current_password')}</label>
                  <input
                    type="password"
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    className="form-input"
                    required
                  />
                </div>

                <div className="form-group">
                  <label>{t('profile.new_password')}</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="form-input"
                    required
                    minLength={8}
                  />
                </div>

                <div className="form-group">
                  <label>{t('profile.confirm_password')}</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="form-input"
                    required
                    minLength={8}
                  />
                </div>

                <button type="submit" className="btn-primary">
                  {t('profile.update_password')}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default UserProfileModal;
