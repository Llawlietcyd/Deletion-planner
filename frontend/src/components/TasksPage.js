import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { getTasks } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import TaskInput from './TaskInput';
import TaskList from './TaskList';

function TasksPage({ hideHeader = false }) {
  const { t } = useLanguage();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('active');
  const [searchQuery, setSearchQuery] = useState('');

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getTasks(filter, searchQuery);
      setTasks(data || []);
    } catch (err) {
      console.error(err);
      setTasks([]);
    }
    setLoading(false);
  }, [filter, searchQuery]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const filters = useMemo(
    () => [
      { value: 'active', label: t.filterActive },
      { value: 'completed', label: t.filterCompleted },
      { value: 'deleted', label: t.filterDeleted },
    ],
    [t]
  );

  return (
    <div className="space-y-4">
      {!hideHeader && (
        <section className="px-1">
          <h1 className="text-3xl text-[color:var(--text)]">{t.tasksTitle}</h1>
          <p className="mt-2 text-sm text-[color:var(--muted)]">{t.tasksSubtitle}</p>
        </section>
      )}

      <TaskInput onTaskCreated={loadTasks} />

      <section className="card space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2">
            {filters.map((item) => (
              <button
                key={item.value}
                onClick={() => setFilter(item.value)}
                className={`rounded-full px-3 py-1.5 text-sm ${
                  filter === item.value
                    ? 'bg-[color:var(--accent-soft)] text-[color:var(--accent)]'
                    : 'bg-white/60 text-[color:var(--muted)]'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <input
            type="text"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={t.searchPlaceholder}
            className="w-full rounded-full border border-[color:var(--line)] bg-white/80 px-4 py-2 text-sm text-[color:var(--text)] outline-none md:max-w-xs"
          />
        </div>

        {!loading && <p className="text-sm text-[color:var(--muted)]">{t.taskCount(tasks.length)}</p>}

        {loading ? (
          <div className="rounded-[20px] border border-dashed border-[color:var(--line)] px-4 py-10 text-center text-sm text-[color:var(--muted)]">
            {t.loadingTasks}
          </div>
        ) : (
          <TaskList tasks={tasks} onRefresh={loadTasks} filter={filter} />
        )}
      </section>
    </div>
  );
}

export default TasksPage;
