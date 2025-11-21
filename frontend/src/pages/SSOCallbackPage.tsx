/**
 * SSO Callback Page
 * Handles token storage after successful SAML SSO authentication
 */

import React, { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { setTokens } from '../services/api.service';

const SSOCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const accessToken = searchParams.get('access');
    const refreshToken = searchParams.get('refresh');

    if (accessToken && refreshToken) {
      // Store access token in memory (cookies set by server)
      setTokens(accessToken, refreshToken);

      // Redirect to dashboard
      window.location.href = '/dashboard';
    } else {
      // No tokens - redirect to login with error
      window.location.href = '/login?error=sso_failed&message=No tokens received';
    }
  }, [searchParams]);

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    }}>
      <div style={{
        background: 'white',
        borderRadius: '1rem',
        padding: '2rem',
        textAlign: 'center',
      }}>
        <div className="spinner" style={{ margin: '0 auto 1rem' }}></div>
        <p>Completing SSO login...</p>
      </div>
    </div>
  );
};

export default SSOCallbackPage;
