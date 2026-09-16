from datetime import date, time

import pytest

from petmed_core import PermissionDenied, ValidationError
from petmed_core.timeutil import to_user_local

from helpers import SAT, SUN, MON, bkk, step_named, steps_named


def setup_house(core, now=None):
    now = now or bkk(SAT, 7)
    owner = core.create_user("Asia/Bangkok")
    house = core.create_house(owner.id, "Asia/Bangkok")
    sever = core.add_animal(owner.id, house.id, "Север")
    jackie = core.add_animal(owner.id, house.id, "Джеки")
    rex = core.add_animal(owner.id, house.id, "Рекс")
    return owner, house, sever, jackie, rex, now


def morning_chain(core, owner, house, sever, jackie, rex, now):
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
        [sever.id],
        now,
        anchor_appointment_id=food.id,
        direction="before",
        offset_minutes=120,
    )
    almagel = core.create_appointment(
        owner.id,
        house.id,
        "Альмагель",
        "relative",
        [jackie.id],
        now,
        anchor_appointment_id=food.id,
        direction="before",
        offset_minutes=30,
    )
    return food, antepsin, almagel


def test_1_assembly(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)

    food = step_named(care, "еда утром")
    antepsin = step_named(care, "Антепсин")
    almagel = step_named(care, "Альмагель")

    assert food.planned_local == time(10, 30)
    assert food.time_accuracy == "inexact"
    assert set(food.animal_ids) == {sever.id, jackie.id, rex.id}

    assert antepsin.planned_local == time(8, 30)
    assert antepsin.time_accuracy == "inexact"
    assert antepsin.animal_ids == [sever.id]

    assert almagel.planned_local == time(10, 0)
    assert almagel.time_accuracy == "inexact"
    assert almagel.animal_ids == [jackie.id]


def test_2_mark_antepsin_shifts_chain(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    antepsin = step_named(care, "Антепсин")

    core.mark_step(owner.id, antepsin.id, "done", bkk(SAT, 8, 35))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 8, 35))
    food = step_named(care, "еда утром")
    almagel = step_named(care, "Альмагель")

    assert food.planned_local == time(10, 35)
    assert food.time_accuracy == "exact"
    assert set(food.animal_ids) == {sever.id, jackie.id, rex.id}
    assert almagel.planned_local == time(10, 5)
    assert almagel.time_accuracy == "exact"

    notes = core.get_notifications(step_id=food.id)
    live_inexact = [n for n in notes if n.kind == "inexact_repeat" and n.status in ("scheduled", "due")]
    exact = [n for n in notes if n.kind == "exact_once" and n.status != "cancelled"]
    assert live_inexact == []
    assert len(exact) == 1
    assert exact[0].fire_at == food.planned_at
    assert exact[0].status == "scheduled"


def test_3_almagel_done_at_shifts_food(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "Антепсин").id, "done", bkk(SAT, 8, 35))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 8, 35))
    almagel = step_named(care, "Альмагель")

    core.mark_step(owner.id, almagel.id, "done_at", bkk(SAT, 10, 20), local_time=time(10, 20))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 10, 20))
    food = step_named(care, "еда утром")
    antepsin = step_named(care, "Антепсин")

    assert food.planned_local == time(10, 50)
    assert food.time_accuracy == "exact"
    assert antepsin.status == "done"
    assert antepsin.planned_local == time(8, 30)


def test_4_skip_antepsin_does_not_move_food(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "Антепсин").id, "skipped", bkk(SAT, 8, 40))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 8, 40))
    food = step_named(care, "еда утром")
    assert food.planned_local == time(10, 30)
    assert food.time_accuracy == "inexact"
    assert food.status == "pending"


def test_5_window_overdue_at_slot_end(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    # скидка 1×TICK на конец слота: в 13:00 ещё не overdue
    core.tick(bkk(SAT, 13, 1))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 13, 1))
    for title in ("еда утром", "Антепсин", "Альмагель"):
        assert step_named(care, title).status == "overdue"
    due = [n for n in core.get_notifications(house_id=house.id) if n.status == "due"]
    assert due == []


def test_6_exact_overdue_after_grace(core):
    """Exact: due в пределах скидки на tick; overdue только после planned + OVERDUE_GRACE."""
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "Антепсин").id, "done", bkk(SAT, 8, 35))
    # еда → 10:35 exact; через 30 с после плана — ещё pending, пуш due
    core.tick(bkk(SAT, 10, 35, 30))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 10, 35, 30))
    food = step_named(care, "еда утром")
    assert food.status == "pending"
    notes = core.get_notifications(step_id=food.id)
    assert any(n.kind == "exact_once" and n.status == "due" for n in notes)
    # после скидки 1×TICK_INTERVAL (1 мин) — overdue
    core.tick(bkk(SAT, 10, 36, 1))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 10, 36, 1))
    assert step_named(care, "еда утром").status == "overdue"
    assert step_named(care, "Альмагель").status == "overdue"


def test_7_independent_evening_chain(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    evening_food = core.create_appointment(
        owner.id,
        house.id,
        "еда вечером",
        "window",
        [sever.id, jackie.id, rex.id],
        now,
        slot="evening",
    )
    evening_antepsin = core.create_appointment(
        owner.id,
        house.id,
        "Антепсин вечером",
        "relative",
        [sever.id],
        now,
        anchor_appointment_id=evening_food.id,
        direction="before",
        offset_minutes=120,
    )
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "Антепсин").id, "done", bkk(SAT, 8, 35))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 8, 35))

    assert step_named(care, "еда вечером").planned_local == time(20, 30)
    assert step_named(care, "еда вечером").time_accuracy == "inexact"
    assert step_named(care, "Антепсин вечером").planned_local == time(18, 30)
    assert step_named(care, "Антепсин вечером").time_accuracy == "inexact"
    assert evening_antepsin.id == step_named(care, "Антепсин вечером").appointment_id


def test_8_medicine_after_medicine(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    a = core.create_appointment(
        owner.id, house.id, "A", "fixed", [sever.id], now, local_time=time(9, 0)
    )
    core.create_appointment(
        owner.id,
        house.id,
        "B",
        "relative",
        [sever.id],
        now,
        anchor_appointment_id=a.id,
        direction="after",
        offset_minutes=30,
    )
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    assert step_named(care, "B").planned_local == time(9, 30)
    assert step_named(care, "B").time_accuracy == "exact"

    core.mark_step(owner.id, step_named(care, "A").id, "done", bkk(SAT, 9, 10))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 9, 10))
    assert step_named(care, "B").planned_local == time(9, 40)
    assert step_named(care, "B").time_accuracy == "exact"
    assert step_named(care, "B").status == "pending"


def test_9_remove_jackie_after_food_done(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    food, _, _ = morning_chain(core, owner, house, sever, jackie, rex, now)
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
    care_before = core.get_care_day(owner.id, house.id, bkk(SAT, 10, 40))
    morning_step = step_named(care_before, "еда утром")
    log_before = core.get_log(house.id)

    core.remove_animal_from_appointment(owner.id, food.id, jackie.id, bkk(SAT, 10, 40))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 10, 40))

    morning_after = step_named(care, "еда утром")
    assert morning_after.id == morning_step.id
    assert morning_after.status == "done"
    assert set(morning_after.animal_ids) == {sever.id, jackie.id, rex.id}
    assert core.get_log(house.id) == log_before

    assert len(steps_named(care, "еда утром")) == 1

    evening_step = step_named(care, "еда вечером")
    assert set(evening_step.animal_ids) == {sever.id, jackie.id, rex.id}
    assert evening_step.appointment_id == evening.id

    leftover = [
        s
        for s in care.steps
        if s.title == "еда утром" and set(s.animal_ids) == {jackie.id}
    ]
    assert leftover == []
    copies = [s for s in care.steps if s.appointment_id != food.id and s.appointment_id != evening.id]
    jackie_copy_steps = [s for s in copies if s.title == "еда утром"]
    assert jackie_copy_steps == []
    assert set(core.get_appointment(food.id).animal_ids) == {sever.id, rex.id}


def test_10_permissions(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    doubler = core.create_user("Europe/Moscow")
    stranger = core.create_user("UTC")
    core.set_doubler(owner.id, house.id, doubler.id)
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    step = step_named(care, "Антепсин")

    core.mark_step(doubler.id, step.id, "done", bkk(SAT, 8, 35))
    cat = core.add_animal(doubler.id, house.id, "Мурка")
    assert cat.name == "Мурка"

    with pytest.raises(PermissionDenied):
        core.set_house_timezone(doubler.id, house.id, "UTC")
    with pytest.raises(PermissionDenied):
        core.set_doubler(doubler.id, house.id, stranger.id)

    with pytest.raises(PermissionDenied):
        core.add_animal(stranger.id, house.id, "Чужой")
    with pytest.raises(PermissionDenied):
        core.get_care_day(stranger.id, house.id, now)
    with pytest.raises(PermissionDenied):
        core.mark_step(stranger.id, step_named(care, "Альмагель").id, "done", bkk(SAT, 10, 1))
    with pytest.raises(PermissionDenied):
        core.set_house_timezone(stranger.id, house.id, "UTC")


def test_11_care_day_boundary(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    core.tick(bkk(SAT, 13, 1))
    sat_care = core.get_care_day(owner.id, house.id, bkk(SAT, 13, 1))
    sat_ids = {s.id: s.status for s in sat_care.steps}
    assert all(status == "overdue" for status in sat_ids.values())

    still_sat = core.get_care_day(owner.id, house.id, bkk(SUN, 2, 0))
    assert still_sat.plan_date == date(2026, 9, SAT)
    assert {s.id for s in still_sat.steps} == set(sat_ids)

    core.tick(bkk(SUN, 4, 0))
    sunday = core.get_care_day(owner.id, house.id, bkk(SUN, 4, 0))
    assert sunday.plan_date == date(2026, 9, SUN)
    assert {s.id for s in sunday.steps}.isdisjoint(sat_ids)
    saturday_again = core.get_care_day(owner.id, house.id, bkk(SUN, 2, 0))
    assert {s.id: s.status for s in saturday_again.steps} == sat_ids
    assert all(s.status == "overdue" for s in saturday_again.steps)


def test_12_done_at_future_forbidden(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    with pytest.raises(ValidationError):
        core.mark_step(
            owner.id,
            step_named(care, "еда утром").id,
            "done_at",
            bkk(SAT, 9, 0),
            local_time=time(10, 30),
        )


def test_13_anchor_cycle(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    food, antepsin, _ = morning_chain(core, owner, house, sever, jackie, rex, now)
    extra = core.create_appointment(
        owner.id,
        house.id,
        "хвост цепи",
        "relative",
        [sever.id],
        now,
        anchor_appointment_id=antepsin.id,
        direction="after",
        offset_minutes=10,
    )
    with pytest.raises(ValidationError, match="цикл"):
        core.update_appointment(
            owner.id,
            antepsin.id,
            now,
            anchor_appointment_id=extra.id,
        )
    with pytest.raises(ValidationError, match="цикл"):
        core.update_appointment(
            owner.id,
            extra.id,
            now,
            anchor_appointment_id=extra.id,
        )


def test_14_shared_food_writes_three_log_rows(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    morning_chain(core, owner, house, sever, jackie, rex, now)
    core.tick(now)
    care = core.get_care_day(owner.id, house.id, now)
    core.mark_step(owner.id, step_named(care, "еда утром").id, "done", bkk(SAT, 10, 40))
    log = [e for e in core.get_log(house.id) if e.title == "еда утром"]
    assert len(log) == 3
    assert {e.animal_id for e in log} == {sever.id, jackie.id, rex.id}
    assert {e.actor_user_id for e in log} == {owner.id}
    assert all(e.skipped is False for e in log)


def test_15_course_ends(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    core.create_appointment(
        owner.id,
        house.id,
        "курс",
        "window",
        [sever.id],
        now,
        slot="morning",
        course_days=2,
        course_start_plan_date=date(2026, 9, SAT),
    )
    core.tick(now)
    assert any(s.title == "курс" for s in core.get_care_day(owner.id, house.id, now).steps)

    core.tick(bkk(SUN, 8, 0))
    assert any(s.title == "курс" for s in core.get_care_day(owner.id, house.id, bkk(SUN, 8, 0)).steps)

    core.tick(bkk(MON, 8, 0))
    monday = core.get_care_day(owner.id, house.id, bkk(MON, 8, 0))
    assert all(s.title != "курс" for s in monday.steps)


def test_silent_appointment_has_no_notifications(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    core.create_appointment(
        owner.id,
        house.id,
        "тихая еда",
        "window",
        [sever.id],
        now,
        slot="morning",
        silent=True,
    )
    core.create_appointment(
        owner.id,
        house.id,
        "громкая еда",
        "window",
        [jackie.id],
        now,
        slot="morning",
    )
    core.tick(bkk(SAT, 10, 30))
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 10, 30))
    quiet = step_named(care, "тихая еда")
    loud = step_named(care, "громкая еда")
    assert quiet.silent is True
    quiet_notes = [n for n in core.get_notifications(step_id=quiet.id) if n.status != "cancelled"]
    loud_notes = [n for n in core.get_notifications(step_id=loud.id) if n.status != "cancelled"]
    assert quiet_notes == []
    assert loud_notes


def test_new_appointment_appears_today(core):
    owner, house, sever, jackie, rex, now = setup_house(core)
    core.tick(now)
    assert core.get_care_day(owner.id, house.id, now).steps == []
    core.create_appointment(
        owner.id, house.id, "укол", "fixed", [sever.id], bkk(SAT, 11, 0), local_time=time(12, 0)
    )
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 11, 0))
    assert step_named(care, "укол").planned_local == time(12, 0)
    assert step_named(care, "укол").time_accuracy == "exact"


def test_to_user_local_helper():
    instant = bkk(SAT, 10, 0)
    shown = to_user_local(instant, "Europe/Moscow")
    assert shown.hour == 6
    assert shown.minute == 0


def test_creator_cannot_be_own_doubler(core):
    owner, house, *_ = setup_house(core)
    with pytest.raises(ValidationError):
        core.set_doubler(owner.id, house.id, owner.id)
