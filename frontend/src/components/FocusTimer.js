import React, { useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

const DURATION_SECONDS = 25 * 60;

function formatRemaining(totalSeconds) {
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
  const seconds = String(totalSeconds % 60).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

function FocusTimer({ tasks = [], selectedTaskId, onSelectedTaskChange }) {
  const { t } = useLanguage();
  const todayKey = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const statsKey = `focus_stats_${todayKey}`;
  const [remainingSeconds, setRemainingSeconds] = useState(DURATION_SECONDS);
  const [isRunning, setIsRunning] = useState(false);
  const [savedMessage, setSavedMessage] = useState('');
  const [stats, setStats] = useState(() => {
    try {
      const cached = window.localStorage.getItem(statsKey);
      if (!cached) {
        return { sessions: 0, minutes: 0 };
      }
      const parsed = JSON.parse(cached);
      return {
        sessions: Number(parsed.sessions) || 0,
        minutes: Number(parsed.minutes) || 0,
      };
    } catch {
      return { sessions: 0, minutes: 0 };
    }
  });

  useEffect(() => {
    window.localStorage.setItem(statsKey, JSON.stringify(stats));
  }, [stats, statsKey]);

  useEffect(() => {
    if (!isRunning) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setRemainingSeconds((current) => {
        if (current <= 1) {
          window.clearInterval(timer);
          setIsRunning(false);
          setStats((previous) => ({
            sessions: previous.sessions + 1,
            minutes: previous.minutes + 25,
          }));
          setSavedMessage(t.focusCompleted);
          window.setTimeout(() => setSavedMessage(''), 2500);
          return DURATION_SECONDS;
        }
        return current - 1;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, [isRunning, t.focusCompleted]);

  useEffect(() => {
    if (tasks.length === 0) {
      return;
    }
    if (!selectedTaskId || !tasks.some((task) => task.id === selectedTaskId)) {
      onSelectedTaskChange(tasks[0].id);
    }
  }, [onSelectedTaskChange, selectedTaskId, tasks]);

  const canRun = tasks.length > 0 && Boolean(selectedTaskId);

  return (
    <section className="card">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl text-[color:var(--text)]">{t.focusTitle}</h2>
          <p className="mt-1 text-sm text-[color:var(--muted)]">{t.focusSubtitle}</p>
        </div>
        <div className="flex gap-3">
          <div className="rounded-[18px] bg-white/60 px-4 py-3 text-center">
            <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">{t.focusSessions}</p>
            <p className="mt-1 text-2xl font-semibold text-[color:var(--text)]">{stats.sessions}</p>
          </div>
          <div className="rounded-[18px] bg-white/60 px-4 py-3 text-center">
            <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">{t.focusMinutes}</p>
            <p className="mt-1 text-2xl font-semibold text-[color:var(--text)]">{stats.minutes}</p>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
        <label className="text-sm text-[color:var(--muted)]">
          <span className="mb-2 block">{t.focusSelectTask}</span>
          <select
            value={selectedTaskId || ''}
            onChange={(event) => onSelectedTaskChange(Number(event.target.value))}
            disabled={tasks.length === 0}
            className="w-full rounded-[18px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none"
          >
            {tasks.length === 0 && <option value="">{t.focusNoTask}</option>}
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>
                {task.title}
              </option>
            ))}
          </select>
        </label>

        <div className="rounded-[20px] border border-[color:var(--line)] bg-[color:var(--bg-strong)] px-5 py-4 text-center">
          <p className="text-4xl font-semibold tracking-tight text-[color:var(--text)]">
            {formatRemaining(remainingSeconds)}
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {!isRunning ? (
          <button
            onClick={() => setIsRunning(true)}
            disabled={!canRun}
            className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            {remainingSeconds === DURATION_SECONDS ? t.focusStart : t.focusResume}
          </button>
        ) : (
          <button onClick={() => setIsRunning(false)} className="btn-primary">
            {t.focusPause}
          </button>
        )}
        <button
          onClick={() => {
            setIsRunning(false);
            setRemainingSeconds(DURATION_SECONDS);
          }}
          className="btn-ghost"
        >
          {t.focusReset}
        </button>
        {savedMessage && <span className="self-center text-sm text-[color:var(--accent)]">{savedMessage}</span>}
      </div>
    </section>
  );
}

export default FocusTimer;
