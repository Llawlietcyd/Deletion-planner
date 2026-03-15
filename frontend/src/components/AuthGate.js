import React from 'react';
import Dashboard from '../Dashboard';
import { useLanguage } from '../i18n/LanguageContext';
import LoginPage from './LoginPage';
import OnboardingPage from './OnboardingPage';
import { useSession } from './SessionContext';

function AuthGate() {
  const { t } = useLanguage();
  const { session, loading } = useSession();

  if (loading) {
    return (
      <main className="mx-auto flex min-h-screen max-w-4xl items-center justify-center px-4">
        <div className="card text-center">
          <p className="text-sm text-[color:var(--muted)]">{t.authLoading}</p>
        </div>
      </main>
    );
  }

  if (!session?.logged_in) {
    return <LoginPage />;
  }

  if (!session?.onboarding_completed) {
    return <OnboardingPage />;
  }

  return <Dashboard />;
}

export default AuthGate;
