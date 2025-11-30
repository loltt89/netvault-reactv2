import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export type ThemeName = 'industrial' | 'neumorphism' | 'isometric' | 'glassmorphism' | 'blueprint';

interface ThemeContextType {
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
}

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
  const [theme, setThemeState] = useState<ThemeName>(() => {
    const saved = localStorage.getItem('theme');
    return (saved as ThemeName) || 'industrial';
  });

  useEffect(() => {
    // Remove all theme classes
    document.body.classList.remove('theme-industrial', 'theme-neumorphism', 'theme-isometric', 'theme-glassmorphism', 'theme-blueprint');
    // Add current theme class
    document.body.classList.add(`theme-${theme}`);
    // Save to localStorage as cache
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Listen for user theme changes from AuthContext
  useEffect(() => {
    const handleUserThemeChange = (event: Event) => {
      const customEvent = event as CustomEvent;
      if (customEvent.detail) {
        setThemeState(customEvent.detail as ThemeName);
      }
    };

    window.addEventListener('userThemeChange', handleUserThemeChange);
    return () => window.removeEventListener('userThemeChange', handleUserThemeChange);
  }, []);

  const setTheme = (newTheme: ThemeName) => {
    setThemeState(newTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
