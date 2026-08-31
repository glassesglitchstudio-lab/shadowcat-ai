from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime

router = APIRouter()

# Davet kodu sistemi - BETA kapali test. Gecerli kodlar burada.
INVITE_CODES = {"GLASSCAT-BETA-2026", "GLASSES-GLITCH"}

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    invite_code: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class SimpleLoginRequest(BaseModel):
    name: str
    beta_key: str

class DevLoginRequest(BaseModel):
    password: str

@router.post("/register")
async def register(req: RegisterRequest, response: Response):
    from middleware.auth import users, hash_password, create_session, _save_users
    code = (req.invite_code or "").strip().upper()
    valid = code in INVITE_CODES
    if not valid:
        try:
            from routes.admin import valid_keys, _save_keys
            key_info = valid_keys.get(code)
            valid = bool(key_info) and key_info.get("is_active", True)
            if valid:
                key_info["used_by"] = req.email
                key_info["last_used"] = datetime.now().isoformat()
                _save_keys()
        except Exception:
            valid = False
    if not valid:
        raise HTTPException(status_code=403, detail="Gecersiz veya eksik davet kodu. Shadowcat su anda davetli kullanicilara aciktir.")
    if req.email in users:
        raise HTTPException(status_code=400, detail="E-posta zaten kayıtlı")
    users[req.email] = {
        "name": req.name,
        "email": req.email,
        "password": hash_password(req.password),
        "is_admin": False,
        "is_dev": False
    }
    _save_users(users)
    token = create_session(req.email)
    response.set_cookie("session_token", token, httponly=True, max_age=7*24*3600)
    return {"message": "Kayıt başarılı", "token": token}

@router.post("/login")
async def login(req: LoginRequest, response: Response):
    from middleware.auth import users, verify_password, create_session, sessions

    # DEV_MODE: şifre doğrulamasını atla
    dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"

    if req.email not in users:
        if dev_mode:
            # DEV_MODE'da otomatik kayıt
            from middleware.auth import hash_password, _save_users
            users[req.email] = {
                "name": req.email.split("@")[0],
                "email": req.email,
                "password": hash_password(req.password),
                "is_admin": True,
                "is_dev": True
            }
            _save_users(users)
        else:
            raise HTTPException(status_code=401, detail="Geçersiz e-posta veya şifre")

    user = users[req.email]
    if not dev_mode and not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=401, detail="Geçersiz e-posta veya şifre")

    token = create_session(req.email)
    response.set_cookie("session_token", token, httponly=True, max_age=7*24*3600)
    return {"message": "Giriş başarılı", "token": token, "user": {"name": user["name"], "email": user["email"]}}

@router.get("/me")
async def get_me(request: Request):
    from middleware.auth import sessions
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Oturum bulunamadı")
    return {"user": sessions[token]}

@router.post("/logout")
async def logout(response: Response):
    from middleware.auth import sessions
    response.delete_cookie("session_token")
    return {"message": "Çıkış yapıldı"}

DEV_SIMPLE_PASSWORD = os.getenv("DEV_SIMPLE_PASSWORD", "adminShadowcat")

@router.post("/simple-login")
async def simple_login(req: SimpleLoginRequest, response: Response):
    """Basit İsim + Beta Key ile giriş"""
    from middleware.auth import users, create_session, _save_users
    name = req.name.strip()
    beta_key = req.beta_key.strip().upper()

    if not name:
        raise HTTPException(status_code=400, detail="İsim gereklidir!")
    if not beta_key:
        raise HTTPException(status_code=400, detail="Beta Key gereklidir!")

    # Gerçek davet kodu kontrolü (sabit kodlar + admin'in ürettiği beta key'ler)
    valid = beta_key in INVITE_CODES
    if not valid:
        try:
            from routes.admin import valid_keys, _save_keys
            key_info = valid_keys.get(beta_key)
            valid = bool(key_info) and key_info.get("is_active", True)
            if valid:
                key_info["used_by"] = name
                key_info["last_used"] = datetime.now().isoformat()
                _save_keys()
        except Exception:
            valid = False
    if not valid:
        raise HTTPException(status_code=401, detail="Gecersiz veya pasif davet kodu! Shadowcat su anda davetli kullanicilara aciktir.")

    users[name] = {
        "name": name,
        "beta_key": beta_key,
        "created_at": datetime.now().isoformat(),
        "last_login": datetime.now().isoformat()
    }
    _save_users(users)

    token = create_session(name)
    response.set_cookie("session_token", token, httponly=True, max_age=7*24*3600)
    return {"success": True, "message": f"Hoş geldin {name}!", "name": name, "token": token}

@router.post("/dev-login-simple")
async def dev_login_simple(req: DevLoginRequest, response: Response):
    """Geliştirici girişi - Şifre: adminShadowcat"""
    from middleware.auth import users, create_session
    password = req.password.strip()

    if not password:
        raise HTTPException(status_code=400, detail="Şifre gereklidir!")
    if password != DEV_SIMPLE_PASSWORD:
        raise HTTPException(status_code=401, detail="Geçersiz şifre!")

    name = "Admin"
    users[name] = {
        "name": name,
        "beta_key": "DEV-MODE-SIMPLE",
        "is_dev": True,
        "created_at": datetime.now().isoformat(),
        "last_login": datetime.now().isoformat()
    }
    from middleware.auth import _save_users
    _save_users(users)

    token = create_session(name)
    response.set_cookie("session_token", token, httponly=True, max_age=7*24*3600)
    return {"success": True, "message": "Geliştirici modu aktif! Hoş geldin Admin!", "name": name, "token": token}
