import React, { useState, useEffect } from 'react';
import { getStats } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

function StatCard({ label, value, sub, color = 'text-slate-800' }) {
  return (
    <div className="card text-center">
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
      <p className="text-sm font-medium text-slate-600 mt-1">{label}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function StatsPanel({ hideHeader = false }) {
  const { t } = useLanguage();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setLoading(true);
    try {
      const data = await getStats();
      setStats(data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="card text-center py-10">
        <p className="text-slate-400">{t.loadingStats}</p>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="card text-center py-10">
        <p className="text-slate-400">{t.statsError}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {!hideHeader && (
        <h1 className="text-2xl font-bold text-slate-800">{t.statsTitle}</h1>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label={t.activeTasks} value={stats.active_tasks} color="text-core" />
        <StatCard label={t.completedTasks} value={stats.completed_tasks} color="text-success" />
        <StatCard label={t.deletedTasks} value={stats.deleted_tasks} color="text-deletion" />
        <StatCard label={t.totalPlans} value={stats.total_plans} color="text-brand" />
      </div>

      <div className="card">
        <h3 className="font-semibold text-slate-800 mb-4">{t.completionRate}</h3>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="h-4 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand to-success rounded-full transition-all duration-500"
                style={{ width: `${Math.min(stats.completion_rate, 100)}%` }}
              />
            </div>
          </div>
          <span className="text-2xl font-bold text-slate-800">
            {stats.completion_rate}%
          </span>
        </div>
        <p className="text-sm text-slate-500 mt-2">
          {t.completionOf(stats.completed_plan_tasks, stats.total_plan_tasks)}
        </p>
      </div>

      <div className="card !bg-slate-50 text-center">
        <p className="text-lg font-medium text-slate-600 italic">
          {t.philosophyQuote}
        </p>
        <p className="text-sm text-slate-400 mt-2">{t.philosophySub}</p>
      </div>
    </div>
  );
}

export default StatsPanel;
