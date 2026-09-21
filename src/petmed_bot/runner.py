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
)

from petmed_bot.delivery import DeliveryLoop, TelegramSendError
from petmed_bot.texts import BTN_DONE, format_telegram_label, reminder_text
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


def reminder_keyboard(notification_id: int, step_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_DONE,
                    callback_data=done_callback_data(notification_id, step_id),
                )
            ],
        ]
    )


class AiogramTelegram:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_reminder(
        self, chat_id: str, text: str, notification_id: int, step_id: int
    ) -> None:
        try:
            await self.bot.send_message(
                chat_id=int(chat_id),
                text=text,
                reply_markup=reminder_keyboard(notification_id, step_id),
            )
        except Exception as exc:
            raise TelegramSendError(str(exc)) from exc


def build_dispatcher(handlers: DeliveryLoop, bot: Bot | None = None) -> Dispatcher:
    dp = Dispatcher()

    async def _creator_label(creator_telegram_id: str | None) -> str | None:
        if not creator_telegram_id:
            return None
        if bot is None:
            return creator_telegram_id
        try:
            chat = await bot.get_chat(int(creator_telegram_id))
            return format_telegram_label(
                first_name=getattr(chat, "first_name", None),
                last_name=getattr(chat, "last_name", None),
                username=getattr(chat, "username", None),
                fallback_id=creator_telegram_id,
            )
        except Exception:
            return creator_telegram_id

    @dp.message(CommandStart())
    async def on_start(message: Message, command: CommandObject) -> None:
        if command.args:
            if message.from_user is None:
                await message.answer(handlers.handle_start())
                return
            text = handlers.handle_start_token(command.args, str(message.from_user.id))
            await message.answer(text)
            return
        tid = str(message.from_user.id) if message.from_user else None
        label = None
        if tid:
            pending = handlers.core.doubler_welcome_pending(tid)
            if pending is not None:
                _actor_id, creator_tid = pending
                label = await _creator_label(creator_tid)
        text = handlers.handle_start(tid, creator_label=label)
        await message.answer(text)

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
    core = Core(create_session(db_url))
    bot = Bot(token)
    gateway = AiogramTelegram(bot)
    handlers = DeliveryLoop(core, _UnusedPort())
    dp = build_dispatcher(handlers, bot=bot)
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
