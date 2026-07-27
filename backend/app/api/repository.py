from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.repository import RepositoryCreate, RepositoryOut
from app.services.auth_service import get_current_user
from app.services.repository_service import (
    get_repository_for_owner,
    list_user_repositories,
    register_repository,
)

router = APIRouter(
    prefix="/repositories",
    tags=["Repositories"],
)

security = HTTPBearer()


# Registers a new repo for whoever's making the request.
@router.post(
    "",
    response_model=RepositoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_repository(
    repo_in: RepositoryCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(db, credentials.credentials)
    return register_repository(db, current_user.id, repo_in)


# Lists every repo belonging to whoever's making the request.
@router.get(
    "",
    response_model=list[RepositoryOut],
)
def list_repositories(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(db, credentials.credentials)
    return list_user_repositories(db, current_user.id)


# Gets one specific repo - only if it belongs to whoever's asking.
@router.get(
    "/{repository_id}",
    response_model=RepositoryOut,
)
def get_repository(
    repository_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(db, credentials.credentials)
    return get_repository_for_owner(db, repository_id, current_user.id)