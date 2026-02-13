import React, { useState, useEffect, useCallback } from 'react';
import { generatePlan, getTodayPlan, submitFeedback } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import DeletionSuggestion from './DeletionSuggestion';

function DailyPlan() {
  const { lang, t } = useLanguage();
  const [plan, setPlan] = useState(null);
  const [deletionSuggestions, setDeletionSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [feedbackMode, setFeedbackMode] = useState(false);
  const [taskStatuses, setTaskStatuses] = useState({});

  const today = new Date().toISOString().split('T')[0];

  // Reload plan whenever language changes
  const loadTodayPlan = useCallback(async () => {
    try {
      const data = await getTodayPlan(lang);
      setPlan(data);
      if (data.deletion_suggestions?.length > 0) {
        setDeletionSuggestions(data.deletion_suggestions);
      }
    } catch {
      setPlan(null);
    }
  }, [lang]);

  useEffect(() => {
    loadTodayPlan();
  }, [loadTodayPlan]);

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await generatePlan(null, lang);
      setPlan(data);
      if (data.deletion_suggestions) {
        setDeletionSuggestions(data.deletion_suggestions);
      }
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleStatusChange = (planTaskId, status) => {
    setTaskStatuses((prev) => ({ ...prev, [planTaskId]: status }));
  };

  const handleSubmitFeedback = async () => {
    const results = Object.entries(taskStatuses).map(([planTaskId, status]) => ({
      plan_task_id: parseInt(planTaskId),
      status,
    }));

    if (results.length === 0) {
      setError(t.markAtLeastOne);
      return;
    }

    setLoading(true);
    setError('');
    try {
      const data = await submitFeedback(today, results, lang);
      if (data.deletion_suggestions?.length > 0) {
        setDeletionSuggestions(data.deletion_suggestions);
      }
      setFeedbackMode(false);
      loadTodayPlan();
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const STATUS_OPTIONS = [
    { value: 'completed', label: t.btnDone, color: 'bg-green-500' },
    { value: 'missed', label: t.btnMissed, color: 'bg-slate-400' },
    { value: 'deferred', label: t.btnDefer, color: 'bg-amber-500' },
  ];

  const STATUS_LABEL = {
    completed: t.actionCompleted,
    deferred: t.actionDeferred,
    missed: t.actionMissed,
    planned: t.planned,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{t.dailyPlanTitle}</h1>
          <p className="text-slate-500 text-sm">{today}</p>
        </div>
        <div className="flex gap-2">
          {plan && !feedbackMode && (
            <button onClick={() => setFeedbackMode(true)} className="btn-ghost">
              {t.giveFeedback}
            </button>
          )}
          {!plan && (
            <button onClick={handleGenerate} disabled={loading} className="btn-primary">
              {loading ? t.generating : t.generatePlan}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 p-3 rounded-lg">{error}</div>
      )}

      {plan?.reasoning && (
        <div className="card !bg-brand/5 !border-brand/20">
          <div className="flex items-start gap-3">
            <span className="text-xl mt-0.5">🤖</span>
            <div>
              <p className="font-medium text-brand text-sm mb-1">{t.aiReasoning}</p>
              <p className="text-slate-700 text-sm leading-relaxed">{plan.reasoning}</p>
            </div>
          </div>
        </div>
      )}

      {plan?.overload_warning && (
        <div className="card !bg-amber-50 !border-amber-200">
          <div className="flex items-start gap-3">
            <span className="text-xl mt-0.5">⚠️</span>
            <p className="text-amber-800 text-sm">{plan.overload_warning}</p>
          </div>
        </div>
      )}

      {plan?.tasks && plan.tasks.length > 0 ? (
        <div className="space-y-2">
          {plan.tasks.map((pt) => (
            <div key={pt.id} className="card !p-4 flex items-center justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      pt.status === 'completed' ? 'bg-green-500' :
                      pt.status === 'deferred' ? 'bg-amber-500' :
                      pt.status === 'missed' ? 'bg-slate-400' :
                      'bg-blue-500'
                    }`}
                  />
                  <span className="font-medium text-slate-800">
                    {pt.task?.title || t.unknownTask}
                  </span>
                  {pt.status !== 'planned' && (
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                      pt.status === 'completed' ? 'bg-green-100 text-green-700' :
                      pt.status === 'deferred' ? 'bg-amber-100 text-amber-700' :
                      'bg-slate-100 text-slate-600'
                    }`}>
                      {STATUS_LABEL[pt.status] || pt.status}
                    </span>
                  )}
                </div>
                {pt.task?.description && (
                  <p className="text-sm text-slate-500 ml-4 mt-1">{pt.task.description}</p>
                )}
              </div>

              {feedbackMode && pt.status === 'planned' && (
                <div className="flex gap-1">
                  {STATUS_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => handleStatusChange(pt.id, opt.value)}
                      className={`px-2 py-1 text-xs rounded-md font-medium transition-all ${
                        taskStatuses[pt.id] === opt.value
                          ? `${opt.color} text-white`
                          : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : !plan ? (
        <div className="card text-center py-10">
          <p className="text-4xl mb-3">📋</p>
          <p className="text-slate-500">{t.noPlan}</p>
          <p className="text-slate-400 text-sm mt-1">{t.noPlanSub}</p>
        </div>
      ) : null}

      {feedbackMode && (
        <div className="flex gap-2">
          <button
            onClick={handleSubmitFeedback}
            disabled={loading || Object.keys(taskStatuses).length === 0}
            className="btn-primary flex-1 disabled:opacity-50"
          >
            {loading ? t.submitting : t.submitFeedback}
          </button>
          <button
            onClick={() => { setFeedbackMode(false); setTaskStatuses({}); }}
            className="btn-ghost"
          >
            {t.cancel}
          </button>
        </div>
      )}

      {deletionSuggestions.length > 0 && (
        <DeletionSuggestion
          suggestions={deletionSuggestions}
          onDismiss={() => setDeletionSuggestions([])}
        />
      )}
    </div>
  );
}

export default DailyPlan;
