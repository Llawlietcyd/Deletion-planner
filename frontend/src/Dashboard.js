import React from 'react';
import { Routes, Route } from 'react-router-dom';
import MainNavbar from './components/MainNavbar';
import InboxPage from './components/InboxPage';
import TodayPage from './components/TodayPage';
import ReviewPage from './components/ReviewPage';
import InsightsPage from './components/InsightsPage';
import SettingsPage from './components/SettingsPage';
import { ROUTE_CONSTANTS } from './constants/RouteConstants';

function Dashboard() {
  return (
    <div className="min-h-screen bg-slate-50">
      <MainNavbar />
      <main className="max-w-3xl mx-auto px-4 py-8">
        <Routes>
          <Route path={ROUTE_CONSTANTS.HOME} element={<InboxPage />} />
          <Route path={ROUTE_CONSTANTS.INBOX} element={<InboxPage />} />
          <Route path={ROUTE_CONSTANTS.TODAY} element={<TodayPage />} />
          <Route path={ROUTE_CONSTANTS.REVIEW} element={<ReviewPage />} />
          <Route path={ROUTE_CONSTANTS.INSIGHTS} element={<InsightsPage />} />
          <Route path={ROUTE_CONSTANTS.SETTINGS} element={<SettingsPage />} />
          <Route path={ROUTE_CONSTANTS.PLAN} element={<TodayPage />} />
          <Route path={ROUTE_CONSTANTS.HISTORY} element={<ReviewPage />} />
          <Route path={ROUTE_CONSTANTS.STATS} element={<InsightsPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default Dashboard;
