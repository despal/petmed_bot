"""Проверка Telegram WebApp initData."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InitDataError(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, *, max_age_sec: int = 86400) -> dict:
    """Вернуть разобранные поля; user — dict с id. Иначе InitDataError."""
    if not init_data or not bot_token:
        raise InitDataError("нет initData или токена")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("нет hash")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        raise InitDataError("подпись неверна")

    auth_date = pairs.get("auth_date")
    if auth_date is not None:
        try:
            age = int(time.time()) - int(auth_date)
        except ValueError as exc:
            raise InitDataError("auth_date битый") from exc
        if age > max_age_sec:
            raise InitDataError("initData устарел")

    user_raw = pairs.get("user")
    if not user_raw:
        raise InitDataError("нет user")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise InitDataError("user битый") from exc
    if "id" not in user:
        raise InitDataError("нет user.id")
    return {"user": user, "auth_date": auth_date, "raw": pairs}
