import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { saveFocusSession, getFocusStats } from '../http/api';

const PRESETS = [
  { work: 25, break: 5, label: '25/5' },
  { work: 50, break: 10, label: '50/10' },
];
const LONG_BREAK_MINUTES = 15;
const SESSIONS_BEFORE_LONG_BREAK = 4;
const STORAGE_KEY = 'daymark_focus_timer_v2';

function formatRemaining(totalSeconds) {
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
  const seconds = String(totalSeconds % 60).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

function playCompletionSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.setValueAtTime(523.25, ctx.currentTime);
    osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.15);
    osc.frequency.setValueAtTime(783.99, ctx.currentTime + 0.3);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.6);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.6);
  } catch {
    // Web Audio not available
  }
}

function PixelBellIcon({ muted = false }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={`h-5 w-5 ${muted ? 'opacity-45' : ''}`}
      fill="currentColor"
      shapeRendering="crispEdges"
    >
      <rect x="9" y="2" width="6" height="2" rx="0.5" />
      <rect x="8" y="4" width="8" height="2" rx="0.5" />
      <rect x="7" y="6" width="10" height="2" rx="0.5" />
      <rect x="6" y="8" width="12" height="2" rx="0.5" />
      <rect x="6" y="10" width="12" height="2" rx="0.5" />
      <rect x="5" y="12" width="14" height="2" rx="0.5" />
      <rect x="4" y="14" width="16" height="2" rx="0.5" />
      <rect x="6" y="16" width="12" height="2" rx="0.5" />
      <rect x="9" y="18" width="6" height="2" rx="0.5" />
      <rect x="10" y="20" width="4" height="2" rx="0.5" />
      {muted && (
        <>
          <rect x="4" y="5" width="2" height="2" rx="0.5" />
          <rect x="6" y="7" width="2" height="2" rx="0.5" />
          <rect x="8" y="9" width="2" height="2" rx="0.5" />
          <rect x="10" y="11" width="2" height="2" rx="0.5" />
          <rect x="12" y="13" width="2" height="2" rx="0.5" />
          <rect x="14" y="15" width="2" height="2" rx="0.5" />
          <rect x="16" y="17" width="2" height="2" rx="0.5" />
          <rect x="18" y="19" width="2" height="2" rx="0.5" />
        </>
      )}
    </svg>
  );
}

function FocusTimer({ tasks = [], selectedTaskId, onSelectedTaskChange = () => {}, compact = false }) {
  const { t } = useLanguage();
  const [presetIndex, setPresetIndex] = useState(0);
  const [customWork, setCustomWork] = useState(25);
  const [customBreak, setCustomBreak] = useState(5);
  const [useCustom, setUseCustom] = useState(false);

  const workMinutes = useCustom ? customWork : PRESETS[presetIndex].work;
  const breakMinutes = useCustom ? customBreak : PRESETS[presetIndex].break;

  const [phase, setPhase] = useState('work'); // work | break
  const durationSeconds = useMemo(
    () => (phase === 'work' ? workMinutes : breakMinutes) * 60,
    [phase, workMinutes, breakMinutes]
  );

  const [remainingSeconds, setRemainingSeconds] = useState(durationSeconds);
  const [isRunning, setIsRunning] = useState(false);
  const [targetEpochMs, setTargetEpochMs] = useState(null);
  const [sessionCount, setSessionCount] = useState(0);
  const [savedMessage, setSavedMessage] = useState('');
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [stats, setStats] = useState({ today: { sessions: 0, minutes: 0 }, week: { sessions: 0, minutes: 0 } });
  const [savedWorkMinutes, setSavedWorkMinutes] = useState(0);

  const timerRef = useRef(null);
  const messageTimeoutRef = useRef(null);
  const phaseRef = useRef(phase);
  const sessionCountRef = useRef(sessionCount);
  const runningRef = useRef(isRunning);
  const savedWorkMinutesRef = useRef(savedWorkMinutes);
  const hydratedRef = useRef(false);
  const restoredTaskIdRef = useRef(null);
  const pendingCompletionRef = useRef(false);
  const skipNextDurationResetRef = useRef(false);
  phaseRef.current = phase;
  sessionCountRef.current = sessionCount;
  runningRef.current = isRunning;
  savedWorkMinutesRef.current = savedWorkMinutes;

  const flashMessage = useCallback((message, duration = 3000) => {
    if (messageTimeoutRef.current && typeof window !== 'undefined') {
      window.clearTimeout(messageTimeoutRef.current);
    }
    setSavedMessage(message);
    if (typeof window !== 'undefined') {
      messageTimeoutRef.current = window.setTimeout(() => {
        setSavedMessage('');
        messageTimeoutRef.current = null;
      }, duration);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const data = await getFocusStats();
      setStats(data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    if (messageTimeoutRef.current && typeof window !== 'undefined') {
      window.clearTimeout(messageTimeoutRef.current);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      hydratedRef.current = true;
      return;
    }
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY);
      if (!raw) {
        hydratedRef.current = true;
        return;
      }
      const snapshot = JSON.parse(raw);
      if (typeof snapshot.presetIndex === 'number') setPresetIndex(snapshot.presetIndex);
      if (typeof snapshot.customWork === 'number') setCustomWork(snapshot.customWork);
      if (typeof snapshot.customBreak === 'number') setCustomBreak(snapshot.customBreak);
      if (typeof snapshot.useCustom === 'boolean') setUseCustom(snapshot.useCustom);
      if (snapshot.phase === 'work' || snapshot.phase === 'break') setPhase(snapshot.phase);
      if (typeof snapshot.sessionCount === 'number') setSessionCount(snapshot.sessionCount);
      if (typeof snapshot.soundEnabled === 'boolean') setSoundEnabled(snapshot.soundEnabled);
      if (typeof snapshot.savedWorkMinutes === 'number') setSavedWorkMinutes(snapshot.savedWorkMinutes);
      if (snapshot.selectedTaskId) restoredTaskIdRef.current = Number(snapshot.selectedTaskId);

      const remaining = Number(snapshot.remainingSeconds);
      const target = Number(snapshot.targetEpochMs);
      const shouldResume = Boolean(snapshot.isRunning) && Number.isFinite(target) && target > 0;
      if (shouldResume) {
        skipNextDurationResetRef.current = true;
        const computed = Math.max(0, Math.ceil((target - Date.now()) / 1000));
        if (computed <= 0) {
          setRemainingSeconds(0);
          setTargetEpochMs(null);
          setIsRunning(false);
          pendingCompletionRef.current = true;
        } else {
          setRemainingSeconds(computed);
          setTargetEpochMs(target);
          setIsRunning(true);
        }
      } else if (Number.isFinite(remaining) && remaining > 0) {
        skipNextDurationResetRef.current = true;
        setRemainingSeconds(remaining);
      }
    } catch {
      // Ignore invalid saved timer state.
    } finally {
      hydratedRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (!hydratedRef.current || typeof window === 'undefined') return;
    const snapshot = {
      presetIndex,
      customWork,
      customBreak,
      useCustom,
      phase,
      remainingSeconds,
      isRunning,
      targetEpochMs,
      sessionCount,
      soundEnabled,
      savedWorkMinutes,
      selectedTaskId: selectedTaskId || null,
    };
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  }, [
    customBreak,
    customWork,
    isRunning,
    phase,
    presetIndex,
    remainingSeconds,
    selectedTaskId,
    sessionCount,
    savedWorkMinutes,
    soundEnabled,
    targetEpochMs,
    useCustom,
  ]);

  // Reset remaining only when the configured duration changes, not when pausing or hydrating.
  useEffect(() => {
    if (!hydratedRef.current) return;
    if (skipNextDurationResetRef.current) {
      skipNextDurationResetRef.current = false;
      return;
    }
    if (!runningRef.current) {
      setRemainingSeconds(durationSeconds);
    }
  }, [durationSeconds]);

  const persistFocusMinutes = useCallback(async (minutes) => {
    if (minutes <= 0) return true;

    try {
      await saveFocusSession(selectedTaskId || null, minutes, 'work');
      await loadStats();
      return true;
    } catch (err) {
      if (err?.status === 404 && selectedTaskId) {
        try {
          await saveFocusSession(null, minutes, 'work');
          await loadStats();
          return true;
        } catch (retryErr) {
          flashMessage(retryErr.message || t.focusSaveFailed || 'Focus session could not be saved.');
          return false;
        }
      }
      flashMessage(err.message || t.focusSaveFailed || 'Focus session could not be saved.');
      return false;
    }
  }, [flashMessage, loadStats, selectedTaskId, t.focusSaveFailed]);

  const handleSessionComplete = useCallback(() => {
    if (soundEnabled) playCompletionSound();

    if (phaseRef.current === 'work') {
      const unsavedMinutes = Math.max(0, workMinutes - savedWorkMinutesRef.current);
      const newCount = sessionCountRef.current + 1;
      setSessionCount(newCount);
      setSavedWorkMinutes(0);

      const completionMessage = newCount % SESSIONS_BEFORE_LONG_BREAK === 0
        ? (t.focusLongBreakStart || 'Time for a long break!')
        : t.focusCompleted;

      if (newCount % SESSIONS_BEFORE_LONG_BREAK === 0) {
        setPhase('break');
        setRemainingSeconds(LONG_BREAK_MINUTES * 60);
      } else {
        setPhase('break');
        setRemainingSeconds(breakMinutes * 60);
      }

      void (async () => {
        const saved = await persistFocusMinutes(unsavedMinutes);
        if (saved) {
          flashMessage(completionMessage);
        }
      })();
    } else {
      setPhase('work');
      setRemainingSeconds(workMinutes * 60);
      setSavedWorkMinutes(0);
      flashMessage(t.focusBreakDone || 'Break over!');
    }
  }, [breakMinutes, flashMessage, persistFocusMinutes, soundEnabled, t, workMinutes]);

  const persistElapsedWork = useCallback(async (remainingNow) => {
    if (phaseRef.current !== 'work') return 0;
    const elapsedMinutes = Math.floor(((workMinutes * 60) - remainingNow) / 60);
    const unsavedMinutes = Math.max(0, elapsedMinutes - savedWorkMinutesRef.current);
    if (unsavedMinutes <= 0) return 0;
    const saved = await persistFocusMinutes(unsavedMinutes);
    if (!saved) return 0;
    setSavedWorkMinutes((current) => current + unsavedMinutes);
    return unsavedMinutes;
  }, [persistFocusMinutes, workMinutes]);

  useEffect(() => {
    if (!hydratedRef.current || !pendingCompletionRef.current) return;
    pendingCompletionRef.current = false;
    handleSessionComplete();
  }, [handleSessionComplete]);

  useEffect(() => {
    if (!isRunning || !targetEpochMs) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    const tick = () => {
      const next = Math.max(0, Math.ceil((targetEpochMs - Date.now()) / 1000));
      setRemainingSeconds(next);
      if (next <= 0) {
        clearInterval(timerRef.current);
        setIsRunning(false);
        setTargetEpochMs(null);
        handleSessionComplete();
      }
    };

    tick();
    timerRef.current = setInterval(() => {
      tick();
    }, 1000);

    return () => clearInterval(timerRef.current);
  }, [handleSessionComplete, isRunning, targetEpochMs]);

  useEffect(() => {
    if (tasks.length === 0) return;
    if (restoredTaskIdRef.current && tasks.some((task) => task.id === restoredTaskIdRef.current)) {
      onSelectedTaskChange(restoredTaskIdRef.current);
      restoredTaskIdRef.current = null;
      return;
    }
    if (!selectedTaskId || !tasks.some((task) => task.id === selectedTaskId)) {
      onSelectedTaskChange(tasks[0].id);
    }
  }, [onSelectedTaskChange, selectedTaskId, tasks]);

  const canRun = tasks.length > 0 && Boolean(selectedTaskId);
  const progress = durationSeconds > 0 ? 1 - remainingSeconds / durationSeconds : 0;
  const circumference = 2 * Math.PI * 54;

  const wrapperClass = compact ? 'h-full rounded-[18px] bg-white/56 p-2.5' : 'card';

  return (
    <section className={wrapperClass}>
      {compact ? (
        <div className="space-y-2.5">
          <div>
            <h2 className="text-[14px] text-[color:var(--text)]">{t.focusTitle}</h2>
            <p className="mt-1 max-w-[18rem] text-[11px] leading-5 text-[color:var(--muted)]">{t.focusSubtitle}</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-[12px] bg-white/60 px-2 py-1.5 text-center">
              <p className="text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)]">{t.focusSessions}</p>
              <p className="mt-1 text-lg font-semibold text-[color:var(--text)]">{stats.today.sessions}</p>
            </div>
            <div className="rounded-[12px] bg-white/60 px-2 py-1.5 text-center">
              <p className="text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)]">{t.focusMinutes}</p>
              <p className="mt-1 text-lg font-semibold text-[color:var(--text)]">{stats.today.minutes}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg text-[color:var(--text)]">{t.focusTitle}</h2>
            <p className="mt-1 text-sm text-[color:var(--muted)]">{t.focusSubtitle}</p>
          </div>
          <div className="flex gap-2">
            <div className="rounded-[12px] bg-white/60 px-2 py-1.5 text-center">
              <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">{t.focusSessions}</p>
              <p className="mt-1 text-lg font-semibold text-[color:var(--text)]">{stats.today.sessions}</p>
            </div>
            <div className="rounded-[12px] bg-white/60 px-2 py-1.5 text-center">
              <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--muted)]">{t.focusMinutes}</p>
              <p className="mt-1 text-lg font-semibold text-[color:var(--text)]">{stats.today.minutes}</p>
            </div>
          </div>
        </div>
      )}

      {/* Preset selector */}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {PRESETS.map((preset, idx) => (
          <button
            key={preset.label}
            onClick={() => { setPresetIndex(idx); setUseCustom(false); setIsRunning(false); setPhase('work'); }}
            className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
              !useCustom && presetIndex === idx
                ? 'border-[color:var(--accent)] bg-[color:var(--accent)] text-white'
                : 'border-[color:var(--line)] text-[color:var(--muted)] hover:border-[color:var(--accent)]'
            }`}
          >
            {preset.label}
          </button>
        ))}
        <button
          onClick={() => { setUseCustom(true); setIsRunning(false); setPhase('work'); }}
          className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
            useCustom
              ? 'border-[color:var(--accent)] bg-[color:var(--accent)] text-white'
              : 'border-[color:var(--line)] text-[color:var(--muted)] hover:border-[color:var(--accent)]'
          }`}
        >
          {t.focusCustom || 'Custom'}
        </button>
        {useCustom && (
          <div className="flex items-center gap-2 text-xs text-[color:var(--muted)]">
            <input
              type="number"
              min={1}
              max={120}
              value={customWork}
              onChange={(e) => setCustomWork(Math.max(1, Math.min(120, Number(e.target.value))))}
              className="w-14 rounded-[12px] border border-[color:var(--line)] bg-white/80 px-2 py-1 text-center text-[color:var(--text)] outline-none"
            />
            <span>/</span>
            <input
              type="number"
              min={1}
              max={60}
              value={customBreak}
              onChange={(e) => setCustomBreak(Math.max(1, Math.min(60, Number(e.target.value))))}
              className="w-14 rounded-[12px] border border-[color:var(--line)] bg-white/80 px-2 py-1 text-center text-[color:var(--text)] outline-none"
            />
            <span>min</span>
          </div>
        )}
        <button
          onClick={() => setSoundEnabled((v) => !v)}
          className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-[10px] border border-[color:var(--line)] bg-white/75 text-[color:var(--text)] transition-colors hover:border-[color:var(--accent)] hover:text-[color:var(--accent)]"
          title={soundEnabled ? (t.focusSoundOn || 'Sound on') : (t.focusSoundOff || 'Sound off')}
          aria-label={soundEnabled ? (t.focusSoundOn || 'Sound on') : (t.focusSoundOff || 'Sound off')}
          aria-pressed={soundEnabled}
        >
          <PixelBellIcon muted={!soundEnabled} />
        </button>
      </div>

      <div className={`grid gap-2.5 ${compact ? 'mt-2' : 'mt-4'} md:grid-cols-[1fr_auto] md:items-end`}>
        <label className="text-sm text-[color:var(--muted)]">
          <span className="mb-2 block">{t.focusSelectTask}</span>
          <select
            value={selectedTaskId || ''}
            onChange={(event) => onSelectedTaskChange(Number(event.target.value))}
            disabled={tasks.length === 0}
            className="w-full rounded-[14px] border border-[color:var(--line)] bg-white/80 px-3 py-2 text-sm text-[color:var(--text)] outline-none"
          >
            {tasks.length === 0 && <option value="">{t.focusNoTask}</option>}
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>
                {task.title}
              </option>
            ))}
          </select>
        </label>

        {/* SVG Progress Ring */}
        <div className="flex flex-col items-center">
          <div className={`relative flex items-center justify-center ${compact ? 'h-[74px] w-[74px]' : 'h-28 w-28'}`}>
            <svg className="absolute inset-0" viewBox="0 0 120 120">
              <circle cx="60" cy="60" r="54" fill="none" stroke="var(--line)" strokeWidth="6" />
              <circle
                cx="60" cy="60" r="54" fill="none"
                stroke="var(--accent)" strokeWidth="6" strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={circumference * (1 - progress)}
                transform="rotate(-90 60 60)"
                className="transition-[stroke-dashoffset] duration-1000 ease-linear"
              />
            </svg>
            <div className="text-center">
              <p className={`${compact ? 'text-[15px]' : 'text-xl'} font-semibold tracking-tight text-[color:var(--text)]`}>
                {formatRemaining(remainingSeconds)}
              </p>
              <p className={`${compact ? 'text-[9px]' : 'text-[10px]'} uppercase tracking-wider text-[color:var(--muted)]`}>
                {phase === 'work' ? (t.focusWorkPhase || 'Focus') : (t.focusBreakPhase || 'Break')}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {!isRunning ? (
          <button
            onClick={() => {
              setTargetEpochMs(Date.now() + remainingSeconds * 1000);
              setIsRunning(true);
            }}
            disabled={!canRun}
            className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            {remainingSeconds === durationSeconds ? t.focusStart : t.focusResume}
          </button>
        ) : (
          <button
            onClick={async () => {
              const next = targetEpochMs ? Math.max(0, Math.ceil((targetEpochMs - Date.now()) / 1000)) : remainingSeconds;
              const recordedMinutes = await persistElapsedWork(next);
              setRemainingSeconds(next);
              setIsRunning(false);
              setTargetEpochMs(null);
              if (recordedMinutes > 0) {
                flashMessage(
                  t.focusPausedSaved
                    ? t.focusPausedSaved.replace('{minutes}', String(recordedMinutes))
                    : `Saved ${recordedMinutes} minute(s).`,
                  2000
                );
              }
            }}
            className="btn-primary"
          >
            {t.focusPause}
          </button>
        )}
        <button
          onClick={async () => {
            if (isRunning) {
              const next = targetEpochMs ? Math.max(0, Math.ceil((targetEpochMs - Date.now()) / 1000)) : remainingSeconds;
              await persistElapsedWork(next);
            }
            setIsRunning(false);
            setTargetEpochMs(null);
            setPhase('work');
            setRemainingSeconds(workMinutes * 60);
            setSavedWorkMinutes(0);
          }}
          className="btn-ghost"
        >
          {t.focusReset}
        </button>
        {sessionCount > 0 && (
          <span className="text-xs text-[color:var(--muted)]">
            #{sessionCount}
          </span>
        )}
        {savedMessage && (
          <span className="self-center text-sm text-[color:var(--accent)]">{savedMessage}</span>
        )}
      </div>
    </section>
  );
}

export default FocusTimer;
