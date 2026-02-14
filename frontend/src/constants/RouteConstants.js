export const ROUTE_CONSTANTS = {
  HOME: '/',
  INBOX: '/inbox',
  TODAY: '/today',
  REVIEW: '/review',
  INSIGHTS: '/insights',
  SETTINGS: '/settings',
  PLAN: '/plan',
  HISTORY: '/history',
  STATS: '/stats',
};

export const API_ENDPOINTS = {
  BASE_URL: process.env.REACT_APP_API_ENDPOINT || 'http://localhost:5000',
  HEALTH: '/health',
  TASKS: '/api/tasks',
  TASKS_BATCH: '/api/tasks/batch',
  PLANS_GENERATE: '/api/plans/generate',
  PLANS_TODAY: '/api/plans/today',
  FEEDBACK: '/api/feedback',
  HISTORY: '/api/history',
  STATS: '/api/stats',
};
