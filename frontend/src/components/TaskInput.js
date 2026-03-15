import React, { useState } from 'react';
import { batchCreateTasks, createTask } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

const PRIORITY_OPTIONS = [
  { value: 0, tone: 'bg-[color:var(--surface)] text-[color:var(--muted)]' },
  { value: 1, tone: 'bg-[color:var(--surface)] text-[color:var(--text)]' },
  { value: 3, tone: 'bg-[color:var(--accent-soft)] text-[color:var(--accent)]' },
  { value: 5, tone: 'bg-[color:var(--accent)] text-white' },
];

function TaskInput({ onTaskCreated, onIdeaCreated, variant = 'default' }) {
  const { t } = useLanguage();
  const isMinimal = variant === 'minimal';
  const [mode, setMode] = useState('single');
  const [title, setTitle] = useState('');
  const [ideaTitle, setIdeaTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(0);
  const [category, setCategory] = useState('unclassified');
  const [dueDate, setDueDate] = useState('');
  const [taskKind, setTaskKind] = useState('temporary');
  const [recurrenceWeekday, setRecurrenceWeekday] = useState('');
  const [batchText, setBatchText] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeSubmit, setActiveSubmit] = useState('task');
  const [error, setError] = useState('');

  const priorityLabels = [t.priorityLow, t.priorityMedium, t.priorityHigh, t.priorityUrgent];

  const resetSingle = () => {
    setTitle('');
    setDescription('');
    setPriority(0);
    setCategory('unclassified');
    setDueDate('');
    setTaskKind('temporary');
    setRecurrenceWeekday('');
  };

  const notifyCreated = (kind = 'task') => {
    if (onTaskCreated) {
      onTaskCreated(kind);
    }
  };

  const handleSingleSubmit = async (event) => {
    event.preventDefault();
    if (!title.trim()) {
      return;
    }

    setLoading(true);
    setActiveSubmit('task');
    setError('');
    try {
      await createTask(
        title.trim(), description, priority, category, dueDate || null,
        taskKind || null,
        taskKind === 'weekly' && recurrenceWeekday !== '' ? Number(recurrenceWeekday) : null
      );
      resetSingle();
      notifyCreated('task');
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleIdeaSubmit = async (event) => {
    event.preventDefault();
    if (!ideaTitle.trim()) {
      return;
    }

    setLoading(true);
    setActiveSubmit('idea');
    setError('');
    try {
      if (isMinimal && onIdeaCreated) {
        onIdeaCreated(ideaTitle.trim());
      } else {
        await createTask(ideaTitle.trim(), t.ideaTaskDescription, 0, 'unclassified', null);
        notifyCreated('idea');
      }
      setIdeaTitle('');
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
    setActiveSubmit('batch');
    setError('');
    try {
      await batchCreateTasks(batchText);
      setBatchText('');
      notifyCreated('batch');
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

  const wrapperClass = isMinimal ? 'space-y-2.5' : 'card space-y-3';

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
        <div className="rounded-2xl border border-[color:var(--accent)]/30 bg-[color:var(--surface)] px-4 py-3 text-sm text-[color:var(--accent)]">
          {error}
        </div>
      )}

      {(isMinimal || mode === 'single') ? (
        isMinimal ? (
          <div className="grid gap-2.5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <form onSubmit={handleSingleSubmit} className="flex gap-2.5">
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t.todayTaskPlaceholder}
                className="min-w-0 flex-1 rounded-[18px] border border-[color:var(--line-strong)] bg-white px-3.5 py-2.5 text-sm text-[color:var(--text)] outline-none transition-all"
              />
              <button
                type="submit"
                disabled={loading || !title.trim()}
                className="btn-primary shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading && activeSubmit === 'task' ? t.adding : t.addTask}
              </button>
            </form>

            <form onSubmit={handleIdeaSubmit} className="flex gap-2.5">
              <input
                type="text"
                value={ideaTitle}
                onChange={(event) => setIdeaTitle(event.target.value)}
                placeholder={t.ideaPlaceholder}
                className="min-w-0 flex-1 rounded-[18px] border border-[color:var(--line-strong)] bg-[color:var(--surface-muted)] px-3.5 py-2.5 text-sm text-[color:var(--text)] outline-none transition-all"
              />
              <button
                type="submit"
                disabled={loading || !ideaTitle.trim()}
                className="shrink-0 rounded-[18px] border border-[color:var(--line-strong)] bg-white px-3.5 py-2.5 text-sm font-medium text-[color:var(--text)] transition hover:bg-[color:var(--surface-muted)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading && activeSubmit === 'idea' ? t.adding : t.ideaAction}
              </button>
            </form>
          </div>
        ) : (
          <form onSubmit={handleSingleSubmit} className="space-y-3">
            <div className="flex flex-col gap-3 md:flex-row">
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t.taskPlaceholder}
                className="min-w-0 flex-1 rounded-[22px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none transition-all focus:border-[color:var(--accent)] focus:ring-2 focus:ring-[color:var(--accent-soft)]"
              />
              <button
                type="submit"
                disabled={loading || !title.trim()}
                className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading && activeSubmit === 'task' ? t.adding : t.addTask}
              </button>
            </div>

            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t.descPlaceholder}
              rows={2}
              className="w-full rounded-[22px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none transition-all focus:border-[color:var(--accent)] focus:ring-2 focus:ring-[color:var(--accent-soft)]"
            />

            <div className="grid gap-3 md:grid-cols-[1.2fr_0.8fr_0.8fr_0.8fr]">
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
                          : 'bg-[color:var(--surface)] text-[color:var(--muted)]'
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

              <label className="rounded-[22px] border border-[color:var(--line)] bg-white/65 p-4 text-sm text-[color:var(--muted)]">
                <span className="text-xs font-semibold uppercase tracking-[0.18em]">
                  {t.taskKindLabel || 'Type'}
                </span>
                <select
                  value={taskKind}
                  onChange={(event) => { setTaskKind(event.target.value); if (event.target.value !== 'weekly') setRecurrenceWeekday(''); }}
                  className="mt-3 w-full rounded-2xl border border-[color:var(--line)] bg-white px-3 py-2 text-sm text-[color:var(--text)] outline-none"
                >
                  <option value="temporary">{t.taskKindTemporary || 'Temporary'}</option>
                  <option value="daily">{t.taskKindDaily || 'Daily'}</option>
                  <option value="weekly">{t.taskKindWeekly || 'Weekly'}</option>
                </select>
                {taskKind === 'weekly' && (
                  <select
                    value={recurrenceWeekday}
                    onChange={(event) => setRecurrenceWeekday(event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-[color:var(--line)] bg-white px-3 py-2 text-sm text-[color:var(--text)] outline-none"
                  >
                    <option value="">{t.selectWeekday || 'Select day'}</option>
                    {(t.weekdays || ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']).map((day, i) => (
                      <option key={i} value={i}>{day}</option>
                    ))}
                  </select>
                )}
              </label>
            </div>
          </form>
        )
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
            {loading && activeSubmit === 'batch' ? t.adding : t.addAllTasks}
          </button>
        </form>
      )}
    </div>
  );
}

export default TaskInput;
