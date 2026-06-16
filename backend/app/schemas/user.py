from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- SHARED PROPERTIES ---
# This base schema contains fields that are common to both creating and reading users
class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)


# --- SCHEMA FOR INCOMING DATA (Request Body) ---
# Used when a user is signing up. They must provide a plain text password.
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=64)


# --- SCHEMA FOR OUTGOING DATA (Response Body) ---
# Used when sending user data back to the frontend.
# Notice we DO NOT include the password or hashed_password here!
class UserOut(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    # This tells Pydantic v2 to automatically read data from SQLAlchemy ORM objects
    model_config = ConfigDict(
        from_attributes=True
    )