import React from 'react';
import StatsPanel from './StatsPanel';
import { useLanguage } from '../i18n/LanguageContext';

function InsightsPage() {
  const { t } = useLanguage();

  return (
    <div className="space-y-4">
      <div className="card !bg-blue-50 !border-blue-200">
        <h1 className="text-xl font-semibold text-slate-800">{t.insightsTitle}</h1>
        <p className="text-sm text-slate-600 mt-1">{t.insightsSubtitle}</p>
      </div>
      <StatsPanel hideHeader />
    </div>
  );
}

export default InsightsPage;
