import React, { useState } from 'react';
import DailyPlan from './DailyPlan';
import TaskInput from './TaskInput';
import { useLanguage } from '../i18n/LanguageContext';

function TodayPage() {
  const { t } = useLanguage();
  const [refreshSignal, setRefreshSignal] = useState(0);

  return (
    <div className="space-y-6">
      <div className="pt-2">
        <p className="text-sm text-slate-500 mb-1">{new Date().toLocaleDateString()}</p>
        <h1 className="text-3xl md:text-4xl font-semibold tracking-tight text-slate-900">{t.todayTitle}</h1>
        <p className="text-sm text-slate-500 mt-2">{t.todaySubtitle}</p>
      </div>

      <TaskInput
        variant="minimal"
        onTaskCreated={() => setRefreshSignal((v) => v + 1)}
      />

      <DailyPlan refreshSignal={refreshSignal} minimal />
    </div>
  );
}

export default TodayPage;
