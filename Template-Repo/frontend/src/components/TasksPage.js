import React, { useState, useEffect, useCallback } from 'react';
import { getTasks } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import TaskInput from './TaskInput';
import TaskList from './TaskList';

function TasksPage() {
  const { t } = useLanguage();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('active');

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTasks(filter);
      setTasks(data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  }, [filter]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const FILTERS = [
    { value: 'active', label: t.filterActive },
    { value: 'completed', label: t.filterCompleted },
    { value: 'deleted', label: t.filterDeleted },
    { value: 'all', label: t.filterAll },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">{t.tasksTitle}</h1>
        <p className="text-slate-500 text-sm">{t.tasksSubtitle}</p>
      </div>

      <TaskInput onTaskCreated={loadTasks} />

      <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5 w-fit">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filter === f.value
                ? 'bg-white text-slate-800 shadow-sm font-medium'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {!loading && (
        <p className="text-sm text-slate-400">{t.taskCount(tasks.length)}</p>
      )}

      {loading ? (
        <div className="card text-center py-10">
          <p className="text-slate-400">{t.loadingTasks}</p>
        </div>
      ) : (
        <TaskList
          tasks={tasks}
          onRefresh={loadTasks}
          showActions={filter === 'active'}
        />
      )}
    </div>
  );
}

export default TasksPage;
