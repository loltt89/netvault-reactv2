import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import CompliancePolicies from '../components/CompliancePolicies';
import ComplianceViolations from '../components/ComplianceViolations';
import '../styles/Settings.css';

const CompliancePage: React.FC = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  // CompliancePolicyViewSet is administrator-only on the backend (a policy
  // can flag/target any device) — violations, on the other hand, are
  // readable by any role that can see the devices themselves. Hide the
  // Policies tab rather than show it and 403 on load.
  const isAdmin = user?.role === 'administrator';
  const [activeTab, setActiveTab] = useState<'violations' | 'policies'>('violations');

  return (
    <div className="devices-page">
      <div className="page-header">
        <h1>✅ {t('compliance.nav_title')}</h1>
        <p className="page-subtitle">{t('compliance.subtitle')}</p>
      </div>

      <div className="settings-container">
        <div className="tabs">
          <button
            className={`tab-btn ${activeTab === 'violations' ? 'active' : ''}`}
            onClick={() => setActiveTab('violations')}
          >
            ⚠️ {t('compliance.tabs.violations')}
          </button>
          {isAdmin && (
            <button
              className={`tab-btn ${activeTab === 'policies' ? 'active' : ''}`}
              onClick={() => setActiveTab('policies')}
            >
              📋 {t('compliance.tabs.policies')}
            </button>
          )}
        </div>

        {activeTab === 'violations' && (
          <div className="settings-tab-content">
            <ComplianceViolations />
          </div>
        )}

        {activeTab === 'policies' && isAdmin && (
          <div className="settings-tab-content">
            <CompliancePolicies />
          </div>
        )}
      </div>
    </div>
  );
};

export default CompliancePage;
