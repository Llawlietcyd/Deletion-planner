import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { useToast } from './ToastContext';
import { getTodayMood, submitMood, getMoodHistory } from '../http/api';

const MOOD_OPTIONS = [
  { level: 1, blobClass: 'blob-rough', mouthClass: 'mouth-wavy', accentClass: 'is-rough', particle: '~', eyeClass: '' },
  { level: 2, blobClass: 'blob-low', mouthClass: 'mouth-sad', accentClass: 'is-low', particle: '·', eyeClass: '' },
  { level: 3, blobClass: 'blob-neutral', mouthClass: 'mouth-neutral', accentClass: 'is-neutral', particle: '—', eyeClass: '' },
  { level: 4, blobClass: 'blob-good', mouthClass: 'mouth-smile', accentClass: 'is-good', particle: '✦', eyeClass: '' },
  { level: 5, blobClass: 'blob-great', mouthClass: 'mouth-smile-wide', accentClass: 'is-great', particle: '✶', eyeClass: 'eyes-squint' },
];

const APP_TIMEZONE = 'America/New_York';
const DAY_WAVE_WIDTH = 200;
const DAY_WAVE_HEIGHT = 112;

function formatDateKeyInTimezone(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: APP_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${lookup.year}-${lookup.month}-${lookup.day}`;
}

function parseDateKey(dateKey) {
  if (!dateKey) {
    return new Date();
  }
  const [year, month, day] = dateKey.split('-').map(Number);
  return new Date(Date.UTC(year, (month || 1) - 1, day || 1, 12));
}

function monthKeyFromDate(dateKey) {
  return dateKey ? dateKey.slice(0, 7) : formatDateKeyInTimezone(new Date()).slice(0, 7);
}

function shiftMonthKey(monthKey, delta) {
  const [year, month] = monthKey.split('-').map(Number);
  const next = new Date(Date.UTC(year, (month || 1) - 1 + delta, 1, 12));
  return `${next.getUTCFullYear()}-${String(next.getUTCMonth() + 1).padStart(2, '0')}`;
}

function getEntryTimestamp(entry) {
  const raw = entry?.created_at || entry?.date;
  const stamp = raw ? new Date(raw).getTime() : Number.NaN;
  return Number.isFinite(stamp) ? stamp : Number.NaN;
}

function getTimelinePositionPercent(entries, index, minPercent = 0, maxPercent = 100) {
  if (!entries.length) {
    return 50;
  }
  if (entries.length === 1) {
    return (minPercent + maxPercent) / 2;
  }
  const stamps = entries.map(getEntryTimestamp).filter(Number.isFinite);
  if (stamps.length < 2) {
    return minPercent + ((maxPercent - minPercent) * index) / (entries.length - 1);
  }
  const start = Math.min(...stamps);
  const end = Math.max(...stamps);
  const current = getEntryTimestamp(entries[index]);
  if (!Number.isFinite(current) || end <= start) {
    return minPercent + ((maxPercent - minPercent) * index) / (entries.length - 1);
  }
  const normalized = (current - start) / (end - start);
  return minPercent + normalized * (maxPercent - minPercent);
}

function getMoodY(level, range = {}) {
  const top = range.top ?? 12;
  const bottom = range.bottom ?? 54;
  const dynamic = Boolean(range.dynamic);
  const minLevel = range.minLevel ?? 1;
  const maxLevel = range.maxLevel ?? 5;

  if (!dynamic) {
    return bottom - ((level - 1) / 4) * (bottom - top);
  }
  if (maxLevel <= minLevel) {
    return (top + bottom) / 2;
  }
  const normalized = (level - minLevel) / (maxLevel - minLevel);
  return bottom - normalized * (bottom - top);
}

function buildWaveGeometry(entries, options = {}) {
  if (!entries.length) {
    return { points: '', areaPoints: '', dots: [] };
  }
  const moodLevels = entries.map((entry) => Number(entry.mood_level || 0)).filter(Boolean);
  const dynamicRange = {
    top: options.top ?? 12,
    bottom: options.bottom ?? 54,
    dynamic: Boolean(options.dynamicScale),
    minLevel: Math.min(...moodLevels),
    maxLevel: Math.max(...moodLevels),
  };
  const dots = entries.map((entry, index) => {
    const x = getTimelinePositionPercent(entries, index, options.minX ?? 8, options.maxX ?? 192);
    const y = getMoodY(entry.mood_level, dynamicRange);
    return { x, y, entry, index };
  });
  const bottom = dynamicRange.bottom;
  return {
    points: dots.map(({ x, y }) => `${x},${y}`).join(' '),
    areaPoints: [
      `${dots[0].x},${bottom}`,
      ...dots.map(({ x, y }) => `${x},${y}`),
      `${dots[dots.length - 1].x},${bottom}`,
    ].join(' '),
    dots,
  };
}

function buildTimelineMarkers(entries, lang) {
  let lastDate = '';
  let previousLeft = -Infinity;
  let currentLane = 0;

  return entries.map((entry, index) => {
    const left = getTimelinePositionPercent(entries, index, 2, 98);
    const dateChanged = entry.date !== lastDate;
    const timestamp = entry?.created_at ? new Date(entry.created_at) : null;
    const label = timestamp
      ? new Intl.DateTimeFormat(lang === 'zh' ? 'zh-CN' : 'en-US', dateChanged ? {
        timeZone: APP_TIMEZONE,
        month: 'numeric',
        day: 'numeric',
        hour: 'numeric',
      } : {
        timeZone: APP_TIMEZONE,
        hour: 'numeric',
        minute: '2-digit',
      }).format(timestamp)
      : (entry?.date || '');

    if (left - previousLeft < 14) {
      currentLane = (currentLane + 1) % 3;
    } else {
      currentLane = 0;
    }

    lastDate = entry.date;
    previousLeft = left;

    return {
      entry,
      index,
      left,
      lane: currentLane,
      label,
    };
  });
}

function MoodCheckIn({ onMoodLogged, refreshSignal = 0 }) {
  const { t, lang } = useLanguage();
  const { showToast } = useToast();
  const [selectedMood, setSelectedMood] = useState(null);
  const [savedMood, setSavedMood] = useState(null);
  const [note, setNote] = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [animationTick, setAnimationTick] = useState(0);
  const [celebrating, setCelebrating] = useState(false);
  const [selectedDate, setSelectedDate] = useState('');
  const [calendarMonth, setCalendarMonth] = useState(monthKeyFromDate(formatDateKeyInTimezone(new Date())));
  const [detailsOpen, setDetailsOpen] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [todayData, historyData] = await Promise.all([
        getTodayMood(),
        getMoodHistory(60),
      ]);
      if (todayData.mood_level) {
        setSavedMood(todayData.mood_level);
        setNote(todayData.note || '');
      }
      if (todayData.date) {
        setSelectedDate((value) => value || todayData.date);
        setCalendarMonth((value) => value || monthKeyFromDate(todayData.date));
      }
      setHistory(historyData || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData, refreshSignal]);

  useEffect(() => {
    if (!animationTick) {
      return undefined;
    }
    setCelebrating(true);
    const timer = window.setTimeout(() => setCelebrating(false), 1400);
    return () => window.clearTimeout(timer);
  }, [animationTick]);

  const handleSubmit = async () => {
    if (!selectedMood) return;
    try {
      const created = await submitMood(selectedMood, note);
      setSavedMood(selectedMood);
      if (created?.date) {
        setSelectedDate(created.date);
        setCalendarMonth(monthKeyFromDate(created.date));
      }
      setAnimationTick((value) => value + 1);
      const historyData = await getMoodHistory(60);
      setHistory(historyData || []);
      if (onMoodLogged) {
        onMoodLogged(created);
      }
    } catch (err) {
      showToast(err.message || 'Failed to save mood');
    }
  };

  const moodLabels = [t.moodTerrible, t.moodBad, t.moodOkay, t.moodGood, t.moodGreat];
  const moodSignals = [
    t.moodSignalTerrible,
    t.moodSignalBad,
    t.moodSignalOkay,
    t.moodSignalGood,
    t.moodSignalGreat,
  ];
  const selectedConfig = MOOD_OPTIONS.find((option) => option.level === selectedMood) || null;
  const currentSignal = selectedMood ? moodSignals[selectedMood - 1] : t.moodStageIdle;
  const timelineEntries = useMemo(() => [...history]
    .filter((entry) => entry.created_at)
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    .slice(-7), [history]);
  const allEntries = useMemo(() => [...history]
    .filter((entry) => entry.date)
    .sort((a, b) => new Date(a.created_at || a.date) - new Date(b.created_at || b.date)), [history]);
  const fallbackDate = allEntries[allEntries.length - 1]?.date || formatDateKeyInTimezone(new Date());
  const activeDate = selectedDate || fallbackDate;

  useEffect(() => {
    if (!selectedDate && fallbackDate) {
      setSelectedDate(fallbackDate);
    }
  }, [fallbackDate, selectedDate]);

  const formatDayLabel = (dateKey) => new Intl.DateTimeFormat(lang === 'zh' ? 'zh-CN' : 'en-US', {
    timeZone: APP_TIMEZONE,
    month: 'short',
    day: 'numeric',
    weekday: 'short',
  }).format(parseDateKey(dateKey));

  const formatMonthLabel = (monthKey) => new Intl.DateTimeFormat(lang === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: 'long',
  }).format(parseDateKey(`${monthKey}-01`));

  const formatDetailTime = (entry) => {
    if (!entry?.created_at) {
      return entry?.date || '';
    }
    return new Intl.DateTimeFormat(lang === 'zh' ? 'zh-CN' : 'en-US', {
      timeZone: APP_TIMEZONE,
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date(entry.created_at));
  };

  const trendSummary = useMemo(() => {
    if (timelineEntries.length < 2) {
      return t.moodTrendInsufficient;
    }
    const todayEntries = timelineEntries.filter((entry) => entry.date === timelineEntries[timelineEntries.length - 1].date);
    if (todayEntries.length >= 2) {
      const startDelta = todayEntries[todayEntries.length - 1].mood_level - todayEntries[0].mood_level;
      if (startDelta >= 1) {
        return t.moodTrendTodayUp;
      }
      if (startDelta <= -1) {
        return t.moodTrendTodayDown;
      }
    }
    const recent = timelineEntries.slice(-3);
    const previous = timelineEntries.slice(0, Math.max(1, timelineEntries.length - recent.length));
    const recentAvg = recent.reduce((sum, entry) => sum + entry.mood_level, 0) / recent.length;
    const previousAvg = previous.reduce((sum, entry) => sum + entry.mood_level, 0) / previous.length;
    const delta = recentAvg - previousAvg;

    if (delta >= 0.55) {
      return t.moodTrendRising;
    }
    if (delta <= -0.55) {
      return t.moodTrendFalling;
    }
    return t.moodTrendStable;
  }, [timelineEntries, t]);
  const entriesByDate = useMemo(() => allEntries.reduce((acc, entry) => {
    if (!acc[entry.date]) {
      acc[entry.date] = [];
    }
    acc[entry.date].push(entry);
    return acc;
  }, {}), [allEntries]);
  const selectedDayEntries = useMemo(
    () => [...(entriesByDate[activeDate] || [])].sort((a, b) => new Date(a.created_at || a.date) - new Date(b.created_at || b.date)),
    [entriesByDate, activeDate],
  );
  const dayAverage = selectedDayEntries.length
    ? selectedDayEntries.reduce((sum, entry) => sum + entry.mood_level, 0) / selectedDayEntries.length
    : null;
  const daySwing = selectedDayEntries.length
    ? Math.max(...selectedDayEntries.map((entry) => entry.mood_level)) - Math.min(...selectedDayEntries.map((entry) => entry.mood_level))
    : 0;
  const notedEntries = selectedDayEntries.filter((entry) => entry.note && entry.note.trim());
  const latestDayNote = notedEntries[notedEntries.length - 1]?.note?.trim() || '';
  const timelineMarkers = useMemo(() => buildTimelineMarkers(timelineEntries, lang), [lang, timelineEntries]);
  const dayWave = useMemo(() => buildWaveGeometry(selectedDayEntries, {
    dynamicScale: true,
    top: 8,
    bottom: 104,
    minX: 10,
    maxX: DAY_WAVE_WIDTH - 10,
  }), [selectedDayEntries]);
  const currentMonthDate = parseDateKey(`${calendarMonth}-01`);
  const monthFirstWeekday = currentMonthDate.getUTCDay();
  const monthDays = new Date(Date.UTC(currentMonthDate.getUTCFullYear(), currentMonthDate.getUTCMonth() + 1, 0, 12)).getUTCDate();
  const weekdayLabels = lang === 'zh' ? ['日', '一', '二', '三', '四', '五', '六'] : ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  const calendarCells = useMemo(() => {
    const cells = [];
    for (let i = 0; i < monthFirstWeekday; i += 1) {
      cells.push(null);
    }
    for (let day = 1; day <= monthDays; day += 1) {
      const dateKey = `${calendarMonth}-${String(day).padStart(2, '0')}`;
      const entries = entriesByDate[dateKey] || [];
      const latestLevel = entries[entries.length - 1]?.mood_level || null;
      cells.push({ dateKey, day, latestLevel, count: entries.length });
    }
    return cells;
  }, [calendarMonth, entriesByDate, monthDays, monthFirstWeekday]);
  const dayDigest = useMemo(() => {
    if (!selectedDayEntries.length) {
      return t.moodDayEmpty;
    }
    if (latestDayNote) {
      return t.moodAIDigest(latestDayNote);
    }
    if (dayAverage >= 4) {
      return t.moodDigestHigh;
    }
    if (dayAverage <= 2) {
      return t.moodDigestLow;
    }
    return t.moodDigestMid;
  }, [selectedDayEntries, latestDayNote, dayAverage, t]);

  if (loading) return null;

  return (
    <section className={`card mood-shell overflow-visible ${selectedConfig ? selectedConfig.accentClass : ''} ${celebrating ? 'is-celebrating' : ''}`}>
      <div className="mood-shell-backdrop" aria-hidden="true" />
      <div className="mood-shell-weather" aria-hidden="true">
        {Array.from({ length: 4 }).map((_, index) => (
          <span key={index} style={{ '--cloud-left': `${10 + index * 24}%`, '--cloud-delay': `${index * 0.22}s` }} />
        ))}
      </div>
      <div className="mood-shell-glow" aria-hidden="true" />
      <div className="mood-shell-ribbon" aria-hidden="true" />
      <div className="mood-shell-scene" aria-hidden="true">
        {Array.from({ length: 8 }).map((_, index) => (
          <span
            key={index}
            style={{
              '--scene-delay': `${index * 0.08}s`,
              '--scene-left': `${8 + (index % 4) * 22}%`,
              '--scene-size': `${18 + (index % 5) * 10}px`,
            }}
          />
        ))}
      </div>
      <div className="mood-shell-burst" aria-hidden="true">
        {celebrating ? Array.from({ length: 10 }).map((_, index) => (
          <span
            key={index}
            style={{
              '--burst-delay': `${index * 0.06}s`,
              '--tx': `${(index % 2 === 0 ? 1 : -1) * (28 + (index % 4) * 14)}px`,
              '--ty': `${-18 - (index % 4) * 12}px`,
            }}
          />
        )) : null}
      </div>
      <div className="flex flex-col gap-2.5 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg text-[color:var(--text)]">{t.moodTitle}</h2>
              <p className="mt-1 text-sm text-[color:var(--muted)]">{t.moodSubtitle}</p>
            </div>
            <div className="hidden min-w-[210px] rounded-[14px] border border-[color:var(--line)] bg-white/58 px-3 py-2 md:block">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]">{t.moodTimeline}</p>
                <p className="text-[10px] text-[color:var(--muted)]">{t.moodAISignal}</p>
              </div>
              <div className="timeline-track mt-2">
                <div className="timeline-line" />
                {timelineMarkers.map(({ entry, index, left, lane, label }) => (
                  <div
                    key={`${entry.id}-${entry.created_at || entry.date}`}
                    className={`timeline-node-wrap ${savedMood === entry.mood_level && index === timelineEntries.length - 1 ? 'is-today' : ''}`}
                    style={{ left: `${left}%` }}
                    title={`${entry.date} · ${moodLabels[entry.mood_level - 1]}`}
                  >
                    <div className={`timeline-node level-${entry.mood_level}`} />
                    <span className={`timeline-label lane-${lane}`}>{label}</span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[11px] leading-4 text-[color:var(--muted)]">{trendSummary}</p>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-start gap-1.5">
            {MOOD_OPTIONS.map((option) => (
              <button
                key={option.level}
                onClick={() => {
                  setSelectedMood(option.level);
                }}
                className={`mood-chip ${selectedMood === option.level ? 'is-selected' : ''}`}
                title={moodLabels[option.level - 1]}
              >
                <div className={`mood-face ${option.blobClass} ${selectedMood === option.level ? option.accentClass : ''}`}>
                  {option.level === 1 ? <div className="mood-scribble" /> : null}
                  <div className="mood-features">
                    <div className={`mood-eyes ${option.eyeClass || ''}`}><span /><span /></div>
                    <div className="mood-nose" />
                    <div className={`mood-mouth ${option.mouthClass}`} />
                  </div>
                </div>
                <span className="mood-chip-label">{moodLabels[option.level - 1]}</span>
              </button>
            ))}
          </div>

          <div
            key={`${selectedMood || 0}-${animationTick}`}
            className={`mood-stage ${selectedConfig ? selectedConfig.accentClass : ''} ${celebrating ? 'stage-submitted' : ''}`}
          >
            <div className="mood-stage-copy">
              <p className="mood-stage-kicker">{selectedMood ? t.moodSelected : t.moodAISignal}</p>
              <p className="mood-stage-text">{currentSignal}</p>
              {!selectedMood ? <p className="mt-1 text-[11px] text-[color:var(--muted)]">{trendSummary}</p> : null}
            </div>
            <div className="mood-stage-visual" aria-hidden="true">
              {selectedConfig ? (
                <>
                  {Array.from({ length: 12 }).map((_, index) => (
                    <span
                      key={`${selectedConfig.level}-${index}`}
                      className={`mood-particle ${selectedConfig.accentClass}`}
                      style={{
                        '--delay': `${index * 0.1}s`,
                        '--offset': `${8 + (index % 6) * 14}px`,
                      }}
                    >
                      {selectedConfig.particle}
                    </span>
                  ))}
                  <div className={`mood-face mood-face-mini ${selectedConfig.blobClass} ${selectedConfig.accentClass}`}>
                    {selectedConfig.level === 1 ? <div className="mood-scribble" /> : null}
                    <div className="mood-features">
                      <div className={`mood-eyes ${selectedConfig.eyeClass || ''}`}><span /><span /></div>
                      <div className="mood-nose" />
                      <div className={`mood-mouth ${selectedConfig.mouthClass}`} />
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-xs text-[color:var(--muted)]">{lang === 'zh' ? '选一个心情开始。' : 'Pick a mood to start.'}</div>
              )}
            </div>
          </div>

          <div className="mt-3 rounded-[18px] border border-[color:var(--line)] bg-white/46 px-3 py-2">
            <button
              type="button"
              onClick={() => setDetailsOpen((value) => !value)}
              className="flex w-full items-center justify-between gap-4 text-left"
            >
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--muted)]">{t.moodCalendar}</p>
                <p className="mt-1 text-sm text-[color:var(--text)]">{formatDayLabel(activeDate)}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="mood-stat-pill">{t.moodEntryCount(selectedDayEntries.length)}</span>
                <span className="mood-stat-pill">{dayAverage ? moodLabels[Math.max(0, Math.round(dayAverage) - 1)] : t.moodNoEntry}</span>
                <span className="text-sm text-[color:var(--muted)]">{detailsOpen ? '▾' : '▸'}</span>
              </div>
            </button>

            {detailsOpen ? (
              <div className="mt-3 grid gap-3 lg:grid-cols-[280px_minmax(0,1fr)]">
                <div className="mood-calendar-panel">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--muted)]">{t.moodCalendar}</p>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => setCalendarMonth((value) => shiftMonthKey(value, -1))}
                        className="calendar-nav-button"
                      >
                        ‹
                      </button>
                      <span className="calendar-month-label">{formatMonthLabel(calendarMonth)}</span>
                      <button
                        type="button"
                        onClick={() => setCalendarMonth((value) => shiftMonthKey(value, 1))}
                        className="calendar-nav-button"
                      >
                        ›
                      </button>
                    </div>
                  </div>
                  <div className="calendar-weekdays">
                    {weekdayLabels.map((label) => (
                      <span key={label}>{label}</span>
                    ))}
                  </div>
                  <div className="calendar-grid">
                    {calendarCells.map((cell, index) => (
                      cell ? (
                        <button
                          key={cell.dateKey}
                          type="button"
                          onClick={() => setSelectedDate(cell.dateKey)}
                          className={`calendar-day ${activeDate === cell.dateKey ? 'is-active' : ''} ${cell.latestLevel ? `level-${cell.latestLevel}` : ''}`}
                        >
                          <span>{cell.day}</span>
                          {cell.latestLevel ? <i className="calendar-day-dot" /> : null}
                        </button>
                      ) : (
                        <span key={`blank-${index}`} className="calendar-day is-blank" />
                      )
                    ))}
                  </div>
                </div>

                <div className="mood-day-panel">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--muted)]">{t.moodDayDetail}</p>
                      <h3 className="mt-1 text-sm font-medium text-[color:var(--text)]">{formatDayLabel(activeDate)}</h3>
                    </div>
                    <div className="flex flex-wrap gap-2 text-[11px] text-[color:var(--muted)]">
                      <span className="mood-stat-pill">{t.moodAverageValue(dayAverage ? dayAverage.toFixed(1) : '--')}</span>
                      <span className="mood-stat-pill">{t.moodSwingValue(daySwing)}</span>
                    </div>
                  </div>

                  <div className="mood-wave-shell">
                    {selectedDayEntries.length ? (
                      <div className="mood-wave-chart">
                        <svg viewBox={`0 0 ${DAY_WAVE_WIDTH} ${DAY_WAVE_HEIGHT}`} className="mood-wave-svg" preserveAspectRatio="none" aria-hidden="true">
                          <polygon points={dayWave.areaPoints} className="mood-wave-area" />
                          <polyline points={dayWave.points} className="mood-wave-line" />
                        </svg>
                        {dayWave.dots.map(({ entry, index, x, y }) => (
                          <span
                            key={entry.id || `${entry.date}-${index}`}
                            className={`mood-wave-dot-pin level-${entry.mood_level}`}
                            style={{
                              left: `${(x / DAY_WAVE_WIDTH) * 100}%`,
                              top: `${(y / DAY_WAVE_HEIGHT) * 100}%`,
                            }}
                            aria-hidden="true"
                          />
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-[color:var(--muted)]">{t.moodDayEmpty}</div>
                    )}
                  </div>

                  <div className="mood-day-digest">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--muted)]">{t.moodAISignal}</p>
                    <p className="mt-1 text-sm leading-6 text-[color:var(--text)]">{dayDigest}</p>
                  </div>

                  <div className="mood-entry-list">
                    {selectedDayEntries.length ? selectedDayEntries.map((entry, index) => (
                      <article key={entry.id || `${entry.date}-${index}`} className="mood-entry-card">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <span className={`timeline-node level-${entry.mood_level}`} />
                            <span className="text-sm font-medium text-[color:var(--text)]">{moodLabels[entry.mood_level - 1]}</span>
                          </div>
                          <span className="text-[11px] text-[color:var(--muted)]">{formatDetailTime(entry)}</span>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">
                          {entry.note?.trim() ? entry.note : t.moodNoNote}
                        </p>
                      </article>
                    )) : (
                      <div className="rounded-[16px] border border-dashed border-[color:var(--line)] px-4 py-4 text-sm text-[color:var(--muted)]">
                        {t.moodDayEmpty}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="w-full xl:w-[260px]">
          <div className="flex flex-col gap-2 sm:flex-row xl:flex-col">
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t.moodNotePlaceholder}
              className="min-w-0 flex-1 rounded-full border border-[color:var(--line)] bg-white/82 px-4 py-2 text-sm text-[color:var(--text)] outline-none transition focus:border-[color:var(--accent)]"
            />
            <button
              onClick={handleSubmit}
              disabled={!selectedMood}
              className="rounded-full bg-[color:var(--accent)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-45"
            >
              {t.moodSubmit}
            </button>
          </div>
        </div>
      </div>

      <style>{`
        .mood-shell {
          position: relative;
          padding-top: 12px;
          padding-bottom: 12px;
        }
        .mood-shell-backdrop {
          position: absolute;
          inset: 0;
          border-radius: inherit;
          opacity: 0;
          pointer-events: none;
          transition: opacity 220ms ease;
        }
        .mood-shell-backdrop::before,
        .mood-shell-backdrop::after {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: inherit;
          opacity: 0;
        }
        .mood-shell-weather {
          position: absolute;
          inset: 0;
          overflow: hidden;
          pointer-events: none;
        }
        .mood-shell-weather span {
          position: absolute;
          opacity: 0;
          transition: opacity 220ms ease;
        }
        .timeline-track {
          position: relative;
          height: 70px;
        }
        .timeline-line {
          position: absolute;
          top: 8px;
          left: 0;
          right: 0;
          height: 2px;
          border-radius: 999px;
          background: linear-gradient(90deg, rgba(255, 109, 109, 0.34), rgba(125, 143, 219, 0.26), rgba(255, 201, 91, 0.32));
        }
        .timeline-node {
          width: 14px;
          height: 14px;
          border-radius: 999px;
          border: 2px solid rgba(255,255,255,0.82);
          box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        }
        .timeline-node-wrap {
          position: absolute;
          top: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 3px;
          transform: translateX(-50%);
        }
        .timeline-node.level-1 { background: #ff6a62; }
        .timeline-node.level-2 { background: #ff9a62; }
        .timeline-node.level-3 { background: #7e95ff; }
        .timeline-node.level-4 { background: #46d577; }
        .timeline-node.level-5 { background: #ffc64f; }
        .timeline-node-wrap.is-today .timeline-node {
          transform: scale(1.1);
          box-shadow: 0 0 0 4px rgba(255,255,255,0.34);
        }
        .timeline-label {
          position: absolute;
          top: 18px;
          left: 50%;
          transform: translateX(-50%);
          font-size: 9px;
          line-height: 1;
          color: var(--muted);
          white-space: nowrap;
          text-align: center;
        }
        .timeline-label.lane-1 {
          top: 30px;
        }
        .timeline-label.lane-2 {
          top: 42px;
        }
        .mood-calendar-panel,
        .mood-day-panel {
          position: relative;
          border: 1px solid var(--line);
          border-radius: 18px;
          background: rgba(255, 255, 255, 0.62);
          padding: 10px 12px;
          backdrop-filter: blur(14px);
        }
        .calendar-weekdays,
        .calendar-grid {
          display: grid;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          gap: 6px;
        }
        .calendar-weekdays {
          margin-top: 10px;
          font-size: 10px;
          color: var(--muted);
          text-align: center;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }
        .calendar-grid {
          margin-top: 8px;
        }
        .calendar-nav-button {
          width: 24px;
          height: 24px;
          border-radius: 999px;
          border: 1px solid var(--line);
          background: rgba(255,255,255,0.8);
          color: var(--text);
          line-height: 1;
        }
        .calendar-month-label {
          min-width: 98px;
          text-align: center;
          font-size: 12px;
          color: var(--text);
        }
        .calendar-day {
          position: relative;
          min-height: 36px;
          border-radius: 12px;
          border: 1px solid rgba(0,0,0,0.05);
          background: rgba(255,255,255,0.76);
          color: var(--text);
          font-size: 12px;
          transition: transform 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
        }
        .calendar-day:hover {
          transform: translateY(-1px);
        }
        .calendar-day.is-active {
          border-color: rgba(210, 86, 44, 0.45);
          box-shadow: 0 10px 24px rgba(210, 86, 44, 0.12);
        }
        .calendar-day.is-blank {
          background: transparent;
          border-color: transparent;
        }
        .calendar-day-dot {
          position: absolute;
          left: 50%;
          bottom: 5px;
          width: 6px;
          height: 6px;
          border-radius: 999px;
          transform: translateX(-50%);
          background: currentColor;
          opacity: 0.9;
        }
        .calendar-day.level-1 { color: #ff6a62; }
        .calendar-day.level-2 { color: #ff9a62; }
        .calendar-day.level-3 { color: #7e95ff; }
        .calendar-day.level-4 { color: #46d577; }
        .calendar-day.level-5 { color: #ffc64f; }
        .mood-stat-pill {
          border-radius: 999px;
          border: 1px solid var(--line);
          background: rgba(255,255,255,0.74);
          padding: 5px 10px;
        }
        .mood-wave-shell {
          margin-top: 12px;
          border-radius: 16px;
          background: linear-gradient(180deg, rgba(255,255,255,0.66), rgba(250,243,234,0.8));
          padding: 6px 10px 2px;
        }
        .mood-wave-chart {
          position: relative;
          width: 100%;
          height: 112px;
        }
        .mood-wave-svg {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          display: block;
        }
        .mood-wave-area {
          fill: rgba(210, 86, 44, 0.08);
        }
        .mood-wave-line {
          fill: none;
          stroke: rgba(210, 86, 44, 0.72);
          stroke-width: 3;
          stroke-linecap: round;
          stroke-linejoin: round;
        }
        .mood-wave-dot-pin {
          position: absolute;
          width: 12px;
          height: 12px;
          border-radius: 999px;
          border: 2px solid rgba(255,255,255,0.9);
          transform: translate(-50%, -50%);
          box-shadow: 0 6px 16px rgba(0,0,0,0.08);
        }
        .mood-wave-dot-pin.level-1 { background: #ff6a62; }
        .mood-wave-dot-pin.level-2 { background: #ff9a62; }
        .mood-wave-dot-pin.level-3 { background: #7e95ff; }
        .mood-wave-dot-pin.level-4 { background: #46d577; }
        .mood-wave-dot-pin.level-5 { background: #ffc64f; }
        .mood-day-digest {
          margin-top: 12px;
          border-radius: 16px;
          background: rgba(255,255,255,0.66);
          padding: 10px 12px;
        }
        .mood-entry-list {
          margin-top: 10px;
          display: grid;
          gap: 8px;
        }
        .mood-entry-card {
          border-radius: 16px;
          background: rgba(255,255,255,0.7);
          border: 1px solid rgba(0,0,0,0.05);
          padding: 10px 12px;
        }
        .mood-shell.is-rough .mood-shell-backdrop {
          opacity: 1;
          background:
            radial-gradient(circle at 50% 104%, rgba(255, 78, 66, 0.28), transparent 26%),
            radial-gradient(circle at 28% 98%, rgba(255, 140, 72, 0.14), transparent 16%),
            radial-gradient(circle at 72% 98%, rgba(255, 96, 46, 0.12), transparent 16%);
        }
        .mood-shell.is-rough .mood-shell-backdrop::before {
          inset: auto 9% 3% 9%;
          height: 18%;
          opacity: 1;
          background:
            radial-gradient(circle at 18% 78%, rgba(255, 118, 54, 0.14), transparent 10%),
            radial-gradient(circle at 46% 88%, rgba(255, 72, 53, 0.18), transparent 15%),
            radial-gradient(circle at 74% 82%, rgba(255, 162, 68, 0.12), transparent 12%),
            linear-gradient(180deg, rgba(255, 115, 44, 0), rgba(189, 22, 22, 0.16));
          filter: blur(6px);
          animation: mood-lava-bed 3200ms ease-in-out infinite;
        }
        .mood-shell.is-rough .mood-shell-backdrop::after {
          inset: auto 12% 4% 12%;
          height: 12%;
          opacity: 1;
          background: linear-gradient(180deg, rgba(255, 188, 82, 0), rgba(255, 75, 48, 0.1) 52%, rgba(130, 0, 0, 0.06));
          mix-blend-mode: screen;
          animation: mood-ember-glow 1800ms ease-in-out infinite;
        }
        .mood-shell.is-low .mood-shell-backdrop {
          opacity: 1;
          background:
            linear-gradient(180deg, rgba(88, 109, 150, 0.14), rgba(255,255,255,0) 34%),
            radial-gradient(circle at 50% -10%, rgba(124, 145, 188, 0.18), transparent 34%);
        }
        .mood-shell.is-low .mood-shell-backdrop::before {
          inset: -4% -6% auto -6%;
          height: 42%;
          opacity: 1;
          background:
            radial-gradient(circle at 18% 62%, rgba(133, 149, 178, 0.18), transparent 16%),
            radial-gradient(circle at 44% 48%, rgba(124, 141, 170, 0.24), transparent 20%),
            radial-gradient(circle at 72% 58%, rgba(142, 156, 183, 0.2), transparent 18%);
          filter: blur(12px);
          animation: mood-cloudbank 4200ms ease-in-out infinite;
        }
        .mood-shell.is-low .mood-shell-backdrop::after {
          inset: 0;
          opacity: 0.72;
          background: linear-gradient(180deg, rgba(132, 165, 220, 0.1), rgba(255,255,255,0) 38%);
        }
        .mood-shell.is-neutral .mood-shell-backdrop {
          opacity: 1;
          background:
            linear-gradient(90deg, rgba(144, 164, 221, 0.08), rgba(255,255,255,0.03) 32%, rgba(144, 164, 221, 0.06) 70%, transparent);
        }
        .mood-shell.is-neutral .mood-shell-backdrop::before {
          inset: 22% -8% 22% -8%;
          opacity: 1;
          background: repeating-linear-gradient(
            90deg,
            rgba(139, 160, 226, 0.02) 0 20px,
            rgba(139, 160, 226, 0.08) 20px 58px,
            rgba(255,255,255,0) 58px 100px
          );
          animation: mood-neutral-drift 3000ms linear infinite;
        }
        .mood-shell.is-good .mood-shell-backdrop {
          opacity: 1;
          background:
            radial-gradient(circle at 18% 78%, rgba(123, 224, 148, 0.12), transparent 18%),
            radial-gradient(circle at 84% 18%, rgba(150, 240, 160, 0.12), transparent 16%);
        }
        .mood-shell.is-good .mood-shell-backdrop::before {
          inset: auto -6% -8% -6%;
          height: 44%;
          opacity: 1;
          background:
            radial-gradient(circle at 12% 84%, rgba(144, 232, 148, 0.14), transparent 16%),
            radial-gradient(circle at 52% 90%, rgba(87, 210, 118, 0.16), transparent 18%),
            radial-gradient(circle at 82% 86%, rgba(138, 230, 136, 0.14), transparent 14%);
          filter: blur(10px);
          animation: mood-meadow-breathe 3400ms ease-in-out infinite;
        }
        .mood-shell.is-great .mood-shell-backdrop {
          opacity: 1;
          background:
            radial-gradient(circle at 50% -8%, rgba(255, 215, 106, 0.24), transparent 28%),
            radial-gradient(circle at 18% 22%, rgba(255, 178, 73, 0.14), transparent 18%),
            radial-gradient(circle at 82% 18%, rgba(255, 204, 93, 0.14), transparent 16%);
        }
        .mood-shell.is-great .mood-shell-backdrop::before {
          inset: -18% -8% auto -8%;
          height: 52%;
          opacity: 1;
          background:
            radial-gradient(circle at 50% 0%, rgba(255, 233, 152, 0.28), transparent 30%),
            radial-gradient(circle at 24% 24%, rgba(255, 184, 84, 0.12), transparent 18%),
            radial-gradient(circle at 78% 18%, rgba(255, 215, 102, 0.14), transparent 16%);
          filter: blur(10px);
          animation: mood-sun-pulse 2600ms ease-in-out infinite;
        }
        .mood-shell.is-low .mood-shell-weather span {
          top: 18px;
          left: var(--cloud-left);
          width: 94px;
          height: 26px;
          border-radius: 999px;
          background: linear-gradient(180deg, rgba(129, 145, 176, 0.28), rgba(178, 188, 210, 0.16));
          filter: blur(0.2px);
          box-shadow:
            -20px 8px 0 6px rgba(176, 186, 208, 0.13),
            18px 4px 0 2px rgba(176, 186, 208, 0.16);
          opacity: 0.78;
        }
        .mood-shell.is-great .mood-shell-weather span {
          top: 18px;
          left: var(--cloud-left);
          width: 12px;
          height: 12px;
          background: radial-gradient(circle, rgba(255,249,209,0.92) 0%, rgba(255,214,87,0.92) 48%, rgba(255,160,60,0.78) 100%);
          clip-path: polygon(50% 0%, 62% 34%, 100% 50%, 62% 66%, 50% 100%, 38% 66%, 0% 50%, 38% 34%);
          box-shadow: 0 0 14px rgba(255, 206, 93, 0.34);
          opacity: 0.92;
        }
        .mood-shell.is-good .mood-shell-weather span {
          bottom: 18px;
          left: var(--cloud-left);
          width: 14px;
          height: 18px;
          border-radius: 0 100% 0 100%;
          background: linear-gradient(135deg, rgba(190, 255, 165, 0.92), rgba(78, 219, 117, 0.92));
          opacity: 0.8;
        }
        .mood-shell.is-neutral .mood-shell-weather span {
          top: 46%;
          left: var(--cloud-left);
          width: 78px;
          height: 2px;
          border-radius: 999px;
          background: linear-gradient(90deg, rgba(170, 189, 255, 0), rgba(142, 162, 233, 0.8), rgba(170, 189, 255, 0));
          opacity: 0.48;
        }
        .mood-shell.is-rough .mood-shell-weather span {
          bottom: 10px;
          left: var(--cloud-left);
          width: 42px;
          height: 8px;
          border-radius: 999px 999px 30% 30%;
          background: linear-gradient(180deg, rgba(255, 140, 72, 0.1), rgba(255, 59, 42, 0.18));
          opacity: 0.28;
          filter: blur(3px);
        }
        .mood-shell.is-rough .mood-shell-weather span {
          animation: mood-heat-roll 2600ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .mood-shell.is-low .mood-shell-weather span {
          animation: mood-cloud-drift 3200ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .mood-shell.is-neutral .mood-shell-weather span {
          animation: mood-current-breathe 2400ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .mood-shell.is-good .mood-shell-weather span {
          animation: mood-leaf-sway 2800ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .mood-shell.is-great .mood-shell-weather span {
          animation: mood-star-twinkle 1800ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .mood-shell-glow {
          position: absolute;
          inset: 0;
          background:
            radial-gradient(circle at 15% 25%, rgba(255, 110, 87, 0.18), transparent 30%),
            radial-gradient(circle at 85% 25%, rgba(255, 191, 73, 0.2), transparent 28%),
            radial-gradient(circle at 50% 100%, rgba(120, 198, 255, 0.12), transparent 34%);
          opacity: 0.6;
          pointer-events: none;
        }
        .mood-shell.is-rough .mood-shell-glow {
          background:
            radial-gradient(circle at 50% 101%, rgba(255, 62, 62, 0.24), transparent 22%),
            radial-gradient(circle at 30% 22%, rgba(255, 122, 69, 0.12), transparent 16%),
            radial-gradient(circle at 70% 24%, rgba(255, 204, 92, 0.1), transparent 14%);
          opacity: 0.58;
        }
        .mood-shell.is-low .mood-shell-glow {
          background:
            linear-gradient(180deg, rgba(95, 131, 191, 0.14), transparent 30%),
            radial-gradient(circle at 50% 0%, rgba(118, 156, 219, 0.14), transparent 36%);
          opacity: 0.7;
        }
        .mood-shell.is-neutral .mood-shell-glow {
          background:
            linear-gradient(90deg, rgba(122, 145, 219, 0.1), transparent 26%, rgba(255,255,255,0.04) 60%, transparent 100%);
          opacity: 0.54;
        }
        .mood-shell.is-good .mood-shell-glow {
          background:
            radial-gradient(circle at 20% 35%, rgba(89, 211, 137, 0.18), transparent 24%),
            radial-gradient(circle at 80% 30%, rgba(132, 228, 158, 0.18), transparent 22%);
          opacity: 0.72;
        }
        .mood-shell.is-great .mood-shell-glow {
          background:
            radial-gradient(circle at 50% 50%, rgba(255, 205, 84, 0.18), transparent 30%),
            radial-gradient(circle at 80% 24%, rgba(255, 157, 54, 0.18), transparent 20%);
          opacity: 0.82;
        }
        .mood-shell-ribbon {
          position: absolute;
          inset: -20% -30%;
          background: linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.42) 50%, transparent 70%);
          opacity: 0;
          transform: translateX(-50%) rotate(-6deg);
          pointer-events: none;
        }
        .mood-shell-scene {
          position: absolute;
          inset: -34% -10% -52%;
          overflow: visible;
          pointer-events: none;
        }
        .mood-shell.is-rough .mood-shell-scene {
          inset: auto 4% -6% 4%;
        }
        .mood-shell-scene span {
          position: absolute;
          left: var(--scene-left);
          bottom: 0;
          width: var(--scene-size);
          height: var(--scene-size);
          opacity: 0;
          transform: translate3d(0, 0, 0) scale(0.7);
        }
        .mood-shell.is-rough .mood-shell-scene span {
          background: linear-gradient(180deg, #fff5b2 0%, #ffb53d 24%, #ff6b33 58%, #b71414 100%);
          clip-path: polygon(50% 0%, 66% 12%, 84% 34%, 78% 62%, 58% 100%, 42% 100%, 22% 62%, 16% 34%, 34% 12%);
          box-shadow: 0 0 12px rgba(255, 100, 43, 0.22);
        }
        .mood-shell.is-low .mood-shell-scene span {
          width: 3px;
          height: calc(var(--scene-size) * 3.2);
          border-radius: 999px;
          background: linear-gradient(180deg, rgba(220, 236, 255, 0), rgba(143, 183, 255, 0.95));
        }
        .mood-shell.is-neutral .mood-shell-scene span {
          width: calc(var(--scene-size) * 2.6);
          height: 3px;
          border-radius: 999px;
          background: linear-gradient(90deg, rgba(175, 192, 255, 0), rgba(140, 161, 255, 0.95), rgba(175, 192, 255, 0));
        }
        .mood-shell.is-good .mood-shell-scene span {
          width: calc(var(--scene-size) * 0.8);
          height: calc(var(--scene-size) * 1.2);
          border-radius: 0 100% 0 100%;
          background: linear-gradient(135deg, #c8ffab, #4fdc79);
          filter: drop-shadow(0 4px 10px rgba(79, 220, 121, 0.24));
        }
        .mood-shell.is-great .mood-shell-scene span {
          width: calc(var(--scene-size) * 1.15);
          height: calc(var(--scene-size) * 1.15);
          background: radial-gradient(circle, #fff9d2 0%, #ffd95b 45%, #ff9a37 95%);
          clip-path: polygon(50% 0%, 61% 32%, 95% 24%, 69% 50%, 95% 76%, 61% 68%, 50% 100%, 39% 68%, 5% 76%, 31% 50%, 5% 24%, 39% 32%);
          filter: drop-shadow(0 8px 18px rgba(255, 180, 64, 0.34));
        }
        .mood-shell-burst {
          position: absolute;
          inset: 0;
          overflow: hidden;
          pointer-events: none;
        }
        .mood-shell-burst span {
          position: absolute;
          top: 50%;
          left: 50%;
          width: 10px;
          height: 10px;
          border-radius: 999px;
          background: rgba(255, 184, 92, 0.95);
          opacity: 0;
          transform: translate(-50%, -50%);
        }
        .mood-shell.is-rough .mood-shell-burst span {
          width: 14px;
          height: 14px;
          background: radial-gradient(circle at 30% 30%, #ffd66b, #ff5a36 62%, #ff2a2a);
          box-shadow: 0 0 16px rgba(255, 77, 54, 0.45);
          border-radius: 40% 60% 60% 40%;
        }
        .mood-shell.is-low .mood-shell-burst span {
          top: -8%;
          width: 2px;
          height: 28px;
          border-radius: 999px;
          background: linear-gradient(180deg, rgba(185, 217, 255, 0.2), rgba(112, 164, 255, 0.95));
          box-shadow: 0 0 8px rgba(112, 164, 255, 0.22);
        }
        .mood-shell.is-neutral .mood-shell-burst span {
          width: 20px;
          height: 2px;
          border-radius: 999px;
          background: linear-gradient(90deg, rgba(145, 168, 255, 0.15), rgba(126, 150, 255, 0.9));
        }
        .mood-shell.is-good .mood-shell-burst span {
          width: 12px;
          height: 12px;
          border-radius: 50% 0 50% 50%;
          background: linear-gradient(135deg, #9bf39d, #47d56b);
        }
        .mood-shell.is-great .mood-shell-burst span {
          width: 12px;
          height: 12px;
          background: radial-gradient(circle, #fff3b0 0%, #ffd350 55%, #ff9b38 100%);
          clip-path: polygon(50% 0%, 62% 35%, 100% 50%, 62% 65%, 50% 100%, 38% 65%, 0% 50%, 38% 35%);
        }
        .is-celebrating .mood-shell-ribbon {
          animation: mood-shell-sweep 900ms ease-out forwards;
        }
        .is-celebrating.mood-shell.is-rough .mood-shell-ribbon {
          background: linear-gradient(100deg, transparent 20%, rgba(255, 131, 66, 0.22) 40%, rgba(255, 61, 61, 0.52) 55%, transparent 78%);
          animation-name: mood-lava-sweep;
        }
        .is-celebrating.mood-shell.is-low .mood-shell-ribbon {
          background: repeating-linear-gradient(
            100deg,
            transparent 0 10px,
            rgba(170, 208, 255, 0.25) 10px 12px,
            transparent 12px 22px
          );
          animation-name: mood-rain-sheet;
        }
        .is-celebrating.mood-shell.is-neutral .mood-shell-ribbon {
          background: linear-gradient(90deg, transparent 10%, rgba(155, 176, 255, 0.18) 50%, transparent 90%);
        }
        .is-celebrating.mood-shell.is-good .mood-shell-ribbon {
          background: linear-gradient(100deg, transparent 15%, rgba(106, 226, 145, 0.18) 45%, rgba(155, 244, 169, 0.28) 55%, transparent 82%);
        }
        .is-celebrating.mood-shell.is-great .mood-shell-ribbon {
          background: linear-gradient(100deg, transparent 15%, rgba(255, 219, 95, 0.18) 42%, rgba(255, 190, 74, 0.34) 55%, transparent 82%);
        }
        .is-celebrating .mood-shell-burst span {
          animation: mood-shell-burst 1000ms ease-out forwards;
          animation-delay: var(--burst-delay);
        }
        .is-celebrating .mood-shell-scene span {
          opacity: 1;
        }
        .is-celebrating.mood-shell.is-rough .mood-shell-burst span {
          animation-name: mood-volcano-burst;
        }
        .is-celebrating.mood-shell.is-rough .mood-shell-scene span {
          animation: mood-lava-fountain 1200ms cubic-bezier(0.19, 0.9, 0.24, 1) forwards;
          animation-delay: var(--scene-delay);
        }
        .is-celebrating.mood-shell.is-low .mood-shell-burst span {
          animation-name: mood-rain-fall;
        }
        .is-celebrating.mood-shell.is-low .mood-shell-scene span {
          animation: mood-storm-rain 1100ms linear forwards;
          animation-delay: var(--scene-delay);
        }
        .is-celebrating.mood-shell.is-low .mood-shell-weather span {
          animation: mood-cloud-drift 1800ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .is-celebrating.mood-shell.is-neutral .mood-shell-burst span {
          animation-name: mood-stream-slide;
        }
        .is-celebrating.mood-shell.is-neutral .mood-shell-scene span {
          animation: mood-current-flow 1200ms ease-in-out forwards;
          animation-delay: var(--scene-delay);
        }
        .is-celebrating.mood-shell.is-neutral .mood-shell-weather span {
          animation: mood-current-breathe 1600ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .is-celebrating.mood-shell.is-good .mood-shell-burst span {
          animation-name: mood-leaf-rise;
        }
        .is-celebrating.mood-shell.is-good .mood-shell-scene span {
          animation: mood-sprout-rise 1250ms cubic-bezier(0.22, 0.76, 0.2, 1) forwards;
          animation-delay: var(--scene-delay);
        }
        .is-celebrating.mood-shell.is-good .mood-shell-weather span {
          animation: mood-leaf-sway 1900ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .is-celebrating.mood-shell.is-great .mood-shell-burst span {
          animation-name: mood-star-burst;
        }
        .is-celebrating.mood-shell.is-great .mood-shell-scene span {
          animation: mood-solar-bloom 1280ms cubic-bezier(0.18, 0.8, 0.24, 1) forwards;
          animation-delay: var(--scene-delay);
        }
        .is-celebrating.mood-shell.is-great .mood-shell-weather span {
          animation: mood-star-twinkle 1400ms ease-in-out infinite;
          animation-delay: var(--cloud-delay);
        }
        .is-celebrating {
          animation: mood-shell-bounce 820ms cubic-bezier(0.2, 0.9, 0.22, 1);
          box-shadow: 0 18px 34px rgba(255, 176, 87, 0.14);
        }
        .is-celebrating .mood-shell-glow {
          animation: mood-shell-glow 950ms ease-out;
        }
        .is-celebrating .mood-stage {
          animation: mood-stage-wobble 820ms ease-out;
        }
        .is-celebrating .mood-face.is-rough,
        .is-celebrating .mood-face.is-low,
        .is-celebrating .mood-face.is-neutral,
        .is-celebrating .mood-face.is-good,
        .is-celebrating .mood-face.is-great {
          animation: mood-face-bounce 760ms cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .mood-chip {
          display: flex;
          min-width: 50px;
          flex-direction: column;
          align-items: center;
          gap: 5px;
          border: 0;
          background: transparent;
          padding: 0;
          transition: transform 180ms ease, opacity 180ms ease;
        }
        .mood-chip:hover {
          transform: translateY(-1px);
        }
        .mood-chip:not(.is-selected) {
          opacity: 0.72;
        }
        .mood-chip-label {
          font-size: 9px;
          color: var(--muted);
        }
        .mood-face {
          position: relative;
          display: flex;
          height: 42px;
          width: 42px;
          align-items: center;
          justify-content: center;
          background: #c9b8b2;
          transition: transform 200ms ease, box-shadow 200ms ease, background-color 200ms ease;
          box-shadow: inset 0 0 12px rgba(0,0,0,0.05);
        }
        .mood-face-mini {
          height: 34px;
          width: 34px;
        }
        .is-selected .mood-face {
          transform: scale(0.96);
          box-shadow: 0 10px 20px rgba(0,0,0,0.1), inset 0 0 12px rgba(255,255,255,0.16);
        }
        .blob-rough { border-radius: 45% 55% 40% 60% / 55% 45% 60% 40%; }
        .blob-low { border-radius: 50% 50% 45% 55% / 40% 60% 40% 60%; }
        .blob-neutral { border-radius: 60% 40% 55% 45% / 50% 40% 60% 50%; }
        .blob-good { border-radius: 40% 60% 50% 50% / 60% 40% 50% 50%; }
        .blob-great { border-radius: 48% 52% 42% 58% / 44% 56% 46% 54%; }
        .mood-face.is-rough { background: linear-gradient(135deg, #ff8b8b, #ff6262); }
        .mood-face.is-low { background: linear-gradient(135deg, #ffbb87, #ff8d5c); }
        .mood-face.is-neutral { background: linear-gradient(135deg, #a8b8ff, #7b92ff); }
        .mood-face.is-good { background: linear-gradient(135deg, #79dca8, #43c77a); }
        .mood-face.is-great { background: linear-gradient(135deg, #ffd86b, #ffb938); }
        .mood-features {
          display: flex;
          flex-direction: column;
          align-items: center;
          transform: translateX(-2px);
        }
        .mood-eyes {
          display: flex;
          gap: 9px;
          margin-bottom: 4px;
        }
        .mood-eyes span {
          height: 5px;
          width: 5px;
          border-radius: 999px;
          background: #1a1817;
        }
        .mood-eyes.eyes-squint span {
          width: 8px;
          height: 2px;
          border-radius: 999px;
          transform: translateY(1px) rotate(8deg);
        }
        .mood-eyes.eyes-squint span:last-child {
          transform: translateY(1px) rotate(-8deg);
        }
        .mood-nose {
          height: 8px;
          width: 2px;
          border-radius: 999px;
          background: #1a1817;
          margin-bottom: 6px;
        }
        .mood-mouth {
          background: #1a1817;
        }
        .mouth-neutral {
          height: 3px;
          width: 12px;
          border-radius: 999px;
        }
        .mouth-smile {
          height: 8px;
          width: 14px;
          border-radius: 0 0 14px 14px;
        }
        .mouth-smile-wide {
          height: 10px;
          width: 16px;
          border-radius: 0 0 16px 16px;
        }
        .mouth-sad {
          height: 8px;
          width: 14px;
          border-radius: 16px 16px 0 0;
        }
        .mouth-wavy {
          height: 5px;
          width: 14px;
          background: none;
          border-bottom: 2px solid #1a1817;
          border-top: 2px solid #1a1817;
          border-radius: 999px;
        }
        .mood-scribble {
          position: absolute;
          top: 9px;
          left: 50%;
          height: 10px;
          width: 18px;
          transform: translateX(-50%);
          border-top: 2px dashed rgba(26,24,23,0.7);
          border-radius: 999px;
        }
        .mood-stage {
          position: relative;
          display: flex;
          min-height: 54px;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          overflow: hidden;
          border-radius: 22px;
          border: 1px solid rgba(84, 67, 55, 0.09);
          background: linear-gradient(90deg, rgba(255,255,255,0.82), rgba(255,255,255,0.56));
          margin-top: 10px;
          padding: 9px 12px;
        }
        .mood-stage-copy {
          position: relative;
          z-index: 2;
          min-width: 0;
        }
        .mood-stage-kicker {
          font-size: 10px;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          color: var(--muted);
        }
        .mood-stage-text {
          margin-top: 4px;
          font-size: 11px;
          color: var(--text);
        }
        .mood-stage-visual {
          position: relative;
          display: flex;
          height: 34px;
          min-width: 70px;
          align-items: center;
          justify-content: center;
        }
        .mood-stage.is-rough { background: linear-gradient(90deg, rgba(106,79,90,0.2), rgba(255,255,255,0.7)); }
        .mood-stage.is-low { background: linear-gradient(90deg, rgba(134,118,109,0.16), rgba(255,255,255,0.7)); }
        .mood-stage.is-neutral { background: linear-gradient(90deg, rgba(137,146,152,0.14), rgba(255,255,255,0.7)); }
        .mood-stage.is-good { background: linear-gradient(90deg, rgba(202,176,101,0.16), rgba(255,255,255,0.72)); }
        .mood-stage.is-great { background: linear-gradient(90deg, rgba(243,168,66,0.18), rgba(255,255,255,0.72)); }
        .mood-particle {
          position: absolute;
          top: 50%;
          left: var(--offset);
          z-index: 1;
          font-size: 13px;
          line-height: 1;
          opacity: 0;
          transform: translateY(-50%);
          animation: mood-float 2.8s ease-in-out infinite;
          animation-delay: var(--delay);
        }
        .mood-particle.is-rough { color: rgba(122, 72, 92, 0.9); animation-name: mood-jitter; }
        .mood-particle.is-low { color: rgba(130, 112, 102, 0.82); animation-name: mood-drip; }
        .mood-particle.is-neutral { color: rgba(110, 122, 130, 0.8); animation-name: mood-slide; }
        .mood-particle.is-good { color: rgba(198, 163, 52, 0.85); animation-name: mood-rise; }
        .mood-particle.is-great { color: rgba(230, 162, 52, 0.92); animation-name: mood-spark; }
        .stage-submitted {
          animation: mood-pop 420ms ease-out;
        }
        @keyframes mood-shell-bounce {
          0% { transform: scale(0.99) rotate(-0.35deg); }
          28% { transform: scale(1.018) rotate(0.4deg); }
          58% { transform: scale(0.998) rotate(-0.25deg); }
          100% { transform: scale(1); }
        }
        @keyframes mood-shell-glow {
          0% { opacity: 0.35; }
          35% { opacity: 1; }
          100% { opacity: 0.6; }
        }
        @keyframes mood-shell-sweep {
          0% { opacity: 0; transform: translateX(-60%) rotate(-6deg); }
          18% { opacity: 1; }
          100% { opacity: 0; transform: translateX(60%) rotate(-6deg); }
        }
        @keyframes mood-lava-sweep {
          0% { opacity: 0; transform: translateX(-70%) rotate(-5deg) scaleY(0.9); }
          15% { opacity: 1; }
          100% { opacity: 0; transform: translateX(50%) rotate(-3deg) scaleY(1.12); }
        }
        @keyframes mood-rain-sheet {
          0% { opacity: 0; transform: translateX(-20%) translateY(-10%) rotate(12deg); }
          20% { opacity: 0.95; }
          100% { opacity: 0; transform: translateX(10%) translateY(24%) rotate(12deg); }
        }
        @keyframes mood-shell-burst {
          0% {
            opacity: 0;
            transform: translate(-50%, -50%) scale(0.4);
          }
          20% {
            opacity: 1;
          }
          100% {
            opacity: 0;
            transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty))) scale(1.4);
          }
        }
        @keyframes mood-volcano-burst {
          0% {
            opacity: 0;
            transform: translate(-50%, 24%) scale(0.35);
          }
          18% {
            opacity: 1;
          }
          100% {
            opacity: 0;
            transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty) - 24px)) scale(1.7);
          }
        }
        @keyframes mood-rain-fall {
          0% {
            opacity: 0;
            transform: translate(calc(-50% + var(--tx) * 0.2), -30px) scaleY(0.6);
          }
          15% {
            opacity: 0.9;
          }
          100% {
            opacity: 0;
            transform: translate(calc(-50% + var(--tx)), 180px) scaleY(1.25);
          }
        }
        @keyframes mood-stream-slide {
          0% {
            opacity: 0;
            transform: translate(-70px, calc(-50% + var(--ty) * 0.1)) scaleX(0.5);
          }
          20% {
            opacity: 0.8;
          }
          100% {
            opacity: 0;
            transform: translate(120px, calc(-50% + var(--ty) * 0.15)) scaleX(1.1);
          }
        }
        @keyframes mood-leaf-rise {
          0% {
            opacity: 0;
            transform: translate(calc(-50% + var(--tx) * 0.2), 28px) rotate(0deg) scale(0.6);
          }
          25% {
            opacity: 0.95;
          }
          100% {
            opacity: 0;
            transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty) - 12px)) rotate(140deg) scale(1.2);
          }
        }
        @keyframes mood-star-burst {
          0% {
            opacity: 0;
            transform: translate(-50%, -50%) scale(0.5) rotate(0deg);
          }
          18% {
            opacity: 1;
          }
          100% {
            opacity: 0;
            transform: translate(calc(-50% + var(--tx)), calc(-50% + var(--ty))) scale(1.85) rotate(90deg);
          }
        }
        @keyframes mood-lava-fountain {
          0% {
            opacity: 0;
            transform: translateY(40px) scale(0.4);
          }
          18% {
            opacity: 1;
          }
          60% {
            opacity: 1;
            transform: translateY(calc(-1 * var(--scene-size) * 4.8)) translateX(calc((var(--scene-left) - 50%) * 0.12)) scale(1.5);
          }
          100% {
            opacity: 0;
            transform: translateY(calc(-1 * var(--scene-size) * 6.6)) translateX(calc((var(--scene-left) - 50%) * 0.22)) scale(0.9);
          }
        }
        @keyframes mood-storm-rain {
          0% {
            opacity: 0;
            transform: translateY(-80px) translateX(0) scaleY(0.6);
          }
          10% {
            opacity: 0.95;
          }
          100% {
            opacity: 0;
            transform: translateY(320px) translateX(-22px) scaleY(1.2);
          }
        }
        @keyframes mood-current-flow {
          0% {
            opacity: 0;
            transform: translateX(-180px) scaleX(0.2);
          }
          20% {
            opacity: 0.8;
          }
          100% {
            opacity: 0;
            transform: translateX(200px) scaleX(1.25);
          }
        }
        @keyframes mood-sprout-rise {
          0% {
            opacity: 0;
            transform: translateY(32px) rotate(-24deg) scale(0.4);
          }
          24% {
            opacity: 1;
          }
          100% {
            opacity: 0;
            transform: translateY(calc(-1 * var(--scene-size) * 7.5)) translateX(calc((var(--scene-left) - 45%) * 0.16)) rotate(160deg) scale(1.15);
          }
        }
        @keyframes mood-solar-bloom {
          0% {
            opacity: 0;
            transform: translateY(8px) scale(0.3) rotate(0deg);
          }
          20% {
            opacity: 1;
          }
          100% {
            opacity: 0;
            transform: translateY(calc(-1 * var(--scene-size) * 4.6)) translateX(calc((var(--scene-left) - 50%) * 0.18)) scale(1.9) rotate(120deg);
          }
        }
        @keyframes mood-cloud-drift {
          0%, 100% { transform: translateX(0) translateY(0); }
          50% { transform: translateX(14px) translateY(2px); }
        }
        @keyframes mood-heat-roll {
          0%, 100% { transform: translateY(0) scaleX(1); opacity: 0.48; }
          50% { transform: translateY(-4px) scaleX(1.08); opacity: 0.72; }
        }
        @keyframes mood-lava-bed {
          0%, 100% { transform: translateY(0) scaleX(1); opacity: 0.9; }
          50% { transform: translateY(-6px) scaleX(1.06); opacity: 1; }
        }
        @keyframes mood-ember-glow {
          0%, 100% { opacity: 0.35; }
          50% { opacity: 0.75; }
        }
        @keyframes mood-cloudbank {
          0%, 100% { transform: translateX(0) translateY(0); opacity: 0.88; }
          50% { transform: translateX(16px) translateY(3px); opacity: 1; }
        }
        @keyframes mood-current-breathe {
          0%, 100% { transform: scaleX(0.9); opacity: 0.34; }
          50% { transform: scaleX(1.14); opacity: 0.62; }
        }
        @keyframes mood-neutral-drift {
          0% { transform: translateX(0); }
          100% { transform: translateX(72px); }
        }
        @keyframes mood-leaf-sway {
          0%, 100% { transform: rotate(-8deg) translateY(0); }
          50% { transform: rotate(10deg) translateY(-6px); }
        }
        @keyframes mood-meadow-breathe {
          0%, 100% { transform: translateY(0) scale(1); opacity: 0.82; }
          50% { transform: translateY(-4px) scale(1.04); opacity: 1; }
        }
        @keyframes mood-star-twinkle {
          0%, 100% { transform: scale(0.9) rotate(0deg); opacity: 0.68; }
          50% { transform: scale(1.2) rotate(18deg); opacity: 1; }
        }
        @keyframes mood-sun-pulse {
          0%, 100% { transform: scale(0.98); opacity: 0.86; }
          50% { transform: scale(1.06); opacity: 1; }
        }
        @keyframes mood-stage-wobble {
          0% { transform: translateY(0) scale(1); }
          30% { transform: translateY(-2px) scale(1.01); }
          55% { transform: translateY(1px) scale(0.998); }
          100% { transform: translateY(0) scale(1); }
        }
        @keyframes mood-face-bounce {
          0% { transform: scale(0.9) rotate(0deg); }
          35% { transform: scale(1.16) rotate(-4deg); }
          60% { transform: scale(0.98) rotate(3deg); }
          100% { transform: scale(1) rotate(0deg); }
        }
        @keyframes mood-pop {
          0% { transform: scale(0.985); }
          60% { transform: scale(1.01); }
          100% { transform: scale(1); }
        }
        @keyframes mood-jitter {
          0%, 100% { opacity: 0.15; transform: translateY(-50%) translateX(0); }
          30% { opacity: 0.9; transform: translateY(-58%) translateX(-4px); }
          70% { opacity: 0.55; transform: translateY(-42%) translateX(4px); }
        }
        @keyframes mood-drip {
          0% { opacity: 0; transform: translateY(-60%) scale(0.9); }
          35% { opacity: 0.85; }
          100% { opacity: 0; transform: translateY(20%) scale(1.1); }
        }
        @keyframes mood-slide {
          0% { opacity: 0; transform: translate(-6px, -50%); }
          40% { opacity: 0.75; }
          100% { opacity: 0; transform: translate(8px, -50%); }
        }
        @keyframes mood-rise {
          0% { opacity: 0; transform: translateY(-30%) scale(0.9); }
          35% { opacity: 0.9; }
          100% { opacity: 0; transform: translateY(-110%) scale(1.05); }
        }
        @keyframes mood-spark {
          0% { opacity: 0; transform: translateY(-50%) scale(0.6) rotate(0deg); }
          35% { opacity: 0.95; }
          100% { opacity: 0; transform: translateY(-115%) scale(1.25) rotate(24deg); }
        }
      `}</style>
    </section>
  );
}

export default MoodCheckIn;
