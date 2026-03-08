import React, { useState } from 'react';
import DailyPlan from './DailyPlan';
import TaskInput from './TaskInput';
import { useLanguage } from '../i18n/LanguageContext';

function TodayPage() {
  const { t } = useLanguage();
  const [refreshSignal, setRefreshSignal] = useState(0);

  return (
    <div className="space-y-4">
      <section className="px-1">
        <h1 className="text-3xl text-[color:var(--text)]">{t.todayTitle}</h1>
        <p className="mt-2 text-sm text-[color:var(--muted)]">{t.todaySubtitle}</p>
      </section>

      <section className="card py-4">
        <TaskInput
          variant="minimal"
          onTaskCreated={() => setRefreshSignal((value) => value + 1)}
        />
      </section>

      <DailyPlan refreshSignal={refreshSignal} />
    </div>
  );
}

export default TodayPage;
