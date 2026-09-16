from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from petmed_api.routes import router
from petmed_core.db import ensure_schema


def create_app() -> FastAPI:
    app = FastAPI(title="petmed API", version="0.1.0")
    db_url = os.environ.get("DATABASE_URL", "sqlite:///petmed.db")
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    ensure_schema(engine)
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    if os.environ.get("DEV_TELEGRAM_ID"):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(router)
    return app


app = create_app()
