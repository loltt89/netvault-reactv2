import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import './styles/themes.css';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import './i18n/config';

// Suppress ResizeObserver loop warnings from Monaco Editor ONLY
// This is a known benign issue with Monaco Editor's layout recalculation
// We filter specifically to avoid hiding real ResizeObserver issues elsewhere
const originalError = console.error;
console.error = (...args: unknown[]) => {
  const message = args[0];

  // Only suppress if it's a ResizeObserver loop error
  if (message && typeof message === 'string' && message.includes('ResizeObserver loop')) {
    // Check if error is from Monaco Editor by looking at the call stack
    const stack = new Error().stack || '';

    // Only suppress if stack trace contains monaco-related code
    if (stack.includes('monaco') || stack.includes('editor')) {
      return;
    }

    // If not from Monaco, log a warning that there's a real ResizeObserver issue
    console.warn('⚠️ ResizeObserver loop detected (NOT from Monaco Editor):', message);
  }

  originalError.apply(console, args);
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>
);
