import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import logger from '../utils/logger';

export interface LogEntry {
  type: string;
  text: string;
  device_name: string;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const AUTO_CLOSE_MS = 30000; // hide the terminal 30s after the last log
const MAX_LOGS = 100;

/**
 * Owns the backup-log WebSocket connection: connect-on-auth, exponential
 * backoff reconnect (capped at MAX_RECONNECT_ATTEMPTS), and an
 * auto-closing log terminal. This was previously ~110 lines embedded
 * directly in Layout.tsx (a navigation/sidebar component) — pulled out so
 * Layout only renders, and this piece of real-time connection state is
 * independently reusable/testable.
 */
export function useTaskSocket() {
  const { user } = useAuth();

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showTerminal, setShowTerminal] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoCloseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const clearLogs = useCallback(() => setLogs([]), []);

  useEffect(() => {
    if (!user) return;

    let isUnmounting = false; // Prevent reconnection attempts during unmount

    const connectWebSocket = () => {
      if (isUnmounting) return;

      try {
        // Token travels via cookie, not the URL. Same host/port as the page
        // — nginx proxies /ws/ to the backend (see install.sh's generated config).
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = window.location.host;
        const wsUrl = `${wsProtocol}//${wsHost}/ws/backup_logs/`;

        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          logger.debug('WebSocket connected');
          setIsConnected(true);
          reconnectAttemptsRef.current = 0;
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data) {
              setLogs((prevLogs) => [...prevLogs, data].slice(-MAX_LOGS));
              setShowTerminal(true);

              if (autoCloseTimeoutRef.current) {
                clearTimeout(autoCloseTimeoutRef.current);
              }
              autoCloseTimeoutRef.current = setTimeout(() => {
                setShowTerminal(false);
                setLogs([]);
              }, AUTO_CLOSE_MS);
            }
          } catch (error) {
            logger.error('Error parsing WebSocket message:', error);
          }
        };

        ws.onclose = (event) => {
          logger.debug('WebSocket disconnected', event.code, event.reason);
          setIsConnected(false);
          wsRef.current = null;

          if (isUnmounting) return;

          if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
            logger.debug(`Reconnecting in ${delay}ms... (attempt ${reconnectAttemptsRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`);

            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptsRef.current++;
              connectWebSocket();
            }, delay);
          } else {
            logger.error('Max WebSocket reconnection attempts reached');
          }
        };

        ws.onerror = (error) => {
          logger.error('WebSocket error:', error);
        };
      } catch (error) {
        logger.error('Failed to establish WebSocket connection:', error);
      }
    };

    connectWebSocket();

    return () => {
      isUnmounting = true;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (autoCloseTimeoutRef.current) {
        clearTimeout(autoCloseTimeoutRef.current);
      }

      if (wsRef.current) {
        const ws = wsRef.current;
        if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
        wsRef.current = null;
      }
    };
    // Only reconnect when the user identity changes, not on every user object update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  return { logs, showTerminal, isConnected, clearLogs };
}
