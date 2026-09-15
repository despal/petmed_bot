"""JSON-сериализация views ядра."""

from __future__ import annotations

from datetime import date, datetime, time

from petmed_core.views import (
    AnimalView,
    AppointmentView,
    CareDayView,
    HouseView,
    MarkView,
    StepView,
    UserView,
)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.astimezone(__import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z")


def _hm(t: time | None) -> str | None:
    if t is None:
        return None
    return f"{t.hour:02d}:{t.minute:02d}"


def _d(d: date | None) -> str | None:
    if d is None:
        return None
    return d.isoformat()


def course_label(appt: AppointmentView, plan_date: date) -> str | None:
    """Та же арифметика, что petmed_bot.texts.course_label."""
    if appt.course_days is None or appt.course_start_plan_date is None:
        return None
    day_no = (plan_date - appt.course_start_plan_date).days + 1
    if day_no < 1:
        return None
    return f"день {day_no} из {appt.course_days}"


def user_json(u: UserView) -> dict:
    return {
        "id": u.id,
        "display_timezone": u.display_timezone,
        "telegram_id": u.telegram_id,
    }


def house_json(h: HouseView | None) -> dict | None:
    if h is None:
        return None
    return {
        "id": h.id,
        "creator_user_id": h.creator_user_id,
        "schedule_timezone": h.schedule_timezone,
        "doubler_user_id": h.doubler_user_id,
    }


def animal_json(a: AnimalView) -> dict:
    return {
        "id": a.id,
        "house_id": a.house_id,
        "name": a.name,
        "archived": a.archived,
        "avatar_key": a.avatar_key,
    }


def appointment_json(a: AppointmentView) -> dict:
    return {
        "id": a.id,
        "house_id": a.house_id,
        "title": a.title,
        "kind": a.kind,
        "animal_ids": list(a.animal_ids),
        "archived": a.archived,
        "silent": a.silent,
        "course_days": a.course_days,
        "course_start_plan_date": _d(a.course_start_plan_date),
        "local_time": _hm(a.local_time),
        "slot": a.slot,
        "reference_local_time": _hm(a.reference_local_time),
        "anchor_appointment_id": a.anchor_appointment_id,
        "direction": a.direction,
        "offset_minutes": a.offset_minutes,
    }


def step_json(s: StepView, *, course: str | None = None) -> dict:
    return {
        "id": s.id,
        "appointment_id": s.appointment_id,
        "house_id": s.house_id,
        "plan_date": _d(s.plan_date),
        "title": s.title,
        "planned_at": _iso(s.planned_at),
        "planned_local": _hm(s.planned_local),
        "time_accuracy": s.time_accuracy,
        "status": s.status,
        "slot": s.slot,
        "animal_ids": list(s.animal_ids),
        "silent": s.silent,
        "course_label": course,
    }


def care_day_json(day: CareDayView, appointments_by_id: dict[int, AppointmentView] | None = None) -> dict:
    appts = appointments_by_id or {}
    steps = []
    for s in day.steps:
        label = None
        appt = appts.get(s.appointment_id)
        if appt is not None:
            label = course_label(appt, s.plan_date)
        steps.append(step_json(s, course=label))
    return {
        "id": day.id,
        "house_id": day.house_id,
        "plan_date": _d(day.plan_date),
        "starts_at": _iso(day.starts_at),
        "ends_at": _iso(day.ends_at),
        "steps": steps,
        "animals": [animal_json(a) for a in day.animals],
    }


def mark_json(m: MarkView) -> dict:
    return {
        "id": m.id,
        "step_id": m.step_id,
        "user_id": m.user_id,
        "kind": m.kind,
        "fact_at": _iso(m.fact_at),
    }


def parse_hm(value: str) -> time:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("ожидали HH:MM")
    return time(int(parts[0]), int(parts[1]))
