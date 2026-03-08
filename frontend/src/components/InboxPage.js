import React from 'react';
import TasksPage from './TasksPage';
import { useLanguage } from '../i18n/LanguageContext';

function InboxPage() {
  const { t } = useLanguage();

  return (
    <div className="space-y-4">
      <section className="px-1">
        <h1 className="text-3xl text-[color:var(--text)]">{t.inboxTitle}</h1>
        <p className="mt-2 text-sm text-[color:var(--muted)]">{t.inboxSubtitle}</p>
      </section>
      <TasksPage hideHeader />
    </div>
  );
}

export default InboxPage;
