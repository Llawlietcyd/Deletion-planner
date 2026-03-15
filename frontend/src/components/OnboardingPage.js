import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ROUTE_CONSTANTS } from '../constants/RouteConstants';
import { useLanguage } from '../i18n/LanguageContext';
import { useSession } from './SessionContext';

function OnboardingPage() {
  const navigate = useNavigate();
  const { session, completeOnboarding, logout } = useSession();
  const { lang, t } = useLanguage();
  const [commitments, setCommitments] = useState('');
  const [goals, setGoals] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await completeOnboarding({
        brain_dump: '',
        commitments,
        goals,
        daily_capacity: Number(session?.daily_capacity || 6),
        lang,
      });
      navigate(ROUTE_CONSTANTS.TODAY);
    } catch (err) {
      setError(err.message);
    }
    setSubmitting(false);
  };

  const handleBack = async () => {
    setError('');
    await logout();
    navigate('/');
  };

  const canSubmit = commitments.trim() || goals.trim();

  return (
    <main className="mx-auto flex min-h-screen max-w-5xl items-center px-4 py-10">
      <section className="card w-full animate-slide-up">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[color:var(--muted)]">
            {t.onboardingEyebrow}
          </p>
          <button onClick={handleBack} className="btn-ghost !px-3 !py-2">
            {t.backToLogin}
          </button>
        </div>
        <h1 className="mt-3 text-4xl text-[color:var(--text)]">
          {t.onboardingTitle(session?.display_name || t.onboardingFallbackName)}
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-[color:var(--muted)]">
          {t.onboardingSubtitle}
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <div className="grid gap-5 md:grid-cols-2">
            <label className="space-y-2 text-sm text-[color:var(--muted)]">
              <span>{t.onboardingCommitments}</span>
              <textarea
                value={commitments}
                onChange={(event) => setCommitments(event.target.value)}
                rows={7}
                placeholder={t.onboardingCommitmentsPlaceholder}
                className="w-full rounded-[22px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none"
              />
            </label>

            <label className="space-y-2 text-sm text-[color:var(--muted)]">
              <span>{t.onboardingGoals}</span>
              <textarea
                value={goals}
                onChange={(event) => setGoals(event.target.value)}
                rows={7}
                placeholder={t.onboardingGoalsPlaceholder}
                className="w-full rounded-[22px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none"
              />
            </label>
          </div>

          {error && (
            <div className="rounded-[18px] border border-[color:var(--accent)]/30 bg-[color:var(--surface)] px-4 py-3 text-sm text-[color:var(--accent)]">
              {error}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={submitting || !canSubmit}
              className="btn-primary disabled:opacity-50"
            >
              {submitting ? t.onboardingLoading : t.onboardingAction}
            </button>
            <p className="text-sm text-[color:var(--muted)]">{t.onboardingHint}</p>
          </div>
        </form>
      </section>
    </main>
  );
}

export default OnboardingPage;
