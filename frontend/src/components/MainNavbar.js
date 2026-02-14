import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ROUTE_CONSTANTS } from '../constants/RouteConstants';
import { useLanguage } from '../i18n/LanguageContext';

function MainNavbar() {
  const location = useLocation();
  const { lang, toggleLang, t } = useLanguage();

  const NAV_ITEMS = [
    { path: ROUTE_CONSTANTS.INBOX, label: t.navInbox },
    { path: ROUTE_CONSTANTS.TODAY, label: t.navToday },
    { path: ROUTE_CONSTANTS.REVIEW, label: t.navReview },
    { path: ROUTE_CONSTANTS.INSIGHTS, label: t.navInsights },
    { path: ROUTE_CONSTANTS.SETTINGS, label: t.navSettings },
  ];

  return (
    <nav className="bg-white/70 backdrop-blur-md border-b border-slate-200/70 sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to={ROUTE_CONSTANTS.INBOX} className="flex items-center gap-2">
            <span className="text-2xl">🎯</span>
            <span className="text-lg font-bold text-slate-800">
              {t.appName}
            </span>
          </Link>

          {/* Nav Links + Lang Toggle */}
          <div className="flex items-center gap-1 bg-white/70 border border-slate-200/70 rounded-2xl p-1">
            {NAV_ITEMS.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-slate-900 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100/80'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}

            {/* Language Toggle */}
            <button
              onClick={toggleLang}
              className="ml-1 px-2.5 py-1.5 text-xs font-semibold rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-100/80 transition-colors"
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
