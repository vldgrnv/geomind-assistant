import hashlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.models import create_user, get_user_by_email
from auth.jwt import create_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str


@router.post("/register", response_model=AuthResponse)
def register(req: AuthRequest):
    if get_user_by_email(req.email):
        raise HTTPException(400, "Email уже зарегистрирован")
    user_id = create_user(req.email, _hash(req.password))
    return AuthResponse(token=create_token(user_id))


@router.post("/login", response_model=AuthResponse)
def login(req: AuthRequest):
    user = get_user_by_email(req.email)
    if not user or user["password_hash"] != _hash(req.password):
        raise HTTPException(401, "Неверный email или пароль")
    return AuthResponse(token=create_token(user["id"]))
