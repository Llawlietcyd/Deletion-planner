# Daymark / Deletion Planner

English | [中文](#中文说明)

Daymark is a deletion-first daily planning app that combines task management, AI-assisted planning, review, mood check-ins, focus timing, music recommendations, tarot-style daily fortune, and an in-app concierge chatbox.

The project is built as a full-stack product:
- `frontend/`: React 18 application
- `server/`: FastAPI v2 backend with SQLAlchemy
- `docker-compose.yml`: local full-stack environment with PostgreSQL

## Table of Contents
- [Project Overview](#project-overview)
- [Core Product Philosophy](#core-product-philosophy)
- [What the App Includes](#what-the-app-includes)
- [Screens and User Flow](#screens-and-user-flow)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Data Model](#data-model)
- [API Surface](#api-surface)
- [Local Development](#local-development)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment Notes](#deployment-notes)
- [Security and Secrets](#security-and-secrets)
- [Known Implementation Notes](#known-implementation-notes)
- [中文说明](#中文说明)

## Project Overview

Most planning tools help users add more tasks. This project starts from the opposite assumption: the real problem is often overload, not lack of ambition.

Daymark is designed to help a user:
- capture tasks and recurring commitments
- generate a smaller and more realistic daily plan
- defer, delete, or complete tasks with a visible history trail
- review behavior across days, weeks, and months
- log mood and focus sessions
- talk to an in-app concierge that can answer questions or act inside the app

The app is bilingual at the product level and already contains significant Chinese-first UX.

## Core Product Philosophy

The core idea is deletion-first planning:
- a shorter plan is better than an unrealistic plan
- deferral history matters
- repeated friction is data
- the system should help the user decide what not to do
- AI should act as a reasoning layer, not just a task storage layer

This philosophy appears in:
- plan generation
- deletion suggestions
- review insights
- concierge actions
- recurring task handling

## What the App Includes

### 1. Authentication and onboarding
- Local multi-user session system
- Login with display name and password
- Optional birthday and gender capture
- Onboarding flow for commitments and goals

### 2. Inbox and task management
- Create single tasks
- Batch task creation
- Task priority
- Task kinds:
  - `temporary`
  - `daily`
  - `weekly`
- Due date support
- Recurrence weekday support
- Reordering and CRUD

### 3. Today view
- Daily plan generation
- Daily completion / defer / delete actions
- Mood check-in
- Focus timer / pomodoro
- Song recommendations
- Daily tarot / fortune card

### 4. Review
- Monthly calendar review
- Daily activity log
- Future / scheduled task visibility
- Weekly summary and review insights
- History of created / planned / completed / deferred / deleted actions

### 5. Insights
- Weekly summary
- Completion and deletion counts
- Completion rate
- Stats dashboard

### 6. Concierge chatbox
- Normal Q&A about app data
- Task creation / update / delete / defer / complete
- Date-aware schedule questions
- Follow-up context like “that day”, “that task”, “next Tuesday then”
- LLM-first answering path with deterministic fallback

### 7. Settings
- DeepSeek runtime configuration
- LLM connectivity test
- Theme and language controls
- Developer reset

## Screens and User Flow

### Main routes
- `/today`
- `/inbox`
- `/review`
- `/insights`
- `/settings`

### Typical flow
1. User logs in.
2. User completes onboarding with commitments and goals.
3. User adds one-off, daily, and weekly tasks.
4. User generates a daily plan.
5. User executes tasks from the Today board.
6. User logs mood and focus sessions.
7. User reviews patterns in Review and Insights.
8. User uses the concierge to query or manipulate data conversationally.

## Architecture

### Frontend
The frontend is a React SPA with a routed dashboard shell.

Important frontend entry points:
- [frontend/src/App.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/App.js)
- [frontend/src/Dashboard.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/Dashboard.js)
- [frontend/src/components/AuthGate.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/AuthGate.js)
- [frontend/src/components/ConciergeChatbox.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/ConciergeChatbox.js)

Important screens:
- [frontend/src/components/TodayPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/TodayPage.js)
- [frontend/src/components/InboxPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/InboxPage.js)
- [frontend/src/components/ReviewPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/ReviewPage.js)
- [frontend/src/components/InsightsPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/InsightsPage.js)
- [frontend/src/components/SettingsPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/SettingsPage.js)

Shared frontend infrastructure:
- `LanguageProvider`
- `DarkModeProvider`
- `ToastProvider`
- `SessionProvider`
- API wrapper in [frontend/src/http/api.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/http/api.js)

### Backend
The active backend is FastAPI v2.

Backend entry point:
- [server/api_v2/main.py](/Users/chenyidian/Documents/anote/Deletion-planner/server/api_v2/main.py)

Main backend concerns:
- sessions and onboarding
- task CRUD and recurrence normalization
- daily plan generation
- history and analytics
- mood logging
- focus logging
- song recommendation
- daily fortune generation
- assistant / concierge orchestration
- runtime LLM settings

### Persistence
The backend uses SQLAlchemy. In local development it defaults to SQLite, while Docker uses PostgreSQL.

Database bootstrap:
- [server/database/db.py](/Users/chenyidian/Documents/anote/Deletion-planner/server/database/db.py)

The SQLite bootstrap layer also includes compatibility patching for local schema evolution, so the app is more forgiving during local iteration.

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | React 18, React Router, React Scripts |
| Backend | FastAPI, Pydantic, SQLAlchemy |
| Database | SQLite by default, PostgreSQL in Docker |
| Migrations | Alembic |
| LLM provider | DeepSeek runtime config + mock fallback |
| Styling | CSS + utility-style classes already embedded in the app |
| Testing | Pytest, React Testing Library |

## Repository Structure

```text
Deletion-planner/
├── README.md
├── docker-compose.yml
├── docs/
│   ├── DEPLOYMENT.md
│   └── WALKTHROUGH_SCRIPT.md
├── frontend/
│   ├── package.json
│   ├── public/
│   └── src/
│       ├── App.js
│       ├── Dashboard.js
│       ├── constants/
│       ├── http/
│       ├── i18n/
│       └── components/
├── server/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── api_v2/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── user_context.py
│   │   └── routers/
│   ├── core/
│   │   ├── planner.py
│   │   ├── deletion.py
│   │   ├── rules.py
│   │   ├── spotify.py
│   │   ├── tarot_catalog.py
│   │   ├── task_kind.py
│   │   ├── time.py
│   │   └── llm/
│   ├── database/
│   │   ├── db.py
│   │   └── models.py
│   ├── migrations/
│   ├── scripts/
│   └── tests/
└── package.json
```

## Data Model

Main entities from [server/database/models.py](/Users/chenyidian/Documents/anote/Deletion-planner/server/database/models.py):

### `User`
- username
- password
- birthday
- gender

### `UserSession`
- token-based local session state

### `Task`
- title
- description
- priority
- category
- status
- `task_kind`
- `recurrence_weekday`
- `due_date`
- deferral and completion counters

### `DailyPlan`
- per-user per-day plan record
- reasoning and overload warning

### `PlanTask`
- selected task rows inside a plan

### `TaskHistory`
- audit trail of:
  - created
  - planned
  - completed
  - missed
  - deferred
  - deleted
  - restored

### `MoodEntry`
- 1-5 mood score + note

### `FocusSession`
- work/break session records

### `DailyFortune`
- JSON payload for daily fortune output

### `AppSetting`
- runtime key/value settings, including LLM config

## API Surface

The backend is mounted under `/api` except the health check.

### Core system
- `GET /health`

### Session and onboarding
- `GET /api/session`
- `POST /api/session/login`
- `POST /api/session/logout`
- `GET /api/onboarding`
- `POST /api/onboarding/complete`

### Tasks
- `GET /api/tasks`
- `POST /api/tasks`
- `POST /api/tasks/batch`
- `PUT /api/tasks/{id}`
- `PUT /api/tasks/reorder`
- `DELETE /api/tasks/{id}`

### Plans and feedback
- `POST /api/plans/generate`
- `GET /api/plans/today`
- `GET /api/plans/{date}`
- `POST /api/feedback`

### Analytics and review
- `GET /api/history`
- `GET /api/stats`
- `GET /api/weekly-summary`
- `GET /api/review-insights`

### Mood and focus
- `POST /api/mood`
- `GET /api/mood/today`
- `GET /api/mood/history`
- `POST /api/focus/sessions`
- `GET /api/focus/stats`
- `GET /api/focus/history`

### Music and fortune
- `GET /api/songs/recommend`
- `POST /api/fortune/daily`
- `GET /api/fortune/today`

### Concierge / assistant
- `GET /api/assistant/state`
- `POST /api/assistant/chat`

### Runtime settings
- `GET /api/settings/llm`
- `PUT /api/settings/llm`
- `POST /api/settings/llm/test`
- `POST /api/settings/developer/reset`

## Local Development

### Prerequisites
- Python 3.9+
- Node.js 18+ recommended
- npm
- Docker Desktop optional but recommended for full-stack demo

### Option A: Run frontend + FastAPI locally

From the repo root:

```bash
npm install
npm run dev
```

This uses the root script in [package.json](/Users/chenyidian/Documents/anote/Deletion-planner/package.json) to start:
- frontend at `http://localhost:3000`
- FastAPI at `http://localhost:5001`

### Option B: Run services separately

#### Backend
```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api_v2.main:app --reload --port 5001
```

#### Frontend
```bash
cd frontend
npm install
npm start
```

### Option C: Run the full Docker stack

```bash
docker compose up --build
```

Services:
- frontend: `http://localhost:3000`
- api: `http://localhost:5001`
- postgres: `localhost:5432`

## Configuration

Reference file:
- [server/.env.example](/Users/chenyidian/Documents/anote/Deletion-planner/server/.env.example)

Common variables:

| Variable | Meaning |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy database URL |
| `CORS_ORIGINS` | Allowed frontend origins |
| `RATE_LIMIT_RPM` | Request rate limit per IP |
| `API_KEY` | Optional backend API protection |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `DEEPSEEK_MODEL` | DeepSeek model name |

Important note:
- the app also supports setting the DeepSeek key and model at runtime from the Settings page
- do not hardcode secrets into the repository
- do not put real secrets into the README

## Testing

### Backend
```bash
PYTHONPATH=server python3 -m pytest server/tests/test_api_v2.py
```

### Frontend targeted tests
```bash
cd frontend
npm test -- --runInBand --watch=false
```

### Production build
```bash
npm run build
```

## Deployment Notes

See:
- [docs/DEPLOYMENT.md](/Users/chenyidian/Documents/anote/Deletion-planner/docs/DEPLOYMENT.md)
- [docs/WALKTHROUGH_SCRIPT.md](/Users/chenyidian/Documents/anote/Deletion-planner/docs/WALKTHROUGH_SCRIPT.md)

Current deployment assumptions:
- local dev can use SQLite
- Docker stack uses PostgreSQL
- FastAPI app is the main backend entry point

## Security and Secrets

Do **not** commit any of the following:
- real DeepSeek API keys
- real production DB credentials
- real session secrets or internal API keys
- personal `.env` files

This repo already ignores:
- `.env`
- `.env.local`
- `node_modules`
- build artifacts

Safe practice:
1. keep secrets in local env files or your deployment platform
2. commit only `.env.example`
3. verify `git status` before every push
4. if a secret is ever committed, rotate it immediately

## Known Implementation Notes

- FastAPI v2 is the real active backend path described in this README.
- The assistant uses an LLM-first path for conversational Q&A, with deterministic fallback for safety and offline failure handling.
- Date handling is intentionally normalized around app time helpers and the `America/New_York` timezone in several product flows.
- The SQLite bootstrap includes compatibility patches for local evolution, which is convenient for development but should not replace disciplined migrations in production.

---

# 中文说明

## 项目概述

Daymark / Deletion Planner 是一个“删除优先”的每日规划产品。它不只是帮用户记任务，而是把任务、每日计划、复盘、心情、专注、音乐推荐、塔罗式每日指引和私人管家聊天框整合到同一个系统里。

项目当前是完整的前后端应用：
- `frontend/`：React 18 前端
- `server/`：FastAPI v2 后端
- `docker-compose.yml`：本地联调用的前后端 + PostgreSQL 栈

## 产品理念

这个产品的核心不是“多做一点”，而是“做得更现实一点”。

也就是说：
- 计划过满比计划过少更危险
- 一直推迟的任务本身就是信号
- 不是所有任务都值得继续挂在列表里
- AI 不应该只是帮你排序，也应该帮你减负

## 主要功能

### 1. 登录与 onboarding
- 本地多用户 session
- 用户名 / 密码登录
- 可选生日与性别
- onboarding 收集长期承诺和目标

### 2. Inbox / 任务管理
- 单条任务创建
- 批量任务创建
- 优先级
- 三类任务形态：
  - `temporary` 临时任务
  - `daily` 每日任务
  - `weekly` 每周任务
- 截止日期
- 周期星期配置
- 排序、编辑、删除

### 3. Today 页面
- 生成当天计划
- 勾选完成 / defer / 删除
- 心情打卡
- 番茄钟 / 专注计时
- 音乐推荐
- 每日运势 / 卡牌

### 4. Review 页面
- 月历复盘
- 每日记录
- 未来安排查看
- 周总结与复盘洞察
- 行为历史轨迹

### 5. Insights 页面
- 周维度总结
- 完成数 / 删除数 / 推迟数
- 完成率
- 统计面板

### 6. 私人管家 chatbox
- 普通问答
- 任务新增、修改、删除、推迟、完成
- 能回答“某天 / 某周几有什么安排”
- 支持“那天”“那个任务”“那下周二呢”这类上下文追问
- 走 LLM 优先问答路径，同时保留本地兜底

### 7. Settings
- DeepSeek 配置
- LLM 连通性测试
- 明暗模式与语言切换
- 开发态重置

## 页面结构

主路由如下：
- `/today`
- `/inbox`
- `/review`
- `/insights`
- `/settings`

前端入口与壳层：
- [frontend/src/App.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/App.js)
- [frontend/src/Dashboard.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/Dashboard.js)
- [frontend/src/components/AuthGate.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/AuthGate.js)

核心页面：
- [frontend/src/components/TodayPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/TodayPage.js)
- [frontend/src/components/InboxPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/InboxPage.js)
- [frontend/src/components/ReviewPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/ReviewPage.js)
- [frontend/src/components/InsightsPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/InsightsPage.js)
- [frontend/src/components/SettingsPage.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/SettingsPage.js)
- [frontend/src/components/ConciergeChatbox.js](/Users/chenyidian/Documents/anote/Deletion-planner/frontend/src/components/ConciergeChatbox.js)

## 后端结构

FastAPI 主入口：
- [server/api_v2/main.py](/Users/chenyidian/Documents/anote/Deletion-planner/server/api_v2/main.py)

主要路由模块：
- `tasks.py`：任务 CRUD、排序、类型归一化
- `plans.py`：每日计划生成
- `feedback.py`：计划反馈
- `analytics.py`：统计、周总结、复盘洞察
- `session.py`：登录、会话、onboarding
- `mood.py`：心情记录
- `focus.py`：番茄钟 / 专注记录
- `songs.py`：音乐推荐
- `fortune.py`：每日运势 / 卡牌
- `assistant.py`：私人管家与聊天动作
- `settings.py`：LLM 运行时配置

## 数据模型

主要数据表定义在 [server/database/models.py](/Users/chenyidian/Documents/anote/Deletion-planner/server/database/models.py)。

核心实体包括：
- `User`
- `UserSession`
- `Task`
- `DailyPlan`
- `PlanTask`
- `TaskHistory`
- `MoodEntry`
- `FocusSession`
- `DailyFortune`
- `AppSetting`

其中 `Task` 是最核心的业务实体，包含：
- 标题
- 描述
- 优先级
- 分类
- 状态
- `task_kind`
- `recurrence_weekday`
- `due_date`
- 推迟次数
- 完成次数

## API 概览

核心接口包括：

### 会话与 onboarding
- `GET /api/session`
- `POST /api/session/login`
- `POST /api/session/logout`
- `GET /api/onboarding`
- `POST /api/onboarding/complete`

### 任务
- `GET /api/tasks`
- `POST /api/tasks`
- `POST /api/tasks/batch`
- `PUT /api/tasks/{id}`
- `PUT /api/tasks/reorder`
- `DELETE /api/tasks/{id}`

### 计划与反馈
- `POST /api/plans/generate`
- `GET /api/plans/today`
- `GET /api/plans/{date}`
- `POST /api/feedback`

### 统计与复盘
- `GET /api/history`
- `GET /api/stats`
- `GET /api/weekly-summary`
- `GET /api/review-insights`

### 心情与专注
- `POST /api/mood`
- `GET /api/mood/today`
- `GET /api/mood/history`
- `POST /api/focus/sessions`
- `GET /api/focus/stats`
- `GET /api/focus/history`

### 音乐与运势
- `GET /api/songs/recommend`
- `POST /api/fortune/daily`
- `GET /api/fortune/today`

### 私人管家
- `GET /api/assistant/state`
- `POST /api/assistant/chat`

### 设置
- `GET /api/settings/llm`
- `PUT /api/settings/llm`
- `POST /api/settings/llm/test`
- `POST /api/settings/developer/reset`

## 本地运行

### 前置依赖
- Python 3.9+
- Node.js 18+ 推荐
- npm
- Docker Desktop 可选

### 方案一：根目录直接启动

```bash
npm install
npm run dev
```

会同时启动：
- 前端：`http://localhost:3000`
- FastAPI：`http://localhost:5001`

### 方案二：前后端分别启动

后端：

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api_v2.main:app --reload --port 5001
```

前端：

```bash
cd frontend
npm install
npm start
```

### 方案三：Docker 联调

```bash
docker compose up --build
```

服务地址：
- 前端：`http://localhost:3000`
- API：`http://localhost:5001`
- PostgreSQL：`localhost:5432`

## 配置说明

配置模板：
- [server/.env.example](/Users/chenyidian/Documents/anote/Deletion-planner/server/.env.example)

常见变量：
- `DATABASE_URL`
- `CORS_ORIGINS`
- `RATE_LIMIT_RPM`
- `API_KEY`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`

另外，应用内 Settings 页面也支持运行时设置 DeepSeek key 和 model。

## 测试命令

后端：

```bash
PYTHONPATH=server python3 -m pytest server/tests/test_api_v2.py
```

前端：

```bash
cd frontend
npm test -- --runInBand --watch=false
```

构建：

```bash
npm run build
```

## 部署说明

现有补充文档：
- [docs/DEPLOYMENT.md](/Users/chenyidian/Documents/anote/Deletion-planner/docs/DEPLOYMENT.md)
- [docs/WALKTHROUGH_SCRIPT.md](/Users/chenyidian/Documents/anote/Deletion-planner/docs/WALKTHROUGH_SCRIPT.md)

当前建议：
- 本地开发可用 SQLite
- 演示或更稳定联调建议用 Docker + PostgreSQL
- 主后端入口以 FastAPI v2 为准

## 安全与密钥

**不要把真实 API key 写进 README，也不要提交到 GitHub。**

不要提交：
- 真实 DeepSeek API key
- 真实数据库密码
- 真实内部 API key
- 本地 `.env`

建议做法：
1. 只提交 `.env.example`
2. 真实配置放本地 env 或部署平台
3. 每次 push 前先看 `git status`
4. 如果 key 曾经提交过，立刻 rotate

## 实现备注

- 现在 README 以 FastAPI v2 作为当前有效后端说明。
- assistant 现在是“LLM 优先问答 + 本地规则兜底”的混合结构。
- 多个页面和数据处理使用 `America/New_York` 作为应用时间基准。
- SQLite 本地开发带了一层自动兼容补丁，便于快速演进；正式环境仍建议依赖规范迁移。
