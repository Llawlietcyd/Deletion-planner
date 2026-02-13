import React from 'react';
import { deleteTask } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

const PRIORITY_DOT = {
  0: '', // low — no dot
  1: 'bg-blue-400',
  3: 'bg-amber-400',
  5: 'bg-red-500',
};

function TaskList({ tasks, onRefresh, showActions = true }) {
  const { t } = useLanguage();

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

  const handleDelete = async (taskId) => {
    if (!window.confirm(t.deleteConfirm)) return;
    try {
      await deleteTask(taskId);
      onRefresh();
    } catch (err) {
      alert(err.message);
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
      {tasks.map((task) => {
        const dotColor = PRIORITY_DOT[task.priority] || '';
        return (
          <div
            key={task.id}
            className="card flex items-start justify-between gap-3 !p-4"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
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

            {showActions && (
              <button
                onClick={() => handleDelete(task.id)}
                className="text-slate-400 hover:text-deletion transition-colors p-1"
                title={t.deleteBtn}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default TaskList;
