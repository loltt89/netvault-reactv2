import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface Props {
  deviceCount: number;
  saving: boolean;
  onClose: () => void;
  onSubmit: (action: 'add' | 'remove' | 'set', tags: string[]) => void;
}

const BulkTagEditModal: React.FC<Props> = ({ deviceCount, saving, onClose, onSubmit }) => {
  const { t } = useTranslation();
  const [action, setAction] = useState<'add' | 'remove' | 'set'>('add');
  const [tagsInput, setTagsInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const tags = tagsInput.split(',').map((s) => s.trim()).filter(Boolean);
    onSubmit(action, tags);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
        <div className="modal-header">
          <h2>🏷️ {t('devices.bulk_tag_edit_title', { count: deviceCount })}</h2>
          <button onClick={onClose} className="btn-close">✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label>{t('devices.bulk_tag_action')}</label>
              <select value={action} onChange={(e) => setAction(e.target.value as 'add' | 'remove' | 'set')}>
                <option value="add">{t('devices.bulk_tag_add')}</option>
                <option value="remove">{t('devices.bulk_tag_remove')}</option>
                <option value="set">{t('devices.bulk_tag_set')}</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>{t('devices.tags')} {action !== 'set' && '*'}</label>
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="core, dc1"
                required={action !== 'set'}
              />
              <small style={{ color: 'var(--text-secondary)' }}>
                {action === 'set' ? t('devices.bulk_tag_set_help') : t('devices.bulk_tag_comma_help')}
              </small>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" onClick={onClose} className="btn-secondary">
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? t('common.saving') : t('common.apply')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default BulkTagEditModal;
