import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { deleteTask, getTasks, updateTask } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import FocusTimer from './FocusTimer';
import InspirationBox from './InspirationBox';

const TASK_CACHE_KEY = 'daymark_today_tasks_v1';
const EASTERN_DATE_FORMATTER = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/New_York',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

function toEasternDateKey(value) {
  if (!value) return '';
  const parsed = value instanceof Date ? value : new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    const parts = EASTERN_DATE_FORMATTER.formatToParts(parsed);
    const year = parts.find((part) => part.type === 'year')?.value;
    const month = parts.find((part) => part.type === 'month')?.value;
    const day = parts.find((part) => part.type === 'day')?.value;
    if (year && month && day) {
      return `${year}-${month}-${day}`;
    }
  }
  return typeof value === 'string' ? value.slice(0, 10) : '';
}

function getEasternDate(offsetDays = 0) {
  const now = new Date();
  const eastern = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  eastern.setDate(eastern.getDate() + offsetDays);
  const year = eastern.getFullYear();
  const month = String(eastern.getMonth() + 1).padStart(2, '0');
  const day = String(eastern.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getEasternNowMeta(lang) {
  const now = new Date();
  const eastern = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const hour = eastern.getHours();
  const minute = String(eastern.getMinutes()).padStart(2, '0');
  const month = String(eastern.getMonth() + 1).padStart(2, '0');
  const day = String(eastern.getDate()).padStart(2, '0');
  const weekday = eastern.toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', { weekday: 'short', timeZone: 'America/New_York' });
  const daypart = lang === 'zh'
    ? (hour < 12 ? '上午' : hour < 18 ? '下午' : '晚上')
    : (hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening');
  return {
    iso: getEasternDate(0),
    tomorrow: getEasternDate(1),
    later: getEasternDate(2),
    weekday: (eastern.getDay() + 6) % 7,
    label: lang === 'zh'
      ? `美东时间 ${month}/${day} ${weekday} ${daypart} ${hour}:${minute}`
      : `ET ${month}/${day} ${weekday} ${hour}:${minute}`,
  };
}

function formatTodayStamp(lang) {
  const now = new Date();
  return now.toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: lang === 'zh' ? 'long' : 'short',
    day: 'numeric',
  }).toUpperCase();
}

function completedOnDate(task, dateKey) {
  return Boolean(task?.completed_at) && toEasternDateKey(task.completed_at) === dateKey;
}

function readTaskCache() {
  try {
    const raw = window.sessionStorage.getItem(TASK_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function writeTaskCache(tasks) {
  try {
    window.sessionStorage.setItem(TASK_CACHE_KEY, JSON.stringify(tasks || []));
  } catch {}
}

function recurringKindLabel(task, lang, fallback) {
  if ((task?.task_kind || 'temporary') !== 'weekly') return fallback;
  const weekday = Number(task?.recurrence_weekday);
  if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6) return fallback;
  const zh = ['每周一', '每周二', '每周三', '每周四', '每周五', '每周六', '每周日'];
  const en = ['Every Mon', 'Every Tue', 'Every Wed', 'Every Thu', 'Every Fri', 'Every Sat', 'Every Sun'];
  return (lang === 'zh' ? zh : en)[weekday];
}

function DailyPlan({ planRefreshSignal = 0, taskRefreshSignal = 0, onPlanUpdated, inspirations = [], onDismissInspiration }) {
  const { lang, t } = useLanguage();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [selectedFocusTaskId, setSelectedFocusTaskId] = useState(null);

  const kindBadgeCopy = lang === 'zh'
    ? { daily: '每日', weekly: '每周', temporary: '临时' }
    : { daily: 'Daily', weekly: 'Weekly', temporary: 'Temporary' };
  const timeCopy = lang === 'zh'
    ? {
        rhythm: '现实时间',
        overdue: '已逾期',
        today: '今天',
        tomorrow: '明天',
        later: '更晚',
        daily: '每日节奏',
        weekly: '每周节奏',
        overdueSub: '这些已经落后于今天了。',
        todaySub: '今天和现在直接相关的事。',
        tomorrowSub: '已经安排到明天的事。',
        laterSub: '更后面的临时任务先放在这里。',
        dailySub: '不看具体日期，每天都会回来。',
        weeklySub: '只会在对应星期出现的固定节奏。',
        dueToday: '今天',
        dueTomorrow: '明天',
        dueLater: '后天起',
      }
    : {
        rhythm: 'Real-world time',
        overdue: 'Overdue',
        today: 'Today',
        tomorrow: 'Tomorrow',
        later: 'Later',
        daily: 'Daily rhythm',
        weekly: 'Weekly rhythm',
        overdueSub: 'These have already slipped behind today.',
        todaySub: 'Things that matter today and now.',
        tomorrowSub: 'Already scheduled for tomorrow.',
        laterSub: 'Temporary tasks scheduled further out.',
        dailySub: 'These return every day regardless of date.',
        weeklySub: 'These only return on their assigned weekday.',
        dueToday: 'Today',
        dueTomorrow: 'Tomorrow',
        dueLater: 'Later',
      };

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError('');
    const cached = readTaskCache();
    if (cached?.length) {
      setTasks(cached);
      if (onPlanUpdated) {
        onPlanUpdated({ tasks: cached });
      }
    }
    try {
      const data = await getTasks('all');
      setTasks(data || []);
      writeTaskCache(data || []);
      if (onPlanUpdated) {
        onPlanUpdated({ tasks: data || [] });
      }
    } catch (err) {
      setError(err.message);
      setTasks([]);
    }
    setLoading(false);
  }, [onPlanUpdated]);

  const mergeTaskLocally = useCallback((updatedTask) => {
    setTasks((current) => {
      const next = current.map((task) => (task.id === updatedTask.id ? updatedTask : task));
      writeTaskCache(next);
      return next;
    });
  }, []);

  const removeTaskLocally = useCallback((taskId) => {
    setTasks((current) => {
      const next = current.filter((task) => task.id !== taskId);
      writeTaskCache(next);
      return next;
    });
  }, []);

  useEffect(() => {
    loadTasks();
  }, [loadTasks, taskRefreshSignal, planRefreshSignal]);

  const handleQuickAction = useCallback(async (taskId, action) => {
    setLoading(true);
    setError('');
    setFeedbackMessage('');
    try {
      const task = tasks.find((entry) => entry.id === taskId);
      if (action === 'delete') {
        removeTaskLocally(taskId);
        await deleteTask(taskId, true);
        setFeedbackMessage(lang === 'zh' ? '已删除。' : 'Deleted.');
      } else if (action === 'complete') {
        const updated = await updateTask(taskId, { status: 'completed' });
        mergeTaskLocally(updated);
        setFeedbackMessage(lang === 'zh' ? '已完成。' : 'Completed.');
      } else if (action === 'defer') {
        const nextDueDate = task?.task_kind === 'weekly' ? getEasternDate(7) : getEasternDate(1);
        setTasks((current) => {
          const next = current.map((entry) => (
            entry.id === taskId
              ? { ...entry, due_date: nextDueDate, deferral_count: (entry.deferral_count || 0) + 1 }
              : entry
          ));
          writeTaskCache(next);
          return next;
        });
        const updated = await updateTask(taskId, { deferral_count_delta: 1, due_date: nextDueDate });
        mergeTaskLocally(updated);
        setFeedbackMessage(
          lang === 'zh'
            ? `已推迟到${task?.task_kind === 'weekly' ? '下一轮' : '明天'}。`
            : `Deferred to ${task?.task_kind === 'weekly' ? 'the next cycle' : 'tomorrow'}.`
        );
      }
    } catch (err) {
      setError(err.message);
      await loadTasks();
    } finally {
      setLoading(false);
    }
  }, [lang, loadTasks, mergeTaskLocally, removeTaskLocally, tasks]);

  const sortedTasks = useMemo(
    () => [...tasks]
      .filter((task) => (task.status || 'active') !== 'deleted')
      .sort((a, b) => {
      if ((a.task_kind || 'temporary') !== (b.task_kind || 'temporary')) {
        const rank = { daily: 0, weekly: 1, temporary: 2 };
        return (rank[a.task_kind || 'temporary'] ?? 9) - (rank[b.task_kind || 'temporary'] ?? 9);
      }
      const aCompleted = completedOnDate(a, getEasternDate(0));
      const bCompleted = completedOnDate(b, getEasternDate(0));
      if (aCompleted !== bCompleted) {
        return aCompleted ? 1 : -1;
      }
      if ((b.priority || 0) !== (a.priority || 0)) {
        return (b.priority || 0) - (a.priority || 0);
      }
      return (a.sort_order || 0) - (b.sort_order || 0);
    }),
    [tasks]
  );

  const dailyCount = sortedTasks.filter((task) => task.task_kind === 'daily').length;
  const weeklyCount = sortedTasks.filter((task) => task.task_kind === 'weekly').length;
  const temporaryCount = sortedTasks.filter((task) => task.task_kind !== 'daily' && task.task_kind !== 'weekly').length;
  const nowMeta = useMemo(() => getEasternNowMeta(lang), [lang]);
  const todayStamp = useMemo(() => formatTodayStamp(lang), [lang]);
  const isSystemMetaDescription = (text) =>
    typeof text === 'string' && /^Imported from .* onboarding\.$/.test(text.trim());

  const groupedTasks = useMemo(() => {
    const groups = { overdue: [], today: [], tomorrow: [], later: [], daily: [], weekly: [] };
    sortedTasks.forEach((task) => {
      const isCompletedToday = completedOnDate(task, nowMeta.iso);
      const status = task.status || 'active';
      if (status === 'completed' && !isCompletedToday) return;

      if ((task.task_kind || 'temporary') === 'daily') {
        if (task.due_date && task.due_date > nowMeta.iso) return;
        groups.daily.push(task);
        return;
      }
      if ((task.task_kind || 'temporary') === 'weekly') {
        if (task.due_date && task.due_date > nowMeta.iso) return;
        if (task.recurrence_weekday == null || Number(task.recurrence_weekday) === nowMeta.weekday) {
          groups.weekly.push(task);
        }
        return;
      }
      if (isCompletedToday) {
        groups.today.push(task);
        return;
      }
      if (!task.due_date || task.due_date <= nowMeta.iso) {
        if (task.due_date && task.due_date < nowMeta.iso) {
          groups.overdue.push(task);
        } else {
          groups.today.push(task);
        }
        return;
      }
      if (task.due_date === nowMeta.tomorrow) {
        groups.tomorrow.push(task);
        return;
      }
      groups.later.push(task);
    });
    return groups;
  }, [nowMeta.iso, nowMeta.tomorrow, nowMeta.weekday, sortedTasks]);

  const sections = [
    { key: 'overdue', title: timeCopy.overdue, subtitle: timeCopy.overdueSub, tasks: groupedTasks.overdue },
    { key: 'today', title: timeCopy.today, subtitle: timeCopy.todaySub, tasks: groupedTasks.today },
    { key: 'daily', title: timeCopy.daily, subtitle: timeCopy.dailySub, tasks: groupedTasks.daily },
    { key: 'weekly', title: timeCopy.weekly, subtitle: timeCopy.weeklySub, tasks: groupedTasks.weekly },
  ].filter((section) => section.tasks.length > 0);

  const visibleTasks = useMemo(
    () => sections.flatMap((section) => section.tasks),
    [sections]
  );

  useEffect(() => {
    if (!visibleTasks.length) {
      setSelectedFocusTaskId(null);
      return;
    }
    if (!selectedFocusTaskId || !visibleTasks.some((task) => task.id === selectedFocusTaskId)) {
      setSelectedFocusTaskId(visibleTasks[0].id);
    }
  }, [selectedFocusTaskId, visibleTasks]);

  const renderDueBadge = (task) => {
    if ((task.task_kind || 'temporary') === 'daily' || (task.task_kind || 'temporary') === 'weekly') {
      return null;
    }
    if (!task.due_date || task.due_date <= nowMeta.iso) {
      return null;
    }
    const copy = task.due_date === nowMeta.tomorrow ? timeCopy.dueTomorrow : timeCopy.dueLater;
    return (
      <span className="rounded-full bg-[color:var(--surface)] px-2.5 py-1 text-[11px] font-medium text-[color:var(--muted)]">
        {copy}
      </span>
    );
  };

  const renderTaskActions = (task) => (
    <div className="flex flex-wrap items-center justify-end gap-3">
      <button
        onClick={() => setSelectedFocusTaskId(task.id)}
        className="daily-log-action"
      >
        {t.focusAction}
      </button>
      <button
        onClick={() => handleQuickAction(task.id, 'defer')}
        disabled={loading || completedOnDate(task, nowMeta.iso)}
        className="daily-log-action disabled:opacity-40"
      >
        {t.btnDefer}
      </button>
      <button
        onClick={() => handleQuickAction(task.id, 'delete')}
        disabled={loading}
        className="daily-log-action disabled:opacity-40"
      >
        {t.deleteBtn}
      </button>
    </div>
  );

  const toggleTodayComplete = async (task) => {
    setLoading(true);
    setError('');
    try {
      if (completedOnDate(task, nowMeta.iso)) {
        setTasks((current) => {
          const next = current.map((entry) => (
            entry.id === task.id ? { ...entry, completed_at: null, status: 'active' } : entry
          ));
          writeTaskCache(next);
          return next;
        });
        const updated = await updateTask(task.id, { status: 'active' });
        mergeTaskLocally(updated);
        setFeedbackMessage(lang === 'zh' ? '已恢复。' : 'Restored.');
      } else {
        const optimisticCompletedAt = new Date().toISOString();
        setTasks((current) => {
          const next = current.map((entry) => (
            entry.id === task.id ? { ...entry, completed_at: optimisticCompletedAt } : entry
          ));
          writeTaskCache(next);
          return next;
        });
        const updated = await updateTask(task.id, { status: 'completed' });
        mergeTaskLocally(updated);
        setFeedbackMessage(lang === 'zh' ? '已标记完成。' : 'Marked complete.');
      }
    } catch (err) {
      setError(err.message);
      await loadTasks();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      {error && (
        <div className="rounded-[18px] border border-[color:var(--accent)]/30 bg-[color:var(--surface)] px-3.5 py-2.5 text-sm text-[color:var(--accent)]">
          {error}
        </div>
      )}
      {feedbackMessage && !error && (
        <div className="rounded-[18px] border border-[color:var(--line)] bg-white px-3.5 py-2.5 text-sm text-[color:var(--muted)]">
          {feedbackMessage}
        </div>
      )}

      <section className="card">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_224px]">
          <div className="board-card p-3.5">
            <div className="mb-2.5 flex items-center justify-between gap-3">
              <div>
                <div className="panel-label">Today // Live Task Stack</div>
                <h2 className="mt-2 text-[32px] leading-none text-[color:var(--text)]">{t.todayPlanTitle}</h2>
                <p className="mt-1 text-sm text-[color:var(--muted)]">{t.todayPlanSubtitle}</p>
                <p className="mt-2 font-[var(--mono)] text-[11px] uppercase tracking-[0.16em] text-[color:var(--muted)]">
                  {timeCopy.rhythm}: {nowMeta.label}
                </p>
              </div>
              <div className="flex flex-wrap justify-end gap-1.5 text-xs">
                <span className="tech-chip">
                  {t.taskKindDaily}: {dailyCount}
                </span>
                <span className="tech-chip">
                  {t.taskKindWeekly}: {weeklyCount}
                </span>
                <span className="tech-chip">
                  {t.taskKindTemporary}: {temporaryCount}
                </span>
              </div>
            </div>

            {loading && !sortedTasks.length ? (
              <div className="rounded-[18px] border border-dashed border-[color:var(--line)] px-4 py-8 text-center">
                <p className="text-sm text-[color:var(--muted)]">{t.loadingTasks}</p>
              </div>
            ) : !sortedTasks.length ? (
              <div className="rounded-[18px] border border-dashed border-[color:var(--line)] px-4 py-8 text-center">
                <p className="text-sm text-[color:var(--muted)]">{t.todayPlanEmpty}</p>
              </div>
            ) : (
              <div className="daily-log-board overflow-hidden px-4 py-4">
                <div className="relative z-[1] flex items-start justify-between gap-4">
                  <div className="inline-flex rotate-[-2deg] border-2 border-[color:var(--line-strong)] bg-white px-3 py-1 font-[var(--mono)] text-[11px] uppercase tracking-[0.22em] text-[color:var(--text)]">
                    {todayStamp}
                  </div>
                  <div className="text-right">
                    <div className="font-[var(--sans)] text-[34px] font-semibold italic leading-none text-[color:var(--text)]">
                      Focus
                    </div>
                    <div className="mt-1 font-[var(--mono)] text-[10px] uppercase tracking-[0.18em] text-[color:var(--muted)]">
                      Daily log
                    </div>
                  </div>
                </div>

                <div className="relative z-[1] mt-4 max-h-[min(50vh,620px)] space-y-3 overflow-y-auto pr-1">
                  {sections.map((section) => (
                    <div key={section.key}>
                      <div className="mb-2 flex items-center gap-3">
                        <h3 className="daily-log-section-label">{section.title}</h3>
                        <div className="daily-log-section-line flex-1" />
                        <span className="font-[var(--mono)] text-[11px] uppercase tracking-[0.18em] text-[color:var(--muted)]">
                          {section.tasks.length}
                        </span>
                      </div>
                      <p className="mb-2 text-[13px] text-[color:var(--muted)]">{section.subtitle}</p>
                      <div className="space-y-0">
                        {section.tasks.map((task) => (
                          <div key={task.id} className="daily-log-row border-b border-dotted border-[color:var(--line)] py-1.5 last:border-b-0">
                            <button
                              type="button"
                              onClick={() => toggleTodayComplete(task)}
                              disabled={loading}
                              className={`daily-log-check ${completedOnDate(task, nowMeta.iso) ? 'checked' : ''}`}
                              aria-label={completedOnDate(task, nowMeta.iso) ? t.btnDone : t.focusAction}
                            />
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <p
                                  className={`truncate font-[var(--mono)] text-[15px] tracking-[0.02em] ${
                                    completedOnDate(task, nowMeta.iso)
                                      ? 'text-[color:var(--muted)] line-through decoration-[color:rgba(17,17,17,0.55)] decoration-2'
                                      : 'text-[color:var(--text)]'
                                  }`}
                                >
                                  {task.title}
                                </p>
                                <span
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                                    task.task_kind === 'daily' || task.task_kind === 'weekly'
                                      ? 'bg-[color:var(--surface)] text-[color:var(--text)]'
                                      : 'bg-[color:var(--surface)] text-[color:var(--muted)]'
                                  }`}
                                >
                                  {recurringKindLabel(task, lang, kindBadgeCopy[task.task_kind] || kindBadgeCopy.temporary)}
                                </span>
                                {renderDueBadge(task)}
                              </div>
                              {task.description && !isSystemMetaDescription(task.description) && (
                                <p className="mt-1 text-[13px] text-[color:var(--muted)]">{task.description}</p>
                              )}
                            </div>
                            {renderTaskActions(task)}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-[18px] border border-[color:var(--line)] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,248,238,0.86))] p-2.5">
            <FocusTimer
              tasks={visibleTasks}
              selectedTaskId={selectedFocusTaskId}
              onSelectedTaskChange={setSelectedFocusTaskId}
              compact
            />
          </div>
        </div>
      </section>

      <InspirationBox ideas={inspirations} onDismissIdea={onDismissInspiration} />
    </div>
  );
}

export default DailyPlan;
