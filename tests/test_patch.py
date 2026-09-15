from datetime import time

import pytest

from petmed_core import ValidationError

from helpers import SAT, SUN, bkk, step_named, steps_named
from test_acceptance import setup_house


def test_patch_1_add_to_pending_group(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    food = core.create_appointment(
        owner.id,
        house.id,
        "еда утром",
        "window",
        [sever.id, jackie.id],
        now,
        slot="morning",
        reference_local_time=time(10, 30),
    )
    core.tick(now)
    core.add_animal_to_appointment(owner.id, food.id, rex.id, now)
    assert set(core.get_appointment(food.id).animal_ids) == {sever.id, jackie.id, rex.id}
    care = core.get_care_day(owner.id, house.id, now)
    assert set(step_named(care, "еда утром").animal_ids) == {sever.id, jackie.id, rex.id}
    core.mark_step(owner.id, step_named(care, "еда утром").id, "done", bkk(SAT, 10, 40))
    log = [e for e in core.get_log(house.id) if e.title == "еда утром"]
    assert {e.animal_id for e in log} == {sever.id, jackie.id, rex.id}


def test_patch_2_add_after_closed(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    food = core.create_appointment(
        owner.id,
        house.id,
        "еда утром",
        "window",
        [sever.id, jackie.id],
        now,
        slot="morning",
        reference_local_time=time(10, 30),
    )
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "еда утром").id, "done", bkk(SAT, 10, 40))
    log_before = core.get_log(house.id)

    core.add_animal_to_appointment(owner.id, food.id, rex.id, bkk(SAT, 11, 0))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 11, 0))
    closed = step_named(care, "еда утром")
    assert set(closed.animal_ids) == {sever.id, jackie.id}
    assert closed.status == "done"
    assert core.get_log(house.id) == log_before
    assert set(core.get_appointment(food.id).animal_ids) == {sever.id, jackie.id, rex.id}

    core.tick(bkk(SUN, 8, 0))
    sunday = core.get_care_day(owner.id, house.id, bkk(SUN, 8, 0))
    assert set(step_named(sunday, "еда утром").animal_ids) == {sever.id, jackie.id, rex.id}


def test_patch_3_archive_future_keep_past(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    food = core.create_appointment(
        owner.id,
        house.id,
        "еда утром",
        "window",
        [sever.id, jackie.id, rex.id],
        now,
        slot="morning",
        reference_local_time=time(10, 30),
    )
    core.create_appointment(
        owner.id,
        house.id,
        "Антепсин",
        "relative",
        [sever.id],
        now,
        anchor_appointment_id=food.id,
        direction="before",
        offset_minutes=120,
    )
    evening = core.create_appointment(
        owner.id,
        house.id,
        "еда вечером",
        "window",
        [sever.id, jackie.id, rex.id],
        now,
        slot="evening",
    )
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "еда утром").id, "done", bkk(SAT, 10, 40))

    core.archive_appointment(owner.id, evening.id, bkk(SAT, 15, 0))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 15, 0))
    assert step_named(care, "еда утром").status == "done"
    assert steps_named(care, "еда вечером") == []
    live_ids = {s.id for s in care.steps}
    live_notes = [n for n in core.get_notifications(house_id=house.id) if n.status in ("due", "scheduled")]
    assert all(n.step_id in live_ids for n in live_notes)
    assert core.get_appointment(evening.id).archived is True

    with pytest.raises(ValidationError, match="якорь"):
        core.archive_appointment(owner.id, food.id, bkk(SAT, 15, 0))
    with pytest.raises(ValidationError, match="уже в архиве"):
        core.archive_appointment(owner.id, evening.id, bkk(SAT, 15, 0))


def test_patch_4_archive_keeps_past_pending(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    food = core.create_appointment(
        owner.id,
        house.id,
        "еда утром",
        "window",
        [sever.id],
        now,
        slot="morning",
        reference_local_time=time(10, 30),
    )
    core.tick(now)
    core.archive_appointment(owner.id, food.id, bkk(SAT, 11, 0))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 11, 0))
    step = step_named(care, "еда утром")
    assert step.status == "pending"
    core.mark_step(owner.id, step.id, "done", bkk(SAT, 11, 5))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 11, 5))
    assert step_named(care, "еда утром").status == "done"


def test_patch_5_unarchive_while_still_future(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    evening = core.create_appointment(
        owner.id,
        house.id,
        "еда вечером",
        "window",
        [sever.id],
        now,
        slot="evening",
    )
    core.tick(now)
    core.archive_appointment(owner.id, evening.id, bkk(SAT, 12, 0))
    core.unarchive_appointment(owner.id, evening.id, bkk(SAT, 15, 0))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 15, 0))
    assert step_named(care, "еда вечером").planned_local == time(20, 30)
    assert core.get_appointment(evening.id).archived is False


def test_patch_5_unarchive_after_plan_passed(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    evening = core.create_appointment(
        owner.id,
        house.id,
        "еда вечером",
        "window",
        [sever.id],
        now,
        slot="evening",
    )
    core.tick(now)
    core.archive_appointment(owner.id, evening.id, bkk(SAT, 12, 0))
    core.unarchive_appointment(owner.id, evening.id, bkk(SAT, 21, 0))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 21, 0))
    assert steps_named(care, "еда вечером") == []
    assert core.get_appointment(evening.id).archived is False


def test_patch_6_archive_animal(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    food = core.create_appointment(
        owner.id,
        house.id,
        "еда утром",
        "window",
        [sever.id, jackie.id, rex.id],
        now,
        slot="morning",
        reference_local_time=time(10, 30),
    )
    antepsin = core.create_appointment(
        owner.id,
        house.id,
        "Антепсин",
        "relative",
        [jackie.id],
        now,
        anchor_appointment_id=food.id,
        direction="before",
        offset_minutes=120,
    )
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "еда утром").id, "done", bkk(SAT, 10, 40))
    log_jackie = [e for e in core.get_log(house.id) if e.animal_id == jackie.id]

    core.archive_animal(owner.id, jackie.id, bkk(SAT, 11, 0))
    assert core.get_animal(jackie.id).archived is True
    assert set(core.get_appointment(food.id).animal_ids) == {sever.id, rex.id}
    assert core.get_appointment(antepsin.id).archived is True
    assert [e for e in core.get_log(house.id) if e.animal_id == jackie.id] == log_jackie

    with pytest.raises(ValidationError, match="архиве"):
        core.add_animal_to_appointment(owner.id, food.id, jackie.id, bkk(SAT, 11, 0))

    core.unarchive_animal(owner.id, jackie.id, bkk(SAT, 11, 5))
    assert core.get_animal(jackie.id).archived is False
    assert jackie.id not in core.get_appointment(food.id).animal_ids


def test_patch_7_archive_animal_vs_anchor(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    food = core.create_appointment(
        owner.id,
        house.id,
        "еда утром",
        "window",
        [sever.id, jackie.id],
        now,
        slot="morning",
        reference_local_time=time(10, 30),
    )
    antepsin = core.create_appointment(
        owner.id,
        house.id,
        "Антепсин",
        "relative",
        [sever.id],
        now,
        anchor_appointment_id=food.id,
        direction="before",
        offset_minutes=120,
    )
    core.tick(now)
    core.archive_animal(owner.id, jackie.id, now)
    assert core.get_animal(jackie.id).archived is True
    assert set(core.get_appointment(food.id).animal_ids) == {sever.id}
    assert core.get_appointment(antepsin.id).archived is False

    with pytest.raises(ValidationError, match="якорь"):
        core.archive_animal(owner.id, sever.id, now)
    assert core.get_animal(sever.id).archived is False
    assert set(core.get_appointment(food.id).animal_ids) == {sever.id}
    assert core.get_appointment(antepsin.id).archived is False


def test_patch_8_rename_animal_keeps_old_log(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    core.create_appointment(
        owner.id,
        house.id,
        "еда утром",
        "window",
        [sever.id],
        now,
        slot="morning",
    )
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "еда утром").id, "done", bkk(SAT, 10, 40))
    log_before = core.get_log(house.id)

    core.rename_animal(owner.id, sever.id, "Север-старший")
    assert core.get_animal(sever.id).name == "Север-старший"
    names = {a.name for a in core.get_care_day(owner.id, house.id, now).animals}
    assert "Север-старший" in names
    assert core.get_log(house.id) == log_before
