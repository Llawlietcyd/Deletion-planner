"""Utilities for protecting showcase/demo accounts from destructive resets."""

from __future__ import annotations

import json
from typing import Iterable

from database.models import AppSetting

PROTECTED_SHOWCASE_SETTING_KEY = "protected_demo_usernames"
DEFAULT_PROTECTED_SHOWCASE_USERNAMES = {"chen"}


def load_protected_showcase_usernames(db) -> set[str]:
    usernames = set(DEFAULT_PROTECTED_SHOWCASE_USERNAMES)
    row = db.query(AppSetting).filter(AppSetting.key == PROTECTED_SHOWCASE_SETTING_KEY).first()
    if not row or not (row.value or "").strip():
        return usernames
    try:
        payload = json.loads(row.value)
    except json.JSONDecodeError:
        return usernames

    if isinstance(payload, list):
        usernames.update(str(item).strip() for item in payload if str(item).strip())
    return usernames


def save_protected_showcase_usernames(db, usernames: Iterable[str]) -> None:
    cleaned = sorted({str(item).strip() for item in usernames if str(item).strip()})
    payload = json.dumps(cleaned, ensure_ascii=False)
    row = db.query(AppSetting).filter(AppSetting.key == PROTECTED_SHOWCASE_SETTING_KEY).first()
    if row:
        row.value = payload
    else:
        db.add(AppSetting(key=PROTECTED_SHOWCASE_SETTING_KEY, value=payload))
    db.flush()
