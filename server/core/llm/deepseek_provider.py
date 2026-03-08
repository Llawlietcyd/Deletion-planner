"""DeepSeek provider using the OpenAI-compatible chat completions API."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from core.llm.base import BaseLLMService
from core.llm.mock import MockLLMService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Deletion-First Daily Planning Assistant. Your primary instinct is to question, reduce, and eliminate tasks, not to add or schedule.

Rules:
1. A shorter, achievable plan beats a full plan that collapses by noon.
2. Non-negotiable tasks (priority >= 5, category "core", or containing "must") must always be kept.
3. Respect the user's capacity constraints and never plan more work than fits.
4. Actively recommend tasks for deletion when they show low commitment signals (repeated deferrals, low completion rate).
5. Explain every trade-off you make in plain language.
"""

DECISION_PROMPT_TEMPLATE = """\
Today is {target_date}. The user has {task_count} active tasks.
Capacity: {capacity_units} units. Required: {required_units} units. Overloaded: {is_overloaded}.

Tasks (id | title | priority | effort | deferral_count | completion_count | non_negotiable | keep_score):
{task_table}

Rule layer pre-selection:
- Selected: {selected_ids}
- Deferred: {deferred_ids}
- Deletion candidates: {deletion_candidates}

Instructions:
1. Review the rule layer's decisions. You may adjust keep/defer, but NEVER remove a non-negotiable task.
2. For deletion candidates, provide a clear, empathetic reason why each should be deleted.
3. Return your response as valid JSON with this exact structure:
{{
  "keep": [task_id, ...],
  "defer": [task_id, ...],
  "delete": [{{"task_id": int, "reason": "string"}}, ...],
  "reasoning": "A 2-3 sentence explanation of your planning logic and trade-offs.",
  "confidence": 0.0-1.0
}}

{lang_instruction}
Return ONLY the JSON object, no markdown fences or extra text.
"""

DELETION_PROMPT_TEMPLATE = """\
Task: "{title}" (priority {priority}, deferred {deferral_count}x, completed {completion_count}x)
Rule signals: {rule_reasons}

Write a brief, empathetic 1-2 sentence explanation for why this task should be considered for deletion.
Be direct but kind. {lang_instruction}
"""


class DeepSeekLLMService(BaseLLMService):
    """DeepSeek API provider for AI-powered planning decisions."""

    def __init__(self, lang: str = "en"):
        super().__init__(lang=lang)
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._fallback = MockLLMService(lang=lang)

        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not set; DeepSeek provider will fall back to mock.")

    def _lang_instruction(self) -> str:
        if self.lang == "zh":
            return "Respond in Simplified Chinese."
        return "Respond in English."

    def _call_deepseek(self, system: str, user: str, max_tokens: int = 1024) -> str:
        import urllib.request

        url = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com") + "/chat/completions"
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
                "max_tokens": max_tokens,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))

        return body["choices"][0]["message"]["content"].strip()

    def recommend_decisions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            return self._fallback.recommend_decisions(context)

        tasks: List[Dict[str, Any]] = context.get("tasks", [])
        rule_snapshot: Dict[str, Any] = context.get("rule_snapshot", {})
        target_date = context.get("target_date", "today")
        task_meta = rule_snapshot.get("task_meta", {})

        rows = []
        for task in tasks:
            task_id = int(task["id"])
            meta = task_meta.get(task_id, {})
            rows.append(
                f'{task_id} | {task.get("title", "")} | '
                f'P{task.get("priority", 0)} | '
                f'{meta.get("effort_units", 1)}u | '
                f'def:{task.get("deferral_count", 0)} | '
                f'done:{task.get("completion_count", 0)} | '
                f'{"YES" if meta.get("non_negotiable") else "no"} | '
                f'{meta.get("keep_score", 0)}'
            )
        task_table = "\n".join(rows) if rows else "(no tasks)"

        deletion_info = []
        for candidate in rule_snapshot.get("deletion_candidates", []):
            deletion_info.append(
                f'id={candidate["task_id"]} reasons={candidate.get("rule_reasons", [])}'
            )

        prompt = DECISION_PROMPT_TEMPLATE.format(
            target_date=target_date,
            task_count=len(tasks),
            capacity_units=rule_snapshot.get("capacity_units", 6),
            required_units=rule_snapshot.get("required_units", 0),
            is_overloaded=rule_snapshot.get("is_overloaded", False),
            task_table=task_table,
            selected_ids=rule_snapshot.get("selected_task_ids", []),
            deferred_ids=rule_snapshot.get("deferred_task_ids", []),
            deletion_candidates="; ".join(deletion_info) or "none",
            lang_instruction=self._lang_instruction(),
        )

        try:
            raw = self._call_deepseek(SYSTEM_PROMPT, prompt)
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
            result = json.loads(raw)
            if not isinstance(result.get("keep"), list):
                raise ValueError("Missing 'keep' list")
            return {
                "keep": result.get("keep", []),
                "defer": result.get("defer", []),
                "delete": result.get("delete", []),
                "reasoning": result.get("reasoning", ""),
                "confidence": float(result.get("confidence", 0.7)),
            }
        except Exception as exc:
            logger.error("DeepSeek recommend_decisions failed: %s", exc)
            return self._fallback.recommend_decisions(context)

    def generate_deletion_reasoning(
        self, task: Dict[str, Any], rule_reasons: List[str]
    ) -> str:
        if not self.api_key:
            return self._fallback.generate_deletion_reasoning(task, rule_reasons)

        prompt = DELETION_PROMPT_TEMPLATE.format(
            title=task.get("title", ""),
            priority=task.get("priority", 0),
            deferral_count=task.get("deferral_count", 0),
            completion_count=task.get("completion_count", 0),
            rule_reasons="; ".join(rule_reasons) if rule_reasons else "No specific rule triggers.",
            lang_instruction=self._lang_instruction(),
        )

        try:
            return self._call_deepseek(SYSTEM_PROMPT, prompt, max_tokens=256)
        except Exception as exc:
            logger.error("DeepSeek deletion reasoning failed: %s", exc)
            return self._fallback.generate_deletion_reasoning(task, rule_reasons)
