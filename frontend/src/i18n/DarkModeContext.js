import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const DarkModeContext = createContext();

export function DarkModeProvider({ children }) {
  const [isDark, setIsDark] = useState(() => {
    try {
      const saved = localStorage.getItem('dp_dark_mode');
      if (saved !== null) return saved === 'true';
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    } catch {
      return false;
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    try {
      localStorage.setItem('dp_dark_mode', String(isDark));
    } catch {}
  }, [isDark]);

  const toggleDark = useCallback(() => {
    setIsDark((prev) => !prev);
  }, []);

  return (
    <DarkModeContext.Provider value={{ isDark, toggleDark }}>
      {children}
    </DarkModeContext.Provider>
  );
}

export function useDarkMode() {
  const context = useContext(DarkModeContext);
  if (!context) {
    throw new Error('useDarkMode must be used within a DarkModeProvider');
  }
  return context;
}
