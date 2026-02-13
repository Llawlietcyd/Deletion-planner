import React, { useState, useEffect } from 'react';
import { getHistory } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

function HistoryPanel() {
  const { t } = useLanguage();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const ACTION_STYLE = {
    created:   { bg: 'bg-slate-100', text: 'text-slate-600', label: t.actionCreated },
    planned:   { bg: 'bg-blue-100',  text: 'text-blue-600',  label: t.actionPlanned },
    completed: { bg: 'bg-green-100', text: 'text-green-600', label: t.actionCompleted },
    missed:    { bg: 'bg-slate-100', text: 'text-slate-500', label: t.actionMissed },
    deferred:  { bg: 'bg-amber-100', text: 'text-amber-600', label: t.actionDeferred },
    deleted:   { bg: 'bg-red-100',   text: 'text-red-600',   label: t.actionDeleted },
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const data = await getHistory();
      setHistory(data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="card text-center py-10">
        <p className="text-slate-400">{t.loadingHistory}</p>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-slate-800">{t.historyTitle}</h1>
        <div className="card text-center py-10">
          <p className="text-4xl mb-3">📜</p>
          <p className="text-slate-500">{t.noHistory}</p>
          <p className="text-slate-400 text-sm mt-1">{t.noHistorySub}</p>
        </div>
      </div>
    );
  }

  // Group by date
  const grouped = {};
  history.forEach((h) => {
    if (!grouped[h.date]) grouped[h.date] = [];
    grouped[h.date].push(h);
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">{t.historyTitle}</h1>

      {Object.entries(grouped)
        .sort(([a], [b]) => b.localeCompare(a))
        .map(([date, entries]) => (
          <div key={date}>
            <h3 className="text-sm font-semibold text-slate-500 mb-2">{date}</h3>
            <div className="space-y-1">
              {entries.map((entry) => {
                const style = ACTION_STYLE[entry.action] || ACTION_STYLE.created;
                return (
                  <div key={entry.id} className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-slate-50">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${style.bg} ${style.text} w-20 text-center`}>
                      {style.label}
                    </span>
                    <span className="text-sm text-slate-700 flex-1">
                      {t.taskLabel(entry.task_id)}
                    </span>
                    {entry.ai_reasoning && (
                      <span className="text-xs text-slate-400 max-w-xs truncate">
                        {entry.ai_reasoning}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
    </div>
  );
}

export default HistoryPanel;
