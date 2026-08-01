from fastapi import APIRouter, Depends, File, status, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.repository import RepositoryCreate, RepositoryOut
from app.services.auth_service import get_current_user
from app.services.repository_service import (
    get_repository_for_owner,
    list_user_repositories,
    register_repository,
    ingest_uploaded_repository,
    ingest_git_repository,
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

# Accepts an uploaded zip file for a repo that was registered as
# source_type "upload", saves + unzips it, and updates its status.
@router.post(
    "/{repository_id}/upload",
    response_model=RepositoryOut,
)
def upload_repository_file(
    repository_id: int,
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(db, credentials.credentials)
    return ingest_uploaded_repository(db, repository_id, current_user.id, file)

# Clones a git repo for a repo that was registered as source_type "git",
# and updates its status accordingly.
@router.post(
    "/{repository_id}/clone",
    response_model=RepositoryOut,
)
def clone_repository_endpoint(
    repository_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(db, credentials.credentials)
    return ingest_git_repository(db, repository_id, current_user.id)