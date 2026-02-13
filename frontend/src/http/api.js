import { API_ENDPOINTS } from '../constants/RouteConstants';

const API_BASE_URL = API_ENDPOINTS.BASE_URL;

// ── Generic fetch helper ────────────────────────────────────
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  };

  const response = await fetch(url, config);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

// ── Task APIs ───────────────────────────────────────────────
export async function getTasks(status = 'active') {
  return apiRequest(`/api/tasks?status=${status}`);
}

export async function createTask(title, description = '', priority = 0) {
  return apiRequest('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({ title, description, priority }),
  });
}

export async function batchCreateTasks(text) {
  return apiRequest('/api/tasks/batch', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function updateTask(taskId, updates) {
  return apiRequest(`/api/tasks/${taskId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export async function deleteTask(taskId) {
  return apiRequest(`/api/tasks/${taskId}`, {
    method: 'DELETE',
  });
}

// ── Plan APIs ───────────────────────────────────────────────
export async function generatePlan(date = null, lang = 'en') {
  const body = {};
  if (date) body.date = date;
  body.lang = lang;
  return apiRequest('/api/plans/generate', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getTodayPlan(lang = 'en') {
  return apiRequest(`/api/plans/today?lang=${lang}`);
}

// ── Feedback APIs ───────────────────────────────────────────
export async function submitFeedback(date, results, lang = 'en') {
  return apiRequest('/api/feedback', {
    method: 'POST',
    body: JSON.stringify({ date, results, lang }),
  });
}

// ── Stats & History APIs ────────────────────────────────────
export async function getHistory(taskId = null, limit = 50) {
  let url = `/api/history?limit=${limit}`;
  if (taskId) url += `&task_id=${taskId}`;
  return apiRequest(url);
}

export async function getStats() {
  return apiRequest('/api/stats');
}

export async function checkHealth() {
  return apiRequest('/health');
}
