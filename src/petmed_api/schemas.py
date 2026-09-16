from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HouseCreateBody(BaseModel):
    schedule_timezone: str


class TimezoneBody(BaseModel):
    schedule_timezone: str | None = None
    display_timezone: str | None = None


class HouseTimezoneBody(BaseModel):
    schedule_timezone: str


class MyTimezoneBody(BaseModel):
    display_timezone: str


class AnimalCreateBody(BaseModel):
    name: str
    avatar_key: str | None = None


class AnimalPatchBody(BaseModel):
    name: str | None = None
    avatar_key: str | None = Field(default=None)
    # Use model to detect if avatar_key was sent — handled via model_fields_set in route
    model_config = {"extra": "forbid"}


class AppointmentCreateBody(BaseModel):
    title: str
    kind: Literal["fixed", "window", "relative"]
    animal_ids: list[int]
    local_time: str | None = None
    slot: str | None = None
    reference_local_time: str | None = None
    anchor_appointment_id: int | None = None
    direction: str | None = None
    offset_minutes: int | None = None
    course_days: int | None = None
    silent: bool = False


class AppointmentPatchBody(BaseModel):
    title: str | None = None
    local_time: str | None = None
    slot: str | None = None
    reference_local_time: str | None = None
    anchor_appointment_id: int | None = None
    direction: str | None = None
    offset_minutes: int | None = None
    course_days: int | None = None
    silent: bool | None = None


class MarkBody(BaseModel):
    kind: Literal["done", "done_at", "skipped"]
    local_time: str | None = None


class DoublerAssignBody(BaseModel):
    username_or_id: str
