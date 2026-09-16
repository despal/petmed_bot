from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from petmed_api.deps import Actor, get_core, get_now, map_core_error, require_actor, require_house
from petmed_api.schemas import (
    AnimalCreateBody,
    AnimalPatchBody,
    AppointmentCreateBody,
    AppointmentPatchBody,
    DoublerAssignBody,
    HouseCreateBody,
    HouseTimezoneBody,
    MarkBody,
    MyTimezoneBody,
)
from petmed_api.serialize import (
    animal_json,
    appointment_json,
    care_day_json,
    house_json,
    mark_json,
    parse_hm,
    user_json,
)
from petmed_api.telegram_resolve import (
    TelegramResolveError,
    display_name_for_telegram_id,
    resolve_chat,
)
from petmed_core import Core, CoreError
from petmed_core.views import AppointmentView

router = APIRouter(prefix="/api")


def _bot_token() -> str:
    return os.environ.get("BOT_TOKEN", "").strip()


def _require_creator(actor: Actor) -> None:
    assert actor.house is not None
    if actor.user.id != actor.house.creator_user_id:
        raise HTTPException(status_code=403, detail="только создатель дома")


def _doubler_payload(core: Core, house_id: int, doubler_user_id: int | None) -> dict:
    if doubler_user_id is None:
        return {"doubler": None}
    user = core.get_user(doubler_user_id)
    display_name = None
    if user.telegram_id:
        display_name = display_name_for_telegram_id(_bot_token(), user.telegram_id)
    return {
        "doubler": {
            "user_id": user.id,
            "telegram_id": user.telegram_id,
            "display_name": display_name or user.telegram_id,
        }
    }


def _appointments_map(core: Core, actor: Actor) -> dict[int, AppointmentView]:
    assert actor.house is not None
    rows = core.list_appointments(actor.user.id, actor.house.id)
    return {a.id: a for a in rows}


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.get("/me")
def me(actor: Annotated[Actor, Depends(require_actor)]) -> dict:
    return {"user": user_json(actor.user), "house": house_json(actor.house)}


@router.post("/house")
def create_house(
    body: HouseCreateBody,
    actor: Annotated[Actor, Depends(require_actor)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    try:
        house = core.create_house(actor.user.id, body.schedule_timezone)
        user = core.set_display_timezone(actor.user.id, body.schedule_timezone)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return {"user": user_json(user), "house": house_json(house)}


@router.patch("/house/timezone")
def patch_house_timezone(
    body: HouseTimezoneBody,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    try:
        house = core.set_house_timezone(actor.user.id, actor.house.id, body.schedule_timezone)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return house_json(house)


@router.patch("/me/timezone")
def patch_my_timezone(
    body: MyTimezoneBody,
    actor: Annotated[Actor, Depends(require_actor)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    try:
        user = core.set_display_timezone(actor.user.id, body.display_timezone)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return user_json(user)


@router.get("/care-day")
def get_care_day(
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict:
    try:
        day = core.get_care_day(actor.user.id, actor.house.id, now)
        return care_day_json(day, _appointments_map(core, actor))
    except CoreError as exc:
        raise map_core_error(exc) from exc


@router.post("/animals")
def add_animal(
    body: AnimalCreateBody,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    try:
        animal = core.add_animal(
            actor.user.id,
            actor.house.id,
            body.name,
            avatar_key=body.avatar_key,
        )
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return animal_json(animal)


@router.patch("/animals/{animal_id}")
def patch_animal(
    animal_id: int,
    body: AnimalPatchBody,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    fields = body.model_fields_set
    try:
        animal = core.get_animal(animal_id)
        if animal.house_id != actor.house.id:
            raise HTTPException(status_code=404, detail="животное не найдено")
        if "name" in fields and body.name is not None:
            animal = core.rename_animal(actor.user.id, animal_id, body.name)
        if "avatar_key" in fields:
            animal = core.set_animal_avatar(actor.user.id, animal_id, body.avatar_key)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return animal_json(animal)


@router.post("/animals/{animal_id}/archive")
def archive_animal(
    animal_id: int,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict:
    try:
        animal = core.archive_animal(actor.user.id, animal_id, now)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return animal_json(animal)


@router.post("/animals/{animal_id}/unarchive")
def unarchive_animal(
    animal_id: int,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict:
    try:
        animal = core.unarchive_animal(actor.user.id, animal_id, now)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return animal_json(animal)


@router.get("/appointments")
def list_appointments(
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
) -> list:
    try:
        rows = core.list_appointments(actor.user.id, actor.house.id)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return [appointment_json(a) for a in rows]


@router.get("/appointments/{appointment_id}")
def get_appointment(
    appointment_id: int,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    try:
        appt = core.get_appointment(appointment_id)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    if appt.house_id != actor.house.id:
        raise HTTPException(status_code=404, detail="назначение не найдено")
    return appointment_json(appt)


@router.post("/appointments")
def create_appointment(
    body: AppointmentCreateBody,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict:
    try:
        kwargs: dict = {
            "silent": body.silent,
            "course_days": body.course_days,
        }
        if body.local_time is not None:
            kwargs["local_time"] = parse_hm(body.local_time)
        if body.slot is not None:
            kwargs["slot"] = body.slot
        if body.reference_local_time is not None:
            kwargs["reference_local_time"] = parse_hm(body.reference_local_time)
        if body.anchor_appointment_id is not None:
            kwargs["anchor_appointment_id"] = body.anchor_appointment_id
        if body.direction is not None:
            kwargs["direction"] = body.direction
        if body.offset_minutes is not None:
            kwargs["offset_minutes"] = body.offset_minutes
        appt = core.create_appointment(
            actor.user.id,
            actor.house.id,
            body.title,
            body.kind,
            body.animal_ids,
            now,
            **kwargs,
        )
    except (CoreError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise map_core_error(exc) from exc
    return appointment_json(appt)


@router.patch("/appointments/{appointment_id}")
def patch_appointment(
    appointment_id: int,
    body: AppointmentPatchBody,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict:
    try:
        appt = core.get_appointment(appointment_id)
        if appt.house_id != actor.house.id:
            raise HTTPException(status_code=404, detail="назначение не найдено")
        kwargs: dict = {}
        fields = body.model_fields_set
        if "title" in fields:
            kwargs["title"] = body.title
        if "local_time" in fields and body.local_time is not None:
            kwargs["local_time"] = parse_hm(body.local_time)
        if "slot" in fields:
            kwargs["slot"] = body.slot
        if "reference_local_time" in fields and body.reference_local_time is not None:
            kwargs["reference_local_time"] = parse_hm(body.reference_local_time)
        if "anchor_appointment_id" in fields:
            kwargs["anchor_appointment_id"] = body.anchor_appointment_id
        if "direction" in fields:
            kwargs["direction"] = body.direction
        if "offset_minutes" in fields:
            kwargs["offset_minutes"] = body.offset_minutes
        if "course_days" in fields:
            kwargs["course_days"] = body.course_days
        if "silent" in fields:
            kwargs["silent"] = body.silent
        appt = core.update_appointment(actor.user.id, appointment_id, now, **kwargs)
    except (CoreError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise map_core_error(exc) from exc
    return appointment_json(appt)


@router.post("/appointments/{appointment_id}/archive")
def archive_appointment(
    appointment_id: int,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict:
    try:
        appt = core.archive_appointment(actor.user.id, appointment_id, now)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return appointment_json(appt)


@router.post("/appointments/{appointment_id}/unarchive")
def unarchive_appointment(
    appointment_id: int,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict:
    try:
        appt = core.unarchive_appointment(actor.user.id, appointment_id, now)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return appointment_json(appt)


@router.post("/steps/{step_id}/mark")
def mark_step(
    step_id: int,
    body: MarkBody,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
    now: Annotated[datetime, Depends(get_now)],
) -> dict:
    try:
        local = parse_hm(body.local_time) if body.local_time else None
        mark = core.mark_step(
            actor.user.id,
            step_id,
            body.kind,
            now,
            local_time=local,
        )
    except (CoreError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise map_core_error(exc) from exc
    return mark_json(mark)


@router.get("/house/doubler")
def get_doubler(
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    _require_creator(actor)
    assert actor.house is not None
    return _doubler_payload(core, actor.house.id, actor.house.doubler_user_id)


@router.put("/house/doubler")
def put_doubler(
    body: DoublerAssignBody,
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    _require_creator(actor)
    assert actor.house is not None
    try:
        chat = resolve_chat(_bot_token(), body.username_or_id)
    except TelegramResolveError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = core.get_user_by_telegram_id(chat.telegram_id)
    if target is None:
        try:
            target = core.create_user("UTC", telegram_id=chat.telegram_id)
        except CoreError as exc:
            raise map_core_error(exc) from exc
    try:
        house = core.set_doubler(actor.user.id, actor.house.id, target.id)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return _doubler_payload(core, house.id, house.doubler_user_id)


@router.delete("/house/doubler")
def delete_doubler(
    actor: Annotated[Actor, Depends(require_house)],
    core: Annotated[Core, Depends(get_core)],
) -> dict:
    _require_creator(actor)
    assert actor.house is not None
    try:
        house = core.set_doubler(actor.user.id, actor.house.id, None)
    except CoreError as exc:
        raise map_core_error(exc) from exc
    return _doubler_payload(core, house.id, house.doubler_user_id)
