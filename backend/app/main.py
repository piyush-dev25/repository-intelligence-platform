from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.repository import router as repository_router 

app = FastAPI()

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