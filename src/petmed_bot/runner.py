"""Long polling. Запуск: python -m petmed_bot.runner"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from petmed_bot.delivery import DeliveryLoop, TelegramSendError
from petmed_bot.texts import BTN_APP, BTN_DONE, reminder_text
from petmed_core import Core, create_session
from petmed_core.timeutil import TICK_INTERVAL

TICK_SECONDS = int(TICK_INTERVAL.total_seconds())


def done_callback_data(notification_id: int, step_id: int) -> str:
    return f"d:{notification_id}:{step_id}"


def parse_done_callback(data: str) -> tuple[int, int] | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "d":
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


def app_button(webapp_url: str | None) -> InlineKeyboardButton:
    if webapp_url:
        return InlineKeyboardButton(text=BTN_APP, web_app=WebAppInfo(url=webapp_url))
    return InlineKeyboardButton(text=BTN_APP, callback_data="app")


def reminder_keyboard(
    notification_id: int, step_id: int, webapp_url: str | None
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_DONE,
                    callback_data=done_callback_data(notification_id, step_id),
                )
            ],
            [app_button(webapp_url)],
        ]
    )


class AiogramTelegram:
    def __init__(self, bot: Bot, webapp_url: str | None):
        self.bot = bot
        self.webapp_url = webapp_url

    async def send_reminder(
        self, chat_id: str, text: str, notification_id: int, step_id: int
    ) -> None:
        try:
            await self.bot.send_message(
                chat_id=int(chat_id),
                text=text,
                reply_markup=reminder_keyboard(notification_id, step_id, self.webapp_url),
            )
        except Exception as exc:
            raise TelegramSendError(str(exc)) from exc


def build_dispatcher(handlers: DeliveryLoop, webapp_url: str | None) -> Dispatcher:
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def on_start(message: Message, command: CommandObject) -> None:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[app_button(webapp_url)]]
        )
        if command.args:
            if message.from_user is None:
                await message.answer(handlers.handle_start(), reply_markup=keyboard)
                return
            text = handlers.handle_start_token(command.args, str(message.from_user.id))
            await message.answer(text, reply_markup=keyboard)
            return
        await message.answer(handlers.handle_start(), reply_markup=keyboard)

    @dp.callback_query(F.data == "app")
    async def on_app(callback: CallbackQuery) -> None:
        await callback.answer(handlers.handle_open_app(), show_alert=True)

    @dp.callback_query(F.data.startswith("d:"))
    async def on_done(callback: CallbackQuery) -> None:
        parsed = parse_done_callback(callback.data or "")
        if parsed is None or callback.from_user is None:
            await callback.answer("Некорректные данные", show_alert=True)
            return
        notification_id, step_id = parsed
        now = datetime.now(timezone.utc)
        text = handlers.handle_done(str(callback.from_user.id), notification_id, step_id, now)
        await callback.answer(text, show_alert=True)
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

    return dp


async def deliver_due_async(core: Core, gateway: AiogramTelegram) -> None:
    for note in core.get_due_notifications():
        sent_ok = 0
        targets = 0
        step = core.get_step(note.step_id)
        for user_id in note.audience:
            user = core.get_user(user_id)
            if not user.telegram_id:
                continue
            targets += 1
            text = reminder_text(core, note, step, user.id)
            try:
                await gateway.send_reminder(user.telegram_id, text, note.id, step.id)
                sent_ok += 1
            except TelegramSendError:
                continue
        if targets == 0 or sent_ok > 0:
            core.consume_notification(note.id)


async def _tick_forever(core: Core, gateway: AiogramTelegram) -> None:
    while True:
        core.tick(datetime.now(timezone.utc))
        await deliver_due_async(core, gateway)
        await asyncio.sleep(TICK_SECONDS)


class _UnusedPort:
    def send_reminder(self, chat_id: str, text: str, notification_id: int, step_id: int) -> None:
        raise TelegramSendError("live-отправка идёт через AiogramTelegram")


async def amain() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Задайте BOT_TOKEN")
    db_url = os.environ.get("DATABASE_URL", "sqlite:///petmed.db")
    webapp_url = (os.environ.get("WEBAPP_URL") or "").strip() or None
    core = Core(create_session(db_url))
    bot = Bot(token)
    gateway = AiogramTelegram(bot, webapp_url)
    handlers = DeliveryLoop(core, _UnusedPort())
    dp = build_dispatcher(handlers, webapp_url)
    ticker = asyncio.create_task(_tick_forever(core, gateway))
    try:
        await dp.start_polling(bot)
    finally:
        ticker.cancel()
        await bot.session.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
