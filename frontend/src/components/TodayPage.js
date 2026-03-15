import React, { useCallback, useEffect, useState } from 'react';
import DailyPlan from './DailyPlan';
import TaskInput from './TaskInput';
import MoodCheckIn from './MoodCheckIn';
import SongRecommendation from './SongRecommendation';
import DailyFortune from './DailyFortune';
import { useLanguage } from '../i18n/LanguageContext';

const INSPIRATION_STORAGE_KEY = 'dp_inspiration_orbs_v1';

function TodayPage() {
  const { t } = useLanguage();
  const [planRefreshSignal, setPlanRefreshSignal] = useState(0);
  const [taskRefreshSignal, setTaskRefreshSignal] = useState(0);
  const [musicContextSignal, setMusicContextSignal] = useState(0);
  const [inspirations, setInspirations] = useState(() => {
    try {
      const stored = window.localStorage.getItem(INSPIRATION_STORAGE_KEY);
      const parsed = stored ? JSON.parse(stored) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });
  const notifyMusicContextChange = useCallback(() => {
    setMusicContextSignal((value) => value + 1);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(INSPIRATION_STORAGE_KEY, JSON.stringify(inspirations));
    } catch {}
  }, [inspirations]);

  useEffect(() => {
    const handleAssistantUpdated = () => {
      setPlanRefreshSignal((value) => value + 1);
      setTaskRefreshSignal((value) => value + 1);
      setMusicContextSignal((value) => value + 1);
    };
    window.addEventListener('dp-assistant-updated', handleAssistantUpdated);
    return () => window.removeEventListener('dp-assistant-updated', handleAssistantUpdated);
  }, []);

  const handleIdeaCreated = useCallback((text) => {
    setInspirations((current) => [
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        text,
        createdAt: new Date().toISOString(),
      },
      ...current,
    ].slice(0, 24));
  }, []);

  const handleIdeaDismiss = useCallback((ideaId) => {
    setInspirations((current) => current.filter((idea) => idea.id !== ideaId));
  }, []);

  return (
    <div className="space-y-4">
      <section className="board-card px-5 py-5">
        <div className="panel-label">Daymark // Today Board</div>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[40px] leading-none text-[color:var(--text)]">{t.todayTitle}</h1>
            <p className="mt-2 text-sm text-[color:var(--muted)]">{t.todaySubtitle}</p>
          </div>
          <div className="hidden font-[var(--mono)] text-[11px] uppercase tracking-[0.18em] text-[color:var(--muted)] md:block">
            Live task board / review trail / assistant actions
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px] xl:items-start">
        <div className="space-y-3">
          <section className="board-card px-4 py-3">
            <TaskInput
              variant="minimal"
              onTaskCreated={() => {
                setTaskRefreshSignal((value) => value + 1);
              }}
              onIdeaCreated={handleIdeaCreated}
            />
          </section>

          <DailyPlan
            planRefreshSignal={planRefreshSignal}
            taskRefreshSignal={taskRefreshSignal}
            onPlanUpdated={notifyMusicContextChange}
            inspirations={inspirations}
            onDismissInspiration={handleIdeaDismiss}
          />

          <MoodCheckIn refreshSignal={taskRefreshSignal + planRefreshSignal} onMoodLogged={notifyMusicContextChange} />

          <DailyFortune />
        </div>

        <aside className="order-first xl:order-last xl:sticky xl:top-24 xl:self-start">
          <SongRecommendation contextSignal={musicContextSignal} />
        </aside>
      </div>
    </div>
  );
}

export default TodayPage;
