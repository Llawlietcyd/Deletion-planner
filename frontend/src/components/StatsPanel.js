import React, { useEffect, useState } from 'react';
import { getStats } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-[24px] border border-[color:var(--line)] bg-white/70 p-5">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--muted)]">{label}</p>
      <p className="mt-3 text-4xl font-semibold text-[color:var(--text)]">{value}</p>
      {sub && <p className="mt-2 text-sm text-[color:var(--muted)]">{sub}</p>}
    </div>
  );
}

function StatsPanel({ hideHeader = false }) {
  const { t } = useLanguage();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function loadStats() {
      setLoading(true);
      try {
        const data = await getStats();
        if (mounted) {
          setStats(data);
        }
      } catch (err) {
        console.error(err);
        if (mounted) {
          setStats(null);
        }
      }
      if (mounted) {
        setLoading(false);
      }
    }

    loadStats();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="card text-center">
        <p className="text-sm text-[color:var(--muted)]">{t.loadingStats}</p>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="card text-center">
        <p className="text-sm text-[color:var(--muted)]">{t.statsError}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {!hideHeader && <h1 className="text-3xl text-[color:var(--text)]">{t.statsTitle}</h1>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label={t.activeTasks} value={stats.active_tasks} />
        <StatCard label={t.completedTasks} value={stats.completed_tasks} />
        <StatCard label={t.deletedTasks} value={stats.deleted_tasks} />
        <StatCard label={t.totalPlans} value={stats.total_plans} />
      </div>

      <div className="card">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--muted)]">
          {t.completionRate}
        </p>
        <div className="mt-4 flex flex-col gap-4 md:flex-row md:items-center">
          <div className="h-4 flex-1 overflow-hidden rounded-full bg-[color:var(--bg-strong)]">
            <div
              className="h-full rounded-full bg-[color:var(--accent)] transition-all duration-500"
              style={{ width: `${Math.min(stats.completion_rate, 100)}%` }}
            />
          </div>
          <p className="text-3xl font-semibold text-[color:var(--text)]">{stats.completion_rate}%</p>
        </div>
        <p className="mt-3 text-sm text-[color:var(--muted)]">
          {t.completionOf(stats.completed_plan_tasks, stats.total_plan_tasks)}
        </p>
      </div>

      <div className="card bg-[color:var(--bg-strong)]">
        <p className="text-xl italic text-[color:var(--text)]">{t.philosophyQuote}</p>
        <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">{t.philosophySub}</p>
      </div>
    </div>
  );
}

export default StatsPanel;
