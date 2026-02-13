"""Mock LLM service using rule-based logic.

This replaces AI calls during development. The rules simulate
intelligent classification, planning, and deletion reasoning.
Supports bilingual output (en / zh).
"""

from typing import List, Dict, Any
from core.llm.base import BaseLLMService

# Keywords that hint at task importance
HIGH_PRIORITY_KEYWORDS = [
    "deadline", "urgent", "important", "submit", "due", "exam",
    "meeting", "presentation", "client", "deploy", "fix", "bug",
    "截止", "紧急", "重要", "提交", "考试", "会议", "演示", "部署", "修复",
]

LOW_PRIORITY_KEYWORDS = [
    "maybe", "someday", "nice to have", "optional", "explore", "research",
    "read", "think about", "consider", "organize",
    "也许", "以后", "可选", "探索", "研究", "阅读", "考虑", "整理",
]


class MockLLMService(BaseLLMService):
    """Rule-based mock that simulates LLM behavior for development."""

    def __init__(self, lang="en"):
        self.lang = lang

    def classify_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for t in tasks:
            text = f"{t.get('title', '')} {t.get('description', '')}".lower()
            deferral_count = t.get("deferral_count", 0)
            priority = t.get("priority", 0)

            if deferral_count >= 3:
                category = "deletion_candidate"
                reason = (
                    f"这个任务已被推迟了 {deferral_count} 次，考虑一下它是否真的重要。"
                    if self.lang == "zh" else
                    f"This task has been deferred {deferral_count} times. "
                    "Consider whether it truly matters."
                )
            elif any(kw in text for kw in HIGH_PRIORITY_KEYWORDS) or priority >= 3:
                category = "core"
                reason = (
                    "这个任务包含紧急指标或具有高优先级。"
                    if self.lang == "zh" else
                    "This task contains urgency indicators or has high priority."
                )
            elif any(kw in text for kw in LOW_PRIORITY_KEYWORDS):
                category = "deferrable"
                reason = (
                    "这个任务看起来是可选的或探索性的。"
                    if self.lang == "zh" else
                    "This task appears optional or exploratory."
                )
            elif deferral_count >= 1:
                category = "deferrable"
                reason = (
                    f"这个任务已被推迟了 {deferral_count} 次。"
                    if self.lang == "zh" else
                    f"This task has been deferred {deferral_count} time(s)."
                )
            else:
                category = "core"
                reason = (
                    "这个任务看起来是可执行且相关的。"
                    if self.lang == "zh" else
                    "This task looks actionable and relevant."
                )

            results.append({
                "task_id": t["id"],
                "category": category,
                "reason": reason,
            })
        return results

    def generate_plan_reasoning(
        self,
        selected_tasks: List[Dict[str, Any]],
        deferred_tasks: List[Dict[str, Any]],
        deletion_suggestions: List[Dict[str, Any]],
    ) -> str:
        parts = []

        if self.lang == "zh":
            parts.append(
                f"今天的计划聚焦于 {len(selected_tasks)} 个核心任务，"
                f"让你的工作量保持现实可行。"
            )
            if deferred_tasks:
                titles = "、".join(t.get("title", "未命名") for t in deferred_tasks[:3])
                parts.append(
                    f"{len(deferred_tasks)} 个任务今天被推迟：{titles}。"
                    "它们将留在你的待办列表中。"
                )
            if deletion_suggestions:
                titles = "、".join(s.get("title", "未命名") for s in deletion_suggestions[:2])
                parts.append(
                    f"建议删除：{titles}。"
                    "这些任务被反复推迟——如果所有事情都重要，那就没有事情是重要的。"
                )
            if not deferred_tasks and not deletion_suggestions:
                parts.append("你的任务量看起来很均衡，保持专注！")
        else:
            parts.append(
                f"Today's plan focuses on {len(selected_tasks)} core task(s) "
                f"to keep your workload realistic and achievable."
            )
            if deferred_tasks:
                titles = ", ".join(t.get("title", "untitled") for t in deferred_tasks[:3])
                parts.append(
                    f"{len(deferred_tasks)} task(s) have been deferred for today: {titles}. "
                    "They will remain in your backlog."
                )
            if deletion_suggestions:
                titles = ", ".join(s.get("title", "untitled") for s in deletion_suggestions[:2])
                parts.append(
                    f"Consider deleting: {titles}. "
                    "These tasks have been repeatedly postponed — "
                    "if everything is important, nothing is important."
                )
            if not deferred_tasks and not deletion_suggestions:
                parts.append("Your task load looks balanced. Stay focused!")

        return " ".join(parts)

    def generate_deletion_reasoning(self, task: Dict[str, Any]) -> str:
        deferral_count = task.get("deferral_count", 0)
        title = task.get("title", "This task")

        if self.lang == "zh":
            if deferral_count >= 5:
                return (
                    f"「{title}」已被推迟了 {deferral_count} 次。"
                    "这个强烈的模式表明它可能不是真正的优先事项。"
                    "删除它将为真正重要的事情腾出心智空间。"
                )
            elif deferral_count >= 3:
                return (
                    f"「{title}」已被推迟了 {deferral_count} 次。"
                    "反复推迟通常表明实际承诺度较低。"
                    "考虑今天就完成它，或者干脆删除它。"
                )
            else:
                return (
                    f"「{title}」可能不符合你当前的目标。"
                    "审视一下这个任务是否仍然相关。"
                )
        else:
            if deferral_count >= 5:
                return (
                    f'"{title}" has been deferred {deferral_count} times over multiple days. '
                    "This strong pattern suggests it may not be a real priority. "
                    "Deleting it will free mental space for what truly matters."
                )
            elif deferral_count >= 3:
                return (
                    f'"{title}" has been deferred {deferral_count} times. '
                    "Repeated postponement often indicates low actual commitment. "
                    "Consider either committing to it today or removing it."
                )
            else:
                return (
                    f'"{title}" may not align with your current goals. '
                    "Review whether this task is still relevant."
                )
