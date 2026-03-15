import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ROUTE_CONSTANTS } from '../constants/RouteConstants';
import { useLanguage } from '../i18n/LanguageContext';
import { useSession } from './SessionContext';
import BrandMark from './BrandMark';

function MainNavbar() {
  const location = useLocation();
  const { lang, toggleLang, t } = useLanguage();
  const { session, logout } = useSession();

  const navItems = [
    { path: ROUTE_CONSTANTS.TODAY, label: t.navToday },
    { path: ROUTE_CONSTANTS.REVIEW, label: t.navReview },
  ];

  const isActive = (path) =>
    location.pathname === path || (path === ROUTE_CONSTANTS.TODAY && location.pathname === '/');

  return (
    <nav className="sticky top-0 z-50 px-4 pt-3">
      <div className="site-shell mx-auto flex max-w-[1360px] items-center justify-between px-5 py-3">
        <div className="flex items-center gap-4">
          <Link to={ROUTE_CONSTANTS.TODAY}>
            <BrandMark size="md" />
          </Link>
          <div className="hidden md:block">
            <div className="panel-label">Daymark // Operations Board</div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`rounded-[16px] px-3 py-2 text-sm transition-all ${
                isActive(item.path)
                  ? 'border border-[color:var(--line-strong)] bg-black font-medium text-white'
                  : 'border border-transparent text-[color:var(--muted)] hover:border-[color:var(--line)] hover:bg-white/75 hover:text-[color:var(--text)]'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {session?.display_name && (
            <span className="hidden font-[var(--mono)] text-[11px] uppercase tracking-[0.18em] text-[color:var(--muted)] md:inline">
              {session.display_name}
            </span>
          )}
          <Link
            to={ROUTE_CONSTANTS.SETTINGS}
            className="btn-ghost !rounded-[16px] !px-3 !py-2"
          >
            {t.navSettings}
          </Link>
          <button onClick={logout} className="btn-ghost !rounded-[16px] !px-3 !py-2">
            {t.logoutAction}
          </button>
          <button onClick={toggleLang} className="btn-ghost !rounded-[16px] !px-3 !py-2 font-[var(--mono)]">
            {lang === 'en' ? '中文' : 'EN'}
          </button>
        </div>
      </div>
    </nav>
  );
}

export default MainNavbar;
