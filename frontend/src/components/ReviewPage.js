import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTE_CONSTANTS } from '../constants/RouteConstants';
import { useLanguage } from '../i18n/LanguageContext';
import { getFocusHistory, getHistory, getMoodHistory, getReviewInsights, getTasks, getWeeklySummary } from '../http/api';

function etDateKey(offsetDays = 0) {
  const now = new Date();
  const eastern = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  eastern.setDate(eastern.getDate() + offsetDays);
  const year = eastern.getFullYear();
  const month = String(eastern.getMonth() + 1).padStart(2, '0');
  const day = String(eastern.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function monthKeyFromDateKey(dateKey) {
  return (dateKey || etDateKey()).slice(0, 7);
}

function shiftMonth(monthKey, offset) {
  const [year, month] = monthKey.split('-').map(Number);
  const next = new Date(year, month - 1 + offset, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`;
}

function parseDateKey(dateKey) {
  const [year, month, day] = dateKey.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function weekdayForDateKey(dateKey) {
  const date = parseDateKey(dateKey);
  return (date.getDay() + 6) % 7;
}

function normalizeDateKey(value) {
  if (!value) return '';
  const raw = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
  const monthDay = raw.match(/^(\d{1,2})[./-](\d{1,2})$/);
  if (monthDay) {
    const today = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }));
    const year = today.getFullYear();
    const month = String(Number(monthDay[1])).padStart(2, '0');
    const day = String(Number(monthDay[2])).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  return raw;
}

function recurringBadgeLabel(task, lang, fallback) {
  if ((task?.task_kind || 'temporary') !== 'weekly') return fallback;
  const weekday = Number(task?.recurrence_weekday);
  if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6) return fallback;
  const zh = ['每周一', '每周二', '每周三', '每周四', '每周五', '每周六', '每周日'];
  const en = ['Every Mon', 'Every Tue', 'Every Wed', 'Every Thu', 'Every Fri', 'Every Sat', 'Every Sun'];
  return (lang === 'zh' ? zh : en)[weekday];
}

function formatMonthLabel(monthKey, lang) {
  const [year, month] = monthKey.split('-').map(Number);
  const date = new Date(year, month - 1, 1);
  return lang === 'zh'
    ? `${year}年 ${month}月`
    : date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function dateRange(startKey, endKey) {
  const values = [];
  let current = parseDateKey(startKey);
  const end = parseDateKey(endKey);
  while (current <= end) {
    const year = current.getFullYear();
    const month = String(current.getMonth() + 1).padStart(2, '0');
    const day = String(current.getDate()).padStart(2, '0');
    values.push(`${year}-${month}-${day}`);
    current.setDate(current.getDate() + 1);
  }
  return values;
}

function isDateOnOrAfter(dateKey, thresholdKey) {
  if (!thresholdKey) return true;
  return dateKey >= thresholdKey;
}

function sum(list, getter) {
  return list.reduce((total, item) => total + getter(item), 0);
}

function specialPlannedTaskCount(stats) {
  if (!stats) return 0;
  return (stats.scheduledTasks || []).length;
}

function extractDeferredTarget(reasoning = '') {
  if (!reasoning) return '';
  const match = reasoning.match(/(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : '';
}

function localizeReasoning(reasoning = '', lang = 'en') {
  if (!reasoning) return '';
  if (lang !== 'zh') return reasoning;

  const deferredTarget = reasoning.match(/Task deferred (?:to ([0-9-]+)|\(total deferrals: (\d+)\))/i);
  if (/Task deferred by concierge to/i.test(reasoning)) {
    const target = extractDeferredTarget(reasoning);
    return target ? `任务被私人管家推迟到 ${target}。` : '任务被私人管家推迟了。';
  }
  if (/Task deferred by concierge/i.test(reasoning)) return '任务被私人管家推迟了。';
  if (/Task deferred to ([0-9-]+) by user/i.test(reasoning)) {
    const target = extractDeferredTarget(reasoning);
    return target ? `任务被你推迟到 ${target}。` : '任务被你推迟了。';
  }
  if (/Task deferred \(total deferrals:/i.test(reasoning) && deferredTarget) {
    return `任务已被推迟（累计推迟 ${deferredTarget[2]} 次）。`;
  }
  if (/Created by concierge/i.test(reasoning)) return '任务由私人管家加入。';
  if (/Created by user/i.test(reasoning)) return '任务由你创建。';
  if (/Deleted by concierge/i.test(reasoning)) return '任务已被私人管家删除。';
  if (/Deleted by user/i.test(reasoning)) return '任务已被你删除。';
  if (/Task created by user/i.test(reasoning)) return '任务由你创建。';
  if (/Task created via batch input/i.test(reasoning)) return '任务通过批量输入创建。';
  if (/Task created by concierge/i.test(reasoning)) return '任务由私人管家加入。';
  if (/Task deleted by user/i.test(reasoning)) return '任务已被你删除。';
  if (/Task deleted by concierge/i.test(reasoning)) return '任务已被私人管家删除。';
  if (/Task completed by user/i.test(reasoning)) return '任务已被你标记完成。';
  if (/Task completed by concierge/i.test(reasoning)) return '任务已被私人管家标记完成。';
  if (/Task restored to active/i.test(reasoning)) return '任务已恢复为进行中。';
  if (/Task imported from onboarding/i.test(reasoning)) return '任务来自首次初始化导入。';
  return reasoning;
}

function buildFallbackInsight(summary, label, lang) {
  const moodLine = summary.moodAverage
    ? (lang === 'zh' ? `心情均值约 ${summary.moodAverage}/5。` : `Average mood was about ${summary.moodAverage}/5.`)
    : (lang === 'zh' ? '还没有足够的心情记录。' : 'There are not enough mood logs yet.');

  if (lang === 'zh') {
    return `${label}里完成 ${summary.completed} 项，推迟 ${summary.deferred} 次，专注 ${summary.focusMinutes} 分钟，未来安排 ${summary.scheduled} 项。${moodLine}`;
  }

  return `In this ${label.toLowerCase()}, you completed ${summary.completed} task(s), deferred ${summary.deferred}, logged ${summary.focusMinutes} focus minute(s), and scheduled ${summary.scheduled} future task(s). ${moodLine}`;
}

function clampPercent(value) {
  return Math.max(0, Math.min(100, value));
}

function ReviewPage() {
  const { lang, t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [moodHistory, setMoodHistory] = useState([]);
  const [focusHistory, setFocusHistory] = useState([]);
  const [selectedDate, setSelectedDate] = useState(etDateKey());
  const [calendarMonth, setCalendarMonth] = useState(monthKeyFromDateKey(etDateKey()));
  const [weeklySummaryText, setWeeklySummaryText] = useState('');
  const [reviewInsights, setReviewInsights] = useState({ daily: '', weekly: '', monthly: '' });

  const copy = useMemo(() => (
    lang === 'zh'
      ? {
          subtitle: '按天、按周、按月看你的完成、推迟、专注和情绪；未来已经安排的任务也会直接挂在日历上。',
          daily: '每日复盘',
          weekly: '每周复盘',
          monthly: '每月复盘',
          calendar: '复盘日历',
          timeline: '当天记录',
          futurePlan: '当天计划 / 未来安排',
          emptyTimeline: '这一天还没有记录。',
          emptyFuture: '这一天还没有挂上的计划任务。',
          created: '新增',
          completed: '完成',
          deferred: '推迟',
          deleted: '删除',
          focus: '专注',
          mood: '心情',
          sessions: '次',
          minutes: '分钟',
          scheduled: '已安排',
          prev: '上月',
          next: '下月',
          scheduledBadge: '计划',
          historyBadge: '记录',
          advice: '建议',
          today: '今天',
          tomorrow: '明天',
          later: '更晚',
          deferredTo: '推迟到',
          movedHere: '被推到这一天',
          moodLogged: '心情记录',
          focusLogged: '专注记录',
          taskRef: '任务',
        }
      : {
          subtitle: 'Review completions, deferrals, focus, and mood by day, week, and month. Future scheduled tasks also appear on the calendar.',
          daily: 'Daily review',
          weekly: 'Weekly review',
          monthly: 'Monthly review',
          calendar: 'Review calendar',
          timeline: 'Activity on this date',
          futurePlan: 'Scheduled for this date',
          emptyTimeline: 'No records on this date yet.',
          emptyFuture: 'No future tasks scheduled on this date.',
          created: 'Created',
          completed: 'Completed',
          deferred: 'Deferred',
          deleted: 'Deleted',
          focus: 'Focus',
          mood: 'Mood',
          sessions: 'sessions',
          minutes: 'minutes',
          scheduled: 'Scheduled',
          prev: 'Prev',
          next: 'Next',
          scheduledBadge: 'Plan',
          historyBadge: 'History',
          advice: 'Advice',
          today: 'Today',
          tomorrow: 'Tomorrow',
          later: 'Later',
          deferredTo: 'Deferred to',
          movedHere: 'Moved to this date',
          moodLogged: 'Mood log',
          focusLogged: 'Focus log',
          taskRef: 'Task',
        }
  ), [lang]);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const [historyData, taskData, moodData, focusData, weeklyData] = await Promise.all([
          getHistory(null, 300, 0),
          getTasks('active'),
          getMoodHistory(120),
          getFocusHistory(120),
          getWeeklySummary(lang),
        ]);
        if (!active) return;
        setHistory(historyData || []);
        setTasks(taskData || []);
        setMoodHistory(moodData || []);
        setFocusHistory(focusData || []);
        setWeeklySummaryText(weeklyData?.summary || '');
      } catch (err) {
        if (!active) return;
        setError(err.message || 'Failed to load review data.');
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    load();
    const reloadOnFocus = () => {
      load();
    };
    const reloadOnVisibility = () => {
      if (!document.hidden) {
        load();
      }
    };
    const reloadOnAssistantUpdate = () => {
      load();
    };
    window.addEventListener('focus', reloadOnFocus);
    document.addEventListener('visibilitychange', reloadOnVisibility);
    window.addEventListener('dp-assistant-updated', reloadOnAssistantUpdate);
    return () => {
      active = false;
      window.removeEventListener('focus', reloadOnFocus);
      document.removeEventListener('visibilitychange', reloadOnVisibility);
      window.removeEventListener('dp-assistant-updated', reloadOnAssistantUpdate);
    };
  }, [lang]);

  useEffect(() => {
    let active = true;
    async function loadInsights() {
      try {
        const data = await getReviewInsights(selectedDate, calendarMonth, lang);
        if (!active) return;
        setReviewInsights({
          daily: data?.daily || '',
          weekly: data?.weekly || '',
          monthly: data?.monthly || '',
        });
      } catch {
        if (!active) return;
        setReviewInsights({ daily: '', weekly: '', monthly: '' });
      }
    }
    loadInsights();
    return () => {
      active = false;
    };
  }, [calendarMonth, lang, selectedDate]);

  const calendarStats = useMemo(() => {
    const grouped = {};
    const ensure = (dateKey) => {
      if (!grouped[dateKey]) {
        grouped[dateKey] = {
          created: 0,
          completed: 0,
          deferred: 0,
          deleted: 0,
          focusMinutes: 0,
          focusSessions: 0,
          moodLevels: [],
          moodEntries: [],
          focusEntries: [],
          scheduledTasks: [],
          dailyTasks: [],
          weeklyTasks: [],
          historyEntries: [],
        };
      }
      return grouped[dateKey];
    };

    history.forEach((entry) => {
      const bucket = ensure(entry.date);
      bucket.historyEntries.push(entry);
      if (entry.action === 'created') bucket.created += 1;
      if (entry.action === 'completed') bucket.completed += 1;
      if (entry.action === 'deferred') bucket.deferred += 1;
      if (entry.action === 'deleted') bucket.deleted += 1;
    });

    focusHistory.forEach((entry) => {
      const bucket = ensure(entry.date);
      bucket.focusMinutes += Number(entry.duration_minutes || 0);
      bucket.focusSessions += 1;
      bucket.focusEntries.push(entry);
    });

    moodHistory.forEach((entry) => {
      const bucket = ensure(entry.date);
      bucket.moodLevels.push(Number(entry.mood_level || 0));
      bucket.moodEntries.push(entry);
    });

    const [calendarYear, calendarMonthNumber] = calendarMonth.split('-').map(Number);
    const daysInVisibleMonth = new Date(calendarYear, calendarMonthNumber, 0).getDate();
    const visibleDateKeys = Array.from({ length: daysInVisibleMonth }, (_, index) => {
      const day = String(index + 1).padStart(2, '0');
      return `${calendarMonth}-${day}`;
    });
    if (!visibleDateKeys.includes(selectedDate)) {
      visibleDateKeys.push(selectedDate);
    }

    tasks.forEach((task) => {
      const normalizedDueDate = normalizeDateKey(task.due_date);
      if (task.task_kind === 'daily') {
        visibleDateKeys.forEach((dateKey) => {
          if (!isDateOnOrAfter(dateKey, normalizedDueDate)) return;
          const bucket = ensure(dateKey);
          bucket.dailyTasks.push(task);
        });
        return;
      }
      if (task.task_kind === 'weekly') {
        visibleDateKeys.forEach((dateKey) => {
          if (!isDateOnOrAfter(dateKey, normalizedDueDate)) return;
          if (task.recurrence_weekday == null || weekdayForDateKey(dateKey) === Number(task.recurrence_weekday)) {
            const bucket = ensure(dateKey);
            bucket.weeklyTasks.push(task);
          }
        });
        return;
      }
      if (normalizedDueDate) {
        const bucket = ensure(normalizedDueDate);
        bucket.scheduledTasks.push(task);
      }
    });

    return grouped;
  }, [calendarMonth, focusHistory, history, moodHistory, selectedDate, tasks]);

  const selectedStats = calendarStats[selectedDate] || {
    created: 0,
    completed: 0,
    deferred: 0,
    deleted: 0,
    focusMinutes: 0,
    focusSessions: 0,
    moodLevels: [],
    moodEntries: [],
    focusEntries: [],
    scheduledTasks: [],
    dailyTasks: [],
    weeklyTasks: [],
    historyEntries: [],
  };

  const summaryForRange = (startKey, endKey) => {
    const keys = dateRange(startKey, endKey);
    const buckets = keys.map((key) => calendarStats[key]).filter(Boolean);
    const moodLevels = buckets.flatMap((bucket) => bucket.moodLevels || []).filter(Boolean);
    const uniqueDailyTaskIds = new Set(
      buckets.flatMap((bucket) => (bucket.dailyTasks || []).map((task) => task.id))
    );
    const uniqueWeeklyTaskIds = new Set(
      buckets.flatMap((bucket) => (bucket.weeklyTasks || []).map((task) => task.id))
    );
    const uniqueScheduledTaskIds = new Set(
      buckets.flatMap((bucket) => (bucket.scheduledTasks || []).map((task) => task.id))
    );
    return {
      created: sum(buckets, (bucket) => bucket.created),
      completed: sum(buckets, (bucket) => bucket.completed),
      deferred: sum(buckets, (bucket) => bucket.deferred),
      deleted: sum(buckets, (bucket) => bucket.deleted),
      focusMinutes: sum(buckets, (bucket) => bucket.focusMinutes),
      focusSessions: sum(buckets, (bucket) => bucket.focusSessions),
      scheduled: uniqueScheduledTaskIds.size + uniqueDailyTaskIds.size + uniqueWeeklyTaskIds.size,
      moodAverage: moodLevels.length ? (sum(moodLevels, (value) => value) / moodLevels.length).toFixed(1) : null,
    };
  };

  const todayKey = etDateKey();
  const todayDate = parseDateKey(todayKey);
  const weekStart = new Date(todayDate);
  const dayOfWeek = todayDate.getDay();
  weekStart.setDate(todayDate.getDate() - ((dayOfWeek + 6) % 7));
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);
  const monthStart = `${calendarMonth}-01`;
  const monthEndDate = new Date(parseDateKey(monthStart).getFullYear(), parseDateKey(monthStart).getMonth() + 1, 0);
  const monthEnd = `${monthEndDate.getFullYear()}-${String(monthEndDate.getMonth() + 1).padStart(2, '0')}-${String(monthEndDate.getDate()).padStart(2, '0')}`;

  const dailySummary = summaryForRange(selectedDate, selectedDate);
  const weeklySummary = summaryForRange(
    `${weekStart.getFullYear()}-${String(weekStart.getMonth() + 1).padStart(2, '0')}-${String(weekStart.getDate()).padStart(2, '0')}`,
    `${weekEnd.getFullYear()}-${String(weekEnd.getMonth() + 1).padStart(2, '0')}-${String(weekEnd.getDate()).padStart(2, '0')}`,
  );
  const monthlySummary = summaryForRange(monthStart, monthEnd);

  const [year, month] = calendarMonth.split('-').map(Number);
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const cells = [];
  for (let index = 0; index < firstDay; index += 1) cells.push(null);
  for (let day = 1; day <= daysInMonth; day += 1) cells.push(day);

  const renderSummaryCard = (title, summary, extraText = '', insightText = '') => {
    const resolvedInsight = insightText || buildFallbackInsight(summary, title, lang);
    const totalActions = summary.completed + summary.deferred + summary.deleted + summary.created;
    const completionPct = totalActions ? clampPercent((summary.completed / totalActions) * 100) : 0;
    const deferPct = totalActions ? clampPercent((summary.deferred / totalActions) * 100) : 0;
    const focusPct = clampPercent((summary.focusMinutes / 180) * 100);
    const moodPct = summary.moodAverage ? clampPercent((Number(summary.moodAverage) / 5) * 100) : 0;
    return (
    <section className="rounded-[20px] border border-[color:var(--line)] bg-white/72 p-3.5">
      <p className="text-xs uppercase tracking-[0.2em] text-[color:var(--muted)]">{title}</p>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-[color:var(--muted)]">
        <div><span className="font-medium text-[color:var(--text)]">{summary.completed}</span> {copy.completed}</div>
        <div><span className="font-medium text-[color:var(--text)]">{summary.deferred}</span> {copy.deferred}</div>
        <div><span className="font-medium text-[color:var(--text)]">{summary.focusMinutes}</span> {copy.minutes}</div>
        <div><span className="font-medium text-[color:var(--text)]">{summary.scheduled}</span> {copy.scheduled}</div>
      </div>
      <div className="mt-3 rounded-[16px] border border-[color:var(--line)] bg-white/70 p-2.5">
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-2">
            <div>
              <div className="mb-1 flex items-center justify-between text-[11px] text-[color:var(--muted)]">
                <span>{lang === 'zh' ? '完成 / 推迟' : 'Done / Deferred'}</span>
                <span>{summary.completed}:{summary.deferred}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-stone-200">
                <div className="flex h-full w-full">
                  <div className="bg-emerald-400/90" style={{ width: `${completionPct}%` }} />
                  <div className="bg-amber-300/95" style={{ width: `${deferPct}%` }} />
                </div>
              </div>
            </div>
            <div>
              <div className="mb-1 flex items-center justify-between text-[11px] text-[color:var(--muted)]">
                <span>{lang === 'zh' ? '专注强度' : 'Focus intensity'}</span>
                <span>{summary.focusMinutes}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-stone-200">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-orange-200 via-orange-300 to-[color:var(--accent)]"
                  style={{ width: `${focusPct}%` }}
                />
              </div>
            </div>
            <div>
              <div className="mb-1 flex items-center justify-between text-[11px] text-[color:var(--muted)]">
                <span>{copy.mood}</span>
                <span>{summary.moodAverage ? `${summary.moodAverage}/5` : (lang === 'zh' ? '暂无' : 'N/A')}</span>
              </div>
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5].map((step) => {
                  const active = summary.moodAverage && Number(summary.moodAverage) >= step - 0.2;
                  return (
                    <span
                      key={step}
                      className={`h-2 flex-1 rounded-full ${active ? 'bg-rose-300' : 'bg-stone-200'}`}
                      style={active && step >= 4 ? { backgroundColor: '#f59e0b' } : undefined}
                    />
                  );
                })}
              </div>
            </div>
          </div>
          <div className="grid h-[68px] w-[56px] grid-cols-7 items-end gap-[2px] rounded-[12px] border border-[color:var(--line)] bg-[color:var(--surface)] px-1.5 py-1.5">
            {[summary.created, summary.completed, summary.deferred, summary.focusSessions, summary.scheduled, Math.round(moodPct / 20), summary.deleted].map((value, index) => {
              const height = Math.max(12, Math.min(100, value * 18));
              const colors = ['#cbd5e1', '#6ee7b7', '#facc15', '#fb923c', '#93c5fd', '#f9a8d4', '#cbd5e1'];
              return (
                <span
                  key={`${title}-${index}`}
                  className="rounded-full"
                  style={{ height: `${height}%`, backgroundColor: colors[index] }}
                />
              );
            })}
          </div>
        </div>
      </div>
      {summary.moodAverage ? (
        <p className="mt-3 text-sm text-[color:var(--muted)]">{copy.mood}: <span className="font-medium text-[color:var(--text)]">{summary.moodAverage}/5</span></p>
      ) : null}
      {extraText ? <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">{extraText}</p> : null}
      <p className="mt-3 text-sm leading-6 text-[color:var(--text)]">{resolvedInsight}</p>
    </section>
    );
  };

  if (loading) {
    return <div className="card text-sm text-[color:var(--muted)]">{t.loadingHistory}</div>;
  }

  if (error) {
    return <div className="card text-sm text-red-600">{error}</div>;
  }

  const actionLabel = (action) => (
    {
      created: copy.created,
      completed: copy.completed,
      deferred: copy.deferred,
      deleted: copy.deleted,
      planned: copy.scheduled,
      missed: lang === 'zh' ? '错过' : 'Missed',
    }[action] || action
  );

  const selectedDateTasks = (() => {
    const merged = [...(selectedStats.dailyTasks || []), ...(selectedStats.weeklyTasks || []), ...(selectedStats.scheduledTasks || [])];
    const seen = new Set();
    return merged.filter((task) => {
      if (!task?.id || seen.has(task.id)) return false;
      seen.add(task.id);
      return true;
    });
  })();

  return (
    <div className="space-y-4">
      <section className="board-card px-5 py-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="panel-label">Daymark // Review Trail</div>
            <h1 className="mt-4 text-[40px] leading-none text-[color:var(--text)]">{t.reviewTitle}</h1>
            <p className="mt-2 text-sm text-[color:var(--muted)]">{copy.subtitle}</p>
          </div>
          <Link to={ROUTE_CONSTANTS.SETTINGS} className="btn-ghost">
            {t.navSettings}
          </Link>
        </div>
      </section>

      <div className="grid gap-3 xl:grid-cols-3">
        {renderSummaryCard(copy.daily, dailySummary, '', reviewInsights.daily)}
        {renderSummaryCard(copy.weekly, weeklySummary, weeklySummaryText, reviewInsights.weekly)}
        {renderSummaryCard(copy.monthly, monthlySummary, '', reviewInsights.monthly)}
      </div>

      <section className="card">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
          <div className="board-card p-3.5">
            <div className="mb-3 flex items-center justify-between">
              <button onClick={() => setCalendarMonth((current) => shiftMonth(current, -1))} className="btn-ghost !px-3">
                {copy.prev}
              </button>
              <h2 className="text-xl text-[color:var(--text)]">{copy.calendar} · {formatMonthLabel(calendarMonth, lang)}</h2>
              <button onClick={() => setCalendarMonth((current) => shiftMonth(current, 1))} className="btn-ghost !px-3">
                {copy.next}
              </button>
            </div>

            <div className="grid grid-cols-7 gap-1.5 text-center">
              {(lang === 'zh' ? ['日', '一', '二', '三', '四', '五', '六'] : ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']).map((day) => (
                <div key={day} className="py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--muted)]">{day}</div>
              ))}
              {cells.map((day, index) => {
                if (day === null) return <div key={`blank-${index}`} />;
                const dateKey = `${calendarMonth}-${String(day).padStart(2, '0')}`;
                const stats = calendarStats[dateKey];
                const plannedCount = specialPlannedTaskCount(stats);
                const isSelected = dateKey === selectedDate;
                const isToday = dateKey === todayKey;
                return (
                  <button
                    key={dateKey}
                    onClick={() => setSelectedDate(dateKey)}
                    className={`min-h-[68px] rounded-[16px] border px-2 py-1.5 text-left transition ${
                      isSelected
                        ? 'border-[color:var(--accent)] bg-[color:var(--accent-soft)]'
                        : isToday
                          ? 'border-[color:var(--line-strong)] bg-white'
                          : 'border-[color:var(--line)] bg-[color:var(--surface-muted)]'
                    }`}
                  >
                    <div className="text-sm font-medium text-[color:var(--text)]">{day}</div>
                    <div className="mt-1.5 space-y-1">
                      {!!stats?.historyEntries?.length && (
                        <div className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                          {copy.historyBadge} {stats.historyEntries.length}
                        </div>
                      )}
                      {!!plannedCount && (
                        <div className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                          {copy.scheduledBadge} {plannedCount}
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-3">
            <section className="board-card p-3.5">
              <h3 className="text-lg text-[color:var(--text)]">{copy.timeline} · {selectedDate}</h3>
              <div className="mt-2.5 space-y-2.5">
                {selectedStats.moodEntries.map((entry, index) => (
                  <div key={`mood-${entry.id || index}`} className="rounded-[16px] border border-[color:var(--line)] bg-white/75 px-3 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-[color:var(--text)]">{copy.moodLogged}</p>
                      <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-medium text-rose-700">
                        {copy.mood} {entry.mood_level}/5
                      </span>
                    </div>
                    {entry.note ? <p className="mt-2 text-sm text-[color:var(--muted)]">{entry.note}</p> : null}
                  </div>
                ))}
                {selectedStats.focusEntries.map((entry, index) => (
                  <div key={`focus-${entry.id || index}`} className="rounded-[16px] border border-[color:var(--line)] bg-white/75 px-3 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-[color:var(--text)]">{copy.focusLogged}</p>
                      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                        {entry.duration_minutes} {copy.minutes}
                      </span>
                    </div>
                    {entry.task_id ? <p className="mt-2 text-sm text-[color:var(--muted)]">{copy.taskRef} #{entry.task_id}</p> : null}
                  </div>
                ))}
                {selectedStats.historyEntries.length === 0 ? (
                  selectedStats.moodEntries.length === 0 && selectedStats.focusEntries.length === 0 ? (
                    <p className="text-sm text-[color:var(--muted)]">{copy.emptyTimeline}</p>
                  ) : null
                ) : selectedStats.historyEntries.map((entry) => (
                  <div key={entry.id} className="rounded-[16px] border border-[color:var(--line)] bg-white/75 px-3 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-[color:var(--text)]">{entry.task_title || `${copy.taskRef} #${entry.task_id}`}</p>
                      <span className="rounded-full bg-[color:var(--surface)] px-2 py-0.5 text-[10px] font-medium text-[color:var(--muted)]">
                        {actionLabel(entry.action)}
                      </span>
                      {entry.action === 'deferred' && extractDeferredTarget(entry.ai_reasoning) ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                          {copy.deferredTo} {extractDeferredTarget(entry.ai_reasoning)}
                        </span>
                      ) : null}
                    </div>
                    {entry.ai_reasoning ? <p className="mt-2 text-sm text-[color:var(--muted)]">{localizeReasoning(entry.ai_reasoning, lang)}</p> : null}
                  </div>
                ))}
              </div>
            </section>

            <section className="board-card p-3.5">
              <h3 className="text-lg text-[color:var(--text)]">{copy.futurePlan}</h3>
              <div className="mt-2.5 space-y-2.5">
                {selectedDateTasks.length === 0 ? (
                  <p className="text-sm text-[color:var(--muted)]">{copy.emptyFuture}</p>
                ) : selectedDateTasks.map((task) => (
                  <div key={task.id} className="rounded-[16px] border border-[color:var(--line)] bg-white/75 px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-[color:var(--text)]">{task.title}</p>
                      {task.task_kind === 'temporary' ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                          {t.taskKindTemporary}
                        </span>
                      ) : null}
                      {task.task_kind === 'weekly' ? (
                        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-medium text-violet-700">
                          {recurringBadgeLabel(task, lang, t.taskKindWeekly)}
                        </span>
                      ) : null}
                      {selectedDate === normalizeDateKey(task.due_date) ? (
                        <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                          {copy.movedHere}
                        </span>
                      ) : null}
                    </div>
                    {task.description ? <p className="mt-2 text-sm text-[color:var(--muted)]">{task.description}</p> : null}
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}

export default ReviewPage;
