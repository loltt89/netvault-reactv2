import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import apiService from '../services/api.service';
import '../styles/ConfigSearch.css';

interface SearchMatch {
  line_number: number;
  line: string;
  context: string;
}

interface SearchResult {
  device_id: number;
  device_name: string;
  device_ip: string;
  vendor: string | null;
  backup_id: number;
  backup_date: string;
  match_count: number;
  matches: SearchMatch[];
}

interface SearchResponse {
  query: string;
  total_devices: number;
  total_matches: number;
  results: SearchResult[];
}

const ConfigSearchPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [query, setQuery] = useState('');
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [regexMode, setRegexMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedDevices, setExpandedDevices] = useState<Set<number>>(new Set());

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 2) {
      setError(t('config_search.min_chars'));
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const data = await apiService.backups.searchConfigs(query, {
        caseSensitive,
        regex: regexMode,
      });
      setResults(data);
      setExpandedDevices(new Set());
    } catch (err: any) {
      setError(err.response?.data?.error || t('config_search.search_error'));
    } finally {
      setLoading(false);
    }
  };

  const toggleDevice = (deviceId: number) => {
    const newExpanded = new Set(expandedDevices);
    if (newExpanded.has(deviceId)) {
      newExpanded.delete(deviceId);
    } else {
      newExpanded.add(deviceId);
    }
    setExpandedDevices(newExpanded);
  };

  const highlightMatch = (text: string, searchQuery: string) => {
    if (!searchQuery || regexMode) return text;

    const regex = new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, caseSensitive ? 'g' : 'gi');
    const parts = text.split(regex);

    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i} className="search-highlight">{part}</mark> : part
    );
  };

  return (
    <div className="config-search-page">
      <div className="page-header">
        <h1>🔍 {t('config_search.title')}</h1>
        <p className="page-subtitle">{t('config_search.subtitle')}</p>
      </div>

      <form onSubmit={handleSearch} className="search-form">
        <div className="search-input-wrapper">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('config_search.placeholder')}
            className="search-input"
          />
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? t('config_search.searching') : t('config_search.search')}
          </button>
        </div>

        <div className="search-options">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={caseSensitive}
              onChange={(e) => setCaseSensitive(e.target.checked)}
            />
            {t('config_search.case_sensitive')}
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={regexMode}
              onChange={(e) => setRegexMode(e.target.checked)}
            />
            {t('config_search.regex')}
          </label>
        </div>
      </form>

      {error && (
        <div className="alert alert-error">{error}</div>
      )}

      {results && (
        <div className="search-results">
          <div className="results-summary">
            {t('config_search.found_matches', {
              devices: results.total_devices,
              matches: results.total_matches,
            })}
          </div>

          {results.results.length === 0 ? (
            <div className="no-results">
              {t('config_search.no_results')}
            </div>
          ) : (
            <div className="results-list">
              {results.results.map((result) => (
                <div key={result.device_id} className="result-card">
                  <div
                    className="result-header"
                    onClick={() => toggleDevice(result.device_id)}
                  >
                    <div className="device-info">
                      <span className="expand-icon">
                        {expandedDevices.has(result.device_id) ? '▼' : '▶'}
                      </span>
                      <span
                        className="device-name"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/devices/${result.device_id}`);
                        }}
                      >
                        {result.device_name}
                      </span>
                      <span className="device-ip">{result.device_ip}</span>
                      {result.vendor && (
                        <span className="device-vendor">{result.vendor}</span>
                      )}
                    </div>
                    <div className="match-count">
                      {result.match_count} {t('config_search.matches')}
                    </div>
                  </div>

                  {expandedDevices.has(result.device_id) && (
                    <div className="result-matches">
                      {result.matches.map((match, idx) => (
                        <div key={idx} className="match-item">
                          <div className="match-line-info">
                            {t('config_search.line')} {match.line_number}
                          </div>
                          <pre className="match-context">
                            {match.context.split('\n').map((line, lineIdx) => {
                              const lineNum = parseInt(line.split(':')[0]);
                              const isMatchLine = lineNum === match.line_number;
                              return (
                                <div
                                  key={lineIdx}
                                  className={`context-line ${isMatchLine ? 'highlight-line' : ''}`}
                                >
                                  {isMatchLine ? highlightMatch(line, query) : line}
                                </div>
                              );
                            })}
                          </pre>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ConfigSearchPage;
