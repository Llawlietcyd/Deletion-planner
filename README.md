# Daymark

English | [中文](#中文说明)

Daymark is a bilingual personal planning product for people who want a clearer day, not a longer task list.

It combines planning, execution, review, mood, focus, and AI conversation into one workflow so the user can decide:
- what matters today
- what should be deferred
- what should be removed
- what the week is actually turning into

## Overview

Most productivity tools are optimized for adding more.

Daymark is built around a different idea: daily life becomes easier when planning, execution, reflection, and emotional context live in the same place.

Instead of treating tasks as a flat list, Daymark organizes the experience around a real rhythm:
- **Inbox** for capturing tasks and recurring commitments
- **Today** for selecting and executing a realistic plan
- **Review** for seeing what actually happened across the month
- **Insights** for behavioral summaries
- **Concierge** for asking questions or operating the app conversationally

## Why Daymark

Daymark is designed as a personal daily operating board, not just a to-do app.

What makes it different:
- **Deletion-aware planning**: the system treats defer and delete as meaningful actions, not failures
- **Time-aware structure**: one-off tasks, daily commitments, and weekly routines live in the same timeline
- **Review-first feedback loop**: the calendar and history surfaces make behavior visible over time
- **Emotion-aware workflow**: mood, focus, music, and daily fortune are part of the day loop
- **Actionable AI**: the in-app concierge can answer schedule questions and perform actions inside the product

## Core Product Experience

### 1. Capture
- Create one-off tasks
- Add daily and weekly recurring tasks
- Batch-create multiple tasks at once
- Store due dates, weekday recurrence, and priority

### 2. Execute
- Generate a realistic Today board
- Complete, defer, or delete tasks directly from the day view
- Run focus sessions with a built-in timer
- Capture lightweight inspiration and day-state signals

### 3. Reflect
- Review the month through a calendar view
- Inspect daily activity and future arrangements
- See created, planned, completed, deferred, and deleted traces
- Read weekly summaries and performance signals

### 4. Feel
- Log mood
- Receive contextual music recommendations
- Generate a daily fortune / tarot-style card

### 5. Ask
- Use the concierge for normal Q&A about app state
- Ask date-aware questions like “What do I have next Tuesday?”
- Follow up with references like “that day” or “that task”
- Create, update, defer, complete, or delete tasks through chat

## Product Flow

1. Sign in and complete onboarding.
2. Add one-off, daily, and weekly commitments into Inbox.
3. Generate a realistic plan for today.
4. Work from the Today board and mark tasks complete, deferred, or deleted.
5. Log mood and focus as the day unfolds.
6. Revisit the month in Review and inspect weekly patterns in Insights.
7. Ask the concierge what is scheduled, what changed, or what should happen next.

## Feature Highlights

### Inbox
- Task creation and editing
- Batch input
- Recurring task setup
- Due dates and priorities

### Today
- Daily plan generation
- Completion and strike-through flow
- Defer and permanent delete actions
- Mood check-in
- Focus timer
- Music and daily fortune

### Review
- Monthly calendar
- Daily record panel
- Future arrangement visibility
- Weekly review summary

### Insights
- Completion count
- Defer and delete counts
- Weekly completion rate
- Lightweight behavioral dashboard

### Concierge
- App-state grounded Q&A
- Task mutation through chat
- Follow-up context handling
- LLM-first answer path with local fallback

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | React 18, React Router, React Scripts |
| Backend | FastAPI, Pydantic, SQLAlchemy |
| Database | SQLite by default, PostgreSQL in Docker |
| Migrations | Alembic |
| AI / LLM | Runtime-configured provider with mock fallback |
| Testing | Pytest, React Testing Library |

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- npm
- Docker Desktop optional

### Run locally from the repo root

```bash
npm install
npm run dev
```

This starts:
- frontend at `http://localhost:3000`
- backend at `http://localhost:5001`

### Run frontend and backend separately

Backend:

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api_v2.main:app --reload --port 5001
```

Frontend:

```bash
cd frontend
npm install
npm start
```

### Run with Docker

```bash
docker compose up --build
```

Services:
- frontend: `http://localhost:3000`
- api: `http://localhost:5001`
- postgres: `localhost:5432`

## Configuration

Use `server/.env.example` as the template for local configuration.

Typical variables include:
- `DATABASE_URL`
- `CORS_ORIGINS`
- `RATE_LIMIT_RPM`
- `API_KEY`
- `LLM_PROVIDER`
- provider-specific API keys

Important:
- keep real secrets in local env files or your deployment platform
- do not commit real API keys
- runtime LLM settings can also be adjusted from the Settings page

## Testing

Backend:

```bash
PYTHONPATH=server python3 -m pytest server/tests/test_api_v2.py
```

Frontend:

```bash
cd frontend
npm test -- --runInBand --watch=false
```

Production build:

```bash
npm run build
```

## Repository Structure

```text
Deletion-planner/  (repository folder; product name: Daymark)
├── README.md
├── docker-compose.yml
├── frontend/
│   ├── package.json
│   ├── public/
│   └── src/
├── server/
│   ├── .env.example
│   ├── api_v2/
│   ├── core/
│   ├── database/
│   ├── migrations/
│   ├── scripts/
│   └── tests/
└── package.json
```

## Developer Notes

- The active backend is FastAPI v2 under `server/api_v2/`.
- The assistant uses an LLM-first path with deterministic fallback behavior.
- Several product flows normalize time handling around `America/New_York`.
- Local SQLite bootstrap includes compatibility patches for fast iteration.

## Security

Do **not** commit:
- real API keys
- real production database credentials
- personal `.env` files
- internal-only secrets

Safe practice:
1. Commit only example configuration files.
2. Check `git status` before every push.
3. Rotate any secret immediately if it was ever exposed.

---

# 中文说明

## 产品简介

Daymark 是一个双语的个人日常规划产品，适合那些想把一天过得更清晰、而不是把任务越堆越多的人。

它把规划、执行、复盘、情绪状态和 AI 对话放进同一个工作流里，帮助用户决定：
- 今天真正重要的是什么
- 哪些事情应该推迟
- 哪些事情应该删掉
- 这一周到底在往什么方向发展

## 产品定位

大多数效率工具都在鼓励用户继续添加。

Daymark 的出发点不一样：当规划、执行、复盘和情绪上下文在同一个系统里时，用户更容易把生活过得更现实、更轻、更稳定。

所以它不是一个单纯的待办清单，而是围绕真实节奏组织体验：
- **Inbox**：收集任务和周期承诺
- **Today**：筛选并执行今天真正要做的事
- **Review**：在月历和每日记录里回看发生了什么
- **Insights**：查看行为统计和周维度总结
- **Concierge**：通过聊天提问，或者直接操作应用

## 为什么它像一个产品，而不是一个任务列表

Daymark 更接近一个个人日常操作台，而不是传统 to-do app。

它的核心差异在于：
- **删除优先**：`defer` 和 `delete` 是有意义的决策，不是失败
- **按时间组织**：一次性任务、每日任务、每周任务在同一条时间轴里运作
- **强调复盘闭环**：月历、历史和周总结帮助用户看到行为模式
- **带情绪上下文**：心情、专注、音乐、每日运势都会影响使用体验
- **AI 能执行动作**：私人管家不只是聊天，也能理解安排并操作应用状态

## 核心体验

### 1. 收集
- 创建单次任务
- 添加每日 / 每周周期任务
- 批量录入多个任务
- 保存截止日期、星期周期和优先级

### 2. 执行
- 生成更现实的 Today board
- 在当天页面里直接完成、推迟或删除
- 使用内置番茄钟 / 专注计时
- 记录轻量的灵感和当天状态

### 3. 复盘
- 通过月历查看整个月的安排与痕迹
- 查看当天记录和未来安排
- 回看创建、计划、完成、推迟、删除等行为轨迹
- 阅读周总结和行为信号

### 4. 感受
- 记录心情
- 获取音乐推荐
- 生成每日运势 / 卡牌

### 5. 对话
- 向私人管家发起普通问答
- 询问“下周二我有什么安排”这类时间相关问题
- 用“那天”“那个任务”这样的上下文继续追问
- 通过聊天新增、修改、推迟、完成或删除任务

## 典型使用流程

1. 登录并完成 onboarding。
2. 在 Inbox 里录入临时任务、每日任务和每周任务。
3. 生成今天的计划。
4. 在 Today board 里执行任务，并决定完成、推迟还是删除。
5. 在过程中记录心情和专注状态。
6. 到 Review 和 Insights 里回看这个月与这一周的行为模式。
7. 通过私人管家提问安排、追踪变化，或者直接操作任务。

## 功能模块

### Inbox
- 任务创建和编辑
- 批量输入
- 周期任务设置
- 截止日期和优先级

### Today
- 每日计划生成
- 完成和划线反馈
- defer 与永久删除
- 心情打卡
- 番茄钟
- 音乐推荐和每日运势

### Review
- 月历复盘
- 当天记录面板
- 未来安排查看
- 周总结

### Insights
- 完成数量
- 推迟 / 删除数量
- 周完成率
- 轻量统计面板

### Concierge
- 基于真实 app 状态的问答
- 通过聊天改任务
- 上下文追问
- LLM 优先 + 本地兜底

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 18、React Router、React Scripts |
| 后端 | FastAPI、Pydantic、SQLAlchemy |
| 数据库 | 默认 SQLite，Docker 下使用 PostgreSQL |
| 迁移 | Alembic |
| AI / LLM | 运行时可配置 provider，带 mock fallback |
| 测试 | Pytest、React Testing Library |

## 快速开始

### 前置依赖
- Python 3.9+
- Node.js 18+
- npm
- Docker Desktop 可选

### 在根目录直接启动

```bash
npm install
npm run dev
```

会启动：
- 前端：`http://localhost:3000`
- 后端：`http://localhost:5001`

### 前后端分开启动

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

### 使用 Docker 启动

```bash
docker compose up --build
```

服务地址：
- 前端：`http://localhost:3000`
- API：`http://localhost:5001`
- PostgreSQL：`localhost:5432`

## 配置说明

本地配置模板见 `server/.env.example`。

常见变量包括：
- `DATABASE_URL`
- `CORS_ORIGINS`
- `RATE_LIMIT_RPM`
- `API_KEY`
- `LLM_PROVIDER`
- 各 provider 对应的 API key

注意：
- 真实密钥请放在本地 env 或部署平台里
- 不要把真实 API key 提交到仓库
- Settings 页面也支持调整运行时 LLM 配置

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

## 仓库结构

```text
Deletion-planner/  （仓库目录名，产品名为 Daymark）
├── README.md
├── docker-compose.yml
├── frontend/
│   ├── package.json
│   ├── public/
│   └── src/
├── server/
│   ├── .env.example
│   ├── api_v2/
│   ├── core/
│   ├── database/
│   ├── migrations/
│   ├── scripts/
│   └── tests/
└── package.json
```

## 开发备注

- 当前有效后端是 `server/api_v2/` 这一套 FastAPI v2。
- assistant 采用的是 `LLM 优先 + 本地规则兜底` 的混合路径。
- 多个产品流程使用 `America/New_York` 作为时间基准。
- 本地 SQLite 启动时包含一层兼容补丁，方便快速迭代。

## 安全说明

不要提交：
- 真实 API key
- 真实生产数据库密码
- 个人 `.env`
- 内部专用密钥

建议做法：
1. 只提交示例配置文件。
2. 每次 push 前先检查 `git status`。
3. 如果密钥曾经暴露，立刻 rotate。
