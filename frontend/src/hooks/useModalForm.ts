import { useCallback, useState } from 'react';

/**
 * The create/edit modal state machine duplicated between
 * BackupSchedules.tsx and BackupRetentionPolicies.tsx: a form pre-filled
 * with defaults for "create", or populated from an existing item for
 * "edit", plus the modal open/close flag. Submit handling stays with the
 * caller — the two forms validate and shape their payload differently
 * (BackupSchedules requires run_time except when frequency is hourly,
 * only sends run_days for weekly, etc.), so that logic isn't something
 * this hook should paper over.
 */
export function useModalForm<T, F>(defaultFormData: F, toFormData: (item: T) => F) {
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<T | null>(null);
  const [formData, setFormData] = useState<F>(defaultFormData);

  const openCreate = useCallback(() => {
    setEditing(null);
    setFormData(defaultFormData);
    setShowModal(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openEdit = useCallback((item: T) => {
    setEditing(item);
    setFormData(toFormData(item));
    setShowModal(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const close = useCallback(() => setShowModal(false), []);

  return { showModal, editing, formData, setFormData, openCreate, openEdit, close };
}
