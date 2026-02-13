import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { LanguageProvider } from './i18n/LanguageContext';
import Dashboard from './Dashboard';

function App() {
  return (
    <LanguageProvider>
      <div className="App">
        <Router>
          <Routes>
            <Route path="/*" element={<Dashboard />} />
          </Routes>
        </Router>
      </div>
    </LanguageProvider>
  );
}

export default App;
