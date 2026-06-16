from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate  # Use your Pydantic schema!


def get_user_by_email(db: Session, email: str) -> User | None:
    """Modern SQLAlchemy 2.0 style select query."""
    statement = select(User).where(User.email == email)
    return db.execute(statement).scalar_one_or_none()


def create_user(db: Session, db_user: User) -> User:
    """Pure data access: takes an entity object and saves it to PostgreSQL."""
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_id(db: Session, user_id: int) -> User | None:
    statement = select(User).where(User.id == user_id)
    return db.execute(statement).scalar_one_or_none()