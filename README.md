# Deletion-Aware Adaptive Daily Planning Assistant

> *If everything is important, nothing is important.*

An AI-powered daily planning assistant built on the **"deletion-first" philosophy** — it doesn't just organize your tasks, it actively helps you decide what **not** to do, so you can focus on what truly matters.

---

## 1. Problem Statement

Many people struggle with **overplanning** rather than under-execution. They create unrealistic daily task lists, complete only a fraction, and feel guilt or frustration about unfinished tasks.

Traditional productivity tools (to-do lists, reminder apps) focus on optimizing schedules or tracking completion, but they do **not** reason about whether certain tasks should be deferred, simplified, or deleted altogether.

**The core problem is not productivity — it is unrealistic planning under real-world constraints** (time, energy, cognitive load).

## 2. Project Objective

Build an AI-powered daily planning assistant that:

- Converts vague goals into **realistic daily plans** (max 4 tasks)
- Detects **overload** and **repeated deferrals**
- Suggests **task deletions** when appropriate, with clear reasoning
- **Adaptively re-plans** when tasks are missed
- Helps users focus on what **truly matters**

The AI acts as a **reasoning assistant**, not a passive scheduler.

## 3. Target Users

| Profile | Description |
|---------|-------------|
| Students | Juggling coursework, projects, and personal goals |
| Early-career professionals | Managing competing priorities with limited experience |
| Independent builders | Fellowship participants, freelancers, side-project creators |
| Overplanners | Motivated but overwhelmed; frequently miss planned tasks |

**Common trait**: Needs decision support, not just reminders.

## 4. Core Features

| Feature | Description |
|---------|-------------|
| **Task Input** | Single or batch (one per line), with 4-level priority selector |
| **AI Task Classification** | Categorizes as Core / Deferrable / Deletion Candidate |
| **Daily Plan Generation** | Limits to 4 achievable tasks; explicitly identifies what NOT to do |
| **Missed Task Handling** | Adaptive re-planning, not automatic rollover |
| **Deletion Logic** | Flags tasks deferred 3+ times; suggests deletion with reasoning |
| **Feedback Loop** | Track completion/deferral/miss patterns; adjusts future plans |
| **Explainable AI** | Every suggestion comes with a clear, human-readable explanation |
| **Bilingual UI** | Full Chinese/English support with one-click language toggle |

## 5. How It Works

```
User enters 10 tasks
        │
        ▼
   AI classifies tasks
   ┌─────────────────────┐
   │ Core (4)            │ → Today's Plan
   │ Deferrable (3)      │ → Backlog
   │ Deletion Candidate  │ → Suggest removal
   └─────────────────────┘
        │
        ▼
   User completes 2, misses 1, defers 1
        │
        ▼
   System adapts:
   • Reduces next-day load
   • Flags repeated deferrals
   • Suggests deleting 1 task
   • Provides reasoning explanation
```

## 6. Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + Tailwind CSS |
| **Backend** | Flask (Python) |
| **Database** | SQLite via SQLAlchemy ORM |
| **AI Engine** | Mock rule-based engine (swappable to Claude / OpenAI API) |
| **i18n** | React Context-based bilingual system (EN / ZH) |

## 7. Project Structure

```
Template-Repo/
├── frontend/                    # React + Tailwind
│   └── src/
│       ├── components/
│       │   ├── TaskInput.js         # Task creation (single/batch + priority)
│       │   ├── TaskList.js          # Task list with category badges
│       │   ├── TasksPage.js         # Main tasks page with filters
│       │   ├── DailyPlan.js         # Plan generation + feedback
│       │   ├── DeletionSuggestion.js# AI deletion suggestions
│       │   ├── HistoryPanel.js      # Action history by date
│       │   ├── StatsPanel.js        # Statistics dashboard
│       │   └── MainNavbar.js        # Navigation + language toggle
│       ├── i18n/
│       │   ├── LanguageContext.js    # React Context for i18n
│       │   └── translations.js      # EN/ZH translation strings
│       ├── http/api.js              # API client
│       └── constants/RouteConstants.js
├── server/                      # Flask backend
│   ├── app.py                       # Flask entry point (11 API routes)
│   ├── api_endpoints/
│   │   ├── tasks/handler.py         # Task CRUD
│   │   ├── plans/handler.py         # Plan generation + retrieval
│   │   └── feedback/handler.py      # Feedback + stats + history
│   ├── core/
│   │   ├── planner.py               # Planning engine
│   │   ├── deletion.py              # Deletion detection engine
│   │   └── llm/
│   │       ├── base.py              # LLM abstract interface
│   │       ├── mock.py              # Rule-based mock (bilingual)
│   │       └── __init__.py          # LLM factory
│   ├── database/
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   └── db.py                    # DB session management
│   ├── requirements.txt
│   └── Dockerfile
└── README.md
```

## 8. Quick Start

### Prerequisites

- Python 3.9+
- Node.js 16+

### Backend

```bash
cd server
pip install -r requirements.txt
flask run
```

API available at `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm start
```

App opens at `http://localhost:3000`.

## 9. API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tasks?status=active` | List tasks (active / completed / deleted / all) |
| `POST` | `/api/tasks` | Create a single task `{title, description, priority}` |
| `POST` | `/api/tasks/batch` | Batch create from text `{text}` (one task per line) |
| `PUT` | `/api/tasks/:id` | Update task fields |
| `DELETE` | `/api/tasks/:id` | Soft-delete a task |
| `POST` | `/api/plans/generate` | Generate AI daily plan `{lang}` |
| `GET` | `/api/plans/today?lang=zh` | Get today's plan (with localized reasoning) |
| `GET` | `/api/plans/:date?lang=en` | Get plan for a specific date |
| `POST` | `/api/feedback` | Submit completion results `{date, results, lang}` |
| `GET` | `/api/history` | Task action history |
| `GET` | `/api/stats` | Summary statistics |

## 10. AI / LLM Architecture

The system uses a **pluggable LLM abstraction layer**:

```
BaseLLMService (abstract)
    ├── MockLLMService      ← Current: rule-based engine
    ├── ClaudeLLMService    ← Future: Anthropic Claude API
    └── OpenAILLMService    ← Future: OpenAI GPT API
```

**Mock engine rules:**
- Priority >= 3 or urgency keywords → **Core** task
- Optional/exploratory keywords → **Deferrable** task
- Deferred 3+ times → **Deletion candidate**
- Completion rate < 30% → **Deletion candidate**

Switch providers via environment variable:
```bash
LLM_PROVIDER=mock    # default
LLM_PROVIDER=claude  # future
LLM_PROVIDER=openai  # future
```

## 11. Deletion Philosophy

This project is built on the philosophy of [Deletion](https://anote-ai.medium.com/deletion-a-philosophy-for-building-great-things-bd08378d3f23) — the disciplined practice of removing everything unnecessary so only the essentials remain.

**This tool is NOT:**
- A full productivity platform
- A calendar replacement
- A habit-tracking app
- A generic to-do manager

**This tool IS:**
- A reasoning-based decision support tool
- An AI assistant that helps you decide what to **stop doing**
- A system that prioritizes **focus over volume**

## 12. Success Criteria

The project succeeds if:

- [x] A user can input vague goals
- [x] The system generates a realistic daily plan (max 4 tasks)
- [x] The system adapts after missed tasks
- [x] The system suggests at least one justified deletion
- [x] The reasoning is explainable and coherent
- [x] Full bilingual (EN/ZH) support

## License

MIT
