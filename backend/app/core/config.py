from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
)

# Where uploaded/cloned repo files get stored on disk.
# Defaults to a local folder if not set in .env - fine for dev,
# you'll likely point this at a real volume/bucket in production.
REPO_STORAGE_DIR = os.getenv("REPO_STORAGE_DIR", "storage/repos")