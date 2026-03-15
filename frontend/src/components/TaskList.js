import React, { useEffect, useMemo, useState } from 'react';
import { deleteTask, reorderTasks, updateTask } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import { useToast } from './ToastContext';

const PRIORITY_DOT = {
  0: 'bg-slate-300',
  1: 'bg-sky-400',
  3: 'bg-amber-400',
  5: 'bg-red-500',
};

function recurringKindLabel(task, lang, fallback) {
  if ((task?.task_kind || 'temporary') !== 'weekly') return fallback;
  const weekday = Number(task?.recurrence_weekday);
  if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6) return fallback;
  const zh = ['每周一', '每周二', '每周三', '每周四', '每周五', '每周六', '每周日'];
  const en = ['Every Mon', 'Every Tue', 'Every Wed', 'Every Thu', 'Every Fri', 'Every Sat', 'Every Sun'];
  return (lang === 'zh' ? zh : en)[weekday];
}

const PRIORITY_OPTIONS = [
  { value: 0, labelKey: 'priorityLow' },
  { value: 1, labelKey: 'priorityMedium' },
  { value: 3, labelKey: 'priorityHigh' },
  { value: 5, labelKey: 'priorityUrgent' },
];

function TaskList({ tasks, onRefresh, filter = 'active' }) {
  const { t, lang } = useLanguage();
  const { showToast } = useToast();
  const [orderedTasks, setOrderedTasks] = useState(tasks || []);
  const [draggedTaskId, setDraggedTaskId] = useState(null);
  const [dropTargetTaskId, setDropTargetTaskId] = useState(null);
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [editForm, setEditForm] = useState({
    title: '',
    description: '',
    priority: 0,
    category: 'unclassified',
    task_kind: 'temporary',
    due_date: '',
  });

  useEffect(() => {
    setOrderedTasks(tasks || []);
  }, [tasks]);

  const isDragEnabled = useMemo(() => filter === 'active', [filter]);

  const categoryBadge = {
    core: 'badge-core',
    deferrable: 'badge-deferrable',
    deletion_candidate: 'badge-deletion',
    unclassified: 'inline-flex items-center rounded-full bg-[color:var(--surface)] px-2.5 py-1 text-xs font-semibold text-[color:var(--muted)]',
  };

  const categoryLabel = {
    core: t.catCore,
    deferrable: t.catDeferrable,
    deletion_candidate: t.catDeletion,
    unclassified: t.catUnclassified,
  };
  const kindBadge = {
    daily: 'inline-flex items-center rounded-full bg-[color:var(--surface)] px-2.5 py-1 text-xs font-semibold text-[color:var(--text)]',
    weekly: 'inline-flex items-center rounded-full bg-[color:var(--surface)] px-2.5 py-1 text-xs font-semibold text-[color:var(--text)]',
    temporary: 'inline-flex items-center rounded-full bg-[color:var(--surface)] px-2.5 py-1 text-xs font-semibold text-[color:var(--muted)]',
  };
  const kindLabel = {
    daily: t.taskKindDaily,
    weekly: t.taskKindWeekly,
    temporary: t.taskKindTemporary,
  };

  const priorityLabel = {
    0: t.priorityLow,
    1: t.priorityMedium,
    3: t.priorityHigh,
    5: t.priorityUrgent,
  };
  const isSystemMetaDescription = (text) =>
    typeof text === 'string' && /^Imported from .* onboarding\.$/.test(text.trim());

  const handleDelete = async (taskId, hard = false) => {
    if (hard) {
      if (!window.confirm(t.permanentDeleteConfirm)) {
        return;
      }
      try {
        await deleteTask(taskId, true);
        onRefresh();
      } catch (err) {
        showToast(err.message);
      }
      return;
    }

    try {
      await deleteTask(taskId, false);
      onRefresh();
      showToast(t.taskDeleted, async () => {
        await updateTask(taskId, { status: 'active' });
        onRefresh();
      });
    } catch (err) {
      showToast(err.message);
    }
  };

  const handleComplete = async (taskId) => {
    try {
      await updateTask(taskId, { status: 'completed' });
      onRefresh();
      showToast(t.taskCompleted, async () => {
        await updateTask(taskId, { status: 'active' });
        onRefresh();
      });
    } catch (err) {
      showToast(err.message);
    }
  };

  const handleRestore = async (taskId) => {
    try {
      await updateTask(taskId, { status: 'active' });
      onRefresh();
      showToast(t.taskRestored);
    } catch (err) {
      showToast(err.message);
    }
  };

  const startEditing = (task) => {
    setEditingTaskId(task.id);
    setEditForm({
      title: task.title || '',
      description: task.description || '',
      priority: task.priority ?? 0,
      category: task.category || 'unclassified',
      task_kind: task.task_kind || 'temporary',
      due_date: task.due_date || '',
    });
  };

  const cancelEditing = () => {
    setEditingTaskId(null);
    setEditForm({
      title: '',
      description: '',
      priority: 0,
      category: 'unclassified',
      task_kind: 'temporary',
      due_date: '',
    });
  };

  const saveEditing = async () => {
    if (!editForm.title.trim()) {
      return;
    }

    try {
      await updateTask(editingTaskId, {
        title: editForm.title.trim(),
        description: editForm.description.trim(),
        priority: editForm.priority,
        category: editForm.category,
        task_kind: editForm.task_kind,
        due_date: editForm.due_date || null,
      });
      cancelEditing();
      onRefresh();
    } catch (err) {
      showToast(err.message);
    }
  };

  const handleDragStart = (taskId) => {
    if (!isDragEnabled) {
      return;
    }
    setDraggedTaskId(taskId);
  };

  const handleDragOver = (event, taskId) => {
    if (!isDragEnabled) {
      return;
    }
    event.preventDefault();
    setDropTargetTaskId(taskId);
  };

  const handleDrop = async (targetTaskId) => {
    if (!isDragEnabled || !draggedTaskId || draggedTaskId === targetTaskId) {
      setDraggedTaskId(null);
      setDropTargetTaskId(null);
      return;
    }

    const fromIndex = orderedTasks.findIndex((task) => task.id === draggedTaskId);
    const toIndex = orderedTasks.findIndex((task) => task.id === targetTaskId);
    if (fromIndex < 0 || toIndex < 0) {
      setDraggedTaskId(null);
      setDropTargetTaskId(null);
      return;
    }

    const next = [...orderedTasks];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    setOrderedTasks(next);
    setDraggedTaskId(null);
    setDropTargetTaskId(null);

    try {
      await reorderTasks(next.map((task) => task.id));
      onRefresh();
    } catch (err) {
      showToast(err.message);
      onRefresh();
    }
  };

  if (!tasks || tasks.length === 0) {
    return (
      <div className="rounded-[24px] border border-dashed border-[color:var(--line)] px-6 py-12 text-center">
        <p className="text-lg text-[color:var(--text)]">{t.noTasks}</p>
        <p className="mt-1 text-sm text-[color:var(--muted)]">{t.noTasksSub}</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {orderedTasks.map((task) => {
        const isEditing = editingTaskId === task.id;

        if (isEditing) {
          return (
            <div key={task.id} className="rounded-[24px] border border-[color:var(--line)] bg-white/75 p-4">
              <div className="space-y-3">
                <input
                  type="text"
                  value={editForm.title}
                  onChange={(event) => setEditForm((form) => ({ ...form, title: event.target.value }))}
                  className="w-full rounded-2xl border border-[color:var(--line)] bg-white px-4 py-2.5 text-sm text-[color:var(--text)] outline-none"
                  placeholder={t.taskPlaceholder}
                />
                <input
                  type="text"
                  value={editForm.description}
                  onChange={(event) => setEditForm((form) => ({ ...form, description: event.target.value }))}
                  className="w-full rounded-2xl border border-[color:var(--line)] bg-white px-4 py-2.5 text-sm text-[color:var(--text)] outline-none"
                  placeholder={t.descPlaceholder}
                />
                <div className="flex flex-wrap gap-2">
                  <select
                    value={editForm.priority}
                    onChange={(event) =>
                      setEditForm((form) => ({ ...form, priority: Number(event.target.value) }))
                    }
                    className="rounded-full border border-[color:var(--line)] bg-white px-3 py-2 text-sm text-[color:var(--text)]"
                  >
                    {PRIORITY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t[option.labelKey]}
                      </option>
                    ))}
                  </select>
                  <select
                    value={editForm.category}
                    onChange={(event) =>
                      setEditForm((form) => ({ ...form, category: event.target.value }))
                    }
                    className="rounded-full border border-[color:var(--line)] bg-white px-3 py-2 text-sm text-[color:var(--text)]"
                  >
                    <option value="unclassified">{t.catUnclassified}</option>
                    <option value="core">{t.catCore}</option>
                    <option value="deferrable">{t.catDeferrable}</option>
                    <option value="deletion_candidate">{t.catDeletion}</option>
                  </select>
                  <select
                    value={editForm.task_kind}
                    onChange={(event) =>
                      setEditForm((form) => ({ ...form, task_kind: event.target.value }))
                    }
                    className="rounded-full border border-[color:var(--line)] bg-white px-3 py-2 text-sm text-[color:var(--text)]"
                  >
                    <option value="temporary">{t.taskKindTemporary}</option>
                    <option value="daily">{t.taskKindDaily}</option>
                    <option value="weekly">{t.taskKindWeekly}</option>
                  </select>
                  <input
                    type="date"
                    value={editForm.due_date}
                    onChange={(event) =>
                      setEditForm((form) => ({ ...form, due_date: event.target.value }))
                    }
                    className="rounded-full border border-[color:var(--line)] bg-white px-3 py-2 text-sm text-[color:var(--text)]"
                  />
                  <div className="flex-1" />
                  <button onClick={saveEditing} className="btn-primary">
                    {t.saveBtn}
                  </button>
                  <button onClick={cancelEditing} className="btn-ghost">
                    {t.cancel}
                  </button>
                </div>
              </div>
            </div>
          );
        }

        const dueDateLabel =
          task.due_date &&
          (() => {
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const due = new Date(`${task.due_date}T00:00:00`);
            const diff = Math.ceil((due - today) / (1000 * 60 * 60 * 24));
            if (diff < 0) {
              return `${task.due_date} (${t.overdue})`;
            }
            if (diff === 0) {
              return `${task.due_date} (${t.dueToday})`;
            }
            return task.due_date;
          })();

        return (
          <div
            key={task.id}
            draggable={isDragEnabled}
            onDragStart={() => handleDragStart(task.id)}
            onDragOver={(event) => handleDragOver(event, task.id)}
            onDrop={() => handleDrop(task.id)}
            onDragEnd={() => {
              setDraggedTaskId(null);
              setDropTargetTaskId(null);
            }}
            className={`rounded-[24px] border border-[color:var(--line)] bg-white/70 p-4 transition-all ${
              isDragEnabled ? 'cursor-grab active:cursor-grabbing' : ''
            } ${dropTargetTaskId === task.id ? 'translate-y-[-2px] border-[color:var(--accent)]' : ''}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${PRIORITY_DOT[task.priority] || PRIORITY_DOT[0]}`} />
                  <span className="truncate text-base font-medium text-[color:var(--text)]">{task.title}</span>
                  <span className={categoryBadge[task.category] || categoryBadge.unclassified}>
                    {categoryLabel[task.category] || t.catUnclassified}
                  </span>
                  <span className={kindBadge[task.task_kind] || kindBadge.temporary}>
                    {recurringKindLabel(task, lang, kindLabel[task.task_kind] || t.taskKindTemporary)}
                  </span>
                  {task.priority >= 3 && (
                    <span className="inline-flex items-center rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[color:var(--muted)]">
                      {priorityLabel[task.priority]}
                    </span>
                  )}
                </div>

                {task.description && !isSystemMetaDescription(task.description) && (
                  <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">{task.description}</p>
                )}

                <div className="mt-3 flex flex-wrap gap-3 text-xs text-[color:var(--muted)]">
                  {dueDateLabel && <span>{dueDateLabel}</span>}
                  {task.deferral_count > 0 && <span>{t.deferred}: {task.deferral_count}x</span>}
                  {task.completion_count > 0 && <span>{t.completed}: {task.completion_count}x</span>}
                </div>
              </div>

              <div className="flex flex-wrap justify-end gap-2">
                {filter === 'active' && (
                  <>
                    <button onClick={() => startEditing(task)} className="btn-ghost">
                      {t.editBtn}
                    </button>
                    <button
                      onClick={() => handleComplete(task.id)}
                      className="btn-primary"
                    >
                      {t.btnDone}
                    </button>
                    <button onClick={() => handleDelete(task.id, false)} className="btn-ghost">
                      {t.deleteBtn}
                    </button>
                  </>
                )}
                {(filter === 'completed' || filter === 'deleted') && (
                  <button
                    onClick={() => handleRestore(task.id)}
                    className="btn-ghost"
                  >
                    {t.restoreBtn}
                  </button>
                )}
                {filter === 'deleted' && (
                  <button
                    onClick={() => handleDelete(task.id, true)}
                    className="rounded-full bg-[color:var(--accent)] px-4 py-2 text-sm font-medium text-white transition-all hover:opacity-80"
                  >
                    {t.permanentDeleteBtn}
                  </button>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default TaskList;
