import { useCallback, useEffect, useRef, useState } from 'react';
import { PaginatedResponse } from '../types';
import { unwrapList } from '../utils/unwrapList';
import logger from '../utils/logger';

/**
 * Loads a list endpoint on mount, tracks loading state, and exposes
 * `reload()` for after create/update/delete. This was the first half of
 * the "load list, unwrap pagination, alert on failure" scaffold
 * copy-pasted between BackupSchedules.tsx and BackupRetentionPolicies.tsx
 * (and, in spirit, several other list pages — but those don't share the
 * create/edit modal shape this hook is paired with, see useModalForm).
 *
 * `fetcher`/`onError` are read from a ref internally, so passing a fresh
 * inline closure each render is safe — it won't cause a reload loop.
 */
export function useListResource<T>(
  fetcher: () => Promise<T[] | PaginatedResponse<T>>,
  onError?: () => void
) {
  const [items, setItems] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetcherRef.current();
      setItems(unwrapList<T>(data));
    } catch (error) {
      logger.error('Error loading list:', error);
      onErrorRef.current?.();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { items, loading, reload: load, setItems };
}
