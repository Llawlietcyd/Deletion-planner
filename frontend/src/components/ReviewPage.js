import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getTodayPlan } from '../http/api';
import { ROUTE_CONSTANTS } from '../constants/RouteConstants';
import { useLanguage } from '../i18n/LanguageContext';
import HistoryPanel from './HistoryPanel';

function ReviewPage() {
  const { lang, t } = useLanguage();
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    let mounted = true;
    async function loadPlan() {
      try {
        const cached = window.localStorage.getItem('planning_capacity_units');
        const parsed = Number(cached);
        const capacityUnits = Number.isFinite(parsed) && parsed > 0 ? parsed : 6;
        const plan = await getTodayPlan(lang, capacityUnits);
        if (mounted) {
          setSuggestions(plan.deletion_suggestions || []);
        }
      } catch {
        if (mounted) {
          setSuggestions([]);
        }
      }
    }

    loadPlan();
    return () => {
      mounted = false;
    };
  }, [lang]);

  return (
    <div className="space-y-4">
      <section className="px-1">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl text-[color:var(--text)]">{t.reviewTitle}</h1>
            <p className="mt-2 text-sm text-[color:var(--muted)]">{t.reviewSubtitle}</p>
          </div>
          <Link to={ROUTE_CONSTANTS.SETTINGS} className="btn-ghost">
            {t.navSettings}
          </Link>
        </div>
      </section>

      {suggestions.length > 0 && (
        <section className="card py-4">
          <p className="text-sm font-medium text-[color:var(--text)]">{suggestions[0].title}</p>
          <p className="mt-1 text-sm text-[color:var(--muted)]">{suggestions[0].deletion_reasoning}</p>
        </section>
      )}

      <HistoryPanel hideHeader />
    </div>
  );
}

export default ReviewPage;
