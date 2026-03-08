import React, { useEffect, useState } from 'react';
import { getWeeklySummary } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import StatsPanel from './StatsPanel';

function InsightsPage() {
  const { lang, t } = useLanguage();
  const [weekly, setWeekly] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function loadWeekly() {
      try {
        const data = await getWeeklySummary(lang);
        if (mounted) {
          setWeekly(data);
        }
      } catch {
        if (mounted) {
          setWeekly(null);
        }
      }
    }

    loadWeekly();
    return () => {
      mounted = false;
    };
  }, [lang]);

  return (
    <div className="space-y-6">
      <section className="card">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[color:var(--muted)]">
          Measure the loop
        </p>
        <h1 className="mt-2 text-3xl text-[color:var(--text)]">{t.insightsTitle}</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[color:var(--muted)]">{t.insightsSubtitle}</p>
      </section>

      {weekly && (
        <section className="card">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--muted)]">
            {t.weeklySummaryTitle}
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <div className="rounded-[22px] border border-[color:var(--line)] bg-emerald-50 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-emerald-700">{t.completedTasks}</p>
              <p className="mt-2 text-3xl font-semibold text-emerald-800">{weekly.completed}</p>
            </div>
            <div className="rounded-[22px] border border-[color:var(--line)] bg-red-50 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-red-700">{t.deletedTasks}</p>
              <p className="mt-2 text-3xl font-semibold text-red-800">{weekly.deleted}</p>
            </div>
            <div className="rounded-[22px] border border-[color:var(--line)] bg-amber-50 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-amber-700">{t.reviewDeferred}</p>
              <p className="mt-2 text-3xl font-semibold text-amber-800">{weekly.deferred}</p>
            </div>
            <div className="rounded-[22px] border border-[color:var(--line)] bg-sky-50 p-4">
              <p className="text-xs uppercase tracking-[0.14em] text-sky-700">{t.completionRate}</p>
              <p className="mt-2 text-3xl font-semibold text-sky-800">{weekly.completion_rate}%</p>
            </div>
          </div>

          <div className="mt-5 rounded-[24px] border border-[color:var(--line)] bg-[color:var(--bg-strong)] p-5">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-[color:var(--text)]">
              {weekly.summary}
            </pre>
          </div>
        </section>
      )}

      <StatsPanel hideHeader />
    </div>
  );
}

export default InsightsPage;
