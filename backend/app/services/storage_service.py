from pathlib import Path
import shutil
import zipfile

from fastapi import UploadFile

from app.core.config import REPO_STORAGE_DIR


def save_and_unzip_repository(repository_id: int, file: UploadFile) -> str:
    # Each repo gets its own folder, named after its id.
    repo_folder = Path(REPO_STORAGE_DIR) / str(repository_id)
    repo_folder.mkdir(parents=True, exist_ok=True)

    zip_path = repo_folder / "repository.zip"
    with open(zip_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(repo_folder)

    zip_path.unlink()

    # Convert to a plain string with forward slashes, so what's stored
    # in the database is consistent no matter which OS this runs on.
    return repo_folder.as_posix()