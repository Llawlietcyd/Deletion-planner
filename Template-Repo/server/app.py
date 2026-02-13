from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys

# Add the server directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db
from api_endpoints.tasks.handler import (
    ListTasksHandler, CreateTaskHandler, BatchCreateTasksHandler,
    UpdateTaskHandler, DeleteTaskHandler,
)
from api_endpoints.plans.handler import (
    GeneratePlanHandler, GetPlanHandler, GetTodayPlanHandler,
)
from api_endpoints.feedback.handler import (
    SubmitFeedbackHandler, GetHistoryHandler, GetStatsHandler,
)

app = Flask(__name__)
CORS(app)

# Initialize database on startup
with app.app_context():
    init_db()

# ── Health Check ─────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "Deletion Planner API"})

# ── Task Endpoints ───────────────────────────────────────────
@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    return ListTasksHandler(request)

@app.route("/api/tasks", methods=["POST"])
def create_task():
    return CreateTaskHandler(request)

@app.route("/api/tasks/batch", methods=["POST"])
def batch_create_tasks():
    return BatchCreateTasksHandler(request)

@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    return UpdateTaskHandler(request, task_id)

@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    return DeleteTaskHandler(request, task_id)

# ── Plan Endpoints ───────────────────────────────────────────
@app.route("/api/plans/generate", methods=["POST"])
def generate_plan():
    return GeneratePlanHandler(request)

@app.route("/api/plans/today", methods=["GET"])
def get_today_plan():
    return GetTodayPlanHandler(request)

@app.route("/api/plans/<plan_date>", methods=["GET"])
def get_plan(plan_date):
    return GetPlanHandler(request, plan_date)

# ── Feedback & Stats Endpoints ───────────────────────────────
@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    return SubmitFeedbackHandler(request)

@app.route("/api/history", methods=["GET"])
def get_history():
    return GetHistoryHandler(request)

@app.route("/api/stats", methods=["GET"])
def get_stats():
    return GetStatsHandler(request)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
