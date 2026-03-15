"""DeepSeek provider using the OpenAI-compatible chat completions API."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from core.llm.base import BaseLLMService
from core.llm.mock import MockLLMService
from core.tarot_catalog import enrich_fortune_card, tarot_reference_lines

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
        from core.llm import get_runtime_config
        config = get_runtime_config()
        self.api_key = config.get("api_key") or ""
        self.model = config.get("model") or "deepseek-chat"
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

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].rstrip()
        return text.strip()

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
            raw = self._strip_markdown_fences(self._call_deepseek(SYSTEM_PROMPT, prompt))
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

    def recommend_songs(
        self, mood_level: int, task_count: int, lang: str = "en",
        mood_note: str = "", top_tasks: str = "", refresh_token: str = "",
        exclude_songs: List[str] | None = None
    ) -> List[Dict[str, str]]:
        if not self.api_key:
            return self._fallback.recommend_songs(
                mood_level,
                task_count,
                lang,
                mood_note=mood_note,
                top_tasks=top_tasks,
                refresh_token=refresh_token,
                exclude_songs=exclude_songs,
            )

        lang_inst = "Respond in Simplified Chinese." if lang == "zh" else "Respond in English."
        mood_labels = {1: "terrible", 2: "bad", 3: "okay", 4: "good", 5: "amazing"}
        exclusion_block = ""
        if exclude_songs:
            exclusion_lines = "\n".join(f"- {item}" for item in exclude_songs[:12])
            exclusion_block = f"\nAvoid repeating these recently shown songs if possible:\n{exclusion_lines}\n"
        prompt = f"""The user is feeling "{mood_labels.get(mood_level, 'okay')}" (level {mood_level}/5).
They have {task_count} active tasks.{f' Mood note: {mood_note}' if mood_note else ''}
{f'Top tasks: {top_tasks}' if top_tasks else ''}
Refresh token: {refresh_token or 'initial-load'}
{exclusion_block}

Recommend exactly 14 songs that match their mood, current task load, and the emotional/cognitive needs implied by the task context.
This is not a generic playlist. Treat the task context as primary.
If the task context suggests writing, reading, coding, analysis, or study, bias toward deep-focus tracks with low lyrical interference.
If the context suggests presentation, meeting, interview, or social activation, bias toward confidence-building, energizing tracks.
If mood is low, prefer regulation, grounding, and safety over hype.
If mood is high and the tasks are important, prefer momentum and precision instead of random party tracks.
Use the refresh token to intentionally explore a different but still coherent slice of music taste on each refresh.
Do not repeat the same obvious global hits every time. Vary genres, decades, artists, and languages while staying coherent.
For each song, include:
- name: song title
- artist: artist name
- album: album name
- mood_tag: one-word mood descriptor

{lang_inst}
Return ONLY a JSON array, no markdown fences."""

        try:
            raw = self._strip_markdown_fences(self._call_deepseek(
                "You are a music recommendation assistant. Return valid JSON only.",
                prompt, max_tokens=900,
            ))
            result = json.loads(raw)
            if isinstance(result, list) and len(result) > 0:
                return result[:14]
        except Exception as exc:
            logger.error("DeepSeek recommend_songs failed: %s", exc)

        return self._fallback.recommend_songs(
            mood_level,
            task_count,
            lang,
            mood_note=mood_note,
            top_tasks=top_tasks,
            refresh_token=refresh_token,
            exclude_songs=exclude_songs,
        )

    def generate_fortune(
        self, birthday: str, current_date: str, lang: str = "en",
        zodiac: Dict[str, str] = None, user_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        if not self.api_key:
            return self._fallback.generate_fortune(birthday, current_date, lang, zodiac=zodiac, user_context=user_context)

        lang_inst = "Respond in Simplified Chinese." if lang == "zh" else "Respond in English."
        zod = zodiac or {}
        ctx = user_context or {}

        zodiac_info = f"Western: {zod.get('western', 'unknown')}, Chinese: {zod.get('chinese', 'unknown')}"
        tarot_reference = "\n".join(tarot_reference_lines())
        prompt = f"""Generate a personalized daily tarot reading for today ({current_date}).

User info:
- Birthday: {birthday}
- Zodiac: {zodiac_info}
- Active tasks: {ctx.get('task_count', 0)}
- Top tasks:\n{ctx.get('top_tasks', 'None')}
- Current mood level: {ctx.get('mood_level', 'unknown')}/5
{f"- Mood note: {ctx.get('mood_note', '')}" if ctx.get('mood_note') else ''}

You must choose exactly ONE card from this Rider-Waite-Smith Major Arcana deck reference:
{tarot_reference}

Base the reading on the chosen card's imagery and its upright/reversed keywords.
Consider the user's zodiac sign, current tasks, and mood.
If there is a focus task or planned tasks, make the reading clearly react to them.

Return JSON with this exact structure:
{{
  "card_number": 0-21,
  "is_reversed": true/false,
  "interpretation": "2-3 sentences personalized to user's tasks and zodiac",
  "auspicious": ["3 favorable activities for today based on their tasks"],
  "inauspicious": ["2 activities to avoid"],
  "lucky_color": "a color",
  "advice": "one sentence of actionable wisdom",
  "zodiac_label": "Western sign · Chinese zodiac",
  "focus_task": "the main task the reading points to, or empty string",
  "planned_tasks": ["up to 3 task titles from today's plan"],
  "visual_theme": "a short visual mood such as moonlit, solar, velvet, ember, oceanic"
}}

{lang_inst}
Return ONLY the JSON object, no markdown fences."""

        try:
            raw = self._strip_markdown_fences(self._call_deepseek(
                "You are a mystical tarot reader who gives insightful, personalized readings. Return valid JSON only.",
                prompt, max_tokens=800,
            ))
            result = json.loads(raw)
            if isinstance(result, dict) and "card_number" in result:
                result = enrich_fortune_card(result, lang)
                result.setdefault("focus_task", ctx.get("focus_task", ""))
                result.setdefault("planned_tasks", ctx.get("planned_tasks", []))
                result.setdefault("visual_theme", "velvet")
                result.setdefault("zodiac_label", zodiac_info)
                return result
        except Exception as exc:
            logger.error("DeepSeek generate_fortune failed: %s", exc)

        return self._fallback.generate_fortune(birthday, current_date, lang, zodiac=zodiac, user_context=user_context)
