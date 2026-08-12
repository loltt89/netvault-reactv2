/**
 * Login Page Component
 * Demonstrates proper JWT authentication flow with 2FA support
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import './LoginPage.css';

const LoginPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    twoFactorToken: '',
  });
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [require2FA, setRequire2FA] = useState<boolean>(false);
  const [ssoEnabled, setSsoEnabled] = useState<boolean>(false);

  useEffect(() => {
    // Check if SSO is enabled
    checkSsoStatus();

    // Check for SSO errors in URL
    const ssoError = searchParams.get('error');
    if (ssoError) {
      setError(`${t('auth.sso_error')}: ${searchParams.get('message') || ssoError}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const checkSsoStatus = async () => {
    try {
      const response = await apiService.saml.status();
      setSsoEnabled(response.enabled);
    } catch (err) {
      logger.debug('SSO status check failed (may not be configured)');
    }
  };

  const handleSsoLogin = () => {
    window.location.href = '/api/v1/saml/login/';
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(
        formData.email,
        formData.password,
        require2FA ? formData.twoFactorToken : undefined
      );
      navigate('/dashboard');
    } catch (err: any) {
      logger.error('Login error:', err);

      if (err.twoFactorRequired) {
        setRequire2FA(true);
        setError(t('auth.two_factor_required'));
      } else if (err.response?.data) {
        const errors = err.response.data;
        if (typeof errors === 'string') {
          setError(errors);
        } else if (errors.detail) {
          setError(errors.detail);
        } else if (errors.non_field_errors) {
          setError(errors.non_field_errors[0]);
        } else {
          setError(t('auth.invalid_credentials'));
        }
      } else {
        setError(t('auth.login_error_generic'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>{t('app.name')}</h1>
          <p>{t('app.title')}</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="email">{t('auth.email')}</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder={t('auth.enter_email')}
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">{t('auth.password')}</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder={t('auth.enter_password')}
              autoComplete="current-password"
            />
          </div>

          {require2FA && (
            <div className="form-group">
              <label htmlFor="twoFactorToken">{t('auth.two_factor_code')}</label>
              <input
                type="text"
                id="twoFactorToken"
                name="twoFactorToken"
                value={formData.twoFactorToken}
                onChange={handleChange}
                required
                disabled={loading}
                placeholder={t('auth.enter_2fa_code')}
                maxLength={6}
                pattern="[0-9]{6}"
              />
            </div>
          )}

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="login-button"
            disabled={loading}
          >
            {loading ? t('auth.logging_in') : t('auth.login')}
          </button>

          {ssoEnabled && (
            <>
              <div className="login-divider">
                <span>{t('auth.or')}</span>
              </div>
              <button
                type="button"
                className="sso-button"
                onClick={handleSsoLogin}
                disabled={loading}
              >
                🔐 {t('auth.login_with_sso')}
              </button>
            </>
          )}
        </form>

        <div className="login-footer">
          <p>
            {t('auth.no_account')} <a href="/register">{t('auth.register')}</a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
