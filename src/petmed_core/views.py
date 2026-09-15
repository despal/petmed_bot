from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass(frozen=True)
class UserView:
    id: int
    display_timezone: str
    telegram_id: str | None


@dataclass(frozen=True)
class HouseView:
    id: int
    creator_user_id: int
    schedule_timezone: str
    doubler_user_id: int | None


@dataclass(frozen=True)
class AnimalView:
    id: int
    house_id: int
    name: str
    archived: bool
    avatar_key: str | None


@dataclass(frozen=True)
class AppointmentView:
    id: int
    house_id: int
    title: str
    kind: str
    animal_ids: list[int]
    archived: bool
    silent: bool
    course_days: int | None
    course_start_plan_date: date | None
    local_time: time | None
    slot: str | None
    reference_local_time: time | None
    anchor_appointment_id: int | None
    direction: str | None
    offset_minutes: int | None


@dataclass(frozen=True)
class StepView:
    id: int
    appointment_id: int
    house_id: int
    plan_date: date
    title: str
    planned_at: datetime
    planned_local: time
    time_accuracy: str
    status: str
    slot: str | None
    animal_ids: list[int]
    silent: bool


@dataclass(frozen=True)
class CareDayView:
    id: int | None
    house_id: int
    plan_date: date
    starts_at: datetime
    ends_at: datetime
    steps: list[StepView]
    animals: list[AnimalView]


@dataclass(frozen=True)
class MarkView:
    id: int
    step_id: int
    user_id: int
    kind: str
    fact_at: datetime | None


@dataclass(frozen=True)
class LogEntryView:
    id: int
    house_id: int
    animal_id: int
    step_id: int
    mark_id: int
    title: str
    fact_at: datetime | None
    skipped: bool
    actor_user_id: int


@dataclass(frozen=True)
class JournalNoteView:
    id: int
    animal_id: int
    author_user_id: int
    body: str
    noted_on: date


@dataclass(frozen=True)
class NotificationView:
    id: int
    step_id: int
    fire_at: datetime
    kind: str
    status: str
    audience: list[int]
