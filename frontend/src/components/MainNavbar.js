import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ROUTE_CONSTANTS } from '../constants/RouteConstants';
import { useLanguage } from '../i18n/LanguageContext';

function MainNavbar() {
  const location = useLocation();
  const { lang, toggleLang, t } = useLanguage();

  const NAV_ITEMS = [
    { path: ROUTE_CONSTANTS.TODAY, label: t.navToday },
    { path: ROUTE_CONSTANTS.REVIEW, label: t.navReview },
    { path: ROUTE_CONSTANTS.SETTINGS, label: t.navSettings },
  ];

  return (
    <nav className="bg-transparent sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to={ROUTE_CONSTANTS.TODAY} className="flex items-center gap-2">
            <span className="text-lg font-semibold tracking-tight text-slate-900">
              {t.appName}
            </span>
          </Link>

          {/* Nav Links + Lang Toggle */}
          <div className="flex items-center gap-1 bg-white/75 backdrop-blur-sm rounded-2xl p-1.5 shadow-[0_4px_18px_rgba(0,0,0,0.04)]">
            {NAV_ITEMS.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-[#007AFF]/10 text-[#007AFF]'
                      : 'text-slate-500 hover:bg-slate-100/80'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}

            {/* Language Toggle */}
            <button
              onClick={toggleLang}
              className="ml-1 px-2.5 py-1.5 text-xs font-semibold rounded-xl text-slate-500 hover:bg-slate-100/80 transition-colors"
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
