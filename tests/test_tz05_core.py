"""TZ-05: дублёр — ядро."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from petmed_core import ValidationError
from petmed_core.db import ensure_schema
from petmed_core.models import House


def _house(core):
    owner = core.create_user("Asia/Bangkok", telegram_id="1001")
    house = core.create_house(owner.id, "Asia/Bangkok")
    return owner, house


def test_set_doubler_ok(core):
    owner, house = _house(core)
    doubler = core.create_user("Europe/Moscow", telegram_id="2002")
    view = core.set_doubler(owner.id, house.id, doubler.id)
    assert view.doubler_user_id == doubler.id
    assert core.get_house_for_user(doubler.id).id == house.id


def test_set_doubler_rejects_creator_of_any_house(core):
    owner, house = _house(core)
    other = core.create_user("UTC", telegram_id="2003")
    core.create_house(other.id, "UTC")
    with pytest.raises(ValidationError, match="уже есть дом"):
        core.set_doubler(owner.id, house.id, other.id)


def test_set_doubler_rejects_self(core):
    owner, house = _house(core)
    with pytest.raises(ValidationError, match="уже есть дом"):
        core.set_doubler(owner.id, house.id, owner.id)


def test_set_doubler_rejects_other_house_doubler(core):
    a = core.create_user("Asia/Bangkok", telegram_id="2010")
    b = core.create_user("Europe/Moscow", telegram_id="2011")
    shared = core.create_user("UTC", telegram_id="2012")
    ha = core.create_house(a.id, "Asia/Bangkok")
    hb = core.create_house(b.id, "Europe/Moscow")
    core.set_doubler(a.id, ha.id, shared.id)
    with pytest.raises(ValidationError, match="уже есть дом"):
        core.set_doubler(b.id, hb.id, shared.id)


def test_set_doubler_slot_busy(core):
    owner, house = _house(core)
    d1 = core.create_user("UTC", telegram_id="2020")
    d2 = core.create_user("UTC", telegram_id="2021")
    core.set_doubler(owner.id, house.id, d1.id)
    with pytest.raises(ValidationError, match="уже назначен"):
        core.set_doubler(owner.id, house.id, d2.id)


def test_clear_doubler(core):
    owner, house = _house(core)
    doubler = core.create_user("UTC", telegram_id="2030")
    core.set_doubler(owner.id, house.id, doubler.id)
    view = core.set_doubler(owner.id, house.id, None)
    assert view.doubler_user_id is None
    assert core.get_house_for_user(doubler.id) is None


def test_welcome_flag_reset_on_assign_and_clear(core):
    owner, house = _house(core)
    doubler = core.create_user("UTC", telegram_id="2040")
    core.set_doubler(owner.id, house.id, doubler.id)
    pending = core.doubler_welcome_pending("2040")
    assert pending is not None
    actor_id, creator_tid = pending
    assert actor_id == doubler.id
    assert creator_tid == "1001"
    assert core.mark_doubler_welcomed(doubler.id) is True
    assert core.doubler_welcome_pending("2040") is None
    assert core.mark_doubler_welcomed(doubler.id) is False

    core.set_doubler(owner.id, house.id, None)
    core.set_doubler(owner.id, house.id, doubler.id)
    assert core.doubler_welcome_pending("2040") is not None


def test_house_for_user_ambiguous_via_raw(core):
    """Страховка: два дома у одного user — ValidationError (через прямой ORM)."""
    a = core.create_user("Asia/Bangkok")
    b = core.create_user("Europe/Moscow")
    ha = core.create_house(a.id, "Asia/Bangkok")
    hb = core.create_house(b.id, "Europe/Moscow")
    row = core.s.get(House, hb.id)
    assert row is not None
    row.doubler_user_id = a.id
    core.s.commit()
    with pytest.raises(ValidationError, match="больше одного дома"):
        core.get_house_for_user(a.id)
    row = core.s.get(House, hb.id)
    assert row is not None
    row.doubler_user_id = None
    core.s.commit()
    assert core.get_house_for_user(a.id).id == ha.id


def test_ensure_schema_adds_doubler_start_seen(tmp_path):
    db = tmp_path / "legacy.db"
    url = f"sqlite:///{db}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, "
                "display_timezone VARCHAR(64) NOT NULL, "
                "telegram_id VARCHAR(64)"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE houses ("
                "id INTEGER PRIMARY KEY, "
                "creator_user_id INTEGER NOT NULL, "
                "schedule_timezone VARCHAR(64) NOT NULL, "
                "doubler_user_id INTEGER"
                ")"
            )
        )
    ensure_schema(engine)
    with engine.connect() as conn:
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(houses)")).fetchall()}
    assert "doubler_start_seen" in cols
    sessionmaker(bind=engine)().close()
