import React, { useState } from 'react';
import { batchCreateTasks, createTask } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

const PRIORITY_OPTIONS = [
  { value: 0, tone: 'bg-slate-100 text-slate-600' },
  { value: 1, tone: 'bg-sky-100 text-sky-700' },
  { value: 3, tone: 'bg-amber-100 text-amber-700' },
  { value: 5, tone: 'bg-red-100 text-red-700' },
];

function TaskInput({ onTaskCreated, variant = 'default' }) {
  const { t } = useLanguage();
  const isMinimal = variant === 'minimal';
  const [mode, setMode] = useState('single');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(0);
  const [category, setCategory] = useState('unclassified');
  const [dueDate, setDueDate] = useState('');
  const [batchText, setBatchText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const priorityLabels = [t.priorityLow, t.priorityMedium, t.priorityHigh, t.priorityUrgent];

  const resetSingle = () => {
    setTitle('');
    setDescription('');
    setPriority(0);
    setCategory('unclassified');
    setDueDate('');
  };

  const handleSingleSubmit = async (event) => {
    event.preventDefault();
    if (!title.trim()) {
      return;
    }

    setLoading(true);
    setError('');
    try {
      await createTask(title, description, priority, category, dueDate || null);
      resetSingle();
      if (onTaskCreated) {
        onTaskCreated();
      }
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleBatchSubmit = async (event) => {
    event.preventDefault();
    if (!batchText.trim()) {
      return;
    }

    setLoading(true);
    setError('');
    try {
      await batchCreateTasks(batchText);
      setBatchText('');
      if (onTaskCreated) {
        onTaskCreated();
      }
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const categoryOptions = [
    { value: 'unclassified', label: t.catUnclassified },
    { value: 'core', label: t.catCore },
    { value: 'deferrable', label: t.catDeferrable },
    { value: 'deletion_candidate', label: t.catDeletion },
  ];

  const wrapperClass = isMinimal ? 'space-y-3' : 'card space-y-4';

  return (
    <div className={wrapperClass}>
      {!isMinimal && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl text-[color:var(--text)]">{t.addTasks}</h2>
            <p className="mt-1 text-sm text-[color:var(--muted)]">{t.tasksSubtitle}</p>
          </div>
          <div className="flex rounded-full border border-[color:var(--line)] bg-white/50 p-1">
            <button
              onClick={() => setMode('single')}
              className={`rounded-full px-4 py-2 text-sm transition-all ${
                mode === 'single'
                  ? 'bg-[color:var(--accent-soft)] text-[color:var(--accent)]'
                  : 'text-[color:var(--muted)]'
              }`}
            >
              {t.singleMode}
            </button>
            <button
              onClick={() => setMode('batch')}
              className={`rounded-full px-4 py-2 text-sm transition-all ${
                mode === 'batch'
                  ? 'bg-[color:var(--accent-soft)] text-[color:var(--accent)]'
                  : 'text-[color:var(--muted)]'
              }`}
            >
              {t.batchMode}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {(isMinimal || mode === 'single') ? (
        <form onSubmit={handleSingleSubmit} className="space-y-3">
          <div className="flex flex-col gap-3 md:flex-row">
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={isMinimal ? t.todayQuickAddPlaceholder : t.taskPlaceholder}
              className="min-w-0 flex-1 rounded-[22px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none transition-all focus:border-[color:var(--accent)] focus:ring-2 focus:ring-[color:var(--accent-soft)]"
            />
            <button
              type="submit"
              disabled={loading || !title.trim()}
              className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? t.adding : t.addTask}
            </button>
          </div>

          {!isMinimal && (
            <>
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder={t.descPlaceholder}
                rows={2}
                className="w-full rounded-[22px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none transition-all focus:border-[color:var(--accent)] focus:ring-2 focus:ring-[color:var(--accent-soft)]"
              />

              <div className="grid gap-3 md:grid-cols-[1.2fr_0.8fr_0.8fr]">
                <div className="rounded-[22px] border border-[color:var(--line)] bg-white/65 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--muted)]">
                    {t.priorityLabel}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {PRIORITY_OPTIONS.map((option, index) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setPriority(option.value)}
                        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-all ${
                          priority === option.value
                            ? `${option.tone} ring-2 ring-[color:var(--accent-soft)]`
                            : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {priorityLabels[index]}
                      </button>
                    ))}
                  </div>
                </div>

                <label className="rounded-[22px] border border-[color:var(--line)] bg-white/65 p-4 text-sm text-[color:var(--muted)]">
                  <span className="text-xs font-semibold uppercase tracking-[0.18em]">
                    {t.categoryLabel}
                  </span>
                  <select
                    value={category}
                    onChange={(event) => setCategory(event.target.value)}
                    className="mt-3 w-full rounded-2xl border border-[color:var(--line)] bg-white px-3 py-2 text-sm text-[color:var(--text)] outline-none"
                  >
                    {categoryOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="rounded-[22px] border border-[color:var(--line)] bg-white/65 p-4 text-sm text-[color:var(--muted)]">
                  <span className="text-xs font-semibold uppercase tracking-[0.18em]">
                    {t.dueDateLabel}
                  </span>
                  <input
                    type="date"
                    value={dueDate}
                    onChange={(event) => setDueDate(event.target.value)}
                    className="mt-3 w-full rounded-2xl border border-[color:var(--line)] bg-white px-3 py-2 text-sm text-[color:var(--text)] outline-none"
                  />
                  {dueDate && (
                    <button
                      type="button"
                      onClick={() => setDueDate('')}
                      className="mt-2 text-xs text-[color:var(--accent)]"
                    >
                      {t.clearDate}
                    </button>
                  )}
                </label>
              </div>
            </>
          )}
        </form>
      ) : (
        <form onSubmit={handleBatchSubmit} className="space-y-3">
          <textarea
            value={batchText}
            onChange={(event) => setBatchText(event.target.value)}
            placeholder={t.batchPlaceholder}
            rows={6}
            className="w-full rounded-[22px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none transition-all focus:border-[color:var(--accent)] focus:ring-2 focus:ring-[color:var(--accent-soft)]"
          />
          <button
            type="submit"
            disabled={loading || !batchText.trim()}
            className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? t.adding : t.addAllTasks}
          </button>
        </form>
      )}
    </div>
  );
}

export default TaskInput;
