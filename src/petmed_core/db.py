from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from petmed_core.models import Base


def create_session(url: str = "sqlite:///:memory:") -> Session:
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
