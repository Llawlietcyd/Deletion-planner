import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  deleteTask,
  generatePlan,
  getTasks,
  getTodayPlan,
  submitFeedback,
  updateTask,
} from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import FocusTimer from './FocusTimer';

function DailyPlan({ refreshSignal = 0 }) {
  const { lang, t } = useLanguage();
  const [plan, setPlan] = useState(null);
  const [activeTasks, setActiveTasks] = useState([]);
  const [deletionSuggestions, setDeletionSuggestions] = useState([]);
  const [capacityUnits, setCapacityUnits] = useState(() => {
    const cached = window.localStorage.getItem('planning_capacity_units');
    const parsed = Number(cached);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 6;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [feedbackMode, setFeedbackMode] = useState(false);
  const [taskStatuses, setTaskStatuses] = useState({});
  const [showDeferred, setShowDeferred] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);
  const [nextPreview, setNextPreview] = useState(null);
  const [selectedFocusTaskId, setSelectedFocusTaskId] = useState(null);

  const today = useMemo(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  }, []);

  const loadPlan = useCallback(async () => {
    try {
      const data = await getTodayPlan(lang, capacityUnits);
      setPlan(data);
      setDeletionSuggestions(data.deletion_suggestions || []);
    } catch {
      setPlan(null);
      setDeletionSuggestions([]);
    }
  }, [lang, capacityUnits]);

  const loadActiveTasks = useCallback(async () => {
    try {
      const data = await getTasks('active');
      setActiveTasks(data || []);
    } catch {
      setActiveTasks([]);
    }
  }, []);

  useEffect(() => {
    loadPlan();
  }, [loadPlan, refreshSignal]);

  useEffect(() => {
    loadActiveTasks();
  }, [loadActiveTasks, refreshSignal]);

  useEffect(() => {
    window.localStorage.setItem('planning_capacity_units', String(capacityUnits));
  }, [capacityUnits]);

  const handleGenerate = async (force = false) => {
    setLoading(true);
    setError('');
    setNextPreview(null);
    try {
      const data = await generatePlan(null, lang, capacityUnits, force);
      setPlan(data);
      setDeletionSuggestions(data.deletion_suggestions || []);
      await loadActiveTasks();
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleQuickAction = async (taskId, action) => {
    setLoading(true);
    setError('');
    try {
      if (action === 'complete') {
        await updateTask(taskId, { status: 'completed' });
      } else if (action === 'defer') {
        await updateTask(taskId, { deferral_count_delta: 1 });
      } else if (action === 'delete') {
        await deleteTask(taskId);
      }
      await Promise.all([loadPlan(), loadActiveTasks()]);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleStatusChange = (planTaskId, status) => {
    setTaskStatuses((current) => ({ ...current, [planTaskId]: status }));
  };

  const handleSubmitFeedback = async () => {
    const results = Object.entries(taskStatuses).map(([planTaskId, status]) => ({
      plan_task_id: Number(planTaskId),
      status,
    }));

    if (results.length === 0) {
      setError(t.markAtLeastOne);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await submitFeedback(today, results, lang, capacityUnits);
      setNextPreview(data.next_day_preview || null);
      setDeletionSuggestions(data.deletion_suggestions || []);
      setFeedbackMode(false);
      setTaskStatuses({});
      await Promise.all([loadPlan(), loadActiveTasks()]);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const planTasks = plan?.tasks || [];
  const deferredTasks = plan?.deferred_tasks || [];
  const decisionSummary = plan?.decision_summary;
  const deletionCandidate = deletionSuggestions[0];
  const focusTasks = planTasks.map((planTask) => planTask.task).filter(Boolean);

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-[20px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="card">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-medium text-[color:var(--text)]">
              {plan && decisionSummary
                ? `${decisionSummary.keep_count} keep / ${decisionSummary.defer_count} defer / ${decisionSummary.delete_count} delete`
                : `${activeTasks.length} active task${activeTasks.length === 1 ? '' : 's'}`}
            </p>
            <p className="mt-1 text-sm text-[color:var(--muted)]">
              {plan && decisionSummary ? decisionSummary.headline : t.noPlanSub}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 rounded-full bg-white/70 px-3 py-2 text-sm text-[color:var(--muted)]">
              {t.capacityLabel}
              <input
                type="number"
                min="1"
                max="24"
                value={capacityUnits}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  if (!Number.isFinite(next)) {
                    return;
                  }
                  setCapacityUnits(Math.max(1, Math.min(24, next)));
                }}
                className="w-12 bg-transparent text-right text-[color:var(--text)] outline-none"
              />
            </label>
            {!plan ? (
              <button onClick={() => handleGenerate(false)} disabled={loading} className="btn-primary">
                {loading ? t.generating : t.generatePlan}
              </button>
            ) : (
              <>
                <button onClick={() => handleGenerate(true)} disabled={loading} className="btn-primary">
                  {loading ? t.regenerating : t.regeneratePlan}
                </button>
                <button onClick={() => setFeedbackMode((value) => !value)} className="btn-ghost">
                  {t.giveFeedback}
                </button>
              </>
            )}
          </div>
        </div>
      </section>

      <FocusTimer
        tasks={focusTasks}
        selectedTaskId={selectedFocusTaskId}
        onSelectedTaskChange={setSelectedFocusTaskId}
      />

      <section className="card">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl text-[color:var(--text)]">{t.keepTodayTitle}</h2>
            <p className="mt-1 text-sm text-[color:var(--muted)]">{t.keepTodaySubtitle}</p>
          </div>
        </div>

        {!plan ? (
          <div className="rounded-[20px] border border-dashed border-[color:var(--line)] px-4 py-10 text-center">
            <p className="text-sm text-[color:var(--muted)]">{t.noPlan}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {planTasks.map((planTask) => (
              <div key={planTask.id} className="rounded-[20px] border border-[color:var(--line)] bg-white/70 px-4 py-3">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-base font-medium text-[color:var(--text)]">
                      {planTask.task?.title || t.unknownTask}
                    </p>
                    {planTask.task?.description && (
                      <p className="mt-1 text-sm text-[color:var(--muted)]">{planTask.task.description}</p>
                    )}
                  </div>

                  {!feedbackMode ? (
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => setSelectedFocusTaskId(planTask.task_id)}
                        className="rounded-full bg-white px-3 py-1.5 text-sm font-medium text-[color:var(--text)]"
                      >
                        {t.focusAction}
                      </button>
                      <button
                        onClick={() => handleQuickAction(planTask.task_id, 'complete')}
                        className="rounded-full bg-emerald-100 px-3 py-1.5 text-sm font-medium text-emerald-700"
                      >
                        {t.btnDone}
                      </button>
                      <button
                        onClick={() => handleQuickAction(planTask.task_id, 'defer')}
                        className="rounded-full bg-amber-100 px-3 py-1.5 text-sm font-medium text-amber-700"
                      >
                        {t.btnDefer}
                      </button>
                      <button
                        onClick={() => handleQuickAction(planTask.task_id, 'delete')}
                        className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700"
                      >
                        {t.deleteBtn}
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {[
                        { value: 'completed', label: t.btnDone },
                        { value: 'missed', label: t.btnMissed },
                        { value: 'deferred', label: t.btnDefer },
                      ].map((option) => (
                        <button
                          key={option.value}
                          onClick={() => handleStatusChange(planTask.id, option.value)}
                          className={`rounded-full px-3 py-1.5 text-sm ${
                            taskStatuses[planTask.id] === option.value
                              ? 'bg-[color:var(--accent)] text-white'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {feedbackMode && (
              <div className="flex gap-2 pt-2">
                <button
                  onClick={handleSubmitFeedback}
                  disabled={loading || Object.keys(taskStatuses).length === 0}
                  className="btn-primary disabled:opacity-50"
                >
                  {loading ? t.submitting : t.submitFeedback}
                </button>
                <button
                  onClick={() => {
                    setFeedbackMode(false);
                    setTaskStatuses({});
                  }}
                  className="btn-ghost"
                >
                  {t.cancel}
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      {plan && (
        <section className="card py-4">
          <button
            onClick={() => setShowDeferred((value) => !value)}
            className="flex w-full items-center justify-between text-left"
          >
            <div>
              <h3 className="text-lg text-[color:var(--text)]">{t.deferTitle}</h3>
              <p className="mt-1 text-sm text-[color:var(--muted)]">
                {deferredTasks.length > 0
                  ? `${deferredTasks.length} task${deferredTasks.length === 1 ? '' : 's'}`
                  : t.noDeferredTasks}
              </p>
            </div>
            <span className="text-sm text-[color:var(--muted)]">{showDeferred ? 'Hide' : 'Show'}</span>
          </button>

          {showDeferred && deferredTasks.length > 0 && (
            <div className="mt-4 space-y-2 border-t border-[color:var(--line)] pt-4">
              {deferredTasks.map((task) => (
                <div key={task.id} className="rounded-[18px] bg-white/60 px-4 py-3">
                  <p className="text-sm font-medium text-[color:var(--text)]">{task.title}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {plan && deletionCandidate && (
        <section className="card py-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium text-[color:var(--text)]">{deletionCandidate.title}</p>
              <p className="mt-1 text-sm text-[color:var(--muted)]">{deletionCandidate.deletion_reasoning}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleQuickAction(deletionCandidate.id, 'delete')}
                className="rounded-full bg-red-600 px-3 py-1.5 text-sm font-medium text-white"
              >
                {t.deleteBtn}
              </button>
              <button
                onClick={() => setDeletionSuggestions((current) => current.slice(1))}
                className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700"
              >
                {t.keepBtn}
              </button>
            </div>
          </div>
        </section>
      )}

      {plan && (
        <section className="card py-4">
          <button
            onClick={() => setShowReasoning((value) => !value)}
            className="flex w-full items-center justify-between text-left"
          >
            <div>
              <h3 className="text-lg text-[color:var(--text)]">{t.whyThisPlanTitle}</h3>
              <p className="mt-1 text-sm text-[color:var(--muted)]">
                {decisionSummary?.next_step || t.aiReasoning}
              </p>
            </div>
            <span className="text-sm text-[color:var(--muted)]">{showReasoning ? 'Hide' : 'Show'}</span>
          </button>

          {showReasoning && (
            <div className="mt-4 border-t border-[color:var(--line)] pt-4">
              <p className="text-sm leading-7 text-[color:var(--text)]">{plan.reasoning}</p>
              {plan.coach_notes?.length > 0 && (
                <div className="mt-3 space-y-1 text-sm text-[color:var(--muted)]">
                  {plan.coach_notes.map((note) => (
                    <p key={note}>{note}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {nextPreview && (
        <section className="card py-4">
          <h3 className="text-lg text-[color:var(--text)]">{t.nextPreviewTitle}</h3>
          <p className="mt-1 text-sm text-[color:var(--muted)]">{nextPreview.adaptive_reason}</p>
          {nextPreview.preview_tasks?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {nextPreview.preview_tasks.slice(0, 3).map((item) => (
                <span
                  key={item.id}
                  className="rounded-full bg-white/70 px-3 py-1.5 text-sm text-[color:var(--text)]"
                >
                  {item.task?.title}
                </span>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default DailyPlan;
