from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from petmed_core.models import Base


def ensure_schema(engine: Engine) -> None:
    """create_all + лёгкие ALTER для уже существующих SQLite-файлов."""
    Base.metadata.create_all(engine)
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(houses)")).fetchall()
        cols = {row[1] for row in rows}
        if "doubler_start_seen" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE houses ADD COLUMN doubler_start_seen "
                    "BOOLEAN NOT NULL DEFAULT 0"
                )
            )


def create_session(url: str = "sqlite:///:memory:") -> Session:
    engine = create_engine(url)
    ensure_schema(engine)
    return sessionmaker(bind=engine)()
