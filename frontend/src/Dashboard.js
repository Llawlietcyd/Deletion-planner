import React from 'react';
import { Routes, Route } from 'react-router-dom';
import MainNavbar from './components/MainNavbar';
import InboxPage from './components/InboxPage';
import TodayPage from './components/TodayPage';
import ReviewPage from './components/ReviewPage';
import InsightsPage from './components/InsightsPage';
import SettingsPage from './components/SettingsPage';
import ConciergeChatbox from './components/ConciergeChatbox';
import { ROUTE_CONSTANTS } from './constants/RouteConstants';

function Dashboard() {
  return (
    <div className="min-h-screen transition-colors">
      <MainNavbar />
      <main className="mx-auto max-w-[1360px] px-4 pb-8 pt-4">
        <div className="site-shell px-6 pb-8 pt-6 md:px-8">
          <Routes>
            <Route path={ROUTE_CONSTANTS.HOME} element={<TodayPage />} />
            <Route path={ROUTE_CONSTANTS.INBOX} element={<InboxPage />} />
            <Route path={ROUTE_CONSTANTS.TODAY} element={<TodayPage />} />
            <Route path={ROUTE_CONSTANTS.REVIEW} element={<ReviewPage />} />
            <Route path={ROUTE_CONSTANTS.INSIGHTS} element={<InsightsPage />} />
            <Route path={ROUTE_CONSTANTS.SETTINGS} element={<SettingsPage />} />
          </Routes>
        </div>
      </main>
      <ConciergeChatbox />
    </div>
  );
}

export default Dashboard;
