from pydantic import BaseModel, EmailStr 


# --- SCHEMA FOR LOGGING IN ---
# What the user sends when hitting the /login endpoint
class LoginRequest(BaseModel):
    email :EmailStr
    password: str


# --- SCHEMA FOR THE TOKEN RESPONSE ---
# What our server sends back when a login is successful
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- SCHEMA FOR INSIDE THE DECODED JWT ---
# Used internally to validate the payload extracted from a user's token
class TokenData(BaseModel):
    sub: str | None = None  # 'sub' stands for Subject, usually stores the user's ID string