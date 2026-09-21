from datetime import date, time

from petmed_bot.delivery import DeliveryLoop, MemoryTelegram
from petmed_bot.texts import ALREADY_MARKED, BTN_DONE, NO_ACCESS
from petmed_core import Core, create_session

from helpers import SAT, bkk


def seeded(telegram_id="1001", tz="Asia/Bangkok"):
    core = Core(create_session())
    owner = core.create_user(tz, telegram_id=telegram_id)
    house = core.create_house(owner.id, "Asia/Bangkok")
    sever = core.add_animal(owner.id, house.id, "Север")
    jackie = core.add_animal(owner.id, house.id, "Джеки")
    return core, owner, house, sever, jackie


def window_food(core, owner, house, animals, now, title="еда утром", slot="morning", **kwargs):
    return core.create_appointment(
        owner.id,
        house.id,
        title,
        "window",
        animals,
        now,
        slot=slot,
        **kwargs,
    )


def test_1_push_due_consumed():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    assert len(tg.sent) == 1
    msg = tg.sent[0]
    assert msg.chat_id == "1001"
    assert "Пора:" in msg.text
    assert "Ориентир" in msg.text
    assert "Север" in msg.text
    assert BTN_DONE in msg.buttons
    due = core.get_due_notifications()
    assert due == []
    notes = core.get_notifications(house_id=house.id)
    assert any(n.status == "consumed" and n.kind == "inexact_repeat" for n in notes)


def test_1b_multi_animals_in_reminder():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id, jackie.id], now)
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    assert "Север" in tg.sent[0].text
    assert "Джеки" in tg.sent[0].text


def test_2_done_button_marks_only_that_step():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    core.create_appointment(
        owner.id, house.id, "укол", "fixed", [sever.id], now, local_time=time(12, 0)
    )
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    food_msg = next(m for m in tg.sent if "еда" in m.text)
    reply = bot.handle_done("1001", food_msg.notification_id, food_msg.step_id, bkk(SAT, 10, 31))
    assert "Отмечено" in reply
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 10, 31))
    by_title = {s.title: s for s in care.steps}
    assert by_title["еда утром"].status == "done"
    assert by_title["укол"].status == "pending"
    assert core.get_log(house.id)


def test_3_unknown_telegram_does_not_mark():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    msg = tg.sent[0]
    reply = bot.handle_done("9999", msg.notification_id, msg.step_id, bkk(SAT, 10, 31))
    assert reply == NO_ACCESS
    care = core.get_care_day(owner.id, house.id, bkk(SAT, 10, 31))
    assert care.steps[0].status == "pending"


def test_4_no_telegram_id_consumes_without_send():
    core = Core(create_session())
    owner = core.create_user("Asia/Bangkok")
    house = core.create_house(owner.id, "Asia/Bangkok")
    sever = core.add_animal(owner.id, house.id, "Север")
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    assert tg.sent == []
    assert core.get_due_notifications() == []
    assert any(n.status == "consumed" for n in core.get_notifications(house_id=house.id))


def test_5_send_error_keeps_due_then_retries():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    tg = MemoryTelegram(fail_next=1)
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    assert tg.sent == []
    assert core.get_due_notifications()
    bot.run_cycle(bkk(SAT, 10, 31))
    assert len(tg.sent) == 1
    assert core.get_due_notifications() == []


def test_6_exact_vs_inexact_wording():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    core.create_appointment(
        owner.id, house.id, "таблетка", "fixed", [sever.id], now, local_time=time(11, 0)
    )
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    inexact = next(m for m in tg.sent if "еда" in m.text)
    assert "Пора:" in inexact.text and "Ориентир" in inexact.text
    bot.run_cycle(bkk(SAT, 11, 0))
    exact = next(m for m in tg.sent if "таблетка" in m.text)
    assert "Сейчас:" in exact.text and "Время" in exact.text


def test_7_course_in_text():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(
        core,
        owner,
        house,
        [sever.id],
        now,
        title="Антепсин",
        course_days=21,
        course_start_plan_date=date(2026, 9, SAT),
    )
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    assert "день 1 из 21" in tg.sent[0].text


def test_8_two_houses_isolated():
    core = Core(create_session())
    a = core.create_user("Asia/Bangkok", telegram_id="2001")
    b = core.create_user("Asia/Bangkok", telegram_id="2002")
    ha = core.create_house(a.id, "Asia/Bangkok")
    hb = core.create_house(b.id, "Asia/Bangkok")
    sa = core.add_animal(a.id, ha.id, "Север")
    sb = core.add_animal(b.id, hb.id, "Джеки")
    now = bkk(SAT, 7)
    window_food(core, a, ha, [sa.id], now, title="еда А")
    window_food(core, b, hb, [sb.id], now, title="еда Б")
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    by_chat = {m.chat_id: m.text for m in tg.sent}
    assert "еда А" in by_chat["2001"]
    assert "еда Б" not in by_chat["2001"]
    assert "еда Б" in by_chat["2002"]
    assert "еда А" not in by_chat["2002"]


def test_9_no_second_send_after_consume():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    assert len(tg.sent) == 1
    bot.run_cycle(bkk(SAT, 10, 31))
    assert len(tg.sent) == 1


def test_10_start_does_not_create_user():
    core, owner, house, sever, jackie = seeded()
    bot = DeliveryLoop(core, MemoryTelegram())
    before = core.get_user(owner.id)
    text = bot.handle_start()
    assert "придут сами" in text
    assert core.get_user_by_telegram_id("1001").id == before.id
    assert core.get_user_by_telegram_id("7777") is None


def test_doubler_first_start_welcome_then_normal():
    core, owner, house, sever, jackie = seeded()
    doubler = core.create_user("Europe/Moscow", telegram_id="3001")
    core.set_doubler(owner.id, house.id, doubler.id)
    bot = DeliveryLoop(core, MemoryTelegram())
    first = bot.handle_start("3001", creator_label="Анна")
    assert first == "Вы добавлены в дом Анна"
    second = bot.handle_start("3001", creator_label="Анна")
    assert "придут сами" in second
    core.set_doubler(owner.id, house.id, None)
    core.set_doubler(owner.id, house.id, doubler.id)
    again = bot.handle_start("3001", creator_label="1001")
    assert again == "Вы добавлены в дом 1001"


def test_already_marked_is_soft():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    tg = MemoryTelegram()
    bot = DeliveryLoop(core, tg)
    bot.run_cycle(bkk(SAT, 10, 30))
    msg = tg.sent[0]
    bot.handle_done("1001", msg.notification_id, msg.step_id, bkk(SAT, 10, 31))
    again = bot.handle_done("1001", msg.notification_id, msg.step_id, bkk(SAT, 10, 32))
    assert again == ALREADY_MARKED


def test_consume_twice_is_noop():
    core, owner, house, sever, jackie = seeded()
    now = bkk(SAT, 7)
    window_food(core, owner, house, [sever.id], now)
    core.tick(bkk(SAT, 10, 30))
    due = core.get_due_notifications()
    assert due
    core.consume_notification(due[0].id)
    again = core.consume_notification(due[0].id)
    assert again.status == "consumed"
    assert core.get_due_notifications() == []
