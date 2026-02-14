import React, { useEffect, useState } from 'react';
import { getTodayPlan } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import DeletionSuggestion from './DeletionSuggestion';
import HistoryPanel from './HistoryPanel';

function ReviewPage() {
  const { lang, t } = useLanguage();
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const plan = await getTodayPlan(lang);
        if (mounted) {
          setSuggestions(plan.deletion_suggestions || []);
        }
      } catch {
        if (mounted) {
          setSuggestions([]);
        }
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, [lang]);

  return (
    <div className="space-y-4">
      <div className="card !bg-amber-50 !border-amber-200">
        <h1 className="text-xl font-semibold text-slate-800">{t.reviewTitle}</h1>
        <p className="text-sm text-slate-600 mt-1">{t.reviewSubtitle}</p>
      </div>
      {suggestions.length > 0 && (
        <DeletionSuggestion
          suggestions={suggestions}
          onSuggestionDeleted={(taskId) => {
            setSuggestions((prev) => prev.filter((s) => s.id !== taskId));
          }}
          onDismiss={() => setSuggestions([])}
        />
      )}
      <HistoryPanel hideHeader />
    </div>
  );
}

export default ReviewPage;
