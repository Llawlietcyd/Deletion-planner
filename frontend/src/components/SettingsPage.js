import React, { useEffect, useState } from 'react';
import { checkHealth } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

function SettingsPage() {
  const { lang, toggleLang, t } = useLanguage();
  const [health, setHealth] = useState('');

  useEffect(() => {
    let mounted = true;
    async function loadHealth() {
      try {
        const res = await checkHealth();
        if (mounted) {
          setHealth(res.ok ? t.backendHealthy : t.backendUnhealthy);
        }
      } catch {
        if (mounted) {
          setHealth(t.backendUnhealthy);
        }
      }
    }
    loadHealth();
    return () => {
      mounted = false;
    };
  }, [t]);

  return (
    <div className="space-y-4">
      <div className="card !bg-slate-50">
        <h1 className="text-xl font-semibold text-slate-800">{t.settingsTitle}</h1>
        <p className="text-sm text-slate-600 mt-1">{t.settingsSubtitle}</p>
      </div>

      <div className="card">
        <h2 className="text-sm font-semibold text-slate-700">{t.languageSetting}</h2>
        <div className="mt-3 flex items-center justify-between">
          <p className="text-sm text-slate-500">
            {lang === 'en' ? t.languageEnglish : t.languageChinese}
          </p>
          <button onClick={toggleLang} className="btn-primary">
            {t.switchLanguage}
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="text-sm font-semibold text-slate-700">{t.systemStatus}</h2>
        <p className="text-sm text-slate-500 mt-2">{health}</p>
      </div>
    </div>
  );
}

export default SettingsPage;
