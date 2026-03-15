import React, { useEffect, useState } from 'react';
import { getHistory } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

function HistoryPanel({ hideHeader = false }) {
  const { lang, t } = useLanguage();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const pageSize = 50;
  const hasChinese = (text) => /[\u3400-\u9fff]/.test(text || '');
  const fallbackReason = (action) => {
    const map = {
      created: t.historyReasonCreated,
      planned: t.historyReasonPlanned,
      completed: t.historyReasonCompleted,
      missed: t.historyReasonMissed,
      deferred: t.historyReasonDeferred,
      deleted: t.historyReasonDeleted,
      restored: t.historyReasonRestored,
    };
    return map[action] || '';
  };

  const actionStyle = {
    created: 'bg-slate-100 text-slate-700',
    planned: 'bg-sky-100 text-sky-700',
    completed: 'bg-emerald-100 text-emerald-700',
    missed: 'bg-slate-200 text-slate-700',
    deferred: 'bg-amber-100 text-amber-700',
    deleted: 'bg-red-100 text-red-700',
    restored: 'bg-sky-100 text-sky-700',
  };

  useEffect(() => {
    let mounted = true;
    async function loadInitial() {
      setLoading(true);
      try {
        const data = await getHistory(null, pageSize, 0);
        if (mounted) {
          setHistory(data || []);
          setHasMore((data || []).length >= pageSize);
        }
      } catch (err) {
        console.error(err);
        if (mounted) {
          setHistory([]);
          setHasMore(false);
        }
      }
      if (mounted) {
        setLoading(false);
      }
    }

    loadInitial();
    return () => {
      mounted = false;
    };
  }, []);

  const handleLoadMore = async () => {
    setLoadingMore(true);
    try {
      const data = await getHistory(null, pageSize, history.length);
      setHistory((current) => [...current, ...(data || [])]);
      setHasMore((data || []).length >= pageSize);
    } catch (err) {
      console.error(err);
    }
    setLoadingMore(false);
  };

  if (loading) {
    return (
      <div className="card text-center">
        <p className="text-sm text-[color:var(--muted)]">{t.loadingHistory}</p>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="space-y-4">
        {!hideHeader && <h1 className="text-3xl text-[color:var(--text)]">{t.historyTitle}</h1>}
        <div className="card text-center">
          <p className="text-lg text-[color:var(--text)]">{t.noHistory}</p>
          <p className="mt-2 text-sm text-[color:var(--muted)]">{t.noHistorySub}</p>
        </div>
      </div>
    );
  }

  const grouped = history.reduce((accumulator, entry) => {
    const dateKey = entry.date || 'unknown';
    if (!accumulator[dateKey]) {
      accumulator[dateKey] = [];
    }
    accumulator[dateKey].push(entry);
    return accumulator;
  }, {});

  return (
    <div className="space-y-6">
      {!hideHeader && <h1 className="text-3xl text-[color:var(--text)]">{t.historyTitle}</h1>}

      {Object.entries(grouped)
        .sort(([left], [right]) => right.localeCompare(left))
        .map(([date, entries]) => (
          <section key={date} className="card">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--muted)]">{date}</p>
            <div className="mt-4 space-y-3">
              {entries.map((entry) => (
                <div
                  key={entry.id}
                  className="flex flex-col gap-2 rounded-[22px] border border-[color:var(--line)] bg-white/70 px-4 py-3 md:flex-row md:items-center md:justify-between"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                        actionStyle[entry.action] || actionStyle.created
                      }`}
                    >
                      {t[`action${entry.action.charAt(0).toUpperCase()}${entry.action.slice(1)}`] || entry.action}
                    </span>
                    <p className="truncate text-sm text-[color:var(--text)]">
                      {entry.task_title || t.taskLabel(entry.task_id, entry.task_title)}
                    </p>
                  </div>

                  {(entry.ai_reasoning || fallbackReason(entry.action)) && (
                    <p className="text-sm text-[color:var(--muted)] md:max-w-md md:text-right">
                      {lang === 'zh' && entry.ai_reasoning && !hasChinese(entry.ai_reasoning)
                        ? fallbackReason(entry.action)
                        : entry.ai_reasoning || fallbackReason(entry.action)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))}

      {hasMore && (
        <div className="text-center">
          <button onClick={handleLoadMore} disabled={loadingMore} className="btn-ghost">
            {loadingMore ? t.loadingMore : t.loadMore}
          </button>
        </div>
      )}

      {!hasMore && history.length > pageSize && (
        <p className="text-center text-xs uppercase tracking-[0.16em] text-[color:var(--muted)]">
          {t.noMoreHistory}
        </p>
      )}
    </div>
  );
}

export default HistoryPanel;
