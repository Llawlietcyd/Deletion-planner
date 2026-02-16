import React, { useState } from 'react';
import { createTask, batchCreateTasks } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

const PRIORITY_OPTIONS = [
  { value: 0, color: 'bg-slate-200 text-slate-600' },
  { value: 1, color: 'bg-blue-100 text-blue-700' },
  { value: 3, color: 'bg-amber-100 text-amber-700' },
  { value: 5, color: 'bg-red-100 text-red-700' },
];

function TaskInput({ onTaskCreated, variant = 'default' }) {
  const { t } = useLanguage();
  const isMinimal = variant === 'minimal';
  const [mode, setMode] = useState('single');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(0);
  const [category, setCategory] = useState('unclassified');
  const [batchText, setBatchText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const priorityLabels = [t.priorityLow, t.priorityMedium, t.priorityHigh, t.priorityUrgent];

  const handleSingleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    setLoading(true);
    setError('');
    try {
      await createTask(title, description, priority, category);
      setTitle('');
      setDescription('');
      setPriority(0);
      setCategory('unclassified');
      onTaskCreated();
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleBatchSubmit = async (e) => {
    e.preventDefault();
    if (!batchText.trim()) return;

    setLoading(true);
    setError('');
    try {
      await batchCreateTasks(batchText);
      setBatchText('');
      onTaskCreated();
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const CATEGORY_OPTIONS = [
    { value: 'unclassified', label: t.catUnclassified },
    { value: 'core', label: t.catCore },
    { value: 'deferrable', label: t.catDeferrable },
    { value: 'deletion_candidate', label: t.catDeletion },
  ];

  return (
    <div className="card">
      {!isMinimal && (
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-800">{t.addTasks}</h2>
          <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
            <button
              onClick={() => setMode('single')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                mode === 'single'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500'
              }`}
            >
              {t.singleMode}
            </button>
            <button
              onClick={() => setMode('batch')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                mode === 'batch'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500'
              }`}
            >
              {t.batchMode}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-3 text-sm text-red-600 bg-red-50 p-2 rounded-lg">
          {error}
        </div>
      )}

      {(isMinimal || mode === 'single') ? (
        <form onSubmit={handleSingleSubmit} className="space-y-3">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={isMinimal ? t.todayQuickAddPlaceholder : t.taskPlaceholder}
              className="w-full px-4 py-3 rounded-2xl bg-white shadow-[0_2px_10px_rgba(0,0,0,0.04)] focus:outline-none focus:ring-2 focus:ring-[#007AFF]/30"
            />
            <button
              type="submit"
              disabled={loading || !title.trim()}
              className="btn-primary !rounded-2xl !px-4 disabled:opacity-50"
            >
              {loading ? t.adding : t.addTask}
            </button>
          </div>

          {!isMinimal && (
            <>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t.descPlaceholder}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand text-sm"
              />
              {/* Priority Selector */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-500">{t.priorityLabel}:</span>
                <div className="flex gap-1">
                  {PRIORITY_OPTIONS.map((opt, i) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setPriority(opt.value)}
                      className={`px-3 py-1 text-xs font-medium rounded-full transition-all ${
                        priority === opt.value
                          ? `${opt.color} ring-2 ring-offset-1 ring-brand/30`
                          : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                      }`}
                    >
                      {priorityLabels[i]}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-500">{t.categoryLabel}:</span>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand/30"
                >
                  {CATEGORY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
        </form>
      ) : (
        <form onSubmit={handleBatchSubmit} className="space-y-3">
          <textarea
            value={batchText}
            onChange={(e) => setBatchText(e.target.value)}
            placeholder={t.batchPlaceholder}
            rows={5}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand text-sm"
          />
          <button
            type="submit"
            disabled={loading || !batchText.trim()}
            className="btn-primary w-full disabled:opacity-50"
          >
            {loading ? t.adding : t.addAllTasks}
          </button>
        </form>
      )}
    </div>
  );
}

export default TaskInput;
