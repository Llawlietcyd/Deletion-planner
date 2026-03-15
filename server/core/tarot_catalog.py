"""Canonical Rider-Waite-Smith Major Arcana card data."""

from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import quote


def _commons_redirect(filename: str) -> str:
    return f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{quote(filename)}"


MAJOR_ARCANA: List[Dict[str, Any]] = [
    {
        "number": 0,
        "key": "fool",
        "en": "The Fool",
        "zh": "愚者",
        "symbol": "🃏",
        "image_url": _commons_redirect("RWS Tarot 00 Fool.jpg"),
        "imagery": "traveler at a cliff edge with white rose, little dog, bright sky, and light pack",
        "upright": ["leap", "beginnings", "trust", "openness"],
        "reversed": ["naivety", "drift", "impulse", "carelessness"],
    },
    {
        "number": 1,
        "key": "magician",
        "en": "The Magician",
        "zh": "魔术师",
        "symbol": "🎩",
        "image_url": _commons_redirect("RWS Tarot 01 Magician.jpg"),
        "imagery": "figure at a table with wand raised, tools of all suits, infinity above the head",
        "upright": ["skill", "focus", "agency", "execution"],
        "reversed": ["scattered power", "trickery", "overpromising", "misfire"],
    },
    {
        "number": 2,
        "key": "high-priestess",
        "en": "The High Priestess",
        "zh": "女祭司",
        "symbol": "🌙",
        "image_url": _commons_redirect("RWS Tarot 02 High Priestess.jpg"),
        "imagery": "priestess between black and white pillars, moon crown, scroll, veil of pomegranates",
        "upright": ["intuition", "stillness", "inner knowing", "discernment"],
        "reversed": ["blocked intuition", "distance", "withholding", "confusion"],
    },
    {
        "number": 3,
        "key": "empress",
        "en": "The Empress",
        "zh": "女皇",
        "symbol": "👑",
        "image_url": _commons_redirect("RWS Tarot 03 Empress.jpg"),
        "imagery": "crowned figure in a wheat field, flowing river, Venus shield, abundant garden",
        "upright": ["nurture", "abundance", "growth", "care"],
        "reversed": ["overgiving", "stagnation", "smothering", "neglect"],
    },
    {
        "number": 4,
        "key": "emperor",
        "en": "The Emperor",
        "zh": "皇帝",
        "symbol": "⚔️",
        "image_url": _commons_redirect("RWS Tarot 04 Emperor.jpg"),
        "imagery": "ruler on a stone throne with ram heads, red robes, mountains behind",
        "upright": ["structure", "order", "authority", "boundary"],
        "reversed": ["rigidity", "control", "stubbornness", "pressure"],
    },
    {
        "number": 5,
        "key": "hierophant",
        "en": "The Hierophant",
        "zh": "教皇",
        "symbol": "📿",
        "image_url": _commons_redirect("RWS Tarot 05 Hierophant.jpg"),
        "imagery": "religious teacher on a throne with crossed keys and two acolytes",
        "upright": ["tradition", "teaching", "ritual", "guidance"],
        "reversed": ["rebellion", "empty ritual", "dogma", "misfit"],
    },
    {
        "number": 6,
        "key": "lovers",
        "en": "The Lovers",
        "zh": "恋人",
        "symbol": "💕",
        "image_url": _commons_redirect("RWS Tarot 06 Lovers.jpg"),
        "imagery": "couple beneath an angel, mountain, tree of knowledge, tree of flame",
        "upright": ["alignment", "choice", "relationship", "values"],
        "reversed": ["misalignment", "avoidance", "mixed signals", "disharmony"],
    },
    {
        "number": 7,
        "key": "chariot",
        "en": "The Chariot",
        "zh": "战车",
        "symbol": "🏇",
        "image_url": _commons_redirect("RWS Tarot 07 Chariot.jpg"),
        "imagery": "armored driver in chariot with black and white sphinxes under a star canopy",
        "upright": ["momentum", "direction", "discipline", "victory"],
        "reversed": ["loss of control", "friction", "stall", "aggression"],
    },
    {
        "number": 8,
        "key": "strength",
        "en": "Strength",
        "zh": "力量",
        "symbol": "🦁",
        "image_url": _commons_redirect("RWS Tarot 08 Strength.jpg"),
        "imagery": "calm figure gently closing a lion's mouth beneath an infinity sign",
        "upright": ["courage", "calm power", "patience", "soft control"],
        "reversed": ["self-doubt", "depletion", "force", "frayed nerves"],
    },
    {
        "number": 9,
        "key": "hermit",
        "en": "The Hermit",
        "zh": "隐者",
        "symbol": "🏔️",
        "image_url": _commons_redirect("RWS Tarot 09 Hermit.jpg"),
        "imagery": "elder on a snowy summit with lantern and staff",
        "upright": ["solitude", "clarity", "search", "wisdom"],
        "reversed": ["isolation", "withdrawal", "avoidance", "overthinking"],
    },
    {
        "number": 10,
        "key": "wheel-of-fortune",
        "en": "Wheel of Fortune",
        "zh": "命运之轮",
        "symbol": "🎡",
        "image_url": _commons_redirect("RWS Tarot 10 Wheel of Fortune.jpg"),
        "imagery": "golden wheel in the sky with winged beings and turning creatures",
        "upright": ["turning point", "cycle", "timing", "change"],
        "reversed": ["delay", "resistance", "bad timing", "stuck loop"],
    },
    {
        "number": 11,
        "key": "justice",
        "en": "Justice",
        "zh": "正义",
        "symbol": "⚖️",
        "image_url": _commons_redirect("RWS Tarot 11 Justice.jpg"),
        "imagery": "seated figure with sword and scales between red curtains",
        "upright": ["truth", "balance", "decision", "accountability"],
        "reversed": ["bias", "avoidance", "unfairness", "self-justifying"],
    },
    {
        "number": 12,
        "key": "hanged-man",
        "en": "The Hanged Man",
        "zh": "倒吊人",
        "symbol": "🙃",
        "image_url": _commons_redirect("RWS Tarot 12 Hanged Man.jpg"),
        "imagery": "figure hanging upside down by one foot with glowing halo",
        "upright": ["pause", "surrender", "new view", "release"],
        "reversed": ["stalling", "martyrdom", "limbo", "resistance"],
    },
    {
        "number": 13,
        "key": "death",
        "en": "Death",
        "zh": "死神",
        "symbol": "🦋",
        "image_url": _commons_redirect("RWS Tarot 13 Death.jpg"),
        "imagery": "skeleton knight on white horse, rising sun, fallen crown, river",
        "upright": ["ending", "transition", "renewal", "shedding"],
        "reversed": ["clinging", "fear of change", "dragging on", "stagnation"],
    },
    {
        "number": 14,
        "key": "temperance",
        "en": "Temperance",
        "zh": "节制",
        "symbol": "🏺",
        "image_url": _commons_redirect("RWS Tarot 14 Temperance.jpg"),
        "imagery": "angel pouring water between cups, one foot on land and one in water",
        "upright": ["moderation", "flow", "integration", "healing"],
        "reversed": ["imbalance", "excess", "friction", "miscalibration"],
    },
    {
        "number": 15,
        "key": "devil",
        "en": "The Devil",
        "zh": "恶魔",
        "symbol": "🔥",
        "image_url": _commons_redirect("RWS Tarot 15 Devil.jpg"),
        "imagery": "horned figure above chained pair, torch, dark pedestal",
        "upright": ["attachment", "temptation", "shadow", "compulsion"],
        "reversed": ["release", "sobering up", "detaching", "breaking habit"],
    },
    {
        "number": 16,
        "key": "tower",
        "en": "The Tower",
        "zh": "高塔",
        "symbol": "⚡",
        "image_url": _commons_redirect("RWS Tarot 16 Tower.jpg"),
        "imagery": "lightning striking a tower, crown blown off, figures falling into black sky",
        "upright": ["shock", "truth break", "collapse", "wake-up"],
        "reversed": ["contained disruption", "avoiding rupture", "aftershock", "resistance"],
    },
    {
        "number": 17,
        "key": "star",
        "en": "The Star",
        "zh": "星星",
        "symbol": "⭐",
        "image_url": _commons_redirect("RWS Tarot 17 Star.jpg"),
        "imagery": "figure kneeling by water under one large star and seven smaller stars",
        "upright": ["hope", "restoration", "guidance", "gentle faith"],
        "reversed": ["dim hope", "fatigue", "distance", "discouragement"],
    },
    {
        "number": 18,
        "key": "moon",
        "en": "The Moon",
        "zh": "月亮",
        "symbol": "🌕",
        "image_url": _commons_redirect("RWS Tarot 18 Moon.jpg"),
        "imagery": "moon above a path with dog, wolf, crayfish, towers, and dark water",
        "upright": ["uncertainty", "dream", "subconscious", "sensitivity"],
        "reversed": ["clearing fog", "surfacing truth", "anxiety spillover", "illusion"],
    },
    {
        "number": 19,
        "key": "sun",
        "en": "The Sun",
        "zh": "太阳",
        "symbol": "☀️",
        "image_url": _commons_redirect("RWS Tarot 19 Sun.jpg"),
        "imagery": "child on a white horse before sunflowers under radiant sun",
        "upright": ["clarity", "warmth", "joy", "confidence"],
        "reversed": ["burnout", "overexposure", "ego", "forced brightness"],
    },
    {
        "number": 20,
        "key": "judgement",
        "en": "Judgement",
        "zh": "审判",
        "symbol": "📯",
        "image_url": _commons_redirect("RWS Tarot 20 Judgement.jpg"),
        "imagery": "angel with trumpet above people rising from coffins in grey sea",
        "upright": ["reckoning", "calling", "evaluation", "release"],
        "reversed": ["avoidance", "self-criticism", "delay", "hesitation"],
    },
    {
        "number": 21,
        "key": "world",
        "en": "The World",
        "zh": "世界",
        "symbol": "🌍",
        "image_url": _commons_redirect("RWS Tarot 21 World.jpg"),
        "imagery": "wreath framing dancing figure with four fixed creatures in the corners",
        "upright": ["completion", "wholeness", "integration", "arrival"],
        "reversed": ["unfinished loop", "loose ends", "delay", "partial closure"],
    },
]

MAJOR_ARCANA_BY_NUMBER = {card["number"]: card for card in MAJOR_ARCANA}


def tarot_reference_lines() -> List[str]:
    return [
        (
            f'{card["number"]}: {card["en"]} | imagery: {card["imagery"]} | '
            f'upright: {", ".join(card["upright"])} | reversed: {", ".join(card["reversed"])}'
        )
        for card in MAJOR_ARCANA
    ]


def get_tarot_card(number: int) -> Dict[str, Any]:
    return MAJOR_ARCANA_BY_NUMBER.get(int(number), MAJOR_ARCANA_BY_NUMBER[0])


def enrich_fortune_card(fortune: Dict[str, Any], lang: str) -> Dict[str, Any]:
    enriched = dict(fortune or {})
    card = get_tarot_card(enriched.get("card_number", 0))
    is_reversed = bool(enriched.get("is_reversed", False))

    enriched["card_number"] = card["number"]
    enriched["card_key"] = card["key"]
    enriched["card"] = card["zh"] if lang == "zh" else card["en"]
    if is_reversed:
        enriched["card"] += "（逆位）" if lang == "zh" else " (Reversed)"
    enriched["card_symbol"] = card["symbol"]
    enriched["card_image_url"] = card["image_url"]
    enriched["card_imagery"] = card["imagery"]
    enriched["card_keywords"] = card["reversed"] if is_reversed else card["upright"]
    return enriched
