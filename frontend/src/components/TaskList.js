import React, { useEffect, useMemo, useState } from 'react';
import { deleteTask, reorderTasks, updateTask } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

const PRIORITY_DOT = {
  0: '', // low — no dot
  1: 'bg-blue-400',
  3: 'bg-amber-400',
  5: 'bg-red-500',
};

function TaskList({ tasks, onRefresh, filter = 'active' }) {
  const { t } = useLanguage();
  const [orderedTasks, setOrderedTasks] = useState(tasks || []);
  const [draggedTaskId, setDraggedTaskId] = useState(null);
  const [dropTargetTaskId, setDropTargetTaskId] = useState(null);

  useEffect(() => {
    setOrderedTasks(tasks || []);
  }, [tasks]);

  const isDragEnabled = useMemo(() => filter === 'active', [filter]);

  const CATEGORY_BADGE = {
    core: 'badge-core',
    deferrable: 'badge-deferrable',
    deletion_candidate: 'badge-deletion',
    unclassified: 'inline-block text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600',
  };

  const CATEGORY_LABEL = {
    core: t.catCore,
    deferrable: t.catDeferrable,
    deletion_candidate: t.catDeletion,
    unclassified: t.catUnclassified,
  };

  const PRIORITY_LABEL = {
    0: t.priorityLow,
    1: t.priorityMedium,
    3: t.priorityHigh,
    5: t.priorityUrgent,
  };

  const handleDelete = async (taskId, hard = false) => {
    const confirmMsg = hard ? t.permanentDeleteConfirm : t.deleteConfirm;
    if (!window.confirm(confirmMsg)) return;
    try {
      await deleteTask(taskId, hard);
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleComplete = async (taskId) => {
    if (!window.confirm(t.completeConfirm)) return;
    try {
      await updateTask(taskId, { status: 'completed' });
      onRefresh();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleDragStart = (taskId) => {
    if (!isDragEnabled) return;
    setDraggedTaskId(taskId);
  };

  const handleDragOver = (e, taskId) => {
    if (!isDragEnabled) return;
    e.preventDefault();
    setDropTargetTaskId(taskId);
  };

  const handleDrop = async (targetTaskId) => {
    if (!isDragEnabled || !draggedTaskId || draggedTaskId === targetTaskId) {
      setDraggedTaskId(null);
      setDropTargetTaskId(null);
      return;
    }

    const fromIdx = orderedTasks.findIndex((t) => t.id === draggedTaskId);
    const toIdx = orderedTasks.findIndex((t) => t.id === targetTaskId);
    if (fromIdx < 0 || toIdx < 0) {
      setDraggedTaskId(null);
      setDropTargetTaskId(null);
      return;
    }

    const next = [...orderedTasks];
    const [moved] = next.splice(fromIdx, 1);
    next.splice(toIdx, 0, moved);
    setOrderedTasks(next);
    setDraggedTaskId(null);
    setDropTargetTaskId(null);

    try {
      await reorderTasks(next.map((t) => t.id));
      onRefresh();
    } catch (err) {
      alert(err.message);
      onRefresh();
    }
  };

  if (!tasks || tasks.length === 0) {
    return (
      <div className="card text-center py-10">
        <p className="text-slate-400 text-lg">{t.noTasks}</p>
        <p className="text-slate-400 text-sm mt-1">{t.noTasksSub}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {orderedTasks.map((task) => {
        const dotColor = PRIORITY_DOT[task.priority] || '';
        return (
          <div
            key={task.id}
            draggable={isDragEnabled}
            onDragStart={() => handleDragStart(task.id)}
            onDragOver={(e) => handleDragOver(e, task.id)}
            onDrop={() => handleDrop(task.id)}
            onDragEnd={() => {
              setDraggedTaskId(null);
              setDropTargetTaskId(null);
            }}
            className={`card flex items-start justify-between gap-3 !p-4 transition-all ${
              isDragEnabled ? 'cursor-grab active:cursor-grabbing' : ''
            } ${
              dropTargetTaskId === task.id ? 'ring-2 ring-brand/30 -translate-y-0.5' : ''
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                {isDragEnabled && (
                  <span className="text-slate-300 text-sm select-none" title={t.dragToReorder}>
                    ⋮⋮
                  </span>
                )}
                {/* Priority dot */}
                {dotColor && (
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`}
                        title={PRIORITY_LABEL[task.priority] || ''} />
                )}
                <span className="font-medium text-slate-800 truncate">
                  {task.title}
                </span>
                <span className={CATEGORY_BADGE[task.category] || CATEGORY_BADGE.unclassified}>
                  {CATEGORY_LABEL[task.category] || t.catUnclassified}
                </span>
                {task.priority >= 3 && (
                  <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${
                    task.priority >= 5
                      ? 'bg-red-100 text-red-600'
                      : 'bg-amber-100 text-amber-600'
                  }`}>
                    {PRIORITY_LABEL[task.priority] || ''}
                  </span>
                )}
              </div>
              {task.description && (
                <p className="text-sm text-slate-500 truncate">{task.description}</p>
              )}
              <div className="flex gap-3 mt-1 text-xs text-slate-400">
                {task.deferral_count > 0 && (
                  <span>{t.deferred}: {task.deferral_count}x</span>
                )}
                {task.completion_count > 0 && (
                  <span>{t.completed}: {task.completion_count}x</span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1">
              {filter === 'active' && (
                <>
                  <button
                    onClick={() => handleComplete(task.id)}
                    className="text-xs px-2.5 py-1.5 rounded-md bg-green-100 text-green-700 hover:bg-green-200 font-medium"
                    title={t.markCompletedBtn}
                  >
                    {t.btnDone}
                  </button>
                  <button
                    onClick={() => handleDelete(task.id, false)}
                    className="text-xs px-2.5 py-1.5 rounded-md bg-slate-100 text-slate-600 hover:bg-slate-200 font-medium"
                    title={t.deleteBtn}
                  >
                    {t.deleteBtn}
                  </button>
                </>
              )}
              {filter === 'deleted' && (
                <button
                  onClick={() => handleDelete(task.id, true)}
                  className="text-xs px-2.5 py-1.5 rounded-md bg-red-100 text-red-700 hover:bg-red-200 font-medium"
                  title={t.permanentDeleteBtn}
                >
                  {t.permanentDeleteBtn}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default TaskList;
