import React, { useEffect } from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { LanguageProvider } from './i18n/LanguageContext';
import { DarkModeProvider } from './i18n/DarkModeContext';
import { ToastProvider } from './components/ToastContext';
import AuthGate from './components/AuthGate';
import { SessionProvider } from './components/SessionContext';
import { useLanguage } from './i18n/LanguageContext';

function AppShell() {
  const { t } = useLanguage();

  useEffect(() => {
    document.title = `${t.appName} · ${t.navToday}`;
  }, [t]);

  return (
    <div className="App">
      <Router>
        <AuthGate />
      </Router>
    </div>
  );
}

function App() {
  return (
    <LanguageProvider>
      <DarkModeProvider>
        <ToastProvider>
          <SessionProvider>
            <AppShell />
          </SessionProvider>
        </ToastProvider>
      </DarkModeProvider>
    </LanguageProvider>
  );
}

export default App;
