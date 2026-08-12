import React, { createContext, useCallback, useContext, useRef, useState, ReactNode } from 'react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  toasts: Toast[];
  show: (message: string, type: ToastType) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
  dismiss: (id: number) => void;
}

const DEFAULT_DURATION_MS = 5000;

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

interface ToastProviderProps {
  children: ReactNode;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback((message: string, type: ToastType) => {
    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => dismiss(id), DEFAULT_DURATION_MS);
  }, [dismiss]);

  const value: ToastContextType = {
    toasts,
    show,
    success: useCallback((message: string) => show(message, 'success'), [show]),
    error: useCallback((message: string) => show(message, 'error'), [show]),
    info: useCallback((message: string) => show(message, 'info'), [show]),
    warning: useCallback((message: string) => show(message, 'warning'), [show]),
    dismiss,
  };

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
};

export default ToastContext;
