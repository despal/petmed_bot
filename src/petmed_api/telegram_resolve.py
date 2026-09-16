"""Резолв Telegram chat через Bot API (getChat). Без вызовов из petmed_core."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class TelegramResolveError(Exception):
    pass


@dataclass(frozen=True)
class TelegramChatInfo:
    telegram_id: str
    display_name: str


def format_telegram_label(
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    username: str | None = None,
    fallback_id: str | int | None = None,
) -> str:
    """Имя → @ник → id."""
    parts = [p for p in (first_name, last_name) if p]
    name = " ".join(parts).strip()
    if name:
        return name
    if username:
        nick = username.lstrip("@")
        return f"@{nick}" if nick else str(fallback_id or "")
    return str(fallback_id) if fallback_id is not None else ""


def _normalize_chat_id(username_or_id: str) -> str:
    raw = username_or_id.strip()
    if not raw:
        raise TelegramResolveError("пользователь не найден")
    if raw.lstrip("-").isdigit():
        return raw
    return raw if raw.startswith("@") else f"@{raw}"


def resolve_chat(bot_token: str, username_or_id: str) -> TelegramChatInfo:
    if not bot_token:
        raise TelegramResolveError("пользователь не найден")
    chat_id = _normalize_chat_id(username_or_id)
    query = urllib.parse.urlencode({"chat_id": chat_id})
    url = f"https://api.telegram.org/bot{bot_token}/getChat?{query}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise TelegramResolveError("пользователь не найден") from exc
    if not payload.get("ok"):
        raise TelegramResolveError("пользователь не найден")
    result = payload.get("result") or {}
    tid = result.get("id")
    if tid is None:
        raise TelegramResolveError("пользователь не найден")
    telegram_id = str(tid)
    label = format_telegram_label(
        first_name=result.get("first_name"),
        last_name=result.get("last_name"),
        username=result.get("username"),
        fallback_id=telegram_id,
    )
    return TelegramChatInfo(telegram_id=telegram_id, display_name=label)


def display_name_for_telegram_id(bot_token: str, telegram_id: str) -> str:
    """Best-effort имя; при ошибке — сам id."""
    try:
        return resolve_chat(bot_token, telegram_id).display_name
    except TelegramResolveError:
        return str(telegram_id)
