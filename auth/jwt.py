import os
import jwt
import datetime
from fastapi import Header, HTTPException

SECRET = os.environ.get("JWT_SECRET", "geomind-secret-key-change-in-prod")
EXPIRE_DAYS = int(os.environ.get("JWT_EXPIRE_DAYS", 30))
ALGORITHM = "HS256"


def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def get_current_user_id(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Невалидный токен")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Токен истёк")
    except jwt.DecodeError:
        raise HTTPException(401, "Невалидный токен")
