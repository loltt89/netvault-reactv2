import React from 'react';
import { useToast, ToastType } from '../contexts/ToastContext';
import '../styles/Toast.css';

const ICONS: Record<ToastType, string> = {
  success: '✓',
  error: '✕',
  info: 'ℹ',
  warning: '⚠',
};

const ToastContainer: React.FC = () => {
  const { toasts, dismiss } = useToast();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="toast-container" role="region" aria-label="Notifications">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast-${toast.type}`}
          role={toast.type === 'error' ? 'alert' : 'status'}
          aria-live={toast.type === 'error' ? 'assertive' : 'polite'}
        >
          <span className="toast-icon" aria-hidden="true">{ICONS[toast.type]}</span>
          <span className="toast-message">{toast.message}</span>
          <button
            className="toast-close"
            onClick={() => dismiss(toast.id)}
            aria-label="Dismiss notification"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
};

export default ToastContainer;
