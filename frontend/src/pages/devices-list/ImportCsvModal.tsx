import React, { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import apiService from '../../services/api.service';
import logger from '../../utils/logger';
import { extractErrorMessage } from '../../utils/extractErrorMessage';
import { useToast } from '../../contexts/ToastContext';

interface ImportPreviewRow {
  row_number: number;
  data: Record<string, string>;
  errors: string[];
  warnings: string[];
  valid: boolean;
}

interface ImportCsvModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called when the import actually created/updated at least one device. */
  onImported: () => void;
}

const ImportCsvModal: React.FC<ImportCsvModalProps> = ({ isOpen, onClose, onImported }) => {
  const { t } = useTranslation();
  const toast = useToast();
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<{
    total_rows: number;
    valid_rows: number;
    duplicate_rows: number;
    error_rows: number;
    rows: ImportPreviewRow[];
  } | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importOptions, setImportOptions] = useState({
    skip_duplicates: true,
    update_existing: false,
  });
  const [importResult, setImportResult] = useState<{
    created: number;
    updated: number;
    skipped: number;
    errors: string[];
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mouseDownOnOverlay = useRef(false);

  const handleClose = () => {
    setImportFile(null);
    setImportPreview(null);
    setImportResult(null);
    onClose();
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImportFile(file);
    setImportLoading(true);
    setImportResult(null);

    try {
      const preview = await apiService.devices.csvPreview(file);
      setImportPreview(preview);
    } catch (error: any) {
      toast.error(extractErrorMessage(error, t('devices.import.preview_error')));
    } finally {
      setImportLoading(false);
    }
  };

  const handleImport = async () => {
    if (!importFile) return;

    setImportLoading(true);
    try {
      const result = await apiService.devices.csvImport(importFile, importOptions);
      setImportResult(result);
      if (result.created > 0 || result.updated > 0) {
        onImported();
      }
    } catch (error: any) {
      toast.error(extractErrorMessage(error, t('devices.import.import_error')));
    } finally {
      setImportLoading(false);
    }
  };

  const getCurrentLanguage = () => {
    const lang = localStorage.getItem('language') || 'en';
    return ['en', 'ru', 'kk'].includes(lang) ? lang : 'en';
  };

  const handleDownloadTemplate = async () => {
    try {
      const lang = getCurrentLanguage();
      const response = await apiService.devices.csvTemplate(lang);
      const blob = response.data;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `devices_template_${lang}.csv`);
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(link);
      }, 100);
    } catch (error) {
      logger.error('Failed to download template:', error);
      toast.error(t('devices.import.template_download_error'));
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onMouseDown={() => { mouseDownOnOverlay.current = true; }}
      onClick={() => { if (mouseDownOnOverlay.current) handleClose(); }}
    >
      <div className="modal-content" onMouseDown={(e) => { e.stopPropagation(); mouseDownOnOverlay.current = false; }} style={{ maxWidth: '800px', maxHeight: '80vh', overflow: 'auto' }}>
        <div className="modal-header">
          <h2>{t('devices.import.title')}</h2>
          <button onClick={handleClose} className="close-btn">✕</button>
        </div>

        <div className="modal-body">
          {/* Download template */}
          <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: 'var(--hover-bg)', borderRadius: '8px' }}>
            <p style={{ margin: '0 0 0.5rem 0', fontWeight: 600 }}>{t('devices.import.download_template')}</p>
            <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              {t('devices.import.template_hint')}
            </p>
            <button
              onClick={handleDownloadTemplate}
              className="btn-primary"
              type="button"
            >
              📄 {t('devices.import.download_button')}
            </button>
          </div>

          {/* File upload */}
          <div style={{ marginBottom: '1.5rem' }}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="btn-primary"
              disabled={importLoading}
              style={{ width: '100%', padding: '1rem' }}
            >
              {importFile ? `📁 ${importFile.name}` : `📂 ${t('devices.import.select_file')}`}
            </button>
          </div>

          {/* Loading */}
          {importLoading && (
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              <p>{t('devices.import.processing')}</p>
            </div>
          )}

          {/* Preview */}
          {importPreview && !importResult && (
            <div>
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <div style={{ padding: '0.5rem 1rem', backgroundColor: 'var(--hover-bg)', borderRadius: '4px' }}>
                  {t('devices.import.total')}: <strong>{importPreview.total_rows}</strong>
                </div>
                <div style={{ padding: '0.5rem 1rem', backgroundColor: '#d4edda', borderRadius: '4px', color: '#155724' }}>
                  {t('devices.import.valid')}: <strong>{importPreview.valid_rows}</strong>
                </div>
                {importPreview.duplicate_rows > 0 && (
                  <div style={{ padding: '0.5rem 1rem', backgroundColor: '#fff3cd', borderRadius: '4px', color: '#856404' }}>
                    {t('devices.import.duplicates')}: <strong>{importPreview.duplicate_rows}</strong>
                  </div>
                )}
                {importPreview.error_rows > 0 && (
                  <div style={{ padding: '0.5rem 1rem', backgroundColor: '#f8d7da', borderRadius: '4px', color: '#721c24' }}>
                    {t('devices.import.errors')}: <strong>{importPreview.error_rows}</strong>
                  </div>
                )}
              </div>

              {/* Options */}
              <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--hover-bg)', borderRadius: '8px' }}>
                <div className="checkbox-group" style={{ marginBottom: '0.5rem' }}>
                  <input
                    type="checkbox"
                    id="skip_duplicates"
                    checked={importOptions.skip_duplicates}
                    onChange={(e) => setImportOptions({ ...importOptions, skip_duplicates: e.target.checked })}
                  />
                  <label htmlFor="skip_duplicates">{t('devices.import.skip_duplicates')}</label>
                </div>
                <div className="checkbox-group">
                  <input
                    type="checkbox"
                    id="update_existing"
                    checked={importOptions.update_existing}
                    onChange={(e) => setImportOptions({ ...importOptions, update_existing: e.target.checked })}
                  />
                  <label htmlFor="update_existing">{t('devices.import.update_existing')}</label>
                </div>
              </div>

              {/* Preview table */}
              <div style={{ maxHeight: '300px', overflow: 'auto', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--card-bg)' }}>
                    <tr>
                      <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>#</th>
                      <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>{t('devices.name')}</th>
                      <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>IP</th>
                      <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>{t('devices.vendor')}</th>
                      <th style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>{t('devices.status')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importPreview.rows.map((row) => (
                      <tr key={row.row_number} style={{ backgroundColor: row.valid ? 'inherit' : '#fff3cd' }}>
                        <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>{row.row_number}</td>
                        <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>{row.data.name}</td>
                        <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>{row.data.ip_address}</td>
                        <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>{row.data.vendor}</td>
                        <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>
                          {row.valid ? (
                            <span style={{ color: '#28a745' }}>✓</span>
                          ) : (
                            <span style={{ color: '#dc3545' }} title={row.errors.join(', ')}>✗ {row.errors[0]}</span>
                          )}
                          {row.warnings.length > 0 && (
                            <span style={{ color: '#ffc107', marginLeft: '0.5rem' }} title={row.warnings.join(', ')}>⚠</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Import result */}
          {importResult && (
            <div style={{ padding: '1rem', backgroundColor: '#d4edda', borderRadius: '8px', color: '#155724' }}>
              <h4 style={{ margin: '0 0 0.5rem 0' }}>{t('devices.import.complete')}</h4>
              <p style={{ margin: 0 }}>
                {t('devices.import.created')}: {importResult.created},
                {t('devices.import.updated_count')}: {importResult.updated},
                {t('devices.import.skipped_count')}: {importResult.skipped}
              </p>
              {importResult.errors.length > 0 && (
                <div style={{ marginTop: '0.5rem', color: '#721c24' }}>
                  <strong>{t('devices.import.errors')}:</strong>
                  <ul style={{ margin: '0.25rem 0 0 1rem', padding: 0 }}>
                    {importResult.errors.slice(0, 5).map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button onClick={handleClose} className="btn-secondary">
            {t('common.close')}
          </button>
          {importPreview && !importResult && importPreview.valid_rows > 0 && (
            <button onClick={handleImport} className="btn-primary" disabled={importLoading}>
              {importLoading ? t('devices.import.importing') : t('devices.import.import_button')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ImportCsvModal;
