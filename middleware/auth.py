import os
import hashlib
import secrets
import json
from datetime import datetime
from functools import wraps
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

USERS_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auth_users.json")

# Session depolama
sessions: dict = {}

def _load_users() -> dict:
    if os.path.exists(USERS_DB):
        try:
            with open(USERS_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_users(data: dict):
    with open(USERS_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users: dict = _load_users()

def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 ile güvenli, salt'lı şifreleme (100,000 tur)"""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"pbkdf2:{salt.hex()}:{key.hex()}"

def verify_password(password: str, stored: str) -> bool:
    """Geriye dönük uyumlu şifre doğrulama (PBKDF2 + Legacy Salted SHA256)"""
    if not stored:
        return False
    try:
        parts = stored.split(":", 2)
        if parts[0] == "pbkdf2":
            salt = bytes.fromhex(parts[1])
            expected_key = parts[2]
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
            return key.hex() == expected_key
        elif len(parts) == 2:
            salt_str, h = parts[0], parts[1]
            return hashlib.sha256(f"{salt_str}{password}".encode()).hexdigest() == h
        else:
            return hashlib.sha256(password.encode()).hexdigest() == stored
    except Exception:
        return False

def create_session(user_email: str) -> str:
    token = secrets.token_hex(32)
    user = users.get(user_email, {})
    sessions[token] = {
        "email": user_email,
        "created": datetime.now().isoformat(),
        "is_admin": bool(user.get("is_admin", False)),
        "is_dev": bool(user.get("is_dev", False)),
    }
    return token

def get_session_user(token: str) -> dict | None:
    return sessions.get(token)

async def require_auth(request: Request):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Oturum açmanız gerekiyor")
    return sessions[token]

async def require_admin(request: Request):
    """Admin yetkisi: kullanıcının is_admin bayrağına bakar (oturum oluşturulurken kopyalanır)."""
    user = await require_auth(request)
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")
    return user
