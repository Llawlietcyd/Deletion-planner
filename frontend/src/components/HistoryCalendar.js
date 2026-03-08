import React, { useMemo, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

const WEEKDAYS_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const WEEKDAYS_ZH = ['日', '一', '二', '三', '四', '五', '六'];

function HistoryCalendar({ history = [], onDateClick }) {
  const { lang } = useLanguage();
  const weekdays = lang === 'zh' ? WEEKDAYS_ZH : WEEKDAYS_EN;
  const [viewDate, setViewDate] = useState(new Date());

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();

  const dateCounts = useMemo(() => {
    const grouped = {};
    history.forEach((entry) => {
      if (!grouped[entry.date]) {
        grouped[entry.date] = { total: 0, completed: 0, deleted: 0 };
      }
      grouped[entry.date].total += 1;
      if (entry.action === 'completed') {
        grouped[entry.date].completed += 1;
      }
      if (entry.action === 'deleted') {
        grouped[entry.date].deleted += 1;
      }
    });
    return grouped;
  }, [history]);

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let index = 0; index < firstDay; index += 1) {
    cells.push(null);
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells.push(day);
  }

  const monthLabel =
    lang === 'zh'
      ? `${year}年 ${month + 1}月`
      : viewDate.toLocaleString('en', { month: 'long', year: 'numeric' });

  const todayStr = new Date().toISOString().slice(0, 10);

  return (
    <div className="card">
      <div className="mb-4 flex items-center justify-between">
        <button onClick={() => setViewDate(new Date(year, month - 1, 1))} className="btn-ghost !px-3">
          Prev
        </button>
        <h3 className="text-xl text-[color:var(--text)]">{monthLabel}</h3>
        <button onClick={() => setViewDate(new Date(year, month + 1, 1))} className="btn-ghost !px-3">
          Next
        </button>
      </div>

      <div className="grid grid-cols-7 gap-2 text-center">
        {weekdays.map((day) => (
          <div key={day} className="py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--muted)]">
            {day}
          </div>
        ))}

        {cells.map((day, index) => {
          if (day === null) {
            return <div key={`empty-${index}`} />;
          }

          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const stats = dateCounts[dateStr];
          const isToday = dateStr === todayStr;

          return (
            <button
              key={dateStr}
              onClick={() => onDateClick && onDateClick(dateStr)}
              className={`relative rounded-2xl px-2 py-3 text-sm font-medium transition-all ${
                isToday
                  ? 'border border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--accent)]'
                  : 'border border-transparent text-[color:var(--text)] hover:border-[color:var(--line)] hover:bg-white/60'
              }`}
            >
              {day}
              {stats?.total > 0 && (
                <span className="absolute bottom-1 left-1/2 flex -translate-x-1/2 gap-1">
                  {stats.completed > 0 && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
                  {stats.deleted > 0 && <span className="h-1.5 w-1.5 rounded-full bg-red-500" />}
                  {stats.completed === 0 && stats.deleted === 0 && (
                    <span className="h-1.5 w-1.5 rounded-full bg-sky-500" />
                  )}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default HistoryCalendar;
