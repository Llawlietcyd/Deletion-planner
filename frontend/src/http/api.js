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

  let data;
  try {
    data = await response.json();
  } catch {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    return {};
  }

  if (!response.ok) {
    // Handle both v1 (data.error) and v2 (data.detail.message or data.message) error formats
    const message =
      (typeof data.detail === 'object' && data.detail?.message) ||
      (typeof data.detail === 'string' && data.detail) ||
      data.message ||
      data.error ||
      `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

// ── Task APIs ───────────────────────────────────────────────
export async function getTasks(status = 'active', query = '') {
  let url = `${API_ENDPOINTS.TASKS}?status=${status}`;
  if (query.trim()) url += `&q=${encodeURIComponent(query.trim())}`;
  return apiRequest(url);
}

export async function createTask(title, description = '', priority = 0, category = 'unclassified', dueDate = null) {
  const body = { title, description, priority, category };
  if (dueDate) body.due_date = dueDate;
  return apiRequest(API_ENDPOINTS.TASKS, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function batchCreateTasks(text) {
  return apiRequest(API_ENDPOINTS.TASKS_BATCH, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function updateTask(taskId, updates) {
  return apiRequest(`${API_ENDPOINTS.TASKS}/${taskId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export async function reorderTasks(orderedTaskIds) {
  return apiRequest(`${API_ENDPOINTS.TASKS}/reorder`, {
    method: 'PUT',
    body: JSON.stringify({ ordered_task_ids: orderedTaskIds }),
  });
}

export async function deleteTask(taskId, hard = false) {
  const suffix = hard ? '?hard=true' : '';
  return apiRequest(`${API_ENDPOINTS.TASKS}/${taskId}${suffix}`, {
    method: 'DELETE',
  });
}

// ── Plan APIs ───────────────────────────────────────────────
export async function generatePlan(date = null, lang = 'en', capacityUnits = null, force = false) {
  const body = {};
  if (date) body.date = date;
  body.lang = lang;
  if (capacityUnits !== null && capacityUnits !== undefined) {
    body.capacity_units = Number(capacityUnits);
  }
  if (force) body.force = true;
  return apiRequest(API_ENDPOINTS.PLANS_GENERATE, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getTodayPlan(lang = 'en', capacityUnits = null) {
  let url = `${API_ENDPOINTS.PLANS_TODAY}?lang=${lang}`;
  if (capacityUnits !== null && capacityUnits !== undefined) {
    url += `&capacity_units=${Number(capacityUnits)}`;
  }
  return apiRequest(url);
}

// ── Feedback APIs ───────────────────────────────────────────
export async function submitFeedback(date, results, lang = 'en', capacityUnits = null) {
  const body = { date, results, lang };
  if (capacityUnits !== null && capacityUnits !== undefined) {
    body.capacity_units = Number(capacityUnits);
  }
  return apiRequest(API_ENDPOINTS.FEEDBACK, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ── Stats & History APIs ────────────────────────────────────
export async function getHistory(taskId = null, limit = 50, offset = 0) {
  let url = `${API_ENDPOINTS.HISTORY}?limit=${limit}&offset=${offset}`;
  if (taskId) url += `&task_id=${taskId}`;
  return apiRequest(url);
}

export async function getStats() {
  return apiRequest(API_ENDPOINTS.STATS);
}

export async function getWeeklySummary(lang = 'en') {
  return apiRequest(`${API_ENDPOINTS.WEEKLY_SUMMARY}?lang=${lang}`);
}

export async function checkHealth() {
  return apiRequest(API_ENDPOINTS.HEALTH);
}

// ── LLM Settings APIs ───────────────────────────────────────
export async function getLLMConfig() {
  return apiRequest(API_ENDPOINTS.SETTINGS_LLM);
}

export async function updateLLMConfig(config) {
  return apiRequest(API_ENDPOINTS.SETTINGS_LLM, {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

export async function testLLMConnection() {
  return apiRequest(API_ENDPOINTS.SETTINGS_LLM_TEST, {
    method: 'POST',
  });
}
