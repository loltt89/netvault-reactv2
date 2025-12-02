/**
 * SSO Callback Page
 * Handles redirect after successful SAML SSO authentication
 * Tokens are passed via HttpOnly cookies (not URL params for security)
 */

import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const SSOCallbackPage: React.FC = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // Tokens are set as HttpOnly cookies by the backend
    // Just redirect to dashboard - API calls will use cookies automatically
    const timer = setTimeout(() => {
      navigate('/dashboard', { replace: true });
    }, 500);

    return () => clearTimeout(timer);
  }, [navigate]);

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
