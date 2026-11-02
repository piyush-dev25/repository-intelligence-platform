from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.repository import router as repository_router
from app.db import base  # noqa: F401 - imported for side effect (registers all models)
from app.db.database import SessionLocal
from app.services.repository_service import reset_interrupted_repositories


# Runs once when the server starts (code before `yield`). Resets repos left
# stuck in scanning/analyzing by a previous run, since their background work
# died with the old server. If the DB is down, warn and start anyway - the
# OperationalError handler below already covers requests in that case.
@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        reset_interrupted_repositories(db)
    except OperationalError:
        print("Startup: database unavailable - skipped resetting interrupted repositories.")
    finally:
        db.close()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected (mock)"}

@app.get("/")
def read_root():
    return {"status": "success", "message": "Repository Intelligence Platform Backend is running!"}

app.include_router(auth_router)

app.include_router(repository_router)

# Catches database connection failures anywhere in the app (e.g. Docker
# not running) and returns a clean error instead of hanging or crashing
# with a raw traceback.
@app.exception_handler(OperationalError)
def database_connection_error_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is currently unavailable. Please try again later."},
    )