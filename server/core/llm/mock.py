"""Deterministic mock provider that mimics structured LLM outputs."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List
from urllib.parse import quote

from core.llm.base import BaseLLMService
from core.rules import localize_rule_reasons
from core.tarot_catalog import MAJOR_ARCANA, enrich_fortune_card


def _spotify_search_url(name: str, artist: str) -> str:
    q = quote(f"{name} {artist}")
    return f"https://open.spotify.com/search/{q}"


class MockLLMService(BaseLLMService):
    """Rule-following mock used for local development and testing."""

    def _localized_reasoning(self, capacity: int, required: int, overload: int) -> str:
        if self.lang == "zh":
            return (
                f"当前容量是 {capacity}，需求工作量是 {required}。"
                f'{"计划已超载，需要继续删减承诺。" if overload > 0 else "当前计划仍在容量范围内。"}'
            )
        return (
            f"Capacity is {capacity} units and required work is {required}. "
            f'{"Plan is overloaded; cut commitments." if overload > 0 else "Plan fits current capacity."}'
        )

    def recommend_decisions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tasks: List[Dict[str, Any]] = context.get("tasks", [])
        rule_snapshot: Dict[str, Any] = context.get("rule_snapshot", {})

        selected_ids = list(rule_snapshot.get("selected_task_ids", []))
        deferred_ids = list(rule_snapshot.get("deferred_task_ids", []))
        candidates = list(rule_snapshot.get("deletion_candidates", []))

        delete_items = []
        for item in candidates[:3]:
            task_id = int(item["task_id"])
            task_title = ""
            for task in tasks:
                if int(task["id"]) == task_id:
                    task_title = task.get("title", "")
                    break
            if self.lang == "zh":
                reason = f'规则层判断"{task_title or task_id}"重复表现出低承诺信号。'
            else:
                reason = f'Rule signals repeated low commitment for "{task_title or task_id}".'
            delete_items.append({"task_id": task_id, "reason": reason})

        capacity = int(rule_snapshot.get("capacity_units", 0) or 0)
        required = int(rule_snapshot.get("required_units", 0) or 0)
        overload = int(rule_snapshot.get("overload_units", 0) or 0)
        reasoning = self._localized_reasoning(capacity, required, overload)

        return {
            "keep": selected_ids,
            "defer": deferred_ids,
            "delete": delete_items,
            "reasoning": reasoning,
            "confidence": 0.65,
        }

    def generate_deletion_reasoning(
        self, task: Dict[str, Any], rule_reasons: List[str]
    ) -> str:
        title = task.get("title", "This task")
        localized_reasons = localize_rule_reasons(rule_reasons, self.lang)
        base = f'考虑删除"{title}"。' if self.lang == "zh" else f'Consider deleting "{title}".'
        if rule_reasons:
            connector = "原因：" if self.lang == "zh" else "Reasons: "
            return f'{base} {connector}{" ".join(localized_reasons)}'
        return base

    def recommend_songs(
        self, mood_level: int, task_count: int, lang: str = "en",
        mood_note: str = "", top_tasks: str = "", refresh_token: str = "",
        exclude_songs: List[str] | None = None
    ) -> List[Dict[str, str]]:
        songs_by_mood = {
            1: [
                {"name": "Fix You", "artist": "Coldplay", "album": "X&Y",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02de09e02aa7febf30b7c02d82"},
                {"name": "Lean on Me", "artist": "Bill Withers", "album": "Still Bill",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02508442956935e39f0e1b2963"},
                {"name": "Here Comes the Sun", "artist": "The Beatles", "album": "Abbey Road",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02dc30583ba717007b00cceb25"},
                {"name": "Holocene", "artist": "Bon Iver", "album": "Bon Iver, Bon Iver"},
                {"name": "Vienna", "artist": "Billy Joel", "album": "The Stranger"},
                {"name": "Blue Banisters", "artist": "Lana Del Rey", "album": "Blue Banisters"},
            ],
            2: [
                {"name": "Let It Be", "artist": "The Beatles", "album": "Let It Be",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e020e2169f0cfb1e3ba3d750bde"},
                {"name": "Breathe Me", "artist": "Sia", "album": "Colour the Small One",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e025c4e475e5d4a97dd1e0d91ac"},
                {"name": "Skinny Love", "artist": "Bon Iver", "album": "For Emma, Forever Ago",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02d5ec78e0ef7cfd7463151eb4"},
                {"name": "Motion Sickness", "artist": "Phoebe Bridgers", "album": "Stranger in the Alps"},
                {"name": "Cigarette Daydreams", "artist": "Cage the Elephant", "album": "Melophobia"},
                {"name": "Ribs", "artist": "Lorde", "album": "Pure Heroine"},
            ],
            3: [
                {"name": "Clocks", "artist": "Coldplay", "album": "A Rush of Blood to the Head",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02de09e02aa7febf30b7c02d82"},
                {"name": "Electric Feel", "artist": "MGMT", "album": "Oracular Spectacular",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e028b32b139981e79f2ebe005eb"},
                {"name": "Sunflower", "artist": "Post Malone", "album": "Spider-Man Soundtrack",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02e2e352d89826aef6dbd16444"},
                {"name": "Float On", "artist": "Modest Mouse", "album": "Good News for People Who Love Bad News"},
                {"name": "Dreams", "artist": "Fleetwood Mac", "album": "Rumours"},
                {"name": "Tongue Tied", "artist": "Grouplove", "album": "Never Trust a Happy Song"},
            ],
            4: [
                {"name": "Walking on Sunshine", "artist": "Katrina & The Waves", "album": "Walking on Sunshine",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e025f38d4ec4b9b3e0adae18dfe"},
                {"name": "Good as Hell", "artist": "Lizzo", "album": "Cuz I Love You",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e024b3de4c78f64214a29be5fb1"},
                {"name": "Happy", "artist": "Pharrell Williams", "album": "G I R L",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02e8107e6d9214baa81bb79bba"},
                {"name": "Shut Up and Dance", "artist": "WALK THE MOON", "album": "Talking Is Hard"},
                {"name": "Dog Days Are Over", "artist": "Florence + The Machine", "album": "Lungs"},
                {"name": "Freedom! '90", "artist": "George Michael", "album": "Listen Without Prejudice Vol. 1"},
            ],
            5: [
                {"name": "Don't Stop Me Now", "artist": "Queen", "album": "Jazz",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02008b06ec3019aea6400b8e7a"},
                {"name": "Uptown Funk", "artist": "Bruno Mars", "album": "Uptown Special",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e02e419ccba0baa8bd3f3d7abf2"},
                {"name": "Levitating", "artist": "Dua Lipa", "album": "Future Nostalgia",
                 "cover_url": "https://i.scdn.co/image/ab67616d00001e024bc66095f8a70bc4e6593f4f"},
                {"name": "Blinding Lights", "artist": "The Weeknd", "album": "After Hours"},
                {"name": "On Top of the World", "artist": "Imagine Dragons", "album": "Night Visions"},
                {"name": "Run Away With Me", "artist": "Carly Rae Jepsen", "album": "E•MO•TION"},
            ],
        }
        songs = list(songs_by_mood.get(mood_level, songs_by_mood[3]))
        if refresh_token:
            seed = hashlib.md5(f"{mood_level}:{refresh_token}".encode()).hexdigest()
            shift = int(seed[:2], 16) % len(songs)
            songs = songs[shift:] + songs[:shift]
        blocked = {item.strip().casefold() for item in (exclude_songs or []) if item.strip()}
        if blocked:
            fresh = [
                song for song in songs
                if f'{song.get("name", "").strip().casefold()} — {song.get("artist", "").strip().casefold()}' not in blocked
            ]
            songs = fresh + [song for song in songs if song not in fresh]
        # Add mood_tag and spotify_url
        mood_tags = {1: "healing", 2: "gentle", 3: "chill", 4: "bright", 5: "energetic"}
        tag = mood_tags.get(mood_level, "chill")
        for song in songs:
            song["mood_tag"] = song.get("mood_tag", tag)
            song["spotify_url"] = _spotify_search_url(song["name"], song["artist"])
        return songs[:12]

    def generate_fortune(
        self, birthday: str, current_date: str, lang: str = "en",
        zodiac: Dict[str, str] = None, user_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        import hashlib

        seed = hashlib.md5(f"{birthday}:{current_date}".encode()).hexdigest()

        idx = int(seed[:2], 16) % 22
        card = MAJOR_ARCANA[idx]
        is_reversed = int(seed[2:4], 16) % 3 == 0  # ~33% chance reversed

        # Zodiac info
        zod = zodiac or {}
        zodiac_label = (
            f'{zod.get("western_zh", "")} · {zod.get("chinese_zh", "")}'
            if lang == "zh"
            else f'{zod.get("western", "")} · {zod.get("chinese", "")}'
        )

        # Context-aware interpretation
        ctx = user_context or {}
        task_count = ctx.get("task_count", 0)
        focus_task = ctx.get("focus_task", "")
        planned_tasks = list(ctx.get("planned_tasks", []))
        visual_themes = [
            "starlit", "ember", "moonlit", "garden", "marble", "ritual", "rose",
            "velocity", "lionheart", "mist", "orbit", "balance", "haze", "phoenix",
            "alchemy", "midnight", "lightning", "aether", "tide", "solar", "echo", "cosmic",
        ]

        if lang == "zh":
            interp_templates = [
                f"愚者牌出现——今天适合放下执念，尝试全新的方式。你目前有{task_count}个任务，不妨先放空再出发。",
                f"魔术师降临——你手中已有一切所需的工具。{task_count}个任务看似多，但你的创造力足以应对。",
                "女祭司提示你倾听内心的声音。今天适合独处思考，不急于做大决定。",
                "女皇带来丰盛的能量——今天适合照顾自己，也照顾身边的人。",
                f"皇帝牌意味着结构与秩序。你的{task_count}个任务需要一个清晰的优先级排序。",
                "教皇代表传统智慧——今天适合向有经验的人请教，或回顾已有的方法。",
                "恋人牌出现——关注你的选择。今天的决定会影响未来的方向。",
                f"战车牌意味着前进的动力！{task_count}个任务？全力冲刺，你有这个力量。",
                "力量牌提醒你——真正的力量来自耐心和温柔，而非蛮力。",
                "隐者牌建议你今天退一步，给自己安静的空间来思考。",
                "命运之轮在转动——变化即将来临，保持灵活应对。",
                "正义牌要求公平与平衡。今天做决定时要考虑长远影响。",
                "倒吊人提示换个角度看问题。暂停一下，也许答案就在转换视角中。",
                "死神牌象征着结束与新生——该放下的就放下，为新事物腾出空间。",
                "节制牌建议保持平衡——不要在任何一件事上投入过多。",
                "恶魔牌提醒你注意那些让你上瘾或分心的事物。",
                "塔牌虽然吓人，但破坏带来重建的机会。拥抱变化。",
                "星星牌带来希望——即使任务繁重，前方依然光明。",
                "月亮牌暗示不确定性。今天可能感到迷茫，但这是正常的。",
                f"太阳牌带来活力！{task_count}个任务？今天的能量足以应对。",
                "审判牌呼唤你做出重要评估——哪些任务真正值得你的时间？",
                "世界牌象征圆满——一个阶段即将结束，庆祝你的成就。",
            ]
            auspicious_templates = [
                ["冒险尝试新事物", "出门散步", "打破常规"],
                ["创意项目", "学习新工具", "展示成果"],
                ["冥想", "写日记", "独处反思"],
                ["照顾自己", "和朋友聊天", "慢节奏"],
                ["制定计划", "整理工作空间", "做重要决策"],
                ["请教前辈", "复习旧知识", "团队讨论"],
                ["做选择题", "深度对话", "表达感受"],
                ["全力推进项目", "运动", "设定目标"],
                ["耐心处理难题", "安慰他人", "自我关怀"],
                ["独处思考", "读书", "整理思绪"],
                ["拥抱变化", "尝试不同方法", "灵活调整"],
                ["公平处事", "权衡利弊", "签合同"],
                ["换角度思考", "暂停休息", "观察周围"],
                ["断舍离", "结束拖延的事", "重新开始"],
                ["保持节制", "合理分配时间", "健康饮食"],
                ["认清诱惑", "设定边界", "戒掉坏习惯"],
                ["接受改变", "打破僵局", "重新规划"],
                ["许愿", "规划未来", "保持信心"],
                ["艺术创作", "做梦", "灵感捕捉"],
                ["享受阳光", "社交活动", "积极行动"],
                ["自我评估", "做重大决定", "回顾成就"],
                ["庆祝", "完成收尾", "分享成果"],
            ]
            inauspicious_templates = [
                ["固执己见", "过度冒险"],
                ["忽视细节", "急于求成"],
                ["忽略直觉", "过度依赖他人"],
                ["过度消费", "忽视健康"],
                ["犹豫不决", "独裁作风"],
                ["盲目跟从", "拒绝新观点"],
                ["逃避选择", "三心二意"],
                ["急躁冲动", "忽视身体信号"],
                ["强迫自己", "咄咄逼人"],
                ["逃避社交", "过度自闭"],
                ["抗拒改变", "固守旧方式"],
                ["偏见判断", "过度纠结"],
                ["拖延逃避", "固执不变"],
                ["执着不放", "害怕改变"],
                ["暴饮暴食", "工作过度"],
                ["沉迷手机", "拖延"],
                ["抗拒必要改变", "逃避现实"],
                ["过度理想化", "脱离现实"],
                ["过度焦虑", "猜疑不信"],
                ["过度乐观", "忽略风险"],
                ["自我批判过度", "后悔过去"],
                ["拒绝结束", "贪心不足"],
            ]
            colors = ["红色", "蓝色", "绿色", "紫色", "金色", "白色",
                       "橙色", "粉色", "银色", "靛蓝", "棕色", "黑色"]
        else:
            interp_templates = [
                f"The Fool appears — today favors fresh starts. With {task_count} tasks, consider dropping one and trying something new.",
                f"The Magician is here — you have all the tools you need. Your {task_count} tasks are manageable with focus.",
                "High Priestess urges you to trust your gut. Step back from the noise and listen within.",
                "The Empress brings abundance — nurture yourself and those around you today.",
                f"The Emperor demands structure. Prioritize your {task_count} tasks with clear hierarchy.",
                "The Hierophant suggests seeking guidance from mentors or proven methods.",
                "The Lovers card appears — today's choices carry weight. Choose deliberately.",
                f"The Chariot drives you forward! {task_count} tasks? Charge through them with determination.",
                "Strength reminds you — true power is patience and gentleness, not force.",
                "The Hermit advises solitude. Take a step back for clarity.",
                "Wheel of Fortune is turning — change is coming. Stay adaptable.",
                "Justice demands balance. Weigh your decisions carefully today.",
                "The Hanged Man suggests a new perspective. Pause and look from a different angle.",
                "Death signals transformation — let go of what no longer serves you.",
                "Temperance advises moderation — don't overcommit to any single thing.",
                "The Devil warns of distractions. Set boundaries with what drains your focus.",
                "The Tower brings sudden change — embrace the rebuilding opportunity.",
                "The Star brings hope — even with a heavy load, the future is bright.",
                "The Moon hints at uncertainty. It's okay to feel unsure today.",
                f"The Sun radiates energy! {task_count} tasks? You've got the vitality to handle them.",
                "Judgement calls for honest self-assessment — which tasks truly deserve your time?",
                "The World signals completion — celebrate what you've accomplished.",
            ]
            auspicious_templates = [
                ["Try something completely new", "Take a walk", "Break routines"],
                ["Creative projects", "Learn a new tool", "Show your work"],
                ["Meditation", "Journaling", "Solo reflection"],
                ["Self-care", "Catching up with friends", "Slowing down"],
                ["Making plans", "Organizing workspace", "Big decisions"],
                ["Asking for advice", "Reviewing past work", "Team discussions"],
                ["Making choices", "Deep conversations", "Expressing feelings"],
                ["Pushing projects forward", "Exercise", "Setting goals"],
                ["Patient problem-solving", "Comforting others", "Self-compassion"],
                ["Solo thinking time", "Reading", "Organizing thoughts"],
                ["Embracing change", "Trying different approaches", "Being flexible"],
                ["Fair dealings", "Weighing options", "Contracts & agreements"],
                ["Changing perspectives", "Taking a break", "Observing"],
                ["Letting go", "Ending procrastination", "Fresh starts"],
                ["Moderation", "Time management", "Healthy eating"],
                ["Recognizing distractions", "Setting boundaries", "Breaking bad habits"],
                ["Accepting change", "Breaking deadlocks", "Replanning"],
                ["Wishing & hoping", "Future planning", "Staying hopeful"],
                ["Art & creativity", "Dreaming", "Catching inspiration"],
                ["Enjoying sunshine", "Social activities", "Positive action"],
                ["Self-evaluation", "Major decisions", "Reviewing achievements"],
                ["Celebrating", "Finishing things", "Sharing results"],
            ]
            inauspicious_templates = [
                ["Being stubborn", "Excessive risk-taking"],
                ["Ignoring details", "Rushing things"],
                ["Ignoring intuition", "Over-relying on others"],
                ["Overspending", "Neglecting health"],
                ["Indecisiveness", "Being too controlling"],
                ["Blindly following", "Rejecting new ideas"],
                ["Avoiding choices", "Being indecisive"],
                ["Impatience", "Ignoring body signals"],
                ["Forcing outcomes", "Being aggressive"],
                ["Avoiding social contact", "Over-isolation"],
                ["Resisting change", "Sticking to old ways"],
                ["Biased judgement", "Overthinking"],
                ["Procrastinating", "Refusing to adapt"],
                ["Clinging to the past", "Fear of change"],
                ["Overworking", "Overindulging"],
                ["Doom-scrolling", "Procrastinating"],
                ["Resisting necessary change", "Escaping reality"],
                ["Being too idealistic", "Losing touch with reality"],
                ["Excessive worry", "Suspicion"],
                ["Over-optimism", "Ignoring risks"],
                ["Harsh self-criticism", "Regretting the past"],
                ["Refusing closure", "Greediness"],
            ]
            colors = ["Red", "Blue", "Green", "Purple", "Gold", "White",
                       "Orange", "Pink", "Silver", "Indigo", "Brown", "Black"]

        color_idx = int(seed[4:6], 16) % len(colors)

        if focus_task:
            if lang == "zh":
                advice = f"今天先围绕“{focus_task}”行动，不要把注意力摊得太开。"
            else:
                advice = f"Center today around '{focus_task}' instead of scattering your attention."
        else:
            advice = interp_templates[idx].split(".")[-1].strip() or interp_templates[idx]

        fortune = {
            "card_number": card["number"],
            "is_reversed": is_reversed,
            "interpretation": interp_templates[idx],
            "auspicious": auspicious_templates[idx],
            "inauspicious": inauspicious_templates[idx],
            "lucky_color": colors[color_idx],
            "advice": advice,
            "zodiac_label": zodiac_label,
            "focus_task": focus_task,
            "planned_tasks": planned_tasks[:3],
            "visual_theme": visual_themes[idx],
        }
        return enrich_fortune_card(fortune, lang)
