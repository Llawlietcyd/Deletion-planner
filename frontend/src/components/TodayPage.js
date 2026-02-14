import React from 'react';
import DailyPlan from './DailyPlan';
import { useLanguage } from '../i18n/LanguageContext';

function TodayPage() {
  const { t } = useLanguage();

  return (
    <div className="space-y-4">
      <div className="card !bg-green-50 !border-green-200">
        <h1 className="text-xl font-semibold text-slate-800">{t.todayTitle}</h1>
        <p className="text-sm text-slate-600 mt-1">{t.todaySubtitle}</p>
      </div>
      <DailyPlan />
    </div>
  );
}

export default TodayPage;
