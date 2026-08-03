from pathlib import Path
import os

IGNORED_FOLDERS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", ".next", ".idea", ".vscode", "target",
}

KEY_FILENAMES = {
    "README.md", "package.json", "requirements.txt", "pyproject.toml",
    "pom.xml", "Cargo.toml", "go.mod", "Dockerfile",
}
KEY_FILENAMES_LOWER = {name.lower() for name in KEY_FILENAMES}

def scan_repository(storage_path: str) -> dict:
    repo_root = Path(storage_path)

    files = []
    total_directories = 0
    total_size_bytes = 0
    language_breakdown: dict[str, int] = {}
    key_files: list[str] = []

    for current_folder, subfolders, filenames in os.walk(repo_root):
        subfolders[:] = [f for f in subfolders if f not in IGNORED_FOLDERS]

        total_directories += 1

        for filename in filenames:
            file_path = Path(current_folder) / filename
            relative_path = file_path.relative_to(repo_root)

            size_bytes = file_path.stat().st_size
            extension = file_path.suffix.lower() or None

            files.append({
                "path": relative_path.as_posix(),
                "extension": extension,
                "size_bytes": size_bytes,
            })

            total_size_bytes += size_bytes

            if extension:
                language_breakdown[extension] = language_breakdown.get(extension, 0) + 1

            if filename.lower() in KEY_FILENAMES_LOWER:
                key_files.append(relative_path.as_posix())

    return {
        "files": files,
        "total_files": len(files),
        "total_directories": total_directories,
        "total_size_bytes": total_size_bytes,
        "language_breakdown": language_breakdown,
        "key_files": key_files,
    }