import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ROUTE_CONSTANTS } from '../constants/RouteConstants';
import { useLanguage } from '../i18n/LanguageContext';

function MainNavbar() {
  const location = useLocation();
  const { lang, toggleLang, t } = useLanguage();

  const NAV_ITEMS = [
    { path: ROUTE_CONSTANTS.HOME, label: t.navTasks },
    { path: ROUTE_CONSTANTS.PLAN, label: t.navPlan },
    { path: ROUTE_CONSTANTS.HISTORY, label: t.navHistory },
    { path: ROUTE_CONSTANTS.STATS, label: t.navStats },
  ];

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2">
            <span className="text-2xl">🎯</span>
            <span className="text-lg font-bold text-slate-800">
              {t.appName}
            </span>
          </Link>

          {/* Nav Links + Lang Toggle */}
          <div className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand/10 text-brand'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}

            {/* Language Toggle */}
            <button
              onClick={toggleLang}
              className="ml-2 px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 transition-colors"
              title={lang === 'en' ? 'Switch to Chinese' : '切换到英文'}
            >
              {lang === 'en' ? '中文' : 'EN'}
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}

export default MainNavbar;
