from pathlib import Path
import shutil
import zipfile
import subprocess

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

def clone_repository(repository_id: int, source_url: str) -> str:
    repo_folder = Path(REPO_STORAGE_DIR) / str(repository_id)

    # git requires an empty target folder - clean up any leftovers from
    # a previous failed attempt before cloning fresh, so retries work.
    if repo_folder.exists():
        shutil.rmtree(repo_folder)
    repo_folder.mkdir(parents=True)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", source_url, str(repo_folder)],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        error = (exc.stderr or exc.stdout or "Unknown git error").strip()
        raise RuntimeError(error)
    
    return repo_folder.as_posix()

# Deletes a repo's entire folder from disk, if it exists.
def delete_repository_files(repository_id: int) -> None:
    repo_folder = Path(REPO_STORAGE_DIR) / str(repository_id)

    if repo_folder.exists():
        shutil.rmtree(repo_folder)