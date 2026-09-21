from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Protocol

from petmed_core import Core, CoreError, PermissionDenied, ValidationError
from petmed_core.views import NotificationView

from petmed_bot.texts import (
    ALREADY_MARKED,
    BTN_DONE,
    INSIDE,
    INVITE_BAD,
    INVITE_OK,
    MARKED,
    NO_ACCESS,
    doubler_welcome_text,
    reminder_text,
    start_text,
)

SendFn = Callable[[str, str, int, int], None]


class TelegramSendError(Exception):
    pass


@dataclass(frozen=True)
class SentMessage:
    chat_id: str
    text: str
    notification_id: int
    step_id: int
    buttons: tuple[str, ...]


class TelegramPort(Protocol):
    def send_reminder(self, chat_id: str, text: str, notification_id: int, step_id: int) -> None:
        """Отправить пуш. Ошибка API — TelegramSendError."""


@dataclass
class MemoryTelegram:
    sent: list[SentMessage] = field(default_factory=list)
    fail_next: int = 0

    def send_reminder(self, chat_id: str, text: str, notification_id: int, step_id: int) -> None:
        if self.fail_next > 0:
            self.fail_next -= 1
            raise TelegramSendError("мок: сбой отправки")
        self.sent.append(
            SentMessage(
                chat_id=chat_id,
                text=text,
                notification_id=notification_id,
                step_id=step_id,
                buttons=(BTN_DONE,),
            )
        )


def deliver_note(core: Core, note: NotificationView, send: SendFn) -> None:
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
            send(user.telegram_id, text, note.id, step.id)
            sent_ok += 1
        except TelegramSendError:
            continue
    if targets == 0 or sent_ok > 0:
        core.consume_notification(note.id)


class DeliveryLoop:
    """Цикл tick → due → Telegram. Без SQL по расписанию."""

    def __init__(self, core: Core, telegram: TelegramPort):
        self.core = core
        self.telegram = telegram

    def run_cycle(self, now: datetime) -> None:
        self.core.tick(now)
        for note in self.core.get_due_notifications():
            deliver_note(self.core, note, self.telegram.send_reminder)

    def handle_start(self, telegram_id: str | None = None, creator_label: str | None = None) -> str:
        if telegram_id:
            pending = self.core.doubler_welcome_pending(str(telegram_id))
            if pending is not None:
                actor_id, creator_tid = pending
                label = creator_label
                if not label:
                    label = creator_tid or ""
                self.core.mark_doubler_welcomed(actor_id)
                return doubler_welcome_text(label)
        return start_text()

    def handle_start_token(self, token: str, telegram_id: str) -> str:
        existing = self.core.get_user_by_telegram_id(str(telegram_id))
        try:
            user = self.core.accept_invite(token, str(telegram_id))
        except ValidationError:
            return INVITE_BAD
        except CoreError as exc:
            return str(exc)
        if existing is not None and existing.id == user.id:
            return INSIDE
        return INVITE_OK

    def handle_done(
        self,
        telegram_id: str,
        notification_id: int,
        step_id: int,
        now: datetime,
    ) -> str:
        user = self.core.get_user_by_telegram_id(str(telegram_id))
        if user is None:
            return NO_ACCESS
        try:
            self.core.mark_step(user.id, step_id, "done", now)
            return MARKED
        except ValidationError as exc:
            if "уже закрыт" in str(exc):
                if any(n.id == notification_id for n in self.core.get_due_notifications()):
                    self.core.consume_notification(notification_id)
                return ALREADY_MARKED
            return str(exc)
        except PermissionDenied:
            return NO_ACCESS
        except CoreError as exc:
            return str(exc)
