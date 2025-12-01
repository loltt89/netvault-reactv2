/**
 * Login Page Component
 * Demonstrates proper JWT authentication flow with 2FA support
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiService from '../services/api.service';
import logger from '../utils/logger';
import './LoginPage.css';

const LoginPage: React.FC = () => {
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
      setError(`SSO Error: ${searchParams.get('message') || ssoError}`);
    }
  }, [searchParams]);

  const checkSsoStatus = async () => {
    try {
      const response = await apiService.request('GET', '/saml/status/');
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
        setError('Please enter your 2FA code');
      } else if (err.response?.data) {
        const errors = err.response.data;
        if (typeof errors === 'string') {
          setError(errors);
        } else if (errors.detail) {
          setError(errors.detail);
        } else if (errors.non_field_errors) {
          setError(errors.non_field_errors[0]);
        } else {
          setError('Login failed. Please check your credentials.');
        }
      } else {
        setError('An error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>NetVault</h1>
          <p>Network Device Configuration Backup System</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="Enter your email"
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="Enter your password"
              autoComplete="current-password"
            />
          </div>

          {require2FA && (
            <div className="form-group">
              <label htmlFor="twoFactorToken">2FA Code</label>
              <input
                type="text"
                id="twoFactorToken"
                name="twoFactorToken"
                value={formData.twoFactorToken}
                onChange={handleChange}
                required
                disabled={loading}
                placeholder="Enter 6-digit code"
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
            {loading ? 'Logging in...' : 'Login'}
          </button>

          {ssoEnabled && (
            <>
              <div className="login-divider">
                <span>or</span>
              </div>
              <button
                type="button"
                className="sso-button"
                onClick={handleSsoLogin}
                disabled={loading}
              >
                🔐 Login with SSO
              </button>
            </>
          )}
        </form>

        <div className="login-footer">
          <p>
            Don't have an account? <a href="/register">Register</a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
