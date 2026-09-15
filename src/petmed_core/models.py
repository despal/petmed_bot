from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    telegram_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)


class House(Base):
    __tablename__ = "houses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    schedule_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    doubler_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    animals: Mapped[list["Animal"]] = relationship(back_populates="house")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="house")


class Animal(Base):
    __tablename__ = "animals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    avatar_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    house: Mapped[House] = relationship(back_populates="animals")


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AppointmentAnimal(Base):
    __tablename__ = "appointment_animals"
    __table_args__ = (UniqueConstraint("appointment_id", "animal_id"),)

    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), primary_key=True)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    silent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    course_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    course_start_plan_date = mapped_column(Date, nullable=True)

    local_time = mapped_column(Time, nullable=True)
    slot: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reference_local_time = mapped_column(Time, nullable=True)

    anchor_appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    house: Mapped[House] = relationship(back_populates="appointments")
    animals: Mapped[list[Animal]] = relationship(secondary="appointment_animals")
    anchor: Mapped["Appointment | None"] = relationship(remote_side=[id])


class CareDay(Base):
    __tablename__ = "care_days"
    __table_args__ = (UniqueConstraint("house_id", "plan_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), nullable=False)
    plan_date = mapped_column(Date, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    steps: Mapped[list["DayStep"]] = relationship(back_populates="care_day")


class DayStep(Base):
    __tablename__ = "day_steps"
    __table_args__ = (UniqueConstraint("care_day_id", "appointment_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    care_day_id: Mapped[int] = mapped_column(ForeignKey("care_days.id"), nullable=False)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), nullable=False)
    animal_ids_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    planned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    time_accuracy: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    slot: Mapped[str | None] = mapped_column(String(16), nullable=True)

    care_day: Mapped[CareDay] = relationship(back_populates="steps")
    appointment: Mapped[Appointment] = relationship()
    marks: Mapped[list["Mark"]] = relationship(back_populates="step")
    notifications: Mapped[list["NotificationDecision"]] = relationship(back_populates="step")


class Mark(Base):
    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("day_steps.id"), nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    fact_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    step: Mapped[DayStep] = relationship(back_populates="marks")


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), nullable=False)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), nullable=False)
    step_id: Mapped[int] = mapped_column(ForeignKey("day_steps.id"), nullable=False)
    mark_id: Mapped[int] = mapped_column(ForeignKey("marks.id"), nullable=False)
    title_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    fact_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class JournalNote(Base):
    __tablename__ = "journal_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), nullable=False)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    noted_on = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class NotificationDecision(Base):
    __tablename__ = "notification_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("day_steps.id"), nullable=False)
    fire_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    audience: Mapped[list] = mapped_column(JSON, nullable=False)

    step: Mapped[DayStep] = relationship(back_populates="notifications")
