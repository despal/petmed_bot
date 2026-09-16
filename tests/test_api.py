"""Автотесты API TZ_04 (с DEV_TELEGRAM_ID)."""

from __future__ import annotations

import os
from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from petmed_api.app import create_app
from petmed_core import Core
from petmed_core.models import Base
from helpers import SAT, bkk


@pytest.fixture()
def api_env(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    url = f"sqlite:///{db}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DEV_TELEGRAM_ID", "1001")
    monkeypatch.delenv("BOT_TOKEN", raising=False)

    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = create_app()
    app.state.session_factory = factory
    client = TestClient(app)
    core = Core(factory())
    return client, core, factory


def test_1_me_no_user_403(api_env):
    client, core, _ = api_env
    r = client.get("/api/me")
    assert r.status_code == 403


def test_2_house_create_and_tz(api_env):
    client, core, _ = api_env
    core.create_user("UTC", telegram_id="1001")

    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.json()["house"] is None

    r = client.post("/api/house", json={"schedule_timezone": "Asia/Bangkok"})
    assert r.status_code == 200
    body = r.json()
    assert body["house"]["schedule_timezone"] == "Asia/Bangkok"
    assert body["user"]["display_timezone"] == "Asia/Bangkok"

    r = client.post("/api/house", json={"schedule_timezone": "UTC"})
    assert r.status_code == 400


def test_3_care_day_after_appointment(api_env):
    client, core, _ = api_env
    owner = core.create_user("Asia/Bangkok", telegram_id="1001")
    house = core.create_house(owner.id, "Asia/Bangkok")
    animal = core.add_animal(owner.id, house.id, "Север")

    r = client.post(
        "/api/appointments",
        json={
            "title": "еда",
            "kind": "window",
            "animal_ids": [animal.id],
            "slot": "morning",
            "reference_local_time": "10:30",
        },
    )
    assert r.status_code == 200

    r = client.get("/api/care-day")
    assert r.status_code == 200
    steps = r.json()["steps"]
    assert any(s["title"] == "еда" for s in steps)


def test_4_mark_done_and_repeat_400(api_env):
    client, core, _ = api_env
    owner = core.create_user("Asia/Bangkok", telegram_id="1001")
    house = core.create_house(owner.id, "Asia/Bangkok")
    animal = core.add_animal(owner.id, house.id, "Север")
    now = bkk(SAT, 10)
    core.create_appointment(
        owner.id,
        house.id,
        "еда",
        "window",
        [animal.id],
        now,
        slot="morning",
        reference_local_time=time(10, 30),
    )
    care = core.get_care_day(owner.id, house.id, now)
    step_id = care.steps[0].id

    r = client.post(f"/api/steps/{step_id}/mark", json={"kind": "done"})
    assert r.status_code == 200
    r = client.post(f"/api/steps/{step_id}/mark", json={"kind": "done"})
    assert r.status_code == 400


def test_5_done_at_future_400(api_env):
    client, core, _ = api_env
    from petmed_api.deps import get_now

    owner = core.create_user("Asia/Bangkok", telegram_id="1001")
    house = core.create_house(owner.id, "Asia/Bangkok")
    animal = core.add_animal(owner.id, house.id, "Север")
    now = bkk(SAT, 10)
    core.create_appointment(
        owner.id,
        house.id,
        "еда",
        "fixed",
        [animal.id],
        now,
        local_time=time(10, 0),
    )
    care = core.get_care_day(owner.id, house.id, now)
    step_id = care.steps[0].id

    client.app.dependency_overrides[get_now] = lambda: now
    try:
        r = client.post(
            f"/api/steps/{step_id}/mark",
            json={"kind": "done_at", "local_time": "23:50"},
        )
        assert r.status_code == 400
    finally:
        client.app.dependency_overrides.clear()


def test_6_bad_auth_401(api_env, monkeypatch):
    client, core, _ = api_env
    monkeypatch.delenv("DEV_TELEGRAM_ID")
    monkeypatch.setenv("BOT_TOKEN", "123:ABC")
    r = client.get("/api/me", headers={"Authorization": "tma junk"})
    assert r.status_code == 401


def test_7_list_appointments_includes_archived(api_env):
    client, core, _ = api_env
    owner = core.create_user("Asia/Bangkok", telegram_id="1001")
    house = core.create_house(owner.id, "Asia/Bangkok")
    animal = core.add_animal(owner.id, house.id, "Север")
    now = bkk(SAT, 10)
    live = core.create_appointment(
        owner.id,
        house.id,
        "живое",
        "window",
        [animal.id],
        now,
        slot="morning",
    )
    archived = core.create_appointment(
        owner.id,
        house.id,
        "старое",
        "window",
        [animal.id],
        now,
        slot="evening",
    )
    core.archive_appointment(owner.id, archived.id, now)

    r = client.get("/api/appointments")
    assert r.status_code == 200
    rows = r.json()
    assert [x["id"] for x in rows] == [live.id, archived.id]
    assert rows[1]["archived"] is True

    r = client.post(f"/api/appointments/{live.id}/archive")
    assert r.status_code == 200
    assert r.json()["archived"] is True


def test_health_no_auth(api_env, monkeypatch):
    client, _, _ = api_env
    monkeypatch.delenv("DEV_TELEGRAM_ID")
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_doubler_assign_remove_and_errors(api_env, monkeypatch):
    from petmed_api import telegram_resolve as tr
    import petmed_api.routes as routes

    client, core, _ = api_env
    owner = core.create_user("Asia/Bangkok", telegram_id="1001")
    house = core.create_house(owner.id, "Asia/Bangkok")

    def fake_resolve(_token: str, username_or_id: str):
        raw = username_or_id.strip().lstrip("@")
        if raw in {"missing", "999"}:
            raise tr.TelegramResolveError("пользователь не найден")
        tid = "5555" if raw in {"friend", "5555"} else raw
        return tr.TelegramChatInfo(telegram_id=str(tid), display_name="Друг")

    monkeypatch.setattr(routes, "resolve_chat", fake_resolve)
    monkeypatch.setattr(
        routes,
        "display_name_for_telegram_id",
        lambda _t, tid: "Друг" if tid == "5555" else tid,
    )

    r = client.get("/api/house/doubler")
    assert r.status_code == 200
    assert r.json() == {"doubler": None}

    r = client.put("/api/house/doubler", json={"username_or_id": "@friend"})
    assert r.status_code == 200
    body = r.json()["doubler"]
    assert body["telegram_id"] == "5555"
    assert body["display_name"] == "Друг"
    assert core.get_house_for_user(core.get_user_by_telegram_id("5555").id).id == house.id

    r = client.put("/api/house/doubler", json={"username_or_id": "@missing"})
    assert r.status_code == 400
    assert "не найден" in r.json()["detail"]

    other = core.create_user("UTC", telegram_id="7777")
    core.create_house(other.id, "UTC")

    def resolve_other(_token: str, username_or_id: str):
        return tr.TelegramChatInfo(telegram_id="7777", display_name="Other")

    monkeypatch.setattr(routes, "resolve_chat", resolve_other)
    r = client.put("/api/house/doubler", json={"username_or_id": "7777"})
    assert r.status_code == 400
    assert "уже есть дом" in r.json()["detail"]

    r = client.delete("/api/house/doubler")
    assert r.status_code == 200
    assert r.json() == {"doubler": None}


def test_doubler_forbidden_for_doubler_role(api_env, monkeypatch):
    client, core, _ = api_env
    owner = core.create_user("Asia/Bangkok", telegram_id="1001")
    house = core.create_house(owner.id, "Asia/Bangkok")
    doubler = core.create_user("UTC", telegram_id="2002")
    core.set_doubler(owner.id, house.id, doubler.id)

    monkeypatch.setenv("DEV_TELEGRAM_ID", "2002")
    r = client.get("/api/house/doubler")
    assert r.status_code == 403
    r = client.put("/api/house/doubler", json={"username_or_id": "1"})
    assert r.status_code == 403
    r = client.delete("/api/house/doubler")
    assert r.status_code == 403
    r = client.patch("/api/house/timezone", json={"schedule_timezone": "UTC"})
    assert r.status_code == 403
