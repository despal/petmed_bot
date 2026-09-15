from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from petmed_api.auth_telegram import InitDataError, validate_init_data
from petmed_core import Core, NotFound, PermissionDenied, ValidationError, create_session
from petmed_core.views import HouseView, UserView


def get_db_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///petmed.db")


def get_session(request: Request) -> Session:
    factory = request.app.state.session_factory
    session: Session = factory()
    try:
        yield session
    finally:
        session.close()


def get_core(session: Annotated[Session, Depends(get_session)]) -> Core:
    return Core(session)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_now() -> datetime:
    return utc_now()


def map_core_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionDenied):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, NotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


class Actor:
    def __init__(self, user: UserView, house: HouseView | None):
        self.user = user
        self.house = house


def _extract_init_data(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "tma "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix) :].strip()
    return None


def require_actor(
    request: Request,
    core: Annotated[Core, Depends(get_core)],
    authorization: Annotated[str | None, Header()] = None,
) -> Actor:
    dev_id = os.environ.get("DEV_TELEGRAM_ID", "").strip()
    telegram_id: str | None = None

    if dev_id:
        telegram_id = dev_id
    else:
        init_data = _extract_init_data(authorization)
        if not init_data:
            raise HTTPException(status_code=401, detail="нужен Authorization: tma <initData>")
        bot_token = os.environ.get("BOT_TOKEN", "")
        try:
            parsed = validate_init_data(init_data, bot_token)
        except InitDataError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        telegram_id = str(parsed["user"]["id"])

    user = core.get_user_by_telegram_id(telegram_id)
    if user is None:
        raise HTTPException(status_code=403, detail="нет доступа")
    try:
        house = core.get_house_for_user(user.id)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Actor(user=user, house=house)


def require_house(actor: Annotated[Actor, Depends(require_actor)]) -> Actor:
    if actor.house is None:
        raise HTTPException(status_code=400, detail="дом ещё не создан")
    return actor
