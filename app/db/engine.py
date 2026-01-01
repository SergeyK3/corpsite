import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/corpsite",
)

engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)
