import React from 'react';
import TasksPage from './TasksPage';
import { useLanguage } from '../i18n/LanguageContext';

function InboxPage() {
  const { t } = useLanguage();

  return (
    <div className="space-y-4">
      <div className="card !bg-brand/5 !border-brand/20">
        <h1 className="text-xl font-semibold text-slate-800">{t.inboxTitle}</h1>
        <p className="text-sm text-slate-600 mt-1">{t.inboxSubtitle}</p>
      </div>
      <TasksPage hideHeader />
    </div>
  );
}

export default InboxPage;
