from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


# connect_timeout tells it to give up after 5 seconds instead of
# hanging forever if the database can't be reached (e.g. Docker's off).
engine = create_engine(
    DATABASE_URL,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()