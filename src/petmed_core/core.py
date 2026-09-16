from collections import defaultdict, deque
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from petmed_core.errors import NotFound, PermissionDenied, ValidationError
from petmed_core.models import (
    Animal,
    Appointment,
    AppointmentAnimal,
    CareDay,
    DayStep,
    House,
    Invite,
    JournalNote,
    LogEntry,
    Mark,
    NotificationDecision,
    User,
)
from petmed_core.timeutil import (
    INEXACT_REPEAT,
    OVERDUE_GRACE,
    UTC,
    as_utc,
    care_day_bounds,
    default_slot_reference,
    house_local_clock,
    local_on_care_day,
    parse_tz,
    slot_end_at,
    to_user_local,
)
from petmed_core.views import (
    AnimalView,
    AppointmentView,
    CareDayView,
    HouseView,
    JournalNoteView,
    LogEntryView,
    MarkView,
    NotificationView,
    StepView,
    UserView,
)

CLOSED = frozenset({"done", "skipped"})
LIVE_NOTIF = frozenset({"scheduled", "due"})


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return as_utc(dt)


def _naive(dt: datetime) -> datetime:
    return as_utc(dt).replace(tzinfo=None)


class Core:
    """Команды ядра. Клиенты не пишут в таблицы расписания напрямую."""

    def __init__(self, session: Session):
        self.s = session

    # --- пользователи и дом ---

    def create_user(self, display_timezone: str, telegram_id: str | None = None) -> UserView:
        parse_tz(display_timezone)
        tid = str(telegram_id) if telegram_id is not None else None
        if tid is not None:
            existing = self.s.scalars(select(User).where(User.telegram_id == tid)).first()
            if existing is not None:
                raise ValidationError("telegram_id уже занят")
        user = User(display_timezone=display_timezone, telegram_id=tid)
        self.s.add(user)
        self.s.commit()
        self.s.refresh(user)
        return self._user_view(user)

    def get_house_for_user(self, user_id: int) -> HouseView | None:
        self._user(user_id)
        houses = list(
            self.s.scalars(
                select(House).where(
                    or_(House.creator_user_id == user_id, House.doubler_user_id == user_id)
                ).order_by(House.id)
            ).all()
        )
        if not houses:
            return None
        if len(houses) > 1:
            raise ValidationError("у пользователя больше одного дома")
        return self._house_view(houses[0])

    def create_house(self, creator_user_id: int, schedule_timezone: str) -> HouseView:
        self._user(creator_user_id)
        parse_tz(schedule_timezone)
        existing = self.s.scalars(select(House).where(House.creator_user_id == creator_user_id)).first()
        if existing:
            raise ValidationError("у создателя уже есть дом")
        house = House(
            creator_user_id=creator_user_id,
            schedule_timezone=schedule_timezone,
            doubler_user_id=None,
        )
        self.s.add(house)
        self.s.commit()
        self.s.refresh(house)
        return self._house_view(house)

    def set_house_timezone(self, actor_user_id: int, house_id: int, schedule_timezone: str) -> HouseView:
        house = self._house(house_id)
        self._require_creator(actor_user_id, house)
        parse_tz(schedule_timezone)
        house.schedule_timezone = schedule_timezone
        self.s.commit()
        return self._house_view(house)

    def set_doubler(self, actor_user_id: int, house_id: int, user_id: int | None) -> HouseView:
        house = self._house(house_id)
        self._require_creator(actor_user_id, house)
        if user_id is None:
            house.doubler_user_id = None
        else:
            if user_id == house.creator_user_id:
                raise ValidationError("создатель не может быть дублёром своего дома")
            self._user(user_id)
            if house.doubler_user_id is not None and house.doubler_user_id != user_id:
                raise ValidationError("дублёр уже назначен, сначала снимите текущего")
            house.doubler_user_id = user_id
        self._refresh_notification_audience(house)
        self.s.commit()
        return self._house_view(house)

    def set_display_timezone(self, actor_user_id: int, display_timezone: str) -> UserView:
        user = self._user(actor_user_id)
        parse_tz(display_timezone)
        user.display_timezone = display_timezone
        self.s.commit()
        return self._user_view(user)

    def add_animal(
        self,
        actor_user_id: int,
        house_id: int,
        name: str,
        avatar_key: str | None = None,
    ) -> AnimalView:
        house = self._house(house_id)
        self._require_content(actor_user_id, house)
        if not name.strip():
            raise ValidationError("имя животного пустое")
        key = self._normalize_avatar_key(avatar_key)
        animal = Animal(house_id=house.id, name=name.strip(), archived=False, avatar_key=key)
        self.s.add(animal)
        self.s.commit()
        self.s.refresh(animal)
        return self._animal_view(animal)

    def rename_animal(self, actor_user_id: int, animal_id: int, name: str) -> AnimalView:
        animal = self._animal(animal_id)
        house = self._house(animal.house_id)
        self._require_content(actor_user_id, house)
        if not name.strip():
            raise ValidationError("имя животного пустое")
        animal.name = name.strip()
        self.s.commit()
        return self._animal_view(animal)

    def set_animal_avatar(
        self,
        actor_user_id: int,
        animal_id: int,
        avatar_key: str | None,
    ) -> AnimalView:
        animal = self._animal(animal_id)
        house = self._house(animal.house_id)
        self._require_content(actor_user_id, house)
        animal.avatar_key = self._normalize_avatar_key(avatar_key)
        self.s.commit()
        return self._animal_view(animal)

    def get_animal(self, animal_id: int) -> AnimalView:
        return self._animal_view(self._animal(animal_id))

    def list_appointments(self, actor_user_id: int, house_id: int) -> list[AppointmentView]:
        house = self._house(house_id)
        self._require_content(actor_user_id, house)
        rows = list(
            self.s.scalars(
                select(Appointment).where(Appointment.house_id == house_id).order_by(
                    Appointment.archived.asc(),
                    Appointment.id.asc(),
                )
            ).all()
        )
        return [self._appointment_view(a) for a in rows]

    def create_invite(self) -> str:
        token = uuid4().hex
        invite = Invite(
            token=token,
            created_at=_naive(datetime.now(UTC)),
            consumed_at=None,
        )
        self.s.add(invite)
        self.s.commit()
        return token

    def accept_invite(self, token: str, telegram_id: str) -> UserView:
        tid = str(telegram_id)
        existing = self.s.scalars(select(User).where(User.telegram_id == tid)).first()
        if existing is not None:
            # Уже внутри: чужой живой токен не гасим, второго User нет.
            return self._user_view(existing)

        invite = self.s.scalars(select(Invite).where(Invite.token == token)).first()
        if invite is None:
            raise ValidationError("приглашение не найдено")
        if invite.consumed_at is not None:
            raise ValidationError("приглашение уже использовано")

        user = User(display_timezone="UTC", telegram_id=tid)
        self.s.add(user)
        invite.consumed_at = _naive(datetime.now(UTC))
        self.s.commit()
        self.s.refresh(user)
        return self._user_view(user)

    # --- назначения ---

    def create_appointment(
        self,
        actor_user_id: int,
        house_id: int,
        title: str,
        kind: str,
        animal_ids: list[int],
        now: datetime,
        *,
        local_time: time | None = None,
        slot: str | None = None,
        reference_local_time: time | None = None,
        anchor_appointment_id: int | None = None,
        direction: str | None = None,
        offset_minutes: int | None = None,
        course_days: int | None = None,
        course_start_plan_date: date | None = None,
        silent: bool = False,
    ) -> AppointmentView:
        house = self._house(house_id)
        self._require_content(actor_user_id, house)
        animals = self._animals_of_house(house, animal_ids)
        fields = self._appointment_fields(
            house,
            kind,
            title,
            local_time=local_time,
            slot=slot,
            reference_local_time=reference_local_time,
            anchor_appointment_id=anchor_appointment_id,
            direction=direction,
            offset_minutes=offset_minutes,
            course_days=course_days,
            course_start_plan_date=course_start_plan_date,
            now=now,
        )
        appt = Appointment(house_id=house.id, silent=silent, archived=False, **fields)
        self.s.add(appt)
        self.s.flush()
        if anchor_appointment_id is not None:
            self._assert_no_cycle(appt.id, anchor_appointment_id)
        for animal in animals:
            self.s.add(AppointmentAnimal(appointment_id=appt.id, animal_id=animal.id))
        self.s.flush()
        self.s.refresh(appt)
        self._ensure_step_for_current_day(house, appt, now)
        self.s.commit()
        self.s.refresh(appt)
        return self._appointment_view(appt)

    def update_appointment(
        self,
        actor_user_id: int,
        appointment_id: int,
        now: datetime,
        *,
        title: str | None = None,
        local_time: time | None = None,
        slot: str | None = None,
        reference_local_time: time | None = None,
        anchor_appointment_id: int | None = None,
        direction: str | None = None,
        offset_minutes: int | None = None,
        course_days: int | None = None,
        course_start_plan_date: date | None = None,
        silent: bool | None = None,
    ) -> AppointmentView:
        appt = self._appointment(appointment_id)
        house = self._house(appt.house_id)
        self._require_content(actor_user_id, house)
        self._require_live_appointment(appt)
        if title is not None:
            if not title.strip():
                raise ValidationError("название пустое")
            appt.title = title.strip()
        if silent is not None:
            appt.silent = silent
        if appt.kind == "fixed" and local_time is not None:
            appt.local_time = local_time
        if appt.kind == "window":
            if slot is not None:
                default_slot_reference(slot)
                appt.slot = slot
                if reference_local_time is None and appt.reference_local_time is None:
                    appt.reference_local_time = default_slot_reference(slot)
            if reference_local_time is not None:
                appt.reference_local_time = reference_local_time
        if appt.kind == "relative":
            if direction is not None:
                if direction not in ("before", "after"):
                    raise ValidationError("direction: before или after")
                appt.direction = direction
            if offset_minutes is not None:
                if offset_minutes < 0:
                    raise ValidationError("смещение не может быть отрицательным")
                appt.offset_minutes = offset_minutes
            if anchor_appointment_id is not None:
                self._assert_valid_anchor(house, anchor_appointment_id)
                self._assert_no_cycle(appt.id, anchor_appointment_id)
                appt.anchor_appointment_id = anchor_appointment_id
        if course_days is not None:
            if course_days <= 0:
                raise ValidationError("длительность курса должна быть > 0")
            appt.course_days = course_days
            if course_start_plan_date is None and appt.course_start_plan_date is None:
                plan, _, _ = care_day_bounds(now, house.schedule_timezone)
                appt.course_start_plan_date = plan
        if course_start_plan_date is not None:
            appt.course_start_plan_date = course_start_plan_date
        self._sync_open_step(house, appt, now)
        self.s.commit()
        return self._appointment_view(appt)

    def remove_animal_from_appointment(
        self,
        actor_user_id: int,
        appointment_id: int,
        animal_id: int,
        now: datetime,
    ) -> AppointmentView:
        appt = self._appointment(appointment_id)
        house = self._house(appt.house_id)
        self._require_content(actor_user_id, house)
        self._require_live_appointment(appt)
        animal = self._animal(animal_id)
        if animal.house_id != house.id:
            raise ValidationError("животное из другого дома")
        current_ids = [a.id for a in appt.animals]
        if animal_id not in current_ids:
            raise ValidationError("животного нет в назначении")
        if len(current_ids) == 1:
            raise ValidationError("нельзя оставить назначение без животных, используйте archive_appointment")

        link = self.s.get(AppointmentAnimal, (appt.id, animal_id))
        if link:
            self.s.delete(link)
        self.s.flush()

        copy = Appointment(
            house_id=house.id,
            title=appt.title,
            kind=appt.kind,
            archived=False,
            silent=appt.silent,
            course_days=appt.course_days,
            course_start_plan_date=appt.course_start_plan_date,
            local_time=appt.local_time,
            slot=appt.slot,
            reference_local_time=appt.reference_local_time,
            anchor_appointment_id=appt.anchor_appointment_id,
            direction=appt.direction,
            offset_minutes=appt.offset_minutes,
        )
        self.s.add(copy)
        self.s.flush()
        self.s.add(AppointmentAnimal(appointment_id=copy.id, animal_id=animal_id))
        self.s.flush()
        self.s.refresh(copy)
        self.s.refresh(appt)

        step = self._current_step(house, appt, now)
        if step is not None and step.status not in CLOSED:
            step.animal_ids_snapshot = [i for i in step.animal_ids_snapshot if i != animal_id]
            if self._current_step(house, copy, now) is None:
                self._clone_open_step(step, copy)
        self.s.commit()
        self.s.refresh(appt)
        return self._appointment_view(appt)

    def get_appointment(self, appointment_id: int) -> AppointmentView:
        return self._appointment_view(self._appointment(appointment_id))

    def add_animal_to_appointment(
        self,
        actor_user_id: int,
        appointment_id: int,
        animal_id: int,
        now: datetime,
    ) -> AppointmentView:
        appt = self._appointment(appointment_id)
        house = self._house(appt.house_id)
        self._require_content(actor_user_id, house)
        self._require_live_appointment(appt)
        animal = self._animal(animal_id)
        if animal.house_id != house.id:
            raise ValidationError("животное из другого дома")
        if animal.archived:
            raise ValidationError("животное в архиве")
        current_ids = self._animal_ids(appt)
        if animal_id in current_ids:
            raise ValidationError("животное уже в назначении")
        self.s.add(AppointmentAnimal(appointment_id=appt.id, animal_id=animal.id))
        self.s.flush()
        step = self._current_step(house, appt, now)
        if step is not None and step.status not in CLOSED:
            ids = list(step.animal_ids_snapshot)
            if animal.id not in ids:
                ids.append(animal.id)
                step.animal_ids_snapshot = ids
        self.s.commit()
        self.s.refresh(appt)
        return self._appointment_view(appt)

    def archive_appointment(self, actor_user_id: int, appointment_id: int, now: datetime) -> AppointmentView:
        appt = self._appointment(appointment_id)
        house = self._house(appt.house_id)
        self._require_content(actor_user_id, house)
        self._apply_archive_appointment(house, appt, now)
        self.s.commit()
        return self._appointment_view(appt)

    def unarchive_appointment(self, actor_user_id: int, appointment_id: int, now: datetime) -> AppointmentView:
        appt = self._appointment(appointment_id)
        house = self._house(appt.house_id)
        self._require_content(actor_user_id, house)
        if not appt.archived:
            raise ValidationError("назначение не в архиве")
        if appt.kind == "relative":
            if appt.anchor_appointment_id is None:
                raise ValidationError("у связного назначения нет якоря")
            self._assert_valid_anchor(house, appt.anchor_appointment_id)
        appt.archived = False
        self._maybe_step_on_unarchive(house, appt, now)
        self.s.commit()
        return self._appointment_view(appt)

    def archive_animal(self, actor_user_id: int, animal_id: int, now: datetime) -> AnimalView:
        animal = self._animal(animal_id)
        house = self._house(animal.house_id)
        self._require_content(actor_user_id, house)
        try:
            if animal.archived:
                raise ValidationError("животное уже в архиве")
            memberships = self.s.scalars(
                select(Appointment).where(
                    Appointment.house_id == house.id,
                    Appointment.archived.is_(False),
                    Appointment.id.in_(
                        select(AppointmentAnimal.appointment_id).where(
                            AppointmentAnimal.animal_id == animal.id
                        )
                    ),
                )
            ).all()
            to_archive: list[Appointment] = []
            for appt in memberships:
                remaining = [aid for aid in self._active_animal_ids(appt) if aid != animal.id]
                if not remaining:
                    to_archive.append(appt)
            for appt in to_archive:
                if self._live_dependents(appt.id):
                    raise ValidationError(
                        "нельзя архивировать якорь, на который ссылаются живые назначения"
                    )
            for appt in memberships:
                link = self.s.get(AppointmentAnimal, (appt.id, animal.id))
                if link:
                    self.s.delete(link)
                self.s.flush()
                step = self._current_step(house, appt, now)
                if step is not None and step.status not in CLOSED:
                    step.animal_ids_snapshot = [i for i in step.animal_ids_snapshot if i != animal.id]
            for appt in to_archive:
                self._apply_archive_appointment(house, appt, now)
            animal.archived = True
            self.s.commit()
        except Exception:
            self.s.rollback()
            raise
        return self._animal_view(animal)

    def unarchive_animal(self, actor_user_id: int, animal_id: int, now: datetime) -> AnimalView:
        animal = self._animal(animal_id)
        house = self._house(animal.house_id)
        self._require_content(actor_user_id, house)
        if not animal.archived:
            raise ValidationError("животное не в архиве")
        animal.archived = False
        self.s.commit()
        return self._animal_view(animal)

    def add_journal_note(
        self,
        actor_user_id: int,
        animal_id: int,
        body: str,
        noted_on: date,
    ) -> JournalNoteView:
        animal = self._animal(animal_id)
        house = self._house(animal.house_id)
        self._require_content(actor_user_id, house)
        if not body.strip():
            raise ValidationError("текст заметки пустой")
        note = JournalNote(
            animal_id=animal.id,
            author_user_id=actor_user_id,
            body=body.strip(),
            noted_on=noted_on,
            created_at=_naive(datetime.now(UTC)),
        )
        self.s.add(note)
        self.s.commit()
        self.s.refresh(note)
        return JournalNoteView(
            id=note.id,
            animal_id=note.animal_id,
            author_user_id=note.author_user_id,
            body=note.body,
            noted_on=note.noted_on,
        )

    def get_care_day(self, actor_user_id: int, house_id: int, now: datetime) -> CareDayView:
        house = self._house(house_id)
        self._require_content(actor_user_id, house)
        plan, starts, ends = care_day_bounds(now, house.schedule_timezone)
        day = self.s.scalars(
            select(CareDay).where(CareDay.house_id == house.id, CareDay.plan_date == plan)
        ).first()
        animals = [self._animal_view(a) for a in house.animals]
        if day is None:
            return CareDayView(
                id=None,
                house_id=house.id,
                plan_date=plan,
                starts_at=starts,
                ends_at=ends,
                steps=[],
                animals=animals,
            )
        steps = [self._step_view(s, house) for s in day.steps]
        steps.sort(key=lambda s: s.planned_at)
        return CareDayView(
            id=day.id,
            house_id=house.id,
            plan_date=day.plan_date,
            starts_at=_aware(day.starts_at),
            ends_at=_aware(day.ends_at),
            steps=steps,
            animals=animals,
        )

    def mark_step(
        self,
        actor_user_id: int,
        step_id: int,
        kind: str,
        now: datetime,
        local_time: time | None = None,
    ) -> MarkView:
        step = self._step(step_id)
        day = self.s.get(CareDay, step.care_day_id)
        house = self._house(day.house_id)
        self._require_content(actor_user_id, house)
        if kind not in ("done", "done_at", "skipped"):
            raise ValidationError("kind отметки: done, done_at или skipped")
        if step.status in CLOSED:
            raise ValidationError("шаг уже закрыт")
        now = as_utc(now)
        if kind == "done":
            fact_at = now
        elif kind == "done_at":
            if local_time is None:
                raise ValidationError("для done_at нужно локальное время")
            fact_at = local_on_care_day(day.plan_date, local_time, house.schedule_timezone)
            if fact_at > now:
                raise ValidationError("нельзя отметить будущее время")
        else:
            fact_at = None

        mark = Mark(
            step_id=step.id,
            user_id=actor_user_id,
            kind=kind,
            fact_at=_naive(fact_at) if fact_at else None,
            created_at=_naive(now),
        )
        self.s.add(mark)
        self.s.flush()
        step.status = "skipped" if kind == "skipped" else "done"
        self._write_log(house, step, mark, fact_at)
        self._cancel_notifications(step)
        if kind != "skipped" and fact_at is not None:
            self._after_fact(step, fact_at, now)
        self.s.commit()
        self.s.refresh(mark)
        return MarkView(
            id=mark.id,
            step_id=mark.step_id,
            user_id=mark.user_id,
            kind=mark.kind,
            fact_at=_aware(mark.fact_at),
        )

    def get_user(self, user_id: int) -> UserView:
        return self._user_view(self._user(user_id))

    def get_user_by_telegram_id(self, telegram_id: str) -> UserView | None:
        user = self.s.scalars(select(User).where(User.telegram_id == str(telegram_id))).first()
        if user is None:
            return None
        return self._user_view(user)

    def get_due_notifications(self) -> list[NotificationView]:
        rows = self.s.scalars(
            select(NotificationDecision).where(NotificationDecision.status == "due").order_by(
                NotificationDecision.id
            )
        ).all()
        return [self._notification_view(n) for n in rows]

    def consume_notification(self, notification_id: int) -> NotificationView:
        note = self.s.get(NotificationDecision, notification_id)
        if note is None:
            raise NotFound("напоминание не найдено")
        if note.status == "due":
            note.status = "consumed"
            self.s.commit()
        return self._notification_view(note)

    def get_step(self, step_id: int) -> StepView:
        step = self._step(step_id)
        day = self.s.get(CareDay, step.care_day_id)
        house = self._house(day.house_id)
        return self._step_view(step, house)

    def tick(self, now: datetime) -> None:
        now = as_utc(now)
        houses = self.s.scalars(select(House)).all()
        for house in houses:
            self._ensure_care_day(house, now)
            self._apply_overdue(house, now)
            self._apply_notifications(house, now)
        self.s.commit()

    def get_notifications(
        self,
        *,
        step_id: int | None = None,
        house_id: int | None = None,
    ) -> list[NotificationView]:
        q = select(NotificationDecision)
        if step_id is not None:
            q = q.where(NotificationDecision.step_id == step_id)
        rows = self.s.scalars(q).all()
        views = [self._notification_view(n) for n in rows]
        if house_id is not None:
            step_ids = {
                s.id
                for s in self.s.scalars(
                    select(DayStep).join(CareDay).where(CareDay.house_id == house_id)
                ).all()
            }
            views = [v for v in views if v.step_id in step_ids]
        views.sort(key=lambda v: (v.step_id, v.fire_at, v.id))
        return views

    def get_log(self, house_id: int) -> list[LogEntryView]:
        rows = self.s.scalars(select(LogEntry).where(LogEntry.house_id == house_id).order_by(LogEntry.id)).all()
        return [
            LogEntryView(
                id=r.id,
                house_id=r.house_id,
                animal_id=r.animal_id,
                step_id=r.step_id,
                mark_id=r.mark_id,
                title=r.title_snapshot,
                fact_at=_aware(r.fact_at),
                skipped=r.skipped,
                actor_user_id=r.actor_user_id,
            )
            for r in rows
        ]

    def to_user_local(self, instant: datetime, user_id: int) -> datetime:
        user = self._user(user_id)
        return to_user_local(instant, user.display_timezone)

    # --- внутренности: права и загрузка ---

    def _user(self, user_id: int) -> User:
        user = self.s.get(User, user_id)
        if user is None:
            raise NotFound("пользователь не найден")
        return user

    def _house(self, house_id: int) -> House:
        house = self.s.get(House, house_id)
        if house is None:
            raise NotFound("дом не найден")
        return house

    def _animal(self, animal_id: int) -> Animal:
        animal = self.s.get(Animal, animal_id)
        if animal is None:
            raise NotFound("животное не найдено")
        return animal

    def _appointment(self, appointment_id: int) -> Appointment:
        appt = self.s.get(Appointment, appointment_id)
        if appt is None:
            raise NotFound("назначение не найдено")
        return appt

    def _step(self, step_id: int) -> DayStep:
        step = self.s.get(DayStep, step_id)
        if step is None:
            raise NotFound("шаг не найден")
        return step

    def _require_creator(self, actor_user_id: int, house: House) -> None:
        if actor_user_id != house.creator_user_id:
            raise PermissionDenied("только создатель дома")

    def _require_content(self, actor_user_id: int, house: House) -> None:
        if actor_user_id not in (house.creator_user_id, house.doubler_user_id):
            raise PermissionDenied("нет доступа к дому")

    def _require_live_appointment(self, appt: Appointment) -> None:
        if appt.archived:
            raise ValidationError("назначение в архиве")

    def _animals_of_house(self, house: House, animal_ids: list[int]) -> list[Animal]:
        if not animal_ids:
            raise ValidationError("нужен хотя бы один участник")
        animals = []
        seen: set[int] = set()
        for aid in animal_ids:
            if aid in seen:
                continue
            seen.add(aid)
            animal = self._animal(aid)
            if animal.house_id != house.id:
                raise ValidationError("животное из другого дома")
            if animal.archived:
                raise ValidationError("животное в архиве")
            animals.append(animal)
        return animals

    # --- поля назначения ---

    def _appointment_fields(
        self,
        house: House,
        kind: str,
        title: str,
        *,
        local_time: time | None,
        slot: str | None,
        reference_local_time: time | None,
        anchor_appointment_id: int | None,
        direction: str | None,
        offset_minutes: int | None,
        course_days: int | None,
        course_start_plan_date: date | None,
        now: datetime,
    ) -> dict:
        if not title.strip():
            raise ValidationError("название пустое")
        if kind not in ("fixed", "window", "relative"):
            raise ValidationError("kind: fixed, window или relative")
        start = course_start_plan_date
        if course_days is not None:
            if course_days <= 0:
                raise ValidationError("длительность курса должна быть > 0")
            if start is None:
                start, _, _ = care_day_bounds(now, house.schedule_timezone)
        fields: dict = {
            "title": title.strip(),
            "kind": kind,
            "course_days": course_days,
            "course_start_plan_date": start,
            "local_time": None,
            "slot": None,
            "reference_local_time": None,
            "anchor_appointment_id": None,
            "direction": None,
            "offset_minutes": None,
        }
        if kind == "fixed":
            if local_time is None:
                raise ValidationError("fixed требует local_time")
            fields["local_time"] = local_time
        elif kind == "window":
            if slot is None:
                raise ValidationError("window требует slot")
            default_slot_reference(slot)
            fields["slot"] = slot
            fields["reference_local_time"] = reference_local_time or default_slot_reference(slot)
        else:
            if anchor_appointment_id is None or direction is None or offset_minutes is None:
                raise ValidationError("relative требует якорь, direction и offset")
            if direction not in ("before", "after"):
                raise ValidationError("direction: before или after")
            if offset_minutes < 0:
                raise ValidationError("смещение не может быть отрицательным")
            self._assert_valid_anchor(house, anchor_appointment_id)
            fields["anchor_appointment_id"] = anchor_appointment_id
            fields["direction"] = direction
            fields["offset_minutes"] = offset_minutes
        return fields

    def _assert_valid_anchor(self, house: House, anchor_id: int) -> Appointment:
        anchor = self._appointment(anchor_id)
        if anchor.house_id != house.id:
            raise ValidationError("якорь из другого дома")
        if anchor.archived:
            raise ValidationError("якорь в архиве")
        return anchor

    def _live_dependents(self, appointment_id: int) -> list[Appointment]:
        return list(
            self.s.scalars(
                select(Appointment).where(
                    Appointment.anchor_appointment_id == appointment_id,
                    Appointment.archived.is_(False),
                    Appointment.id != appointment_id,
                )
            ).all()
        )

    def _apply_archive_appointment(self, house: House, appt: Appointment, now: datetime) -> None:
        if appt.archived:
            raise ValidationError("уже в архиве")
        if self._live_dependents(appt.id):
            raise ValidationError("нельзя архивировать якорь, на который ссылаются живые назначения")
        appt.archived = True
        self._drop_future_pending_today(house, appt, now)

    def _drop_future_pending_today(self, house: House, appt: Appointment, now: datetime) -> None:
        now = as_utc(now)
        step = self._current_step(house, appt, now)
        if step is None:
            return
        if step.status == "pending" and _aware(step.planned_at) > now:
            self._drop_step(step)

    def _drop_step(self, step: DayStep) -> None:
        for note in list(step.notifications):
            self.s.delete(note)
        self.s.delete(step)
        self.s.flush()

    def _maybe_step_on_unarchive(self, house: House, appt: Appointment, now: datetime) -> None:
        now = as_utc(now)
        plan, _, _ = care_day_bounds(now, house.schedule_timezone)
        if not self._course_active(appt, plan) or not self._active_animal_ids(appt):
            return
        leftover = self._current_step(house, appt, now)
        if leftover is not None:
            return
        day = self._ensure_care_day(house, now)
        assembled = self._step_for(day, appt.id)
        if assembled is not None:
            if assembled.status == "pending" and _aware(assembled.planned_at) <= now:
                self._drop_step(assembled)
            return
        planned, _, _ = self._plan_step(house, day, appt)
        if planned is None or planned <= now:
            return
        self._create_step(house, day, appt)

    def _assert_no_cycle(self, appointment_id: int, anchor_id: int) -> None:
        seen: set[int] = set()
        current: int | None = anchor_id
        while current is not None:
            if current == appointment_id:
                raise ValidationError("цикл якорей")
            if current in seen:
                raise ValidationError("цикл якорей")
            seen.add(current)
            node = self.s.get(Appointment, current)
            if node is None:
                break
            current = node.anchor_appointment_id

    def _course_active(self, appt: Appointment, plan_date: date) -> bool:
        if appt.archived:
            return False
        if appt.course_days is None:
            return True
        if appt.course_start_plan_date is None:
            return True
        start = appt.course_start_plan_date
        return start <= plan_date < start + timedelta(days=appt.course_days)

    # --- сутки и шаги ---

    def _ensure_care_day(self, house: House, now: datetime) -> CareDay:
        plan, starts, ends = care_day_bounds(now, house.schedule_timezone)
        day = self.s.scalars(
            select(CareDay).where(CareDay.house_id == house.id, CareDay.plan_date == plan)
        ).first()
        if day is None:
            day = CareDay(
                house_id=house.id,
                plan_date=plan,
                starts_at=_naive(starts),
                ends_at=_naive(ends),
            )
            self.s.add(day)
            self.s.flush()
            self._assemble_day(house, day)
        return day

    def _assemble_day(self, house: House, day: CareDay) -> None:
        appts = [
            a
            for a in self.s.scalars(select(Appointment).where(Appointment.house_id == house.id)).all()
            if self._course_active(a, day.plan_date) and self._active_animal_ids(a)
        ]
        for appt in self._topo(appts):
            if self._step_for(day, appt.id) is None:
                self._create_step(house, day, appt)

    def _ensure_step_for_current_day(self, house: House, appt: Appointment, now: datetime) -> DayStep | None:
        plan, _, _ = care_day_bounds(now, house.schedule_timezone)
        if not self._course_active(appt, plan) or not self._active_animal_ids(appt):
            return None
        day = self._ensure_care_day(house, now)
        existing = self._step_for(day, appt.id)
        if existing:
            return existing
        return self._create_step(house, day, appt)

    def _current_step(self, house: House, appt: Appointment, now: datetime) -> DayStep | None:
        plan, _, _ = care_day_bounds(now, house.schedule_timezone)
        day = self.s.scalars(
            select(CareDay).where(CareDay.house_id == house.id, CareDay.plan_date == plan)
        ).first()
        if day is None:
            return None
        return self._step_for(day, appt.id)

    def _step_for(self, day: CareDay, appointment_id: int) -> DayStep | None:
        return self.s.scalars(
            select(DayStep).where(DayStep.care_day_id == day.id, DayStep.appointment_id == appointment_id)
        ).first()

    def _topo(self, appts: list[Appointment]) -> list[Appointment]:
        ids = {a.id for a in appts}
        by_id = {a.id: a for a in appts}
        incoming: dict[int, int] = {a.id: 0 for a in appts}
        edges: dict[int, list[int]] = defaultdict(list)
        for a in appts:
            if a.kind == "relative" and a.anchor_appointment_id in ids:
                edges[a.anchor_appointment_id].append(a.id)
                incoming[a.id] += 1
        queue = deque(sorted(i for i, n in incoming.items() if n == 0))
        ordered: list[Appointment] = []
        while queue:
            i = queue.popleft()
            ordered.append(by_id[i])
            for nxt in edges[i]:
                incoming[nxt] -= 1
                if incoming[nxt] == 0:
                    queue.append(nxt)
        if len(ordered) != len(appts):
            leftover = [by_id[i] for i in ids if i not in {a.id for a in ordered}]
            ordered.extend(leftover)
        return ordered

    def _animal_ids(self, appt: Appointment) -> list[int]:
        return list(
            self.s.scalars(
                select(AppointmentAnimal.animal_id).where(AppointmentAnimal.appointment_id == appt.id)
            ).all()
        )

    def _active_animal_ids(self, appt: Appointment) -> list[int]:
        ids = []
        for aid in self._animal_ids(appt):
            animal = self.s.get(Animal, aid)
            if animal is not None and not animal.archived:
                ids.append(aid)
        return ids

    def _create_step(self, house: House, day: CareDay, appt: Appointment) -> DayStep | None:
        planned, accuracy, slot = self._plan_step(house, day, appt)
        if planned is None:
            return None
        step = DayStep(
            care_day_id=day.id,
            appointment_id=appt.id,
            animal_ids_snapshot=self._active_animal_ids(appt),
            planned_at=_naive(planned),
            time_accuracy=accuracy,
            status="pending",
            slot=slot,
        )
        self.s.add(step)
        self.s.flush()
        self._rebuild_notifications(house, step)
        return step

    def _clone_open_step(self, source: DayStep, copy: Appointment) -> DayStep:
        step = DayStep(
            care_day_id=source.care_day_id,
            appointment_id=copy.id,
            animal_ids_snapshot=self._active_animal_ids(copy),
            planned_at=source.planned_at,
            time_accuracy=source.time_accuracy,
            status="pending",
            slot=source.slot,
        )
        self.s.add(step)
        self.s.flush()
        house = self._house(copy.house_id)
        self._rebuild_notifications(house, step)
        return step

    def _plan_step(
        self, house: House, day: CareDay, appt: Appointment
    ) -> tuple[datetime | None, str, str | None]:
        ends = _aware(day.ends_at)
        if appt.kind == "fixed":
            planned = local_on_care_day(day.plan_date, appt.local_time, house.schedule_timezone)
            return self._clip_end(planned, ends), "exact", None
        if appt.kind == "window":
            planned = local_on_care_day(day.plan_date, appt.reference_local_time, house.schedule_timezone)
            return self._clip_end(planned, ends), "inexact", appt.slot
        anchor_step = self._step_for(day, appt.anchor_appointment_id)
        if anchor_step is None:
            return None, "inexact", None
        delta = timedelta(minutes=appt.offset_minutes or 0)
        origin = _aware(anchor_step.planned_at)
        planned = origin - delta if appt.direction == "before" else origin + delta
        accuracy = "exact" if anchor_step.time_accuracy == "exact" else "inexact"
        return self._clip_end(planned, ends), accuracy, anchor_step.slot

    def _clip_end(self, planned: datetime, ends: datetime) -> datetime:
        if planned >= ends:
            return ends - timedelta(microseconds=1)
        return planned

    def _sync_open_step(self, house: House, appt: Appointment, now: datetime) -> None:
        step = self._current_step(house, appt, now)
        if step is None:
            self._ensure_step_for_current_day(house, appt, now)
            return
        if step.status != "pending":
            return
        planned, accuracy, slot = self._plan_step(house, self.s.get(CareDay, step.care_day_id), appt)
        if planned is None:
            return
        step.planned_at = _naive(planned)
        step.time_accuracy = accuracy
        step.slot = slot
        self._rebuild_notifications(house, step)
        self._recompute_pending_dependents(house, appt, now)

    def _recompute_pending_dependents(self, house: House, origin: Appointment, now: datetime) -> None:
        day = self._ensure_care_day(house, now)
        for dep in self._dependent_appts(origin.id):
            step = self._step_for(day, dep.id)
            if step is None or step.status != "pending":
                continue
            planned, accuracy, slot = self._plan_step(house, day, dep)
            if planned is None:
                continue
            step.planned_at = _naive(planned)
            step.time_accuracy = accuracy
            step.slot = slot
            self._rebuild_notifications(house, step)
            self._recompute_pending_dependents(house, dep, now)

    # --- отметки и пересчёт ---

    def _write_log(self, house: House, step: DayStep, mark: Mark, fact_at: datetime | None) -> None:
        title = step.appointment.title
        for animal_id in step.animal_ids_snapshot:
            self.s.add(
                LogEntry(
                    house_id=house.id,
                    animal_id=animal_id,
                    step_id=step.id,
                    mark_id=mark.id,
                    title_snapshot=title,
                    fact_at=_naive(fact_at) if fact_at else None,
                    skipped=mark.kind == "skipped",
                    actor_user_id=mark.user_id,
                )
            )

    def _after_fact(self, step: DayStep, fact_at: datetime, now: datetime) -> None:
        self._shift_anchor_from_before(step, fact_at, now)
        self._cascade_dependents(step, fact_at, now)

    def _shift_anchor_from_before(self, step: DayStep, fact_at: datetime, now: datetime) -> None:
        appt = step.appointment
        if appt.kind != "relative" or appt.direction != "before":
            return
        day = self.s.get(CareDay, step.care_day_id)
        anchor_step = self._step_for(day, appt.anchor_appointment_id)
        if anchor_step is None or anchor_step.status in CLOSED:
            return
        new_time = fact_at + timedelta(minutes=appt.offset_minutes or 0)
        if new_time > now and new_time < _aware(day.ends_at):
            house = self._house(day.house_id)
            anchor_step.planned_at = _naive(new_time)
            anchor_step.time_accuracy = "exact"
            self._rebuild_notifications(house, anchor_step)
            self._cascade_dependents(anchor_step, new_time, now)

    def _cascade_dependents(self, origin_step: DayStep, origin_time: datetime, now: datetime) -> None:
        day = self.s.get(CareDay, origin_step.care_day_id)
        house = self._house(day.house_id)
        for dep in self._dependent_appts(origin_step.appointment_id):
            dep_step = self._step_for(day, dep.id)
            if dep_step is None or dep_step.status in CLOSED:
                continue
            delta = timedelta(minutes=dep.offset_minutes or 0)
            new_time = origin_time - delta if dep.direction == "before" else origin_time + delta
            if new_time > now and new_time < _aware(day.ends_at):
                dep_step.planned_at = _naive(new_time)
                dep_step.time_accuracy = "exact"
                self._rebuild_notifications(house, dep_step)
                self._cascade_dependents(dep_step, new_time, now)

    def _dependent_appts(self, appointment_id: int) -> list[Appointment]:
        return list(
            self.s.scalars(
                select(Appointment).where(
                    Appointment.anchor_appointment_id == appointment_id,
                    Appointment.archived.is_(False),
                    Appointment.kind == "relative",
                )
            ).all()
        )

    # --- просрочка и напоминания ---

    def _apply_overdue(self, house: House, now: datetime) -> None:
        days = self.s.scalars(select(CareDay).where(CareDay.house_id == house.id)).all()
        for day in days:
            for step in day.steps:
                if step.status != "pending":
                    continue
                # Скидка OVERDUE_GRACE: иначе tick раз в минуту помечает exact
                # overdue раньше, чем scheduled успевает стать due и уйти.
                if step.time_accuracy == "exact" and now > _aware(step.planned_at) + OVERDUE_GRACE:
                    step.status = "overdue"
                    self._cancel_notifications(step)
                    continue
                if step.time_accuracy == "inexact" and step.slot:
                    end = slot_end_at(day.plan_date, step.slot, house.schedule_timezone)
                    if end is not None and now >= end + OVERDUE_GRACE:
                        step.status = "overdue"
                        self._cancel_notifications(step)

    def _apply_notifications(self, house: House, now: datetime) -> None:
        days = self.s.scalars(select(CareDay).where(CareDay.house_id == house.id)).all()
        for day in days:
            for step in day.steps:
                if step.status != "pending" or step.appointment.silent:
                    continue
                if step.time_accuracy == "inexact":
                    self._maybe_inexact_repeat(house, day, step, now)
                for note in list(step.notifications):
                    if note.status == "scheduled" and _aware(note.fire_at) <= now:
                        note.status = "due"

    def _maybe_inexact_repeat(self, house: House, day: CareDay, step: DayStep, now: datetime) -> None:
        planned = _aware(step.planned_at)
        end = slot_end_at(day.plan_date, step.slot, house.schedule_timezone) if step.slot else None
        if now < planned:
            return
        if end is not None and now >= end:
            return
        elapsed = now - planned
        n = int(elapsed.total_seconds() // INEXACT_REPEAT.total_seconds())
        fire_at = planned + INEXACT_REPEAT * n
        if end is not None and fire_at >= end:
            return
        existing = [
            n
            for n in step.notifications
            if n.kind == "inexact_repeat" and _aware(n.fire_at) == fire_at and n.status != "cancelled"
        ]
        if existing:
            return
        self.s.add(
            NotificationDecision(
                step_id=step.id,
                fire_at=_naive(fire_at),
                kind="inexact_repeat",
                status="due",
                audience=self._audience(house),
            )
        )
        self.s.flush()

    def _rebuild_notifications(self, house: House, step: DayStep) -> None:
        self._cancel_notifications(step)
        if step.status != "pending" or step.appointment.silent:
            return
        kind = "exact_once" if step.time_accuracy == "exact" else "inexact_repeat"
        self.s.add(
            NotificationDecision(
                step_id=step.id,
                fire_at=step.planned_at,
                kind=kind,
                status="scheduled",
                audience=self._audience(house),
            )
        )
        self.s.flush()

    def _cancel_notifications(self, step: DayStep) -> None:
        for note in step.notifications:
            if note.status in LIVE_NOTIF:
                note.status = "cancelled"

    def _audience(self, house: House) -> list[int]:
        ids = [house.creator_user_id]
        if house.doubler_user_id:
            ids.append(house.doubler_user_id)
        return ids

    def _refresh_notification_audience(self, house: House) -> None:
        audience = self._audience(house)
        steps = self.s.scalars(select(DayStep).join(CareDay).where(CareDay.house_id == house.id)).all()
        for step in steps:
            for note in step.notifications:
                if note.status in LIVE_NOTIF:
                    note.audience = audience

    # --- представления ---

    def _user_view(self, user: User) -> UserView:
        return UserView(id=user.id, display_timezone=user.display_timezone, telegram_id=user.telegram_id)

    def _house_view(self, house: House) -> HouseView:
        return HouseView(
            id=house.id,
            creator_user_id=house.creator_user_id,
            schedule_timezone=house.schedule_timezone,
            doubler_user_id=house.doubler_user_id,
        )

    def _animal_view(self, animal: Animal) -> AnimalView:
        return AnimalView(
            id=animal.id,
            house_id=animal.house_id,
            name=animal.name,
            archived=animal.archived,
            avatar_key=animal.avatar_key,
        )

    def _normalize_avatar_key(self, avatar_key: str | None) -> str | None:
        if avatar_key is None:
            return None
        key = avatar_key.strip()
        if not key:
            raise ValidationError("avatar_key пустой")
        if len(key) > 64:
            raise ValidationError("avatar_key слишком длинный")
        return key

    def _appointment_view(self, appt: Appointment) -> AppointmentView:
        return AppointmentView(
            id=appt.id,
            house_id=appt.house_id,
            title=appt.title,
            kind=appt.kind,
            animal_ids=[a.id for a in appt.animals],
            archived=appt.archived,
            silent=appt.silent,
            course_days=appt.course_days,
            course_start_plan_date=appt.course_start_plan_date,
            local_time=appt.local_time,
            slot=appt.slot,
            reference_local_time=appt.reference_local_time,
            anchor_appointment_id=appt.anchor_appointment_id,
            direction=appt.direction,
            offset_minutes=appt.offset_minutes,
        )

    def _step_view(self, step: DayStep, house: House) -> StepView:
        planned = _aware(step.planned_at)
        day = self.s.get(CareDay, step.care_day_id)
        return StepView(
            id=step.id,
            appointment_id=step.appointment_id,
            house_id=house.id,
            plan_date=day.plan_date,
            title=step.appointment.title,
            planned_at=planned,
            planned_local=house_local_clock(planned, house.schedule_timezone),
            time_accuracy=step.time_accuracy,
            status=step.status,
            slot=step.slot,
            animal_ids=list(step.animal_ids_snapshot),
            silent=step.appointment.silent,
        )

    def _notification_view(self, note: NotificationDecision) -> NotificationView:
        return NotificationView(
            id=note.id,
            step_id=note.step_id,
            fire_at=_aware(note.fire_at),
            kind=note.kind,
            status=note.status,
            audience=list(note.audience),
        )
