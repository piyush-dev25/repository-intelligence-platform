from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.user import UserCreate, UserOut
from app.services.auth_service import get_current_user, login, signup
from app.schemas.auth import LoginRequest, Token

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def signup_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    return signup(db, user)

@router.post(
    "/login",
    response_model=Token,
)
def login_user(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    return login(db, login_data)

security = HTTPBearer()

@router.get(
    "/me",
    response_model=UserOut,
)
def read_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    return get_current_user(
        db,
        credentials.credentials,
    )