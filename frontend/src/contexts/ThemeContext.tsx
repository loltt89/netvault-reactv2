import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Theme, ThemeContextType } from '../types';
import { useAuth } from './AuthContext';

const DEFAULT_THEME: Theme = 'industrial';

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

interface ThemeProviderProps {
  children: ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = localStorage.getItem('theme');
    return (saved as Theme) || DEFAULT_THEME;
  });

  // ThemeProvider is mounted inside AuthProvider (see index.tsx) specifically
  // so it can read the user's saved preference directly via context — no
  // window CustomEvent bridge needed between the two.
  const { user } = useAuth();

  useEffect(() => {
    // Remove all theme classes
    document.body.classList.remove('theme-industrial', 'theme-neumorphism', 'theme-isometric', 'theme-glassmorphism', 'theme-blueprint');
    // Add current theme class
    document.body.classList.add(`theme-${theme}`);
    // Save to localStorage as cache
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Sync to the authenticated user's saved theme preference once it loads
  useEffect(() => {
    if (user?.theme && user.theme !== theme) {
      setThemeState(user.theme);
    }
    // Only re-sync when the user (or their saved preference) changes —
    // `theme` itself is intentionally excluded so a manual setTheme() call
    // below isn't immediately overwritten by this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.theme]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
