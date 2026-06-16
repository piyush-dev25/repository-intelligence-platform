from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from jwt import InvalidTokenError
from app.data_access.user_data_access import (
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from app.models.user import User
from app.schemas.user import UserCreate

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.schemas.auth import (
    LoginRequest,
    Token,
    TokenData,
)

def signup(db: Session, user_in: UserCreate) -> User:
    # Check if email is already registered
    existing_user = get_user_by_email(db, user_in.email)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Business logic
    hashed_password = hash_password(user_in.password)

    user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hashed_password,
    )

    return create_user(db, user)


def login(
    db: Session,
    login_data: LoginRequest,
) -> Token:
    user = get_user_by_email(db, login_data.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(
        login_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        {
            "sub": str(user.id),
        }
    )

    return Token(
        access_token=access_token,
    )

def get_current_user(db: Session, token: str) -> User:
    # 1. Try to decode the raw string token safely
    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Extract the subject ('sub') from the token payload
    token_data = TokenData(sub=payload.get("sub"))

    # 3. Ensure the token actually contained a user ID
    if token_data.sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Look up the user in PostgreSQL
    user = get_user_by_id(db, int(token_data.sub))

    # 5. If the user was deleted from the DB but still has a valid token, reject them
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user