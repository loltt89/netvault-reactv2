import { useCallback, useEffect, useRef } from 'react';

interface UsePollingOptions {
  /** Stop automatically after this many ticks. Omit for unlimited (runs until stop()/unmount). */
  maxAttempts?: number;
}

/**
 * Runs `callback` on a fixed interval via start(), always cleaning up on
 * unmount. Two independent call sites (TasksTable.tsx's continuous
 * task-list refresh, DeviceDetailPage.tsx's bounded post-backup poll) had
 * each hand-rolled their own setInterval + ref + cleanup — same shape,
 * different interval/attempt-limit. This covers both: pass `maxAttempts`
 * for the bounded case, omit it for continuous polling.
 *
 * The interval itself is not recreated when `callback` changes identity
 * (it's read from a ref each tick) — callers that need to restart on their
 * own dependency changes call start() again explicitly, same as they did
 * with the old useEffect-per-dependency pattern.
 */
export function usePolling(callback: () => void | Promise<void>, intervalMs: number, options?: UsePollingOptions) {
  const maxAttempts = options?.maxAttempts;
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const start = useCallback(() => {
    stop();
    let attempts = 0;
    intervalRef.current = setInterval(() => {
      attempts++;
      callbackRef.current();
      if (maxAttempts && attempts >= maxAttempts) {
        stop();
      }
    }, intervalMs);
  }, [intervalMs, maxAttempts, stop]);

  // Always stop on unmount, regardless of who called start().
  useEffect(() => stop, [stop]);

  return { start, stop };
}
