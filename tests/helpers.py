from datetime import datetime
from zoneinfo import ZoneInfo

BKK = ZoneInfo("Asia/Bangkok")
SAT = 12
SUN = 13
MON = 14


def bkk(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=BKK)


def step_named(care, title: str):
    found = [s for s in care.steps if s.title == title]
    assert len(found) == 1, f"ожидали один шаг «{title}», есть {[s.title for s in care.steps]}"
    return found[0]


def steps_named(care, title: str):
    return [s for s in care.steps if s.title == title]
