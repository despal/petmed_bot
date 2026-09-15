from petmed_bot.delivery import DeliveryLoop, MemoryTelegram
from petmed_bot.texts import INSIDE, INVITE_BAD, INVITE_OK
from petmed_core import Core, create_session


def test_start_invite_creates_user():
    core = Core(create_session())
    bot = DeliveryLoop(core, MemoryTelegram())
    token = core.create_invite()
    text = bot.handle_start_token(token, "7777")
    assert text == INVITE_OK
    user = core.get_user_by_telegram_id("7777")
    assert user is not None
    assert user.display_timezone == "UTC"
    assert core.get_house_for_user(user.id) is None


def test_start_invite_already_inside():
    core = Core(create_session())
    bot = DeliveryLoop(core, MemoryTelegram())
    core.create_user("Asia/Bangkok", telegram_id="7778")
    token = core.create_invite()
    text = bot.handle_start_token(token, "7778")
    assert text == INSIDE
    # token still open for someone else
    text2 = bot.handle_start_token(token, "7779")
    assert text2 == INVITE_OK


def test_start_invite_bad_token():
    core = Core(create_session())
    bot = DeliveryLoop(core, MemoryTelegram())
    assert bot.handle_start_token("nope", "7780") == INVITE_BAD
