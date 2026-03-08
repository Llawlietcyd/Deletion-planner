import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ROUTE_CONSTANTS } from '../constants/RouteConstants';
import { useLanguage } from '../i18n/LanguageContext';

function MainNavbar() {
  const location = useLocation();
  const { lang, toggleLang, t } = useLanguage();

  const navItems = [
    { path: ROUTE_CONSTANTS.TODAY, label: t.navToday },
    { path: ROUTE_CONSTANTS.INBOX, label: t.navInbox },
    { path: ROUTE_CONSTANTS.REVIEW, label: t.navReview },
  ];

  const isActive = (path) =>
    location.pathname === path || (path === ROUTE_CONSTANTS.TODAY && location.pathname === '/');

  return (
    <nav className="sticky top-0 z-50 px-4 pt-4">
      <div className="mx-auto flex max-w-4xl items-center justify-between rounded-[24px] border border-[color:var(--line)] bg-[color:var(--surface)] px-4 py-3 shadow-[0_12px_28px_rgba(49,32,18,0.08)] backdrop-blur">
        <Link to={ROUTE_CONSTANTS.TODAY} className="text-sm font-semibold text-[color:var(--text)]">
          {t.appName}
        </Link>

        <div className="flex items-center gap-1">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`rounded-full px-3 py-2 text-sm transition-all ${
                isActive(item.path)
                  ? 'bg-[color:var(--accent-soft)] font-medium text-[color:var(--accent)]'
                  : 'text-[color:var(--muted)] hover:bg-white/60 hover:text-[color:var(--text)]'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <Link
            to={ROUTE_CONSTANTS.SETTINGS}
            className="rounded-full px-3 py-2 text-sm text-[color:var(--muted)] transition-all hover:bg-white/60 hover:text-[color:var(--text)]"
          >
            {t.navSettings}
          </Link>
          <button onClick={toggleLang} className="btn-ghost !px-3 !py-2">
            {lang === 'en' ? '中文' : 'EN'}
          </button>
        </div>
      </div>
    </nav>
  );
}

export default MainNavbar;
