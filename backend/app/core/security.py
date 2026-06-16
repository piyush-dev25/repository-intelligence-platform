from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from typing import Any

from app.core.config import (
	ACCESS_TOKEN_EXPIRE_MINUTES,
	JWT_ALGORITHM,
	JWT_SECRET_KEY,
)


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
	return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
	return password_hash.verify(password, hashed_password)


def create_access_token(data: dict) -> str:
	payload = data.copy()
	payload["exp"] = datetime.now(timezone.utc) + timedelta(
		minutes=ACCESS_TOKEN_EXPIRE_MINUTES
	)
	return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
	return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])