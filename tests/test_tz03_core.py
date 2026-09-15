"""Приёмка доработок ядра TZ_03_APP часть A."""

from datetime import time

import pytest

from petmed_core import PermissionDenied, ValidationError
from tests.helpers import bkk


def test_a1_house_for_user_empty_then_creator(core):
    user = core.create_user("Asia/Bangkok")
    assert core.get_house_for_user(user.id) is None
    house = core.create_house(user.id, "Asia/Bangkok")
    got = core.get_house_for_user(user.id)
    assert got is not None
    assert got.id == house.id


def test_a1_house_for_user_doubler(core):
    owner = core.create_user("Asia/Bangkok")
    house = core.create_house(owner.id, "Asia/Bangkok")
    doubler = core.create_user("Europe/Moscow")
    core.set_doubler(owner.id, house.id, doubler.id)
    got = core.get_house_for_user(doubler.id)
    assert got is not None
    assert got.id == house.id


def test_a1_house_for_user_ambiguous(core):
    a = core.create_user("Asia/Bangkok")
    b = core.create_user("Europe/Moscow")
    ha = core.create_house(a.id, "Asia/Bangkok")
    hb = core.create_house(b.id, "Europe/Moscow")
    core.set_doubler(b.id, hb.id, a.id)
    with pytest.raises(ValidationError, match="больше одного дома"):
        core.get_house_for_user(a.id)
    core.set_doubler(b.id, hb.id, None)
    assert core.get_house_for_user(a.id).id == ha.id


def test_a2_list_appointments(core):
    owner = core.create_user("Asia/Bangkok")
    stranger = core.create_user("UTC")
    house = core.create_house(owner.id, "Asia/Bangkok")
    animal = core.add_animal(owner.id, house.id, "Север")
    now = bkk(12, 10)
    live1 = core.create_appointment(
        owner.id,
        house.id,
        "Еда",
        "window",
        [animal.id],
        now,
        slot="morning",
        reference_local_time=time(10, 30),
    )
    live2 = core.create_appointment(
        owner.id,
        house.id,
        "Антепсин",
        "fixed",
        [animal.id],
        now,
        local_time=time(8, 30),
    )
    archived = core.create_appointment(
        owner.id,
        house.id,
        "Старое",
        "window",
        [animal.id],
        now,
        slot="evening",
        reference_local_time=time(20, 30),
    )
    core.archive_appointment(owner.id, archived.id, now)

    rows = core.list_appointments(owner.id, house.id)
    assert [r.id for r in rows] == [live1.id, live2.id, archived.id]
    assert [r.archived for r in rows] == [False, False, True]

    with pytest.raises(PermissionDenied):
        core.list_appointments(stranger.id, house.id)


def test_a3_avatar_key(core):
    owner = core.create_user("Asia/Bangkok")
    house = core.create_house(owner.id, "Asia/Bangkok")
    animal = core.add_animal(owner.id, house.id, "Север", avatar_key="img01")
    assert animal.avatar_key == "img01"
    assert core.get_animal(animal.id).avatar_key == "img01"

    care = core.get_care_day(owner.id, house.id, bkk(12, 10))
    found = next(a for a in care.animals if a.id == animal.id)
    assert found.avatar_key == "img01"

    updated = core.set_animal_avatar(owner.id, animal.id, "img02")
    assert updated.avatar_key == "img02"
    assert core.get_animal(animal.id).avatar_key == "img02"

    renamed = core.rename_animal(owner.id, animal.id, "Северчик")
    assert renamed.name == "Северчик"
    assert renamed.avatar_key == "img02"

    cleared = core.set_animal_avatar(owner.id, animal.id, None)
    assert cleared.avatar_key is None

    with pytest.raises(ValidationError, match="пустой"):
        core.set_animal_avatar(owner.id, animal.id, "  ")


def test_a4_invite_ok(core):
    token = core.create_invite()
    user = core.accept_invite(token, "9001")
    assert user.telegram_id == "9001"
    assert user.display_timezone == "UTC"
    assert core.get_house_for_user(user.id) is None


def test_a5_invite_token_reuse(core):
    token = core.create_invite()
    core.accept_invite(token, "9002")
    with pytest.raises(ValidationError, match="использовано"):
        core.accept_invite(token, "9003")


def test_a6_invite_existing_telegram_keeps_token(core):
    core.create_user("Asia/Bangkok", telegram_id="9004")
    token = core.create_invite()
    again = core.accept_invite(token, "9004")
    assert again.telegram_id == "9004"
    # токен всё ещё живой — другой человек может принять
    other = core.accept_invite(token, "9005")
    assert other.telegram_id == "9005"
    assert other.id != again.id


def test_a7_unique_telegram_id(core):
    core.create_user("Asia/Bangkok", telegram_id="9006")
    with pytest.raises(ValidationError, match="занят"):
        core.create_user("UTC", telegram_id="9006")
