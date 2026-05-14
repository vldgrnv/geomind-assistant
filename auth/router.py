from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from auth.passwords import hash_password, verify_password
from database.models import create_user, get_user_by_email, update_user_password_hash
from auth.jwt import create_token

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str


@router.post("/register", response_model=AuthResponse)
def register(req: AuthRequest):
    if get_user_by_email(req.email):
        raise HTTPException(400, "Email уже зарегистрирован")
    user_id = create_user(req.email, hash_password(req.password))
    return AuthResponse(token=create_token(user_id))


@router.post("/login", response_model=AuthResponse)
def login(req: AuthRequest):
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(401, "Неверный email или пароль")
    is_valid, needs_upgrade = verify_password(req.password, user["password_hash"])
    if not is_valid:
        raise HTTPException(401, "Неверный email или пароль")
    if needs_upgrade:
        update_user_password_hash(user["id"], hash_password(req.password))
    return AuthResponse(token=create_token(user["id"]))
