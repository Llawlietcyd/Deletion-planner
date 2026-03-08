import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { LanguageProvider } from './i18n/LanguageContext';
import { DarkModeProvider } from './i18n/DarkModeContext';
import { ToastProvider } from './components/ToastContext';
import Dashboard from './Dashboard';

function App() {
  return (
    <LanguageProvider>
      <DarkModeProvider>
        <ToastProvider>
          <div className="App">
            <Router>
              <Routes>
                <Route path="/*" element={<Dashboard />} />
              </Routes>
            </Router>
          </div>
        </ToastProvider>
      </DarkModeProvider>
    </LanguageProvider>
  );
}

export default App;
