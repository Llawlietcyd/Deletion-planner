import React from 'react';
import { Routes, Route } from 'react-router-dom';
import MainNavbar from './components/MainNavbar';
import TasksPage from './components/TasksPage';
import DailyPlan from './components/DailyPlan';
import HistoryPanel from './components/HistoryPanel';
import StatsPanel from './components/StatsPanel';
import { ROUTE_CONSTANTS } from './constants/RouteConstants';

function Dashboard() {
  return (
    <div className="min-h-screen bg-slate-50">
      <MainNavbar />
      <main className="max-w-3xl mx-auto px-4 py-8">
        <Routes>
          <Route path={ROUTE_CONSTANTS.HOME} element={<TasksPage />} />
          <Route path={ROUTE_CONSTANTS.PLAN} element={<DailyPlan />} />
          <Route path={ROUTE_CONSTANTS.HISTORY} element={<HistoryPanel />} />
          <Route path={ROUTE_CONSTANTS.STATS} element={<StatsPanel />} />
        </Routes>
      </main>
    </div>
  );
}

export default Dashboard;
