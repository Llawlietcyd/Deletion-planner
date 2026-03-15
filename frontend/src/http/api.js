import { API_ENDPOINTS } from '../constants/RouteConstants';

const API_BASE_URL = API_ENDPOINTS.BASE_URL;
const SESSION_TOKEN_KEY = 'dp_session_token';
const PROTOTYPE_LOCAL_KEYS = ['dp_session_token', 'dp_inspiration_orbs_v1', 'planning_capacity_units'];

export function getSessionToken() {
  try {
    return window.localStorage.getItem(SESSION_TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setSessionToken(token) {
  try {
    if (token) {
      window.localStorage.setItem(SESSION_TOKEN_KEY, token);
    } else {
      window.localStorage.removeItem(SESSION_TOKEN_KEY);
    }
  } catch {}
}

export function clearPrototypeLocalState() {
  try {
    PROTOTYPE_LOCAL_KEYS.forEach((key) => window.localStorage.removeItem(key));
  } catch {}
}

// ── Generic fetch helper ────────────────────────────────────
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const sessionToken = getSessionToken();
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...(sessionToken ? { 'X-Session-Token': sessionToken } : {}),
      ...options.headers,
    },
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
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

// ── Task APIs ───────────────────────────────────────────────
export async function getTasks(status = 'active', query = '') {
  let url = `${API_ENDPOINTS.TASKS}?status=${status}`;
  if (query.trim()) url += `&q=${encodeURIComponent(query.trim())}`;
  return apiRequest(url);
}

export async function createTask(title, description = '', priority = 0, category = 'unclassified', dueDate = null, taskKind = null, recurrenceWeekday = null) {
  const body = { title, description, priority, category };
  if (dueDate) body.due_date = dueDate;
  if (taskKind) body.task_kind = taskKind;
  if (recurrenceWeekday !== null && recurrenceWeekday !== undefined) body.recurrence_weekday = recurrenceWeekday;
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

export async function getReviewInsights(date, month = '', lang = 'en') {
  const monthPart = month ? `&month=${encodeURIComponent(month)}` : '';
  return apiRequest(`${API_ENDPOINTS.REVIEW_INSIGHTS}?date=${encodeURIComponent(date)}${monthPart}&lang=${lang}`);
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

export async function resetDeveloperData() {
  return apiRequest('/api/settings/developer/reset', {
    method: 'POST',
  });
}

// ── Session & Onboarding APIs ─────────────────────────────
export async function getSession() {
  return apiRequest(API_ENDPOINTS.SESSION);
}

export async function login(displayName, password, birthday, gender) {
  const body = { display_name: displayName, password };
  if (birthday) body.birthday = birthday;
  if (gender) body.gender = gender;
  return apiRequest(API_ENDPOINTS.SESSION_LOGIN, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function logout() {
  return apiRequest(API_ENDPOINTS.SESSION_LOGOUT, {
    method: 'POST',
  });
}

export async function getOnboarding() {
  return apiRequest(API_ENDPOINTS.ONBOARDING);
}

export async function completeOnboarding(payload) {
  return apiRequest(API_ENDPOINTS.ONBOARDING_COMPLETE, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ── Mood APIs ────────────────────────────────────────────
export async function submitMood(moodLevel, note = '') {
  return apiRequest(API_ENDPOINTS.MOOD, {
    method: 'POST',
    body: JSON.stringify({ mood_level: moodLevel, note }),
  });
}

export async function getTodayMood() {
  return apiRequest(API_ENDPOINTS.MOOD_TODAY);
}

export async function getMoodHistory(days = 30) {
  return apiRequest(`${API_ENDPOINTS.MOOD_HISTORY}?days=${days}`);
}

// ── Focus APIs ───────────────────────────────────────────
export async function saveFocusSession(taskId, durationMinutes, sessionType = 'work') {
  return apiRequest(API_ENDPOINTS.FOCUS_SESSIONS, {
    method: 'POST',
    body: JSON.stringify({ task_id: taskId, duration_minutes: durationMinutes, session_type: sessionType }),
  });
}

export async function getFocusStats() {
  return apiRequest(API_ENDPOINTS.FOCUS_STATS);
}

export async function getFocusHistory(days = 90) {
  return apiRequest(`${API_ENDPOINTS.FOCUS_HISTORY}?days=${days}`);
}

// ── Song Recommendation APIs ─────────────────────────────
export async function getSongRecommendations(lang = 'en', refreshToken = '') {
  const suffix = refreshToken ? `&refresh_token=${encodeURIComponent(refreshToken)}` : '';
  return apiRequest(`${API_ENDPOINTS.SONGS_RECOMMEND}?lang=${lang}${suffix}`);
}

// ── Fortune APIs ─────────────────────────────────────────
export async function getDailyFortune(lang = 'en') {
  return apiRequest(`${API_ENDPOINTS.FORTUNE_DAILY}?lang=${lang}`, {
    method: 'POST',
  });
}

export async function getTodayFortune(lang = 'en') {
  return apiRequest(`${API_ENDPOINTS.FORTUNE_TODAY}?lang=${lang}`);
}

// ── Concierge APIs ───────────────────────────────────────
export async function getAssistantState(lang = 'en') {
  return apiRequest(`${API_ENDPOINTS.ASSISTANT_STATE}?lang=${lang}`);
}

export async function sendAssistantMessage(message, lang = 'en') {
  return apiRequest(API_ENDPOINTS.ASSISTANT_CHAT, {
    method: 'POST',
    body: JSON.stringify({ message, lang }),
  });
}
