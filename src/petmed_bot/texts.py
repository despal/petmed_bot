from datetime import date, datetime

from petmed_core import Core
from petmed_core.views import AppointmentView, NotificationView, StepView

BTN_DONE = "Сделано"
BTN_APP = "Открыть приложение"
START_TEXT = (
    "Напоминания придут сами. Настройка животных и назначений — в приложении."
)
APP_STUB = "Скоро"
ALREADY_MARKED = "Уже отмечено"
NO_ACCESS = "Нет доступа"
MARKED = "Отмечено"
INSIDE = "Ты внутри"
INVITE_BAD = "Ссылка недействительна"
INVITE_OK = "Добро пожаловать. Открой приложение, чтобы настроить дом."


def doubler_welcome_text(creator_label: str) -> str:
    label = (creator_label or "").strip()
    if label:
        return f"Вы добавлены в дом {label}"
    return "Вы добавлены в дом"


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


def format_clock(local: datetime) -> str:
    return local.strftime("%H:%M")


def course_label(appt: AppointmentView, plan_date: date) -> str | None:
    if appt.course_days is None or appt.course_start_plan_date is None:
        return None
    day_no = (plan_date - appt.course_start_plan_date).days + 1
    if day_no < 1:
        return None
    return f"день {day_no} из {appt.course_days}"


def reminder_text(
    core: Core,
    note: NotificationView,
    step: StepView,
    recipient_user_id: int,
) -> str:
    appt = core.get_appointment(step.appointment_id)
    local = core.to_user_local(step.planned_at, recipient_user_id)
    clock = format_clock(local)
    if note.kind == "exact_once":
        line = f"Сейчас: {step.title}. Время {clock}."
    else:
        line = f"Пора: {step.title}. Ориентир {clock}."
    if step.animal_ids:
        names = [core.get_animal(aid).name for aid in step.animal_ids]
        line += " " + ", ".join(names) + "."
    progress = course_label(appt, step.plan_date)
    if progress:
        line += f" ({progress})"
    return line


def start_text() -> str:
    return START_TEXT
