-- Deletion-Aware Adaptive Daily Planning Assistant
-- SQLite Schema (auto-created by SQLAlchemy, this file is for reference only)

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    category VARCHAR(30) DEFAULT 'unclassified',
    status VARCHAR(20) DEFAULT 'active',
    priority INTEGER DEFAULT 0,
    deferral_count INTEGER DEFAULT 0,
    completion_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date VARCHAR(10) NOT NULL UNIQUE,
    reasoning TEXT DEFAULT '',
    overload_warning TEXT DEFAULT '',
    max_tasks INTEGER DEFAULT 4,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plan_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES daily_plans(id),
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    status VARCHAR(20) DEFAULT 'planned',
    "order" INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    date VARCHAR(10) NOT NULL,
    action VARCHAR(20) NOT NULL,
    ai_reasoning TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
