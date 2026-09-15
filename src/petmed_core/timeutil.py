from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from petmed_core.errors import ValidationError

UTC = timezone.utc

CARE_DAY_START = time(4, 0)

SLOTS = {
    "morning": (time(8, 0), time(13, 0), time(10, 30)),
    "day": (time(13, 0), time(18, 0), time(15, 30)),
    "evening": (time(18, 0), time(23, 0), time(20, 30)),
}

SLOT_END = {
    "morning": time(13, 0),
    "day": time(18, 0),
    "evening": time(23, 0),
}

INEXACT_REPEAT = timedelta(minutes=60)


def parse_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, Exception) as exc:
        raise ValidationError(f"неизвестная таймзона: {name}") from exc


def as_utc(instant: datetime) -> datetime:
    if instant.tzinfo is None:
        raise ValidationError("время «сейчас» должно быть с таймзоной")
    return instant.astimezone(UTC)


def to_user_local(instant: datetime, display_timezone: str) -> datetime:
    return as_utc(instant).astimezone(parse_tz(display_timezone))


def care_day_bounds(now: datetime, schedule_timezone: str) -> tuple[date, datetime, datetime]:
    """Сутки ухода, в которые попадает now. Возвращает plan_date, starts_at UTC, ends_at UTC."""
    tz = parse_tz(schedule_timezone)
    local = as_utc(now).astimezone(tz)
    if local.timetz().replace(tzinfo=None) >= CARE_DAY_START:
        plan = local.date()
    else:
        plan = local.date() - timedelta(days=1)
    start_local = datetime.combine(plan, CARE_DAY_START, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return plan, start_local.astimezone(UTC), end_local.astimezone(UTC)


def local_on_care_day(plan_date: date, local_t: time, schedule_timezone: str) -> datetime:
    """Часы в контексте суток: 00:00–03:59 — хвост (следующая календарная дата)."""
    tz = parse_tz(schedule_timezone)
    calendar = plan_date + timedelta(days=1) if local_t < CARE_DAY_START else plan_date
    local = datetime.combine(calendar, local_t, tzinfo=tz)
    return local.astimezone(UTC)


def slot_end_at(plan_date: date, slot: str, schedule_timezone: str) -> datetime | None:
    end_t = SLOT_END.get(slot)
    if end_t is None:
        return None
    tz = parse_tz(schedule_timezone)
    return datetime.combine(plan_date, end_t, tzinfo=tz).astimezone(UTC)


def default_slot_reference(slot: str) -> time:
    if slot not in SLOTS:
        raise ValidationError(f"неизвестный слот: {slot}")
    return SLOTS[slot][2]


def house_local_clock(instant: datetime, schedule_timezone: str) -> time:
    local = as_utc(instant).astimezone(parse_tz(schedule_timezone))
    return time(local.hour, local.minute, local.second)
