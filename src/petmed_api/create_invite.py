"""Печать ссылки-приглашения: python -m petmed_api.create_invite"""

from __future__ import annotations

import os
import sys

from petmed_core import Core, create_session


def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "sqlite:///petmed.db")
    bot_username = os.environ.get("BOT_USERNAME", "").lstrip("@")
    if not bot_username:
        print("Задайте BOT_USERNAME (имя бота без @)", file=sys.stderr)
        raise SystemExit(1)

    core = Core(create_session(db_url))
    token = core.create_invite()
    link = f"https://t.me/{bot_username}?start={token}"
    print(f"token: {token}")
    print(f"link:  {link}")


if __name__ == "__main__":
    main()
