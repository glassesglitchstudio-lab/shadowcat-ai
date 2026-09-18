"""Shadowcat AI - Web Server (FastAPI)"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
import httpx
import asyncio
import logging
import os
import json
import re
import shlex
import hashlib
import secrets
from datetime import datetime
import uuid
import io
import csv
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from middleware.auth import require_admin

import subprocess as _sub
if os.name == "nt":
    _CREATE_NO_WINDOW = 0x08000000
    _sub_orig_run = _sub.run
    _sub_orig_popen_init = _sub.Popen.__init__

    def _gizle(kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        return kwargs

    def _patched_run(*args, **kwargs):
        return _sub_orig_run(*args, **_gizle(kwargs))

    def _patched_popen_init(self, *args, **kwargs):
        _sub_orig_popen_init(self, *args, **_gizle(kwargs))

    _sub.run = _patched_run
    _sub.Popen.__init__ = _patched_popen_init


try:

    from shadowcat_core import get_core

    CORE_AVAILABLE = True

except ImportError:

    CORE_AVAILABLE = False



try:

    from codes_router import get_codes_router, is_codes_tier

except ImportError:

    def get_codes_router():
        raise RuntimeError("codes_router.py eksik")

    def is_codes_tier(value: str) -> bool:
        return False



# Modüller

from actions import launch_app, APP_MAPPINGS

from utils import get_system_status

# ── Context Archive: 0 kayıpsız sonsuz context (özetsiz retrieval bellek) ──
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "elytra_vnpu"))
    from context_archive import ContextArchive
    CONTEXT_ARCHIVE_AVAILABLE = True
except Exception:  # ImportError veya sys.path sorunu
    CONTEXT_ARCHIVE_AVAILABLE = False

_CONTEXT_ARCHIVE = None

def get_context_archive():
    """Sohbet geçmişinin 0-kayıpsız arşivi (lazy singleton)."""
    global _CONTEXT_ARCHIVE
    if _CONTEXT_ARCHIVE is None and CONTEXT_ARCHIVE_AVAILABLE:
        try:
            _CONTEXT_ARCHIVE = ContextArchive(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "storage", "context_archive.db"))
            logger.info("[ContextArchive] Aktif — context dolunca eskiler özetsiz arşive gider, sorguya göre geri gelir")
        except Exception as e:
            logger.warning(f"[ContextArchive] Başlatılamadı: {e}")
    return _CONTEXT_ARCHIVE

import sys as _sys
_context_window_soft_limit = 24000   # yaklaşık karakter eşiği (≈6K token) — async stack'lerde bilgi amaçlı
_context_keep_last = 12              # prompt'ta tutulacak son mesaj sayısı

def _normalize_history(raw: Optional[List[Any]]) -> List[Dict[str, str]]:
    """Frontend'den gelen history'yi temizler: role/content stringleri, max 80 mesaj.
    Frontend rolü 'ai' → Ollama rolü 'assistant' eşlemesi burada yapılır."""
    if not isinstance(raw, list):
        return []
    _ROLE_MAP = {"ai": "assistant", "bot": "assistant", "model": "assistant", "human": "user", "system": "system"}
    out = []
    for m in raw[-80:]:
        if not isinstance(m, dict):
            continue
        role = _ROLE_MAP.get(str(m.get("role", "user")).lower(), "user")
        content = m.get("content", m.get("text", ""))
        if not isinstance(content, str):
            content = str(content)
        if content.strip():
            out.append({"role": role, "content": content})
    return out


def _archive_from_history(username: str, conv_id: str, history: List[Dict[str, str]]) -> None:
    """Gelen geçmişi arşive yazar (idempotent id'lerle)."""
    arc = get_context_archive()
    if not arc or not history:
        return
    base = f"{username}:{conv_id}:"
    for i, m in enumerate(history):
        try:
            # idempotent, içerik-bağımlı id → aynı mesaj tekrar arşive yazılmaz
            ctag = hashlib.md5(m["content"].encode("utf-8")).hexdigest()[:10]
            arc.add(base + str(i) + ":" + ctag, m["content"],
                    {"role": m["role"], "username": username, "conv_id": conv_id})
        except Exception:
            pass


def _build_context_block(user_query: str) -> str:
    """Arşivden sorguya göre ilgili eski bağlamı getirir (0 kayıp: özet yok, orijinal metin)."""
    arc = get_context_archive()
    if not arc:
        return ""
    try:
        return arc.build_context(user_query, k=3, max_chars=2000) or ""
    except Exception:
        return ""


def _effective_messages(history: List[Dict[str, str]], user_msg: str, system_prompt: str) -> List[Dict[str, str]]:
    """Modele gidecek mesaj listesi: [system] + [arşiv bağlamı] + [son N geçmiş] + [yeni mesaj].
    Geçmiş yumuşak limiti aşarsa en eski kısım arşive taşınır (özetsiz — kayıp yok)."""
    msgs: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    hist = list(history or [])
    # Mükerrer engelle: frontend son kullanıcı mesajını history'ye de koyabilir
    if hist and hist[-1].get("role") == "user" and hist[-1].get("content", "").strip() == user_msg.strip():
        hist.pop()
    # Yumuşak pencere: geçmiş çok uzunsa eskileri arşive at, son N'i tut
    while len(hist) > _context_keep_last:
        oldest = hist.pop(0)
        arc = get_context_archive()
        if arc:
            try:
                arc.add(f"soft:{uuid.uuid4().hex[:12]}", oldest["content"],
                        {"role": oldest["role"], "note": "soft-window"})
            except Exception:
                pass
    ctx_block = _build_context_block(user_msg)
    if ctx_block:
        msgs.append({"role": "system", "content": ctx_block})
    msgs.extend(hist)
    msgs.append({"role": "user", "content": user_msg})
    return msgs

from vision import analyze_image, ocr_from_image



# Logging ayarları

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)



# Kullanıcı veritabanı

USERS_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_users.json")

SESSIONS = {}

# Davet kodu sistemi - BETA kapali test

INVITE_CODES = {'glasscat-beta-2026', 'glasses-glitch-demo'}

INVITE_CODES_REQUIRED = True



def load_users():

    """Kullanıcıları yükle"""

    if os.path.exists(USERS_DB):

        with open(USERS_DB, 'r', encoding='utf-8') as f:

            return json.load(f)

    return {}



def save_users(users):

    """Kullanıcıları kaydet"""

    with open(USERS_DB, 'w', encoding='utf-8') as f:

        json.dump(users, f, ensure_ascii=False, indent=2)


def hash_password(password: str) -> str:
    """Sifreyi guvende hashle - PBKDF2-HMAC-SHA256 + rastgele salt (100_000 tur)."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2:{salt.hex()}:{key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Geriye donuk uyumlu dogrulama: PBKDF2 (yeni) + plain SHA256 (eski kayitlar)."""
    if not stored:
        return False
    try:
        parts = stored.split(":", 2)
        if len(parts) == 3 and parts[0] == "pbkdf2":
            salt = bytes.fromhex(parts[1])
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
            return key.hex() == parts[2]
        return hashlib.sha256(password.encode()).hexdigest() == stored
    except Exception:
        return False




# Gunluk mesaj limiti - BETA korumasi

DAILY_MSG_LIMIT = 0  # 0 = sinirsiz (kisitlama kapali)

USAGE_DB = 'usage.json'



def _today() -> str:

    return datetime.now().strftime('%Y-%m-%d')



def load_usage() -> dict:

    if os.path.exists(USAGE_DB):

        try:

            with open(USAGE_DB, 'r', encoding='utf-8') as f:

                return json.load(f)

        except Exception:

            pass

    return {}



def save_usage(data: dict):

    try:

        with open(USAGE_DB, 'w', encoding='utf-8') as f:

            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception:

        pass



def check_message_limit(username: str) -> Optional[dict]:

    # Limit 0 ise kisitlama kapali - sinirsiz kullanim

    if DAILY_MSG_LIMIT <= 0:

        return None

    """Limit asildiysa hata dict dondurur, asilmadisa None"""

    usage = load_usage()

    key = username or 'misafir'

    today = _today()

    day = usage.get(key, {})

    count = day.get(today, 0) if isinstance(day, dict) else 0

    if count >= DAILY_MSG_LIMIT:

        return {

            'success': False,

            'error': 'Gunluk mesaj limitin doldu (100). Yarin tekrar gorusuruz!'

        }

    return None



def increment_message_count(username: str):

    usage = load_usage()

    key = username or 'misafir'

    today = _today()

    day = usage.get(key)

    if not isinstance(day, dict):

        day = {}

    day[today] = int(day.get(today, 0)) + 1

    usage[key] = day

    save_usage(usage)

    return day[today]



def get_message_count(username: str) -> int:

    usage = load_usage()

    key = username or 'misafir'

    day = usage.get(key, {})

    if not isinstance(day, dict):

        return 0

    return int(day.get(_today(), 0))

def generate_token() -> str:

    """Token oluştur"""

    return secrets.token_urlsafe(32)



# FastAPI uygulaması

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Başlangıç: Ollama servisini otomatik başlat
    try:
        ensure_ollama_running()
    except Exception as e:
        logger.warning(f"[Startup] Ollama kontrolü atlandı: {e}")
    yield
    # Kapanış: burada gerekiyorsa temizlik yapılabilir

app = FastAPI(

    title="Shadowcat BETA",

    description="SWA 1.6 Mimarisi - Hibrit Zeka Sistemi",

    version="1.0.0",

    lifespan=lifespan

)



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "web", "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "web", "templates")

# Templates ve Static dosyalar
templates = Jinja2Templates(directory=TEMPLATES_DIR if os.path.exists(TEMPLATES_DIR) else "web/templates")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
elif os.path.exists("web/static"):
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

def normalize_ollama_base_url(url: Optional[str] = None) -> str:
    base = (url or os.getenv("OLLAMA_URL", "http://localhost:11434")).strip().rstrip("/")
    if base.endswith("/api/chat"):
        base = base[:-9]
    elif base.endswith("/api/generate"):
        base = base[:-13]
    return base.rstrip("/")

def _find_static_file(filename: str) -> Optional[str]:
    candidates = [
        os.path.join(STATIC_DIR, filename),
        os.path.join(BASE_DIR, "docs", filename),
        os.path.join(BASE_DIR, filename),
        os.path.join("web", "static", filename),
        os.path.join("docs", filename),
        filename,
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isfile(c):
            return c
    return None

# Root statik dosya rotaları (404 önleyici)
@app.get("/shadowcat-logo.png")
async def get_root_logo():
    p = _find_static_file("shadowcat-logo.png")
    if p:
        return FileResponse(p, media_type="image/png")
    return Response(status_code=404)

@app.get("/skill-logo.png")
async def get_root_skill_logo():
    p = _find_static_file("skill-logo.png")
    if p:
        return FileResponse(p, media_type="image/png")
    return Response(status_code=404)

@app.get("/skills-library.js")
async def get_root_skills_lib():
    p = _find_static_file("skills-library.js")
    if p:
        return FileResponse(p, media_type="application/javascript")
    return Response(status_code=404)

@app.get("/select-script.js")
async def get_root_select_script():
    p = _find_static_file("select-script.js")
    if p:
        return FileResponse(p, media_type="application/javascript")
    return Response(status_code=404)

@app.get("/favicon.ico")
async def get_root_favicon():
    p = _find_static_file("shadowcat-logo.png")
    if p:
        return FileResponse(p, media_type="image/png")
    return Response(status_code=204)



# CORS ayarları

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)



# Modüler route'ları dahil et

try:

    from routes import router as api_router

    app.include_router(api_router)

    logger.info("Modüler route'lar yüklendi")

except Exception as e:

    logger.debug(f"Route yükleme hatası: {e}")

# Model Hub (LM Studio benzeri model kesfi/indirme)
try:
    from model_hub import router as hub_router
    app.include_router(hub_router)
    logger.info("Model Hub (HuggingFace) yüklendi: /hub/*")
except Exception as e:
    logger.debug(f"Model Hub yüklenemedi: {e}")


@app.get("/hub", response_class=HTMLResponse)
async def hub_page():
    """Model Hub web arayuzu."""
    return FileResponse(os.path.join(BASE_DIR, "web", "templates", "hub.html"))


@app.get("/app", response_class=HTMLResponse)
@app.get("/engine", response_class=HTMLResponse)
async def app_page():
    """Elytra Engine: LM Studio benzeri yerel NPU arayüzü (sidebar + chat + telemetri)."""
    engine_template = os.path.join(BASE_DIR, "web", "templates", "elytra_engine.html")
    if os.path.exists(engine_template):
        return FileResponse(engine_template, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return FileResponse(os.path.join(BASE_DIR, "web", "templates", "app.html"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})




# Hibrit Zeka Yapılandırması

AI_CONFIG = {

    "primary": {

        "url": "http://localhost:11434",

        "name": "Ollama",

        "enabled": True

    },

    "fallback": {

        "url": "http://localhost:11434",

        "name": "Ollama",

        "enabled": True

    }

}





def create_code_block(code: str, language: str = "python") -> str:

    """Artifacts mantığı - temiz kod blokları oluşturma"""

    return f"```{language}\n{code}\n```"





def extract_code_blocks(text: str) -> list:

    """Metinden kod bloklarını çıkar"""

    pattern = r'```(\w+)?\n(.*?)```'

    matches = re.findall(pattern, text, re.DOTALL)

    return [{"language": lang or "text", "code": code.strip()} for lang, code in matches]





class ChatRequest(BaseModel):

    message: str

    model: Optional[str] = None

    username: Optional[str] = None

    token: Optional[str] = None

    stream: Optional[bool] = False

    history: Optional[List[Any]] = None  # [{role, content}, ...] — 0-kayıpsız context için

    conv_id: Optional[str] = None      # arşiv id-keying için sohbet kimliği





class SkillHuntRequest(BaseModel):

    query: str

    source: str = "both"





class SkillInstallRequest(BaseModel):

    command: str





class LaunchRequest(BaseModel):

    app_name: str





class ScanRequest(BaseModel):

    text: Optional[str] = None

    file_path: Optional[str] = None





class RegisterRequest(BaseModel):

    username: str

    password: str

    email: Optional[str] = None

    invite_code: Optional[str] = None





class LoginRequest(BaseModel):

    username: str

    password: str





async def call_ai_engine(message: str, config: Dict[str, Any], num_predict: int = 2000) -> Optional[str]:

    """AI motoruna asenkron çağrı - Ollama entegrasyonu"""

    try:

        async with httpx.AsyncClient(timeout=300.0) as client:

            # Ollama API - /api/chat formatı

            payload = {

                "model": config.get("model", "glassesglitchstudio/x_opus:V1_X_OPUS"),

                "messages": [

                    {"role": "system", "content": "Sen Shadowcat'sın. Yardımcı ve nazik bir Türkçe yapay zeka asistanısın. Kısa ve faydalı yanıtlar verirsin. Oyunları bilirsin. Saygılı davranırsın."},

                    {"role": "user", "content": message}

                ],

                "stream": False,

                "think": False,

                "options": {"temperature": 0.7, "num_predict": num_predict}

            }

            target_url = f"{normalize_ollama_base_url(config.get('url'))}/api/chat"

            response = await client.post(

                target_url,

                json=payload

            )

            

            if response.status_code == 200:

                data = response.json()

                msg = data.get("message", {})

                content = msg.get("content", "").strip()

                if not content:

                    content = msg.get("thinking", "").strip()

                return content

            return None

            

    except Exception as e:

        logger.error(f"AI motoru hatası ({config['name']}): {str(e)}")

        return None





async def get_ai_response(message: str, model: Optional[str] = None, num_predict: int = 2000) -> str:

    """Hibrit AI sistemi - Ana motor başarısız olursa yedeğe geçer"""

    

    # Önce ana motoru dene

    if AI_CONFIG["primary"]["enabled"]:

        logger.info(f"Ana motor deneniyor: {AI_CONFIG['primary']['name']}")

        response = await call_ai_engine(message, AI_CONFIG["primary"], num_predict=num_predict)

        if response:

            logger.info(f"Ana motor yanıt verdi")

            return response

        else:

            logger.warning(f"Ana motor yanıt vermedi, yedeğe geçiliyor")

    

    # Yedek motoru dene

    if AI_CONFIG["fallback"]["enabled"]:

        logger.info(f"Yedek motor deneniyor: {AI_CONFIG['fallback']['name']}")

        response = await call_ai_engine(message, AI_CONFIG["fallback"], num_predict=num_predict)

        if response:

            logger.info(f"Yedek motor yanıt verdi")

            return response

        else:

            logger.error(f"Yedek motor da yanıt vermedi")

    

    return "AI motorları yanıt vermedi. Lütfen Foundry Local veya Ollama'nın çalıştığından emin olun."





@app.get("/", response_class=HTMLResponse)

async def root(request: Request):

    """Ana sayfa - Claude tarzı sohbet arayüzü"""

    try:

        return templates.TemplateResponse(

            request=request,

            name="chat.html",

            context={"request": request},

            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}

        )

    except Exception as e:

        logger.error(f"Error: {type(e).__name__}: {str(e)}")

        return HTMLResponse(content="<h1>Shadowcat AI</h1><p>Template yüklenemedi</p>")



@app.get("/docs", response_class=HTMLResponse)

async def docs_page(request: Request):

    """Dokümantasyon sayfası - static HTML"""

    try:

        docs_path = os.path.join(os.path.dirname(__file__), "docs", "index.html")

        if os.path.exists(docs_path):

            with open(docs_path, "r", encoding="utf-8") as f:

                return HTMLResponse(content=f.read())

        return HTMLResponse(content="<h1>Shadowcat AI</h1><p>Doküman bulunamadı</p>")

    except Exception as e:

        logger.error(f"Error: {type(e).__name__}: {str(e)}")

        return HTMLResponse(content="<h1>Shadowcat AI</h1><p>Template yüklenemedi</p>")





@app.get("/status")

def status():

    """Sistem durumu - CPU, RAM, sıcaklık"""

    return get_system_status()





@app.get("/screen_status")

async def screen_status():

    """Ekran durumu - Web arayüzü için"""

    return {

        "status": "active",

        "screen": "main"

    }





@app.get("/api/diagnostics")
def api_diagnostics():
    """Canli sistem teshisi: durum + kurulu modeller + benchmark ozeti"""
    import json as _json, time as _time
    sonuc = {"status": get_system_status(), "tarih": _time.strftime("%Y-%m-%d %H:%M")}
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15)
        satirlar = [l for l in (r.stdout or "").splitlines()[1:] if l.strip()]
        sonuc["kurulu_modeller"] = [l.split()[0] for l in satirlar]
    except Exception as e:
        sonuc["kurulu_modeller"] = f"alinamadi: {e}"
    try:
        yol = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
        with open(yol, encoding="utf-8") as f:
            d = _json.load(f)
        oturum = (d.get("oturumlar") or [{}])[-1]
        sonuc["benchmark_ozet"] = oturum.get("ollama_testleri") or oturum.get("gpu") or "veri yok"
    except Exception as e:
        sonuc["benchmark_ozet"] = f"alinamadi: {e}"
    return sonuc

@app.post("/chat")

async def chat(request: ChatRequest):

    """AI sohbet - Shadowcat Core ile gelismis zeka sistemi"""

    try:

        logger.info(f"[DEBUG] Gelen mesaj: {request.message}")

        

        # Token kontrolü ve kullanıcı ismi al

        username = request.username

        if request.token and request.token in SESSIONS:

            username = SESSIONS[request.token]["username"]

        

        # Gunluk mesaj limiti kontrolu (BETA korumasi)

        limit_hata = check_message_limit(username)

        if limit_hata:

            limit_hata["limit"] = True

            return limit_hata

        # Mesaj sayisini artir (limit kullanimi)

        increment_message_count(username)

        

        # ── 0-KAYIPSIZ CONTEXT: geçmişi al, arşivle, ilgili kısmı geri çağır ──
        conv_id = request.conv_id or "default"
        history = _normalize_history(request.history)
        if history:
            _archive_from_history(username, conv_id, history)
        else:
            arc = get_context_archive()
            if arc:
                try:  # frontend geçmişi göndermediyse sunucu tarafı hafızadan kurtar
                    recovered = [h for h in arc.search(request.message, k=6) if h["score"] > 0.05]
                    recovered.sort(key=lambda x: x.get("ts", ""))  # kronolojik sıra
                    for h in recovered:
                        history.append({"role": h["role"], "content": h["content"]})
                except Exception:
                    pass
        history = history[-_context_keep_last:]
        # Routerlar (xopus/codes) mevcut mesajı kendileri ekler → history'den çıkar (mükerrer engel)
        if history and history[-1]["role"] == "user" and history[-1]["content"].strip() == request.message.strip():
            history = history[:-1]



        

        # Model seçimi: frontend'den gelen modele göre yönlendir

        deeper_data = None

        model_choice = (request.model or "X_OPUS").upper()

        

        # ── STREAMING MODU ──

        if request.stream:

            def sse(data: dict):

                return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            

            async def stream_gen():

                try:

                    if model_choice in ("X_OPUS", "X_GLITCH_OPUS", "X_FABLE_CODER"):

                        from xopus_router import get_xopus, GLITCH_MODEL, CODE_MODEL

                        xopus = get_xopus()

                        override = None
                        if model_choice == "X_GLITCH_OPUS":
                            override = GLITCH_MODEL
                        elif model_choice == "X_FABLE_CODER":
                            override = CODE_MODEL

                        for ch in xopus.chat_stream(
                            message=request.message,
                            system_prompt=None,
                            model=override,
                            context=history
                        ):

                            yield sse(ch)

                        yield sse({"done": True})

                    elif is_codes_tier(model_choice):

                        # CodeS ticari kademeleri → sınıflandırma + fallback
                        codes = get_codes_router()
                        for ch in codes.chat_stream(request.message, tier=model_choice, context=history):
                            yield sse(ch)
                        yield sse({"done": True})

                    elif CORE_AVAILABLE:

                        # ── GERÇEK TOKEN-BY-TOKEN STREAMING ──
                        # Ollama API'ye stream:true ile bağlanıp her token'ı anında yield ediyoruz
                        core = get_core()
                        raw_ollama_url = "http://localhost:11434"
                        if core and core.model_router:
                            raw_ollama_url = getattr(core.model_router, 'ollama_url', raw_ollama_url)
                        
                        target_api_url = f"{normalize_ollama_base_url(raw_ollama_url)}/api/chat"
                        
                        stream_model = request.model
                        if not stream_model and core and core.model_router:
                            stream_model = getattr(core.model_router, 'default_model', None)
                        if not stream_model:
                            stream_model = os.getenv("DEFAULT_MODEL", "glassesglitchstudio/x_opus:V1_X_OPUS")

                        # Sistem prompt'u
                        system_prompt = "Sen Shadowcat AI'sın — Elytra-ai stüdyosunun yapay zeka asistanı. Türkçe yanıt ver, kısa ve faydalı ol. Kod bloklarında dil etiketi kullan. Doğrudan çözüme odaklan."
                        
                        # Extended thinking desteği
                        think_enabled = getattr(core, '_extended_thinking', False) if core else False
                        
                        try:
                            _eff_msgs = _effective_messages(history, request.message, system_prompt)
                            async with httpx.AsyncClient(timeout=180.0) as client:
                                async with client.stream(
                                    "POST",
                                    target_api_url,
                                    json={
                                        "model": stream_model,
                                        "messages": _eff_msgs,
                                        "stream": True,
                                        "think": think_enabled,
                                        "options": {"temperature": 0.7, "num_predict": 2000}
                                    }
                                ) as response:
                                    thinking_buf = ""
                                    async for line in response.aiter_lines():
                                        if not line:
                                            continue
                                        try:
                                            data = json.loads(line)
                                        except json.JSONDecodeError:
                                            continue
                                        
                                        msg = data.get("message", {})
                                        content = msg.get("content", "")
                                        
                                        # Thinking content (deepseek-r1 tarzı <think> blokları)
                                        thinking = msg.get("thinking", "")
                                        if thinking:
                                            thinking_buf += thinking
                                            yield sse({"thinking": thinking, "done": False})
                                            continue
                                        
                                        # Normal token
                                        if content:
                                            yield sse({"token": content, "done": False})
                                        
                                        # Stream bitti
                                        if data.get("done"):
                                            break
                                    
                            yield sse({"done": True})
                        
                        except Exception as stream_err:
                            logger.warning(f"Ollama streaming hatası, fallback: {stream_err}")
                            # Fallback: Core ile non-streaming
                            import threading
                            from shadowcat_agent_loop import extract_answer
                            holder = {}
                            def run_core():
                                try:
                                    res = core.process_message(request.message)
                                    holder["text"] = res.get("response", "")
                                    holder["thinking"] = res.get("thinking", "")
                                except Exception as e:
                                    holder["error"] = str(e)
                            th = threading.Thread(target=run_core, daemon=True)
                            th.start()
                            th.join(timeout=120)
                            if holder.get("error"):
                                yield sse({"error": holder["error"]})
                                return
                            text = holder.get("text", "")
                            if isinstance(text, dict):
                                text = text.get("response") or text.get("text") or str(text)
                            text = extract_answer(text or "")
                            if holder.get("thinking"):
                                yield sse({"thinking": holder["thinking"], "done": False})
                            yield sse({"token": text, "done": False})
                            yield sse({"done": True})

                    else:

                        text = await get_ai_response(request.message, request.model)

                        yield sse({"token": text, "done": False})

                        yield sse({"done": True})

                except Exception as e:

                    logger.error(f"Stream hatasi: {e}")

                    yield sse({"error": str(e)})

            

            return StreamingResponse(

                stream_gen(),

                media_type="text/event-stream",

                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

            )

        

        # Düşünme gösterimi

        logger.info("Düşünüyorum...")

        

        # YENİ: Shadowcat Core ile işle

        response_text = ""

        tool_calls = []

        thoughts = []

        thinking_text = ""

        

        # Model seçimi: frontend'den gelen modele göre yönlendir

        model_choice = (request.model or "X_OPUS").upper()

        

        if model_choice in ("X_GLITCH_OPUS", "X_FABLE_CODER"):

            try:

                from xopus_router import get_xopus, GLITCH_MODEL, CODE_MODEL

                xopus = get_xopus()

                override = GLITCH_MODEL if model_choice == "X_GLITCH_OPUS" else CODE_MODEL

                result = xopus.chat(
                    message=request.message,
                    system_prompt=None,
                    model=override,
                    context=history
                )

                response_text = result.get("response", "")

                thinking_text = result.get("thinking", "")

                deeper_data = result.get("deeper")

                if result.get("routing"):

                    thoughts = [result["routing"]]

                if not response_text:

                    response_text = f"Üzgünüm, {model_choice} yanıt üretemedi: {result.get('error', 'bilinmeyen hata')}"

            except ImportError:

                response_text = "X_OPUS modülü bulunamadı. `xopus_router.py` eksik."

            except Exception as e:

                logger.error(f"X_OPUS hatası: {e}")

                response_text = f"{model_choice} hatası: {e}"

        elif is_codes_tier(model_choice):

            # CodeS ticari kademeleri → sınıflandırma + tam fallback
            try:

                codes = get_codes_router()

                result = codes.chat(request.message, tier=model_choice, context=history)

                response_text = result.get("response", "")

                thinking_text = result.get("thinking", "")

                if result.get("routing"):

                    thoughts = [result["routing"]]

                if not response_text:

                    response_text = f"Üzgünüm, {model_choice} yanıt üretemedi: {result.get('error', 'bilinmeyen hata')}"

            except Exception as e:

                logger.error(f"CodeS router hatası: {e}")

                response_text = f"CodeS hatası: {e}"

        elif CORE_AVAILABLE:

            try:

                core = get_core()

                result = core.process_message(request.message)

                response_text = result.get("response", "")

                

                # Güvenlik ağı: response dict/dict-repr gelirse metni ayıkla

                if isinstance(response_text, dict):

                    response_text = response_text.get("response") or response_text.get("text") or response_text.get("error") or str(response_text)

                elif isinstance(response_text, str) and response_text.startswith("{") and ("'response'" in response_text[:80] or "'error'" in response_text[:80]):

                    try:

                        import ast

                        inner = ast.literal_eval(response_text)

                        if isinstance(inner, dict):

                            response_text = inner.get("response") or inner.get("text") or inner.get("error") or str(inner)

                    except Exception:

                        pass

                

                tool_calls = result.get("tool_calls", [])

                thoughts = result.get("thoughts", [])

                thinking_text = result.get("thinking", "")

                

                if not response_text:

                    response_text = "Üzgünüm, yanıt üretemedim."

            except Exception as e:

                logger.error(f"Core hatası, legacy moda geçiliyor: {e}")

                response_text = await get_ai_response(request.message, request.model)

        else:

            # Legacy hibrit sistem

            response_text = await get_ai_response(request.message, request.model)

        

        # Hata toleransı

        if not response_text:

            response_text = "AI motorları yanıt vermedi."
        
        # ── AI cevabını da arşive yaz (MIRA: kendi ürettiğini hatırlama) ──
        _arc = get_context_archive()
        if _arc and response_text:
            try:
                _arc.add(f"{username}:{conv_id}:ai:{uuid.uuid4().hex[:8]}", str(response_text),
                         {"role": "assistant", "username": username, "conv_id": conv_id})
            except Exception:
                pass

        

        return {

            "success": True,

            "response": response_text,

            "engine_used": model_choice,

            "username": username,

            "tool_calls": tool_calls[:5] if tool_calls else [],

            "thoughts": thoughts[-3:] if thoughts else [],

            "thinking": thinking_text,

            "deeper": deeper_data,
            "context_stats": {
                "history_used": len(history),
                "archived": (get_context_archive().count() if get_context_archive() else 0)
            }
        }

    except Exception as e:

        logger.error(f"Sunucu iç hatası: {str(e)}")

        return {

            "success": False,

            "response": "Sunucu iç hatası oluştu. Lütfen tekrar deneyin.",

            "error": str(e)

        }





@app.post("/launch/{app_name}")

async def launch(app_name: str):

    """Uygulama başlatma"""

    try:

        result = launch_app(app_name)

        return {

            "success": True,

            "app": app_name,

            "result": result

        }

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))





@app.post("/scan")

async def scan(request: ScanRequest):

    """OCR tarama - Metin veya resim"""

    try:

        if request.text:

            result = {"success": True, "response": ocr_from_image(request.text) if os.path.exists(request.text) else f"Metin: {request.text[:100]}..."}

        elif request.file_path:

            result = analyze_image(request.file_path)

        else:

            raise HTTPException(status_code=400, detail="Metin veya dosya yolu gerekli")

        

        return {

            "success": True,

            "result": result

        }

    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))





@app.get("/apps")

async def list_apps():

    """Mevcut uygulamaları listele"""

    return {

        "apps": list(APP_MAPPINGS.keys())

    }





@app.get("/health")

async def health():

    """Sağlık kontrolü"""

    return {

        "status": "healthy",

        "ai_primary": AI_CONFIG["primary"]["enabled"],

        "ai_fallback": AI_CONFIG["fallback"]["enabled"]

    }





@app.get("/api/context/stats")

async def context_stats():

    """0-kayıpsız context arşivi durumu"""

    arc = get_context_archive()

    return {

        "available": CONTEXT_ARCHIVE_AVAILABLE,

        "archived_segments": arc.count() if arc else 0,

        "window_keep_last": _context_keep_last,

        "note": "Eski mesajlar özetlenmez — SQLite'a orijinal haliyle gömülür, sorguya göre geri çağrılır"

    }





@app.get("/api/auth/me")

async def auth_me():

    """Kimlik kontrolü - Web arayüzü için"""

    return {

        "authenticated": True

    }





@app.post("/api/auth/register")

async def register(request: RegisterRequest):

    """Kullanıcı kayıt"""

    users = load_users()

    

    if request.username in users:

        return {

            "success": False,

            "error": "Kullanıcı adı zaten kullanılıyor"

        }

    

    if INVITE_CODES_REQUIRED and (request.invite_code or "") not in INVITE_CODES:

        return {

            "success": False,

            "error": "Gecersiz veya eksik davet kodu. Shadowcat su anda davetli kullanicilara aciktir."

        }

    

    users[request.username] = {

        "password": hash_password(request.password),

        "email": request.email,

        "created_at": str(datetime.now())

    }

    

    save_users(users)

    

    return {

        "success": True,

        "message": "Kayıt başarılı"

    }





@app.post("/api/auth/login")

async def login(request: LoginRequest):

    """Kullanıcı giriş"""

    users = load_users()

    

    if request.username not in users:

        return {

            "success": False,

            "error": "Kullanıcı bulunamadı"

        }

    

    user_info = users[request.username]
    stored_password = user_info.get("password") if isinstance(user_info, dict) else None
    
    if not stored_password or not verify_password(request.password, stored_password):
        return {
            "success": False,
            "error": "Şifre hatalı"
        }

    

    token = generate_token()

    SESSIONS[token] = {

        "username": request.username,

        "created_at": str(datetime.now())

    }

    

    return {

        "success": True,

        "token": token,

        "username": request.username

    }





@app.get("/api/auth/logout")

async def logout(token: str):

    """Kullanıcı çıkış"""

    if token in SESSIONS:

        del SESSIONS[token]

    

    return {

        "success": True,

        "message": "Çıkış başarılı"

    }





@app.get("/check-model")

async def check_model():

    """Model kontrolü - Web arayüzü için"""

    return {

        "status": "ready"

    }





@app.get("/preview")

async def preview():

    """Web preview - HTML/CSS/JS projeleri için"""

    return {

        "message": "Web preview özelliği aktif. HTML/CSS/JS dosyalarını web/templates klasörüne koyun.",

        "url": "http://localhost:5000"

    }





# ─────────────────────────────────────────────────────────────

# DOSYA YÜKLEME VE İŞLEME

# ─────────────────────────────────────────────────────────────



UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "storage", "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)



ALLOWED_EXTENSIONS = {

    ".pdf": "document",

    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".webp": "image", ".svg": "image",

    ".py": "code", ".js": "code", ".ts": "code", ".jsx": "code", ".tsx": "code",

    ".html": "code", ".css": "code", ".json": "code", ".xml": "code", ".yaml": "code", ".yml": "code",

    ".md": "code", ".txt": "code", ".csv": "data", ".tsv": "data",

    ".docx": "document", ".doc": "document"

}



def parse_uploaded_file(file_path: str, ext: str) -> dict:

    ext = ext.lower()

    content = ""

    preview = ""

    file_type = ALLOWED_EXTENSIONS.get(ext, "unknown")

    try:

        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):

            with open(file_path, "rb") as f:

                import base64

                b64 = base64.b64encode(f.read()).decode()

                preview = f"data:image/{ext.lstrip('.')};base64,{b64[:100]}..."

                content = f"[Image: {os.path.basename(file_path)}]"

        elif ext == ".pdf":

            try:

                import PyPDF2

                with open(file_path, "rb") as f:

                    reader = PyPDF2.PdfReader(f)

                    pages = [p.extract_text() for p in reader.pages[:10]]

                    content = "\n\n".join(pages)

                    preview = content[:500]

            except ImportError:

                content = f"[PDF: {os.path.basename(file_path)} (PyPDF2 gerekli)]"

                preview = content

        elif ext == ".csv":

            with open(file_path, "r", encoding="utf-8") as f:

                lines = f.readlines()[:30]

                content = "".join(lines)

                preview = content[:500]

        elif ext == ".docx":

            try:

                from docx import Document

                doc = Document(file_path)

                paras = [p.text for p in doc.paragraphs[:50]]

                content = "\n".join(paras)

                preview = content[:500]

            except ImportError:

                content = f"[DOCX: {os.path.basename(file_path)} (python-docx gerekli)]"

                preview = content

        else:

            with open(file_path, "r", encoding="utf-8") as f:

                content = f.read()

                preview = content[:500]

    except Exception as e:

        content = f"[Dosya okunamadı: {e}]"

        preview = content

    return {"content": content, "preview": preview, "type": file_type, "extension": ext}



@app.post("/api/upload")

async def upload_file(file: UploadFile = File(...), project_id: str = Form(default="")):

    try:

        ext = os.path.splitext(file.filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:

            return {"success": False, "error": f"Desteklenmeyen dosya türü: {ext}. İzin verilenler: {', '.join(ALLOWED_EXTENSIONS.keys())}"}



        file_id = uuid.uuid4().hex[:8]

        safe_name = f"{file_id}_{file.filename}"

        file_path = os.path.join(UPLOAD_DIR, safe_name)



        content_bytes = await file.read()

        with open(file_path, "wb") as f:

            f.write(content_bytes)



        parsed = parse_uploaded_file(file_path, ext)

        file_info = {

            "id": file_id,

            "name": file.filename,

            "path": file_path,

            "size": len(content_bytes),

            "type": parsed["type"],

            "extension": ext,

            "preview": parsed["preview"][:300]

        }



        if project_id:

            from shadowcat_core import get_core

            c = get_core()

            if c.get_project(project_id):

                c.add_file_to_project(project_id, file_info)



        return {

            "success": True,

            "file": file_info,

            "content": parsed["content"],

            "message": f"{file.filename} yüklendi ({len(content_bytes)} bayt)"

        }

    except Exception as e:

        return {"success": False, "error": str(e)}





@app.get("/api/upload/{file_id}")

async def get_uploaded_file(file_id: str):

    try:

        for fname in os.listdir(UPLOAD_DIR):

            if fname.startswith(file_id):

                path = os.path.join(UPLOAD_DIR, fname)

                ext = os.path.splitext(fname)[1].lower()

                parsed = parse_uploaded_file(path, ext)

                return {"success": True, "file": {"name": fname, "path": path}, **parsed}

        return {"success": False, "error": "Dosya bulunamadı"}

    except Exception as e:

        return {"success": False, "error": str(e)}





@app.post("/api/site-builder/upload-image")

async def site_builder_upload_image(file: UploadFile = File(...)):

    """Site Builder gorsel yukleme — web/static/uploads'a kaydeder, /static/... URL'si doner"""

    try:

        ext = os.path.splitext(file.filename)[1].lower()

        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):

            return {"success": False, "error": f"Gorsel desteklenmiyor: {ext}. PNG/JPG/GIF/WEBP/SVG kullan."}



        sb_upload_dir = os.path.join(os.path.dirname(__file__), "web", "static", "uploads")

        os.makedirs(sb_upload_dir, exist_ok=True)



        file_id = uuid.uuid4().hex[:8]

        safe_name = f"{file_id}{ext}"

        file_path = os.path.join(sb_upload_dir, safe_name)



        content_bytes = await file.read()

        if len(content_bytes) > 8 * 1024 * 1024:

            return {"success": False, "error": "Gorsel 8MB'dan buyuk olamaz"}

        with open(file_path, "wb") as f:

            f.write(content_bytes)



        url = f"/static/uploads/{safe_name}"

        return {

            "success": True,

            "url": url,

            "message": f"{file.filename} yuklendi. HTML'e <img src='{url}'> olarak ekleyebilirsin."

        }

    except Exception as e:

        return {"success": False, "error": str(e)}





# ─────────────────────────────────────────────────────────────

# KONUŞMA PAYLAŞMA LİNKİ

# ─────────────────────────────────────────────────────────────



SHARES: Dict[str, dict] = {}



@app.post("/api/share")

async def share_conversation(data: dict):

    try:

        share_id = uuid.uuid4().hex[:10]

        SHARES[share_id] = {

            "messages": data.get("messages", []),

            "title": data.get("title", "Paylaşılan Sohbet"),

            "created": datetime.now().isoformat()

        }

        return {"success": True, "share_id": share_id, "url": f"/share/{share_id}"}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.get("/api/share/{share_id}")

async def get_share(share_id: str):

    share = SHARES.get(share_id)

    if not share:

        return {"success": False, "error": "Paylaşım bulunamadı"}

    return {"success": True, **share}



@app.get("/share/{share_id}", response_class=HTMLResponse)

async def share_page(share_id: str):

    share = SHARES.get(share_id)

    if not share:

        return HTMLResponse("<h1>Paylaşım bulunamadı</h1>")

    msgs_html = ""

    for m in share.get("messages", []):

        role = m.get("role", "user")

        content = m.get("content", "")

        label = "Kullanıcı" if role == "user" else "Shadowcat"

        msgs_html += f'<div style="margin-bottom:16px;padding:12px;background:{ "#f5f5f5" if role=="user" else "#f3e8ff" };border-radius:8px"><strong>{label}</strong><p style="margin-top:4px">{content}</p></div>'

    return HTMLResponse(f"""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{share["title"]} — Shadowcat</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet"><style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Inter',sans-serif;background:#fafafa;color:#1a1a1a;padding:40px 24px;max-width:720px;margin:0 auto}}h1{{font-size:1.1rem;font-weight:600;margin-bottom:24px;color:#7c3aed}}.meta{{font-size:0.75rem;color:#888;margin-bottom:32px}}</style></head><body><h1>{share["title"]}</h1><div class="meta">{share.get("created","")} · Paylaşılan Sohbet</div>{msgs_html}</body></html>""")





# Admin Paneli Endpoint'leri

from dotenv import load_dotenv

load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Degistirilmeli123!")



@app.get("/admin", response_class=HTMLResponse)

async def admin_panel(request: Request):

    """Admin paneli - API key ve davet kodu yonetimi"""

    try:

        admin_path = os.path.join(os.path.dirname(__file__), "web", "templates", "admin.html")

        if os.path.exists(admin_path):

            with open(admin_path, "r", encoding="utf-8") as f:

                return HTMLResponse(content=f.read())

        return HTMLResponse(content="<h1>Admin paneli bulunamadi</h1>")

    except Exception as e:

        logger.error(f"Admin panel hatasi: {e}")

        return HTMLResponse(content=f"<h1>Admin paneli hatasi: {e}</h1>")




@app.get("/manage", response_class=HTMLResponse)

async def manage_panel(request: Request):

    """Yönetim paneli"""

    return HTMLResponse(content=f"""<!DOCTYPE html>

<html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">

<title>Yönetim — Shadowcat</title>

<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>

*{{margin:0;padding:0;box-sizing:border-box}}

body{{font-family:'Inter',sans-serif;background:#0c0a09;color:#f5f0eb;padding:40px 24px}}

h1{{font-size:1.3rem;font-weight:600;margin-bottom:24px}}

.card{{background:#141110;border:1px solid #1e1b18;border-radius:6px;padding:20px;margin-bottom:16px;max-width:500px}}

.card h2{{font-size:0.9rem;font-weight:500;margin-bottom:8px;color:#a8a29e}}

.card p{{font-size:0.8rem;color:#6b6560}}

</style></head><body>

<h1>Shadowcat Yönetim</h1>

<div class="card"><h2>Yönetim Paneli</h2><p>Yapım aşamasında.</p></div>

</body></html>""")





@app.post("/api/settings/mode")

async def set_mode(data: dict):

    """Agent modunu değiştir"""

    try:

        from shadowcat_core import get_core

        c = get_core()

        mode = data.get("mode", "normal")

        c.set_mode(mode)

        return {"success": True, "mode": mode}

    except Exception as e:

        return {"success": False, "error": str(e)}





class SetModeRequest(BaseModel):

    mode: str





@app.post("/api/set_mode")

async def api_set_mode(req: SetModeRequest):

    """Agent modunu degistir: normal, developer, silent, game, memory_agent"""

    try:

        from shadowcat_core import get_core

        c = get_core()

        ok = c.set_mode(req.mode)

        if ok:

            return {"success": True, "mode": req.mode}

        else:

            return {"success": False, "error": f"Gecersiz mode: {req.mode}. Gecerli modlar: normal, developer, silent, game, memory_agent"}

    except Exception as e:

        return {"success": False, "error": str(e)}





@app.post("/api/settings/style")

async def set_style(data: dict):

    """Yanıt stilini değiştir: normal, concise, explanatory, formal, code_first"""

    try:

        from shadowcat_core import get_core, BUILTIN_STYLES, STYLES

        c = get_core()

        style = data.get("style", "normal")

        if style not in BUILTIN_STYLES:

            return {"success": False, "error": f"Geçersiz stil. Seçenekler: {', '.join(BUILTIN_STYLES)}"}

        c.set_style(style)

        return {"success": True, "style": style, "description": STYLES[style]}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.get("/api/settings/style")

async def get_style():

    try:

        from shadowcat_core import get_core

        c = get_core()

        return {"success": True, "style": c.get_style()}

    except Exception as e:

        return {"success": False, "error": str(e)}



# ── MaxCode (GCVIPER) yetkili kilit açma ────────────────────────────────────

_maxcode_attempts = {"count": 0, "locked_until": 0.0}



@app.post("/api/admin/maxcode-unlock")

async def maxcode_unlock(data: dict):

    """Yetkili (Admin) kilit açma. Şifre .env'deki MAXCODE_ADMIN_PASSWORD.

    5 hatalı deneme = 5 dakika kilit (brute-force koruması)."""

    import time as _time

    now = _time.time()

    if now < _maxcode_attempts["locked_until"]:

        wait = int(_maxcode_attempts["locked_until"] - now)

        return {"success": False, "error": f"Çok fazla hatalı deneme. {wait} sn bekleyin."}



    expected = os.getenv("MAXCODE_ADMIN_PASSWORD", "").strip()

    if not expected:

        return {"success": False, "error": "Admin şifresi tanımlı değil (.env → MAXCODE_ADMIN_PASSWORD)."}



    given = str(data.get("password", ""))

    if given == expected:

        _maxcode_attempts["count"] = 0

        return {"success": True, "model": "MAXCODE", "tier_label": "MaxCode (GCVIPER)"}



    _maxcode_attempts["count"] += 1

    if _maxcode_attempts["count"] >= 5:

        _maxcode_attempts["locked_until"] = now + 300

        _maxcode_attempts["count"] = 0

        return {"success": False, "error": "5 hatalı deneme — 5 dakika kilitlendi."}

    return {"success": False, "error": "Şifre hatalı."}
    

_aegis_cyber_attempts = {"count": 0, "locked_until": 0.0}

@app.post("/api/admin/aegis-cyber-unlock")
async def aegis_cyber_unlock(data: dict):
    """Aegis-Cyber Siber Güvenlik Kasa kilit açma. Şifre .env'deki AEGIS_CYBER_PASSWORD.
    5 hatalı deneme = 5 dakika kilit."""
    import time as _time
    now = _time.time()
    if now < _aegis_cyber_attempts["locked_until"]:
        wait = int(_aegis_cyber_attempts["locked_until"] - now)
        return {"success": False, "error": f"Çok fazla hatalı deneme. {wait} sn bekleyin."}

    expected = os.getenv("AEGIS_CYBER_PASSWORD", "CYBER22").strip()
    given = str(data.get("password", "")).strip()
    if given == expected:
        _aegis_cyber_attempts["count"] = 0
        return {"success": True, "model": "AEGIS_CYBER", "tier_label": "Aegis-Cyber (RovX Shield)"}

    _aegis_cyber_attempts["count"] += 1
    if _aegis_cyber_attempts["count"] >= 5:
        _aegis_cyber_attempts["locked_until"] = now + 300
        _aegis_cyber_attempts["count"] = 0
        return {"success": False, "error": "5 hatalı deneme — 5 dakika kilitlendi."}
    return {"success": False, "error": "Siber Kasa şifresi hatalı."}



@app.post("/api/settings/preferences")

async def set_preferences(data: dict):

    try:

        from shadowcat_core import get_core

        c = get_core()

        text = data.get("text", "")

        c.set_personal_preferences(text)

        return {"success": True, "length": len(text)}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.get("/api/settings/preferences")

async def get_preferences():

    try:

        from shadowcat_core import get_core

        c = get_core()

        return {"success": True, "text": c.get_personal_preferences()}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.post("/api/settings/extended-thinking")

async def set_extended_thinking(data: dict):

    try:

        from shadowcat_core import get_core

        c = get_core()

        enabled = data.get("enabled", False)

        c.set_extended_thinking(enabled)

        return {"success": True, "enabled": enabled}

    except Exception as e:

        return {"success": False, "error": str(e)}





# ─────────────────────────────────────────────────────────────

# PROJE YÖNETİMİ API

# ─────────────────────────────────────────────────────────────



@app.post("/api/projects")
async def create_project(data: dict):
    try:
        from shadowcat_core import get_core
        c = get_core()
        proj = c.create_project(
            project_id=data.get("id", ""),
            name=data.get("name", ""),
            instructions=data.get("instructions", ""),
            folder_path=data.get("folder_path", "")
        )
        return {"success": True, "project": proj}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/projects/{project_id}/scan")
async def scan_project(project_id: str, data: dict = None):
    try:
        from shadowcat_core import get_core
        c = get_core()
        folder_path = (data or {}).get("folder_path", "")
        files = c.scan_project_directory(project_id, folder_path=folder_path)
        return {"success": True, "files": files, "count": len(files)}
    except Exception as e:
        return {"success": False, "error": str(e)}



@app.get("/api/projects")

async def list_projects():

    try:

        from shadowcat_core import get_core

        c = get_core()

        return {"success": True, "projects": c.list_projects()}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.get("/api/projects/{project_id}")

async def get_project(project_id: str):

    try:

        from shadowcat_core import get_core

        c = get_core()

        proj = c.get_project(project_id)

        if not proj:

            return {"success": False, "error": "Proje bulunamadı"}

        return {"success": True, "project": proj}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.post("/api/projects/{project_id}/activate")

async def activate_project(project_id: str):

    try:

        from shadowcat_core import get_core

        c = get_core()

        success = c.set_active_project(project_id)

        return {"success": success, "active_project": project_id if success else None}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.delete("/api/projects/{project_id}")

async def delete_project(project_id: str):

    try:

        from shadowcat_core import get_core

        c = get_core()

        success = c.delete_project(project_id)

        return {"success": success}

    except Exception as e:

        return {"success": False, "error": str(e)}





# ─────────────────────────────────────────────────────────────

# MESAJ DÜZENLEME / BRANCHING API

# ─────────────────────────────────────────────────────────────



@app.post("/api/conversations/{conv_id}/edit")

async def edit_message(conv_id: str, data: dict):

    try:

        from shadowcat_core import get_core

        c = get_core()

        msg_index = data.get("message_index", -1)

        new_content = data.get("new_content", "")

        branch_id = c.edit_message(conv_id, msg_index, new_content)

        return {"success": True, "branch_id": branch_id, "message": "Yeni branch oluşturuldu"}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.get("/api/conversations/{conv_id}/branches")

async def get_branches(conv_id: str):

    try:

        from shadowcat_core import get_core

        c = get_core()

        branches = c.get_branches(conv_id)

        return {"success": True, "branches": branches}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.post("/api/conversations/branches/{branch_id}/switch")

async def switch_branch(branch_id: str):

    try:

        from shadowcat_core import get_core

        c = get_core()

        success = c.switch_branch(branch_id)

        msgs = []

        for m in c.conversation_history:

            msgs.append({"role": m.role, "content": m.content})

        return {"success": success, "messages": msgs}

    except Exception as e:

        return {"success": False, "error": str(e)}





@app.post("/admin/keys")

async def get_keys(request: Request):

    """Erişim kodlarını listele"""

    # Basit implementasyon - gerçek veritabanı gerekli

    return {

        "keys": []

    }





@app.post("/admin/keys/create")

async def create_key(request: Request):

    """Yeni erişim kodu oluştur"""

    # Basit implementasyon

    import secrets

    key = secrets.token_urlsafe(16)

    return {

        "success": True,

        "key": key

    }





@app.post("/admin/keys/toggle")

async def toggle_key(request: Request):

    """Erişim kodunu aktif/pasif yap"""

    return {

        "success": True

    }





@app.post("/admin/keys/delete")

async def delete_key(request: Request):

    """Erişim kodunu sil"""

    return {

        "success": True

    }





# ═══════════════════════════════════════════════════════════════

# SHADOWCAT CORE API ENDPOINTS

# ═══════════════════════════════════════════════════════════════



@app.get("/api/core/status")

async def core_status():

    """Core sistem durumu"""

    if not CORE_AVAILABLE:

        return {"available": False, "message": "ShadowcatCore yuklu degil"}

    

    try:

        core = get_core()

        status = core.get_status()

        return {

            "available": True,

            "version": status.get("version", "?"),

            "uptime": status.get("uptime", "?"),

            "modules": status.get("modules", {}),

            "state": status.get("state", {}),

            "stats": status.get("stats", {})

        }

    except Exception as e:

        return {"available": False, "error": str(e)}

class FeedbackRequest(BaseModel):

    vote: str

    text: Optional[str] = ""

    username: Optional[str] = None

    token: Optional[str] = None



@app.post("/api/feedback")

async def feedback(req: FeedbackRequest):

    """Yanit geri bildirimi - iyi/kotu (BETA veri toplama)"""

    try:

        fdb = []

        if os.path.exists('feedback.json'):

            try:

                with open('feedback.json', 'r', encoding='utf-8') as f:

                    fdb = json.load(f)

            except Exception:

                fdb = []

        fby = "good" if req.vote in ("good", "1", 1) else "bad"

        fdb.append({

            "vote": fby,

            "text": (req.text or "").strip()[:500],

            "username": req.username or "misafir",

            "time": str(datetime.now())

        })

        with open('feedback.json', 'w', encoding='utf-8') as f:

            json.dump(fdb, f, ensure_ascii=False, indent=2)

        return {"success": True, "count": len(fdb)}

    except Exception as e:

        return {"success": False, "error": str(e)}



@app.get("/api/feedback/stats")

async def feedback_stats():

    """Geri bildirim istatistikleri - admin kontrolu"""

    try:

        if not os.path.exists('feedback.json'):

            return {"success": True, "total": 0, "good": 0, "bad": 0}

        with open('feedback.json', 'r', encoding='utf-8') as f:

            fdb = json.load(f)

        good = sum(1 for x in fdb if x.get("vote") == "good")

        return {

            "success": True,

            "total": len(fdb),

            "good": good,

            "bad": len(fdb) - good

        }

    except Exception as e:

        return {"success": False, "error": str(e)}







class TaskRequest(BaseModel):

    task: str

    username: Optional[str] = None

    token: Optional[str] = None





@app.post("/api/task/execute")

async def execute_task(request: TaskRequest):

    """Cok adimli gorev yurut"""

    if not CORE_AVAILABLE:

        return {"success": False, "error": "ShadowcatCore yuklu degil"}

    

    try:

        core = get_core()

        result = core.execute_task(request.task)

        return {

            "success": result.get("success", False),

            "summary": result.get("summary", ""),

            "results": result.get("results", [])

        }

    except Exception as e:

        return {"success": False, "error": str(e)}





@app.post("/api/artifacts/edit")

async def edit_artifact(req: dict):

    """Secili HTML elementi icin AI ile CSS duzenlemesi uretir"""

    selector = (req.get("selector") or "").strip()

    instruction = (req.get("instruction") or "").strip()

    html_src = (req.get("html") or "").strip()[:20000]

    if not selector or not instruction:

        return {"success": False, "error": "selector ve instruction gerekli"}

    if not CORE_AVAILABLE:

        return {"success": False, "error": "ShadowcatCore yuklu degil"}

    

    prompt = (

        "Sen bir web tasarim asistanisin. Kullanici, olusturulan HTML sayfasinda tek bir elementi duzenlemek istiyor.\n"

        f"Secili element (CSS selector): `{selector}`\n"

        f"Kullanici talimati: {instruction}\n\n"

        "Sayfanin HTML'i:\n```html\n" + html_src + "\n```\n\n"

        "Sadece bu element icin bir CSS kural blogu dondur: `{ selector { property: value; } }` seklinde.\n"

        "Sayfanin geri kalanini degistirme. Aciklama yazma, markdown kullanma."

    )

    

    try:

        core = get_core()

        result = core.process_message(prompt)

        resp = (result.get("response") or "").strip()

    except Exception as e:

        return {"success": False, "error": f"AI motoru hatasi: {e}"}

    

    # Model yaniti gercek bir metin degilse (dict-string / hata / bos) fallback'e dus

    if (not resp or resp.startswith("{")

            or "Ollama baglantisi yok" in resp

            or "'success': False" in resp

            or '"success": false' in resp):

        css = fallback_element_css(selector, instruction)

        return {"success": True, "css": css, "engine_used": "FallbackCSS"}

    

    m = re.search(re.escape(selector) + r"\s*\{[\s\S]*\}", resp)

    if not m:

        m = re.search(r"[^{}\n]+\{[\s\S]*\}", resp)

    if not m:

        css = fallback_element_css(selector, instruction)

        return {"success": True, "css": css, "engine_used": "FallbackCSS"}

    

    css = m.group(0).strip()

    return {"success": True, "css": css, "engine_used": "ShadowcatCore"}





# ─────────────────────────────────────────────

# SKILL AVCIISI — skillsllm.com + GitHub araştırması + terminal kurulumu

# ─────────────────────────────────────────────



def _gh_headers():

    return {"User-Agent": "shadowcat-skill-hunter", "Accept": "application/vnd.github+json"}





def _hunt_skillsllm(query: str) -> List[Dict]:

    """skillsllm.com ana listesinden (yildiz sirali) aday toplar."""

    out = []

    try:

        resp = httpx.get("https://skillsllm.com/?sort=stars", timeout=30, follow_redirects=True,

                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

        if resp.status_code != 200:

            return out

        html = resp.text

        # Kartlar: github.com/owner/repo baglantilari + /skill/slug linkleri

        for m in re.finditer(r'github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', html):

            repo = m.group(1).rstrip("/")

            if repo not in [c["repo"] for c in out]:

                out.append({"repo": repo, "source": "skillsllm", "stars": 0})

        # Yildiz sayilari: "234,966" formatinda

        stars = re.findall(r'([\d,]{4,9})\s*[Ss]tars?', html)

        # slug'lar

        slugs = re.findall(r'/skill/([A-Za-z0-9_.-]+)', html)

        if slugs:

            slug_map = {}

            for i, s in enumerate(slugs):

                slug_map.setdefault(s, stars[i] if i < len(stars) else 0)

            for c in out:

                slug = c["repo"].split("/")[-1]

                for s, st in slug_map.items():

                    if s == slug or s.replace("-", "") == slug.replace("-", ""):

                        c["stars"] = st

                        c["slug"] = s

                        break

                if "slug" not in c:

                    c["slug"] = slug

        for c in out:

            c.setdefault("slug", c["repo"].split("/")[-1])

        return out[:30]

    except Exception:

        return out





def _hunt_github(query: str) -> List[Dict]:

    """GitHub aramasi ile skill koleksiyonu repolari bulur."""

    out = []

    try:

        resp = httpx.get(

            "https://api.github.com/search/repositories",

            params={"q": f"{query} skill", "per_page": 10, "sort": "stars"},

            headers=_gh_headers(), timeout=30,

        )

        if resp.status_code == 200:

            for r in resp.json().get("items", []):

                out.append({

                    "repo": r["full_name"],

                    "stars": r.get("stargazers_count") or 0,

                    "updated_at": r.get("updated_at", ""),

                    "desc": (r.get("description") or "")[:200],

                    "source": "github",

                })

    except Exception:

        pass

    return out





def _skill_install_command(repo: str, slug: str = "") -> str:

    """Skill sayfasindaki / repo'daki kurulum komutunu bulur (npx, git clone vs)."""

    tries = []

    if slug:

        tries.append(f"https://skillsllm.com/skill/{slug}")

    tries.append(f"https://raw.githubusercontent.com/{repo}/main/SKILL.md")

    tries.append(f"https://raw.githubusercontent.com/{repo}/main/README.md")

    for url in tries:

        try:

            resp = httpx.get(url, timeout=20, follow_redirects=True,

                             headers={"User-Agent": "Mozilla/5.0"})

            if resp.status_code != 200:

                continue

            text = resp.text

            # ``` bash/code bloklari icinde npx/git clone/curl komutu ara

            for m in re.finditer(r'```(?:bash|sh|shell|console)?\s*\n([\s\S]{0,600}?)```', text):

                block = m.group(1)

                for line in block.splitlines():

                    line = line.strip()

                    if re.match(r'^(npx|npm|git clone|curl|pip install|uv tool|brew install)', line):

                        return line

            # duz satirlarda da ara

            for line in text.splitlines():

                line = line.strip()

                if line.startswith("npx ") or line.startswith("git clone https://github.com/" + repo):

                    return line

        except Exception:

            continue

    return f"git clone https://github.com/{repo}.git"





@app.post("/api/skills/hunt")

async def skills_hunt(req: SkillHuntRequest):

    """skillsllm.com + GitHub uzerinden skill arastirir, en iyi adaylari puanlar."""

    query = (req.query or "").strip()

    source = (req.source or "both").strip()

    if not query:

        return {"success": False, "error": "arama metni gerekli"}

    try:

        llm_candidates = []

        gh_candidates = []

        if source in ("both", "skillsllm"):

            llm_candidates = _hunt_skillsllm(query)

        if source in ("both", "github"):

            gh_candidates = _hunt_github(query)



        seen = set()

        merged = []

        for c in llm_candidates + gh_candidates:

            if c["repo"].lower() in seen:

                continue

            seen.add(c["repo"].lower())

            merged.append(c)



        # Puanla: yildiz + konu eslesmesi

        qw = [w for w in re.split(r"\W+", query.lower()) if len(w) >= 2]

        for c in merged:

            repo_l = c["repo"].lower()

            c["score"] = int(min(int(c.get("stars") or 0), 5000) / 50)

            c["keywords_hit"] = sum(1 for w in qw if w in repo_l)

            c["score"] += c["keywords_hit"] * 10

            c["score"] = min(c["score"], 100)



        merged.sort(key=lambda c: (c["score"], c.get("stars") or 0), reverse=True)

        top = merged[:8]



        for c in top:

            slug = c.get("slug", "")

            if not slug:

                slug = c["repo"].split("/")[-1]

                c["slug"] = slug

            c["install_command"] = _skill_install_command(c["repo"], slug)

            c["zip_url"] = f"https://github.com/{c['repo']}/archive/refs/heads/main.zip"



        return {"success": True, "query": query, "candidates": top}

    except Exception as e:

        return {"success": False, "error": str(e)}





@app.post("/api/skills/install")

async def skills_install(req: SkillInstallRequest, user=Depends(require_admin)):

    """Verilen kurulum komutunu Shadowcat'in kendi terminalinde calistirir."""

    command = (req.command or "").strip()

    if not command:

        return {"success": False, "error": "komut gerekli"}

    if any(op in command for op in (";", "&&", "||", "|", "`", "$(", ">", "<", chr(10), chr(13))):

        return {"success": False, "error": "Komutta zincirleme/yonlendirme operatoru olamaz"}

    if not re.match(r"^(git clone|npx\s|npm\s)", command):

        return {"success": False, "error": "Sadece 'git clone', 'npx' veya 'npm' komutlari calistirilabilir"}

    workdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_skills")

    os.makedirs(workdir, exist_ok=True)

    try:

        import subprocess

        proc = subprocess.run(

            shlex.split(command), shell=False, cwd=workdir, capture_output=True, text=True,

            timeout=600, encoding="utf-8", errors="replace",

        )

        output = (proc.stdout or "")[-4000:]

        if proc.returncode != 0:

            return {"success": False, "error": (proc.stderr or output)[-2000:], "output": output}

        return {"success": True, "output": output, "workdir": workdir}

    except subprocess.TimeoutExpired:

        return {"success": False, "error": "Komut 10 dakikada bitmedi"}

    except Exception as e:

        return {"success": False, "error": str(e)}





def fallback_element_css(selector, instruction):

    """AI motoru yanit veremediginde kelime -> CSS kurali uretir"""

    l = instruction.lower()

    props = []

    colors = {

        "mor": "#7c3aed", "turuncu": "#ff6a00", "kirmizi": "#e11d48", "kırmızı": "#e11d48",

        "mavi": "#2563eb", "yesil": "#16a34a", "yeşil": "#16a34a", "siyah": "#111111",

        "beyaz": "#ffffff", "sari": "#eab308", "sarı": "#eab308", "pembe": "#ec4899"

    }

    for k, v in colors.items():

        if k in l:

            props.append(f"color: {v}")

            break

    if "büyüt" in l or "buyut" in l or "büyük" in l or "buyuk" in l or "artır" in l or "artir" in l:

        props.append("font-size: 2.2rem")

    if "küçült" in l or "kucult" in l or "küçük" in l or "kucuk" in l or "azalt" in l:

        props.append("font-size: 0.9rem")

    if "ortala" in l or "center" in l:

        props.append("text-align: center")

    if "kalın" in l or "kalin" in l or "bold" in l:

        props.append("font-weight: 700")

    if "gölge" in l or "golge" in l or "shadow" in l:

        props.append("box-shadow: 0 8px 24px rgba(0,0,0,0.15)")

    if "yuvarla" in l or "köşe" in l or "kose" in l or "radius" in l:

        props.append("border-radius: 12px")

    if "arkaplan" in l or "arka plan" in l or "background" in l or "zemin" in l:

        props.append("background-color: #f3e8ff")

    if not props:

        props.append("color: #7c3aed")

    return f"{selector} {{ {'; '.join(props)}; }}"





@app.get("/api/memory/search")

async def search_memory(query: str, max_results: int = 5):

    """Hafizada ara"""

    if not CORE_AVAILABLE:

        return {"success": False, "error": "Core yuklu degil"}

    

    try:

        core = get_core()

        if core.memory:

            results = core.memory.recall(query, max_results=max_results)

            return {

                "success": True,

                "query": query,

                "results": [

                    {

                        "path": r.get("path", ""),

                        "preview": r.get("content_preview", "")[:200],

                        "type": r.get("type", "")

                    }

                    for r in results

                ],

                "count": len(results)

            }

        return {"success": False, "error": "Hafiza aktif degil"}

    except Exception as e:

        return {"success": False, "error": str(e)}





@app.get("/api/memory/stats")

async def memory_stats():

    """Hafiza istatistikleri"""

    if not CORE_AVAILABLE:

        return {"success": False, "error": "Core yuklu degil"}

    

    try:

        core = get_core()

        if core.memory:

            return {

                "success": True,

                "total_files": core.memory.get_memory_count(),

                "total_size": core.memory.get_total_size(),

                "recent": [r.get("path", "") for r in core.memory.recall_recent(5)]

            }

        return {"success": False, "error": "Hafiza aktif degil"}

    except Exception as e:

        return {"success": False, "error": str(e)}





@app.get("/api/agent/loop/status")

async def agent_loop_status():

    """Agent Loop durumu"""

    if not CORE_AVAILABLE:

        return {"success": False, "error": "Core yuklu degil"}

    

    try:

        from shadowcat_agent_loop import get_agent_loop

        loop = get_agent_loop()

        return {"success": True, "status": "active", "max_iterations": 10}

    except ImportError:

        return {"success": False, "error": "Agent loop yuklu degil"}

    except Exception as e:

        return {"success": False, "error": str(e)}





# ═══════════════════════════════════════════════════════════════

# SITE BUILDER — AI ile web sitesi olusturma

# ═══════════════════════════════════════════════════════════════



class SiteBuilderRequest(BaseModel):

    message: str

    current_html: str = ""

    template: Optional[str] = None

    theme: Optional[str] = None



class SiteBuilderEditRequest(BaseModel):

    selector: str

    instruction: str

    html: str



DEFAULT_SITE_HTML = """<!doctype html>

<html lang="tr">

<head>

<meta charset="utf-8">

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Sitem</title>

<style>

*{box-sizing:border-box;margin:0;padding:0}

body{font-family:system-ui,sans-serif;background:#faf8f4;color:#1f2937;line-height:1.6}

.hero{text-align:center;padding:80px 24px 60px}

.hero h1{font-size:2.5rem;font-weight:800;margin-bottom:12px}

.hero p{color:#6b7280;max-width:480px;margin:0 auto 24px}

.cta-btn{background:#7c3aed;color:#fff;border:none;border-radius:999px;padding:12px 32px;font-size:1rem;cursor:pointer}

img{max-width:100%;height:auto}

@media(max-width:600px){.hero{padding:48px 16px 36px}.hero h1{font-size:1.8rem}}

</style>

</head>

<body>

<section class="hero">

<h1>Hoş Geldiniz</h1>

<p>Burasi sizin siteniz. AI'ya soyleyerek duzenleyin.</p>

<button class="cta-btn">Baslayalim</button>

</section>

</body>

</html>"""



SITE_TEMPLATES = {

    "restoran": {

        "name": "Restoran",

        "icon": "",

        "html": """<!doctype html>

<html lang="tr">

<head>

<meta charset="utf-8">

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Restoran</title>

<style>

*{box-sizing:border-box;margin:0;padding:0}

body{font-family:system-ui,sans-serif;background:#faf8f4;color:#1f2937;line-height:1.6}

.navbar{display:flex;justify-content:space-between;align-items:center;padding:16px 32px;background:#fff;border-bottom:1px solid #e5e7eb;position:sticky;top:0;z-index:10}

.logo{font-size:1.3rem;font-weight:800;color:#b45309}

.nav-links a{margin-left:20px;text-decoration:none;color:#555;font-weight:600;font-size:.9rem}

.hero{text-align:center;padding:90px 24px;background:linear-gradient(180deg,#fffbeb,#faf8f4)}

.hero h1{font-size:3rem;font-weight:800;margin-bottom:12px;color:#92400e}

.hero p{color:#78716c;max-width:520px;margin:0 auto 28px}

.cta-btn{background:#d97706;color:#fff;border:none;border-radius:999px;padding:14px 34px;font-size:1rem;font-weight:700;cursor:pointer;transition:.3s}

.cta-btn:hover{background:#b45309;transform:scale(1.05)}

.menu{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;padding:60px 6%;max-width:1100px;margin:auto}

.card{background:#fff;border-radius:16px;padding:24px;box-shadow:0 4px 20px rgba(0,0,0,.05);transition:.3s}

.card:hover{transform:translateY(-4px);box-shadow:0 8px 30px rgba(0,0,0,.1)}

.card h3{margin-bottom:8px;color:#92400e}

.card p{color:#78716c;font-size:.9rem}

.price{font-weight:800;color:#d97706;margin-top:10px}

footer{text-align:center;padding:32px;background:#fff;border-top:1px solid #eee;color:#a8a29e;font-size:.85rem}

@media(max-width:600px){.navbar{padding:14px 18px}.nav-links a{margin-left:12px;font-size:.8rem}.hero h1{font-size:2.2rem}.menu{padding:40px 5%}}

</style>

</head>

<body>

<nav class="navbar">

    <div class="logo">Lezzet Durağı</div>

    <div class="nav-links"><a href="#menu">Menü</a><a href="#iletisim">İletişim</a></div>

</nav>

<section class="hero">

    <h1>Eşsiz Lezzetler</h1>

    <p>Yöresel malzemelerle hazırlanan özenli yemeklerimizle sizi bekliyoruz.</p>

    <button class="cta-btn">Rezervasyon Yap</button>

</section>

<section class="menu" id="menu">

    <div class="card"><h3>Izgara Köfte</h3><p>Özel baharatlarla marine edilmiş.</p><div class="price">145 TL</div></div>

    <div class="card"><h3>Ev Yapımı Mantı</h3><p>Sarımsaklı yoğurt ve sos ile.</p><div class="price">120 TL</div></div>

    <div class="card"><h3>Fıstıklı Baklava</h3><p>Günde sınırlı üretim.</p><div class="price">90 TL</div></div>

</section>

<footer id="iletisim">© 2026 Lezzet Durağı · 0212 000 00 00</footer>

</body>

</html>"""

    },

    "portfolyo": {

        "name": "Portfolyo",

        "icon": "",

        "html": """<!doctype html>

<html lang="tr">

<head>

<meta charset="utf-8">

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Portfolyo</title>

<style>

*{box-sizing:border-box;margin:0;padding:0}

body{font-family:system-ui,sans-serif;background:#fff;color:#111827;line-height:1.6}

.navbar{display:flex;justify-content:space-between;align-items:center;padding:18px 36px;border-bottom:1px solid #f3f4f6}

.logo{font-size:1.2rem;font-weight:800}

.nav-links a{margin-left:22px;text-decoration:none;color:#555;font-weight:500;font-size:.9rem}

.hero{text-align:center;padding:100px 24px 60px}

.hero .name{font-size:3rem;font-weight:800;letter-spacing:-1px}

.hero .role{color:#9ca3af;font-size:1.2rem;margin-top:8px}

.hero .bio{color:#6b7280;max-width:480px;margin:20px auto 0}

.work{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;padding:40px 6%;max-width:1100px;margin:auto}

.proj{background:#f9fafb;border-radius:16px;padding:28px;transition:.3s}

.proj:hover{box-shadow:0 8px 30px rgba(0,0,0,.08);transform:translateY(-3px)}

.proj h3{margin-bottom:6px}

.proj p{color:#6b7280;font-size:.9rem}

.tag{display:inline-block;background:#eef2ff;color:#4f46e5;border-radius:99px;padding:3px 12px;font-size:.75rem;margin-top:12px}

footer{text-align:center;padding:40px;color:#9ca3af;font-size:.85rem}

@media(max-width:600px){.hero .name{font-size:2.2rem}.navbar{padding:14px 18px}}

</style>

</head>

<body>

<nav class="navbar">

    <div class="logo">Ayşe Yılmaz</div>

    <div class="nav-links"><a href="#isler">İşler</a><a href="#iletisim">İletişim</a></div>

</nav>

<section class="hero">

    <div class="name">Ayşe Yılmaz</div>

    <div class="role">UI/UX Tasarımcı & Geliştirici</div>

    <p class="bio">Kullanıcı odaklı, estetik ve işlevsel dijital deneyimler tasarlıyorum.</p>

</section>

<section class="work" id="isler">

    <div class="proj"><h3>E-Ticaret Uygulaması</h3><p>Mobil öncelikli alışveriş deneyimi tasarımı.</p><span class="tag">UI/UX</span></div>

    <div class="proj"><h3>Kurumsal Web Sitesi</h3><p>Yenilikçi marka kimliği ve site tasarımı.</p><span class="tag">Web</span></div>

    <div class="proj"><h3>Mobil Uygulama</h3><p>Sağlık takip uygulaması tasarım sistemi.</p><span class="tag">Mobile</span></div>

</section>

<footer id="iletisim">hello@ayseyilmaz.com · İstanbul</footer>

</body>

</html>"""

    },

    "eticaret": {

        "name": "E-Ticaret",

        "icon": "",

        "html": """<!doctype html>

<html lang="tr">

<head>

<meta charset="utf-8">

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Mağaza</title>

<style>

*{box-sizing:border-box;margin:0;padding:0}

body{font-family:system-ui,sans-serif;background:#fafafa;color:#111827;line-height:1.6}

.navbar{display:flex;justify-content:space-between;align-items:center;padding:16px 32px;background:#fff;border-bottom:1px solid #f3f4f6;position:sticky;top:0;z-index:10}

.logo{font-size:1.3rem;font-weight:800}

.nav-links a{margin-left:20px;text-decoration:none;color:#555;font-weight:600;font-size:.9rem}

.hero{text-align:center;padding:70px 24px;background:linear-gradient(135deg,#eef2ff,#fff)}

.hero h1{font-size:2.5rem;font-weight:800;margin-bottom:10px}

.hero p{color:#6b7280;margin-bottom:24px}

.cta-btn{background:#111827;color:#fff;border:none;border-radius:8px;padding:12px 30px;font-weight:700;cursor:pointer}

.products{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px;padding:50px 6%;max-width:1100px;margin:auto}

.product{background:#fff;border-radius:14px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,.05);text-align:center;transition:.3s}

.product:hover{transform:translateY(-3px);box-shadow:0 8px 26px rgba(0,0,0,.09)}

.product .thumb{height:150px;background:#f3f4f6;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:2.5rem;margin-bottom:14px}

.product h3{font-size:.95rem;margin-bottom:4px}

.product .price{font-weight:800;color:#111827;margin-top:8px}

.buy-btn{background:#4f46e5;color:#fff;border:none;border-radius:8px;padding:8px 22px;cursor:pointer;font-size:.85rem;margin-top:10px;transition:.2s}

.buy-btn:hover{background:#4338ca}

footer{text-align:center;padding:32px;color:#9ca3af;font-size:.85rem}

@media(max-width:600px){.navbar{padding:14px 18px}.hero h1{font-size:2rem}}

</style>

</head>

<body>

<nav class="navbar">

    <div class="logo">Trendy</div>

    <div class="nav-links"><a href="#urunler">Ürünler</a><a href="#iletisim">İletişim</a></div>

</nav>

<section class="hero">

    <h1>Yeni Sezon Kampanyası</h1>

    <p>Seçili ürünlerde %50'ye varan indirim!</p>

    <button class="cta-btn">Alışverişe Başla</button>

</section>

<section class="products" id="urunler">

    <div class="product"><div class="thumb"></div><h3>Koşu Ayakkabısı</h3><div class="price">1.299 TL</div><button class="buy-btn">Sepete Ekle</button></div>

    <div class="product"><div class="thumb"></div><h3>Klasik Mont</h3><div class="price">899 TL</div><button class="buy-btn">Sepete Ekle</button></div>

    <div class="product"><div class="thumb"></div><h3>Kablosuz Kulaklık</h3><div class="price">649 TL</div><button class="buy-btn">Sepete Ekle</button></div>

</section>

<footer id="iletisim">© 2026 Trendy · Kargo ücretsiz</footer>

</body>

</html>"""

    },

    "blog": {

        "name": "Blog",

        "icon": "",

        "html": """<!doctype html>

<html lang="tr">

<head>

<meta charset="utf-8">

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Blog</title>

<style>

*{box-sizing:border-box;margin:0;padding:0}

body{font-family:system-ui,sans-serif;background:#fff;color:#111827;line-height:1.7}

.navbar{display:flex;justify-content:space-between;align-items:center;padding:18px 36px;border-bottom:1px solid #f3f4f6;max-width:900px;margin:auto}

.logo{font-size:1.2rem;font-weight:800}

.nav-links a{margin-left:20px;text-decoration:none;color:#555;font-size:.9rem}

.posts{max-width:700px;margin:40px auto;padding:0 24px}

.post{border-bottom:1px solid #f3f4f6;padding:28px 0}

.post .date{color:#9ca3af;font-size:.8rem}

.post h2{font-size:1.4rem;margin:8px 0;cursor:pointer}

.post h2:hover{color:#4f46e5}

.post p{color:#6b7280;font-size:.95rem}

.post .read{color:#4f46e5;font-size:.85rem;font-weight:600;margin-top:10px;display:inline-block}

footer{text-align:center;padding:40px;color:#9ca3af;font-size:.85rem}

@media(max-width:600px){.navbar{padding:14px 18px}}

</style>

</head>

<body>

<nav class="navbar">

    <div class="logo">Günlük Düşünceler</div>

    <div class="nav-links"><a href="#">Yazılar</a><a href="#">Hakkında</a></div>

</nav>

<section class="posts">

    <div class="post"><div class="date">1 Ağustos 2026</div><h2>Yapay Zeka ile Üretkenlik</h2><p>AI araçlarının günlük iş akışını nasıl dönüştürdüğüne dair kişisel deneyimlerim...</p><span class="read">Devamını Oku </span></div>

    <div class="post"><div class="date">25 Temmuz 2026</div><h2>Kod Yazmanın Geleceği</h2><p>Düşük kod ve no-code araçların yükselişi üzerine notlar ve tahminler...</p><span class="read">Devamını Oku </span></div>

    <div class="post"><div class="date">10 Temmuz 2026</div><h2>Minimalizm ve Odak</h2><p>Daha az araç, daha derin çalışma: dijital minimalizm rehberi...</p><span class="read">Devamını Oku </span></div>

</section>

<footer>© 2026 Günlük Düşünceler</footer>

</body>

</html>"""

    },

    "kisisel": {

        "name": "Kişisel",

        "icon": "",

        "html": """<!doctype html>

<html lang="tr">

<head>

<meta charset="utf-8">

<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Kişisel Sayfa</title>

<style>

*{box-sizing:border-box;margin:0;padding:0}

body{font-family:system-ui,sans-serif;background:#f8fafc;color:#0f172a;line-height:1.6}

.page{max-width:720px;margin:0 auto;padding:40px 24px;text-align:center}

.avatar{width:110px;height:110px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#8b5cf6);margin:0 auto 20px;display:flex;align-items:center;justify-content:center;font-size:2.6rem;color:#fff}

.name{font-size:2.2rem;font-weight:800}

.title{color:#64748b;margin-top:6px}

.bio{color:#475569;max-width:480px;margin:18px auto 30px}

.social{display:flex;gap:12px;justify-content:center;margin-bottom:40px}

.social a{background:#fff;border:1px solid #e2e8f0;border-radius:99px;padding:9px 22px;text-decoration:none;color:#334155;font-size:.85rem;font-weight:600;transition:.2s}

.social a:hover{border-color:#6366f1;color:#6366f1}

.skills{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:20px 0 50px}

.skill{background:#eef2ff;color:#4f46e5;border-radius:99px;padding:6px 16px;font-size:.8rem;font-weight:600}

footer{color:#94a3b8;font-size:.8rem;padding:20px}

@media(max-width:600px){.name{font-size:1.8rem}}

</style>

</head>

<body>

<div class="page">

    <div class="avatar"></div>

    <div class="name">Merhaba, Ben Ali</div>

    <div class="title">Yazılım Geliştirici</div>

    <p class="bio">Türkiye'den bir yazılım tutkunu. Web, yapay zeka ve açık kaynak projeleriyle ilgileniyorum.</p>

    <div class="social"><a href="#">GitHub</a><a href="#">LinkedIn</a><a href="#">Twitter</a></div>

    <div class="skills"><span class="skill">Python</span><span class="skill">JavaScript</span><span class="skill">AI/ML</span><span class="skill">Web</span></div>

</div>

<footer>© 2026 Ali · İletişim: ali@example.com</footer>

</body>

</html>"""

    },

}



SITE_THEMES = {

    "mor": {"name": "Mor", "hint": "Ana renk #7c3aed (mor), vurgu mor tonlari, arka plan acik kremsi"},

    "mavi": {"name": "Mavi", "hint": "Ana renk #2563eb (mavi), vurgu mavi tonlari, arka plan acik mavi-beyaz"},

    "koyu": {"name": "Koyu", "hint": "Koyu tema: arka plan #0f172a, metin #e2e8f0, vurgu #38bdf8 (acik mavi)"},

    "neon": {"name": "Neon", "hint": "Neon tema: koyu arka plan #0a0a0f, neon yesil #22c55e ve neon pembe #ec4899 vurgular, parlak efektler"},

    "yesil": {"name": "Yeşil", "hint": "Ana renk #16a34a (yesil), dogal yesil tonlar, acik yaprak yesili arka plan"},

    "kirmizi": {"name": "Kırmızı", "hint": "Ana renk #dc2626 (kirmizi), sicak tonlar, acik krem arka plan"},

}



SITE_FONTS = "Google Fonts kullanabilirsin: <link href='https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Poppins:wght@400;600&display=swap' rel='stylesheet'> ile 'Playfair Display' basliklarda, 'Poppins' metinlerde kullanabilirsin. Alternatif fontlar: 'Inter', 'Space Grotesk', 'DM Serif Display'."



def _site_builder_agent_logic(message: str, current_html: str = "", template: Optional[str] = None, theme: Optional[str] = None) -> dict:

    """Site Builder mantigi: mesaji analiz et, HTML guncelle, AI yaniti hazirla"""

    theme_hint = ""

    if theme and theme in SITE_THEMES:

        theme_hint = f"\nTEMA: '{theme}' temasini kullan: {SITE_THEMES[theme]['hint']}. Tum renkleri bu temaya uygun sec.\n"

    template_hint = ""

    if template and template in SITE_TEMPLATES:

        template_hint = f"\nSABLON: '{template}' sablonu secildi. Bu sablonun yapisini ve bolumlerini koru, talebi ona uygula.\n"

    prompt = (

        f"Kullanici site hakkinda su talepte bulundu: \"{message}\"\n\n"

        f"Su anki HTML:\n```html\n{current_html or DEFAULT_SITE_HTML}\n```\n\n"

        "Gorevlerin:\n"

        "1. Talebi anla (ekleme, degisiklik, silme, stil vs)\n"

        "2. HTML'i guncelle - talebi gercekten uygula\n"

        "3. Sadece degisen kismi degil, TUM HTML'i dondur\n"

        "4. Tum CSS <style> icinde olsun\n"

        "5. Elementlere anlamli class adlari ver (navbar, hero, card, footer vb)\n"

        "6. Eksiksiz ve gecerli bir HTML dokumani olmali - <!doctype html> ile baslamali\n"

        "7. MOBIL UYUM ZORUNLU: <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"> head icinde olmali, @media(max-width:600px) ile mobil stiller ekle, flexbox/grid kullan\n"

        "8. RESIM: Kullanici resim isterse <img> ekle. Gorsel URL'si belirtilmediyse placeholder olarak https://picsum.photos/seed/site{n}/800/500 kullan. Tum img'lere max-width:100%;height:auto ver\n"

        "9. COKLU SAYFA: Kullanici 'sayfa ekle', 'hakkimizda sayfasi' gibi bir sey isterse, tek HTML dosyasinda birden fazla bolum (<section id=\"...\">) olustur ve navbar'daki linklerle (href=\"#id\") bagla. Kullanici istemedikce yeni dosya acma.\n"

        f"10. {SITE_FONTS}\n"

        f"{template_hint}{theme_hint}\n"

        "Yanit format (KESINLIKLE uygula):\n"

        "---HTML---\n<!doctype html> ile baslayan TUM HTML kodu\n"

        "---MESAJ---\n[kullaniciya kisa aciklama, 1-2 cumle]\n"

        "SADECE bu formatta yanit ver, baska hicbir sey yazma."

    )

    return {"prompt": prompt, "current_html": current_html or DEFAULT_SITE_HTML}



def _sanitize_html(html: str) -> str:

    """Regex son kontrol - AI hata yapsa bile temiz HTML garanti eder"""

    import re as _re

    # 1. Negatif padding/margin degerlerini sifirla (gecersiz CSS)

    html = _re.sub(r'(padding|margin)(?:-top|-bottom|-left|-right)?\s*:\s*-\d+(?:\.\d+)?(?:px|rem|em|vh|vw)?\s*;?', lambda m: m.group(0).split(':')[0] + ':0;', html)

    # 2. Eksik text-shadow (renk degeri olmayan) satirlarini sil

    html = _re.sub(r'text-shadow\s*:\s*rgba\([^)]*\)\s*;?', '', html)

    # 3. Tanimsiz var() kullanimini kaldir (--x tanimli degilse)

    html = _re.sub(r'calc\(-1\s*\*\s*var\(--content-padding\)\)', '0', html)

    # 3b. Bos kalmis CSS kurallarini sil (.hero{})

    html = _re.sub(r'[^{}]{1,80}\{\s*\}', '', html)

    # 4. Viewport yoksa ekle

    if 'name="viewport"' not in html and '<head>' in html:

        html = html.replace('<head>', '<head>\n<meta name="viewport" content="width=device-width,initial-scale=1">', 1)

    # 5. </html> yoksa ekle

    if '</html>' not in html.lower():

        html += '\n</html>'

    # 5b. </html>'den sonrasini kes (AI ekstra metni sayfa altina dusmesin)

    import re as _re2

    _m2 = _re2.search(r'(?is)^(.*?</html>)', html)

    if _m2:

        html = _m2.group(1)

    # 6. Ard arda bos satirlari tek bos satira indir

    html = _re.sub(r'\n{3,}', '\n\n', html)

    return html.strip()





async def _recover_html_with_ai(html: str) -> str:

    """Recovery subagent - X_FABLE_CODER (kod modeli) HTML'i temizler"""

    if not html or len(html) < 100:

        return _sanitize_html(html)

    prompt = (

        "Sen bir HTML temizlik uzmanisin. Asagidaki kullanici tarafindan AI ile uretilmis HTML'i duzelt:\n"

        "- Negatif padding/margin degerlerini 0 yap\n"

        "- Eksik veya bozuk text-shadow ozelliklerini sil\n"

        "- Tanimsiz CSS degiskeni kullanimlarini kaldir\n"

        "- Gecersiz CSS kurallarini sil (tarayicida sorun cikaranlar)\n"

        "- <meta name=\"viewport\"> head icinde yoksa ekle\n"

        "- </html> kapanis etiketi yoksa ekle\n"

        "- Icerik, yapi ve sinif adlarina DOKUNMA\n"

        "- SADECE duzeltilmis TUM HTML kodunu dondur, baska hicbir sey yazma (aciklama yok, kod blogu isareti yok)\n\n"

        f"HTML:\n{html}"

    )

    recovery_config = dict(AI_CONFIG["primary"])

    recovery_config["model"] = "glassesglitchstudio/x_fable_coder:V1"

    try:

        cleaned = await call_ai_engine(prompt, recovery_config, num_predict=6000)

        if cleaned and "<html" in cleaned.lower() or (cleaned and "<body" in cleaned.lower()):

            return _sanitize_html(cleaned)

    except Exception as e:

        logger.warning(f"Recovery subagent hatasi: {e}")

    return _sanitize_html(html)





def _html_needs_recovery(html: str) -> bool:

    """Sanitizer sonrasi hala kusur var mi? (subagent sadece gerekirse calisir)"""

    import re as _re

    if _re.search(r'(padding|margin)(?:-top|-bottom|-left|-right)?\s*:\s*-\d', html):

        return True

    if 'text-shadow:rgba' in html or 'var(--' in html:

        return True

    if 'name="viewport"' not in html or '</html>' not in html.lower():

        return True

    if _re.search(r'[^{}]{1,80}\{\s*\}', html):

        return True

    return False





@app.get("/api/site-builder/templates")

async def site_builder_templates():

    """Site Builder sablon ve tema listesi"""

    return {

        "success": True,

        "templates": {k: {"name": v["name"], "icon": v["icon"]} for k, v in SITE_TEMPLATES.items()},

        "themes": {k: {"name": v["name"]} for k, v in SITE_THEMES.items()}

    }



@app.post("/api/site-builder/chat")

async def site_builder_chat(req: SiteBuilderRequest):

    """Site Builder sohbet — mesaj alir, HTML gunceller, AI yaniti doner"""

    try:

        start_html = req.current_html

        if not start_html and req.template and req.template in SITE_TEMPLATES:

            start_html = SITE_TEMPLATES[req.template]["html"]

        logic = _site_builder_agent_logic(req.message, start_html, template=req.template, theme=req.theme)

        ai_resp = await get_ai_response(logic["prompt"], num_predict=8000)

        msg_part = "Site guncellendi!"



        if ai_resp and "" not in ai_resp:

            import re

            new_html = None

            # 1. ---HTML--- / ---MESAJ--- formatı

            m = re.search(r'---HTML---\s*\n(.*?)(?:\n---MESAJ---|$)', ai_resp, re.DOTALL)

            if m and ("<html" in m.group(1) or "<body" in m.group(1) or "<!doctype" in m.group(1).lower()):

                new_html = m.group(1).strip()

                if "---MESAJ---" in ai_resp:

                    msg_part = ai_resp.split("---MESAJ---")[-1].strip()[:300]

            # 2. Fenced code block

            if not new_html:

                m = re.search(r'```(?:html)?\s*\n(.*?)```', ai_resp, re.DOTALL)

                if m and ("<html" in m.group(1) or "<body" in m.group(1) or "<!doctype" in m.group(1).lower()):

                    new_html = m.group(1).strip()

            # 3. Direkt HTML

            if not new_html and ("<html" in ai_resp or "<body" in ai_resp or "<!doctype" in ai_resp.lower()):

                new_html = ai_resp.strip()

            # 4. AI tamamlanmamış HTML döndürdüyse default şablonu kullan

            if new_html:

                cleaned = _sanitize_html(new_html)

                if _html_needs_recovery(cleaned):

                    cleaned = await _recover_html_with_ai(cleaned)

                return {"success": True, "html": cleaned[:20000], "message": msg_part}



        return {"success": True, "html": start_html or logic["current_html"], "message": "Anlamadim. Lutfen net bir istek yazin."}

    except Exception as e:

        logger.error(f"Site Builder hatasi: {e}")

        return {"success": False, "error": str(e), "html": req.current_html or DEFAULT_SITE_HTML}



@app.post("/api/site-builder/edit")

async def site_builder_edit(req: SiteBuilderEditRequest):

    """Site Builder element duzeltme — secili elemente CSS uygula"""

    try:

        edit_prompt = (

            f"Kullanici su elementi duzenlemek istiyor:\n"

            f"CSS selector: `{req.selector}`\n"

            f"Talimat: {req.instruction}\n\n"

            f"Sayfanin HTML'i:\n```html\n{req.html[:8000]}\n```\n\n"

            "Sadece bir CSS kural blogu dondur: `{ selector { property: value; } }` seklinde.\n"

            "Aciklama yazma, markdown kullanma."

        )

        result = await get_ai_response(edit_prompt, num_predict=4000)

        if result and "" not in result:

            m = re.search(r'\{[\s\S]*\}', result)

            if m:

                css = m.group(0).strip()

                return {"success": True, "css": css}

        return {"success": False, "error": "CSS uretilemedi", "css": ""}

    except Exception as e:

        return {"success": False, "error": str(e)}





# ═══════════════════════════════════════════════════════════════

# SWARM SUBAGENT — Paralel Alt Ajan Sistemi

# ═══════════════════════════════════════════════════════════════



class SwarmRequest(BaseModel):

    message: str



@app.post("/api/swarm")

async def swarm_execute(request: SwarmRequest):

    """Swarm Agent — mesajı alt görevlere böl, paralel çalıştır, birleştir"""

    try:

        msg = request.message

        subtask_status = [

            {"name": "web_search", "label": "Web'de ara", "icon": "", "status": "running"},

            {"name": "memory_search", "label": "Hafızada ara", "icon": "", "status": "running"},

            {"name": "ai_analyze", "label": "AI analiz", "icon": "", "status": "running"},

            {"name": "code_gen", "label": "Kod üretimi", "icon": "", "status": "running"},

            {"name": "skill_matcher", "label": "Skill eşleştirme", "icon": "", "status": "running"},

            {"name": "translate", "label": "Çeviri", "icon": "", "status": "running"},

        ]



        # 6 alt ajanı paralel çalıştır

        web_task = _swarm_web_search(msg)

        memory_task = _swarm_memory_search(msg)

        ai_task = _swarm_ai_analyze(msg)

        code_task = _swarm_code_gen(msg)

        skill_task = _swarm_skill_matcher(msg)

        translate_task = _swarm_translate(msg)



        web_result, memory_result, ai_result, code_result, skill_result, translate_result = await asyncio.gather(

            web_task, memory_task, ai_task, code_task, skill_task, translate_task, return_exceptions=True

        )



        # Hataları temizle

        def clean(r):

            return "" if isinstance(r, Exception) else (r or "")

        web_result = clean(web_result)

        memory_result = clean(memory_result)

        ai_result = clean(ai_result)

        code_result = clean(code_result)

        skill_result = clean(skill_result)

        translate_result = clean(translate_result)



        # Subtask durumlarını güncelle

        for s in subtask_status:

            s["status"] = "done"



        # Birleştir

        combined = _swarm_combine(msg, web_result, memory_result, ai_result, code_result, skill_result, translate_result)



        # Tüm alt ajanlar boş döndüyse direkt AI'ya sor

        if not combined:

            direct = await get_ai_response(msg)

            if direct and "" not in direct:

                combined = (

                    f"**Swarm Agent** — Alt ajanlar veri bulamadı, direkt AI yanıtı:\n\n"

                    f"{direct}"

                )

            else:

                combined = "Swarm Agent şu anda yanıt üretemedi. Lütfen tekrar dene."



        return {

            "success": True,

            "response": combined,

            "subtasks": subtask_status

        }

    except Exception as e:

        logger.error(f"Swarm hatası: {e}")

        return {"success": False, "error": str(e), "subtasks": []}





async def _swarm_web_search(query: str) -> str:

    """Web arama alt ajanı — DuckDuckGo üzerinden anlık bilgi toplar"""

    try:

        async with httpx.AsyncClient(timeout=15.0) as client:

            resp = await client.get(

                "https://api.duckduckgo.com/",

                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},

                headers={"User-Agent": "Shadowcat-Swarm/1.0"}

            )

            if resp.status_code == 200:

                data = resp.json()

                abstract = data.get("AbstractText", "") or ""

                source = data.get("AbstractSource", "") or ""

                if abstract:

                    result = abstract[:600]

                    if source:

                        result += f"\nKaynak: {source}"

                    return result

                # Fallback: İlgili başlıklar

                topics = data.get("RelatedTopics", [])

                if topics:

                    lines = []

                    for t in topics[:3]:

                        if isinstance(t, dict):

                            text = t.get("Text", "") or t.get("Result", "") or ""

                            if text:

                                lines.append(text[:200])

                    if lines:

                        return "\n".join(lines)

    except Exception as e:

        logger.warning(f"Swarm web_search hatası: {e}")

    return ""





async def _swarm_memory_search(query: str) -> str:

    """Hafıza arama alt ajanı — Obsidian'dan ilgili bilgileri getirir"""

    if not CORE_AVAILABLE:

        return ""

    try:

        core = get_core()

        if core.memory:

            results = core.memory.recall(query, max_results=5)

            if results:

                parts = []

                seen = set()

                for r in results:

                    path = r.get("path", "")

                    if path in seen:

                        continue

                    seen.add(path)

                    preview = r.get("content_preview", "")[:200].replace("\n", " ").strip()

                    mtype = r.get("type", "not")

                    parts.append(f"{'' if mtype != 'konusma' else ''} {preview}")

                if parts:

                    return "\n".join(parts[:3])

    except Exception as e:

        logger.warning(f"Swarm memory_search hatası: {e}")

    return ""





async def _swarm_ai_analyze(query: str) -> str:

    """AI analiz alt ajanı — mesajı derinlemesine analiz eder"""

    try:

        analysis_prompt = (

            f"Kullanıcı şunu dedi: \"{query}\"\n\n"

            "Bunu analiz et:\n"

            "1. Bu ne tür bir istek/soru?\n"

            "2. Hangi alt başlıkları var?\n"

            "3. Kısa bir özet çıkar (2-3 cümle)\n\n"

            "Format:\n"

            "Tür: ...\n"

            "Özet: ..."

        )

        result = await get_ai_response(analysis_prompt)

        if result and "" not in result:

            return result[:400]

    except Exception as e:

        logger.warning(f"Swarm ai_analyze hatası: {e}")

    return ""





async def _swarm_code_gen(query: str) -> str:

    """Kod üretim alt ajanı — kod taleplerini algılar, artifact hazırlar"""

    try:

        # Kod talebi var mı kontrol et

        code_keywords = ["yaz", "kod", "kodla", "fonksiyon", "program", "script", "python", "javascript", "html", "css", "yap", "oluştur", "üret"]

        ql = query.lower()

        if not any(k in ql for k in code_keywords):

            return ""



        code_prompt = (

            f"Kullanıcı şunu istedi: \"{query}\"\n\n"

            "Sadece kod üret. Açıklama yazma. Markdown kullanma.\n"

            "Dil: python, javascript, html veya uygun olan neyse.\n"

            "Kodu ```python veya ```javascript veya ```html blokları içinde döndür."

        )

        result = await get_ai_response(code_prompt)

        if result and "" not in result:

            # Kod bloğu yakala

            import re

            blocks = re.findall(r'```(\w+)?\n(.*?)```', result, re.DOTALL)

            if blocks:

                parts = []

                for lang, code in blocks[:2]:

                    lang_label = lang or "text"

                    code_clean = code.strip()[:300]

                    parts.append(f"```{lang_label}\n{code_clean}\n```")

                if parts:

                    return "\n\n".join(parts)

            return result[:500]

    except Exception as e:

        logger.warning(f"Swarm code_gen hatası: {e}")

    return ""





async def _swarm_skill_matcher(query: str) -> str:

    """Skill eşleştirme alt ajanı — mesaja en uygun skill'i bulur"""

    try:

        ql = query.lower()

        # Skill kontrolü (frontend'deki BUILTIN_SKILLS ile senkron)

        skills_db = [

            ("site-builder", "", ["site", "web sitesi", "web sayfası", "arayüz", "tasarım"], "Web sitesi ve arayüz geliştirme"),

            ("tailwind-css", "", ["tailwind", "responsive tasarım", "css framework"], "Utility-first CSS framework"),

            ("ui-pro-max", "", ["animasyon", "glassmorphism", "neon stil", "ui"], "Animasyon motorları"),

            ("ui-ux-pro-max", "", ["ui/ux", "tasarım zekası", "kullanıcı deneyimi"], "Tasarım zekası"),

        ]

        matches = []

        for sid, icon, keywords, desc in skills_db:

            if any(k in ql for k in keywords):

                matches.append(f"{icon} **{sid}** — {desc}")

        if matches:

            return "Eşleşen skill'ler:\n" + "\n".join(matches[:3])

    except Exception as e:

        logger.warning(f"Swarm skill_matcher hatası: {e}")

    return ""





async def _swarm_translate(query: str) -> str:

    """Çeviri alt ajanı — dil algılar ve çeviri yapar"""

    try:

        ql = query.lower()

        # Çeviri talebi kontrolü

        translate_triggers = ["çevir", "çeviri", "translate", "ingilizce", "türkçe", "english", "turkish", "şu metni"]

        if not any(t in ql for t in translate_triggers):

            return ""



        translate_prompt = (

            f"Kullanıcı mesajı: \"{query}\"\n\n"

            "Bu bir çeviri talebi. Şunları yap:\n"

            "1. Kaynak dili ve hedef dili tespit et\n"

            "2. Çeviriyi yap\n"

            "3. Çevrilen metni döndür\n\n"

            "Format:\n"

            "Dil: kaynak hedef\n"

            "Çeviri: ..."

        )

        result = await get_ai_response(translate_prompt)

        if result and "" not in result:

            return result[:400]

    except Exception as e:

        logger.warning(f"Swarm translate hatası: {e}")

    return ""





def _swarm_combine(query: str, web: str, memory: str, ai: str, code: str = "", skill: str = "", translate: str = "") -> str:

    """Alt ajan sonuçlarını birleştirip tek bir yanıt oluşturur"""

    parts = []

    has_any = False



    if code:

        has_any = True

        parts.append(f"**Kod Çıktısı**\n{code}")



    if skill:

        has_any = True

        parts.append(f"**Skill Eşleşmesi**\n{skill}")



    if translate:

        has_any = True

        parts.append(f"**Çeviri**\n{translate}")



    if memory:

        has_any = True

        parts.append(f"**Hafızamdan Bulduklarım**\n{memory}")



    if web:

        has_any = True

        parts.append(f"**Web'den Anlık Bilgiler**\n{web}")



    if ai:

        has_any = True

        parts.append(f"**Analizim**\n{ai}")



    if not has_any:

        return ""



    return (

        f"**Swarm Agent — Paralel İşleme Tamamlandı**\n\n"

        f"Sorgun: _{query}_\n\n"

        + "\n\n".join(parts) +

        "\n\n---\n_Tüm alt ajanlar paralel çalıştırıldı ve sonuçlar birleştirildi._"

    )





# ═══════════════════════════════════════════════════════════════

# V4+ TEXT-TO-IMAGE API ENDPOINT

# ═══════════════════════════════════════════════════════════════



class ImageRequest(BaseModel):

    prompt: str



@app.post("/api/image/generate")

async def generate_image(request: ImageRequest):

    """

    V4+ Görsel Üretim Motoru (Text-to-Image)

    Pollinations.ai + Flux ile sıfır kurulum, sınırsız ücretsiz

    """

    try:

        import urllib.parse



        prompt = request.prompt

        guvenli_prompt = urllib.parse.quote(prompt)

        gorsel_url = (

            "https://image.pollinations.ai/p/"

            + guvenli_prompt

            + "?width=1920&height=1080&model=flux"

        )



        logger.info(f"V4+ Görsel oluşturuldu: {gorsel_url}")



        return {

            "success": True,

            "prompt": prompt,

            "url": gorsel_url,

            "width": 1920,

            "height": 1080,

            "model": "flux",

            "engine": "glassesglitchstudio/gulmzcetiner:V4Plus"

        }

    except Exception as e:

        logger.error(f"V4+ görsel hatası: {str(e)}")

        return {

            "success": False,

            "error": str(e)

        }





# ==================== OLLAMA OTO-BASLATMA ====================

def ensure_ollama_running():
    """Ollama servisinin aktif olup olmadigini kontrol eder, kapaliysa arka planda otomatik baslatir."""
    import socket
    import subprocess
    import shutil

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    is_running = (sock.connect_ex(('127.0.0.1', 11434)) == 0)
    sock.close()

    if is_running:
        logger.info("[Ollama] Ollama servisi zaten calisiyor (port 11434).")
        return True

    logger.info("[Ollama] Ollama servisi kapali, otomatik baslatiliyor...")
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        default_win_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
        if os.path.exists(default_win_path):
            ollama_path = default_win_path

    if ollama_path:
        try:
            if os.name == 'nt':
                subprocess.Popen([ollama_path, "serve"], creationflags=0x08000000 | 0x00000008)  # CREATE_NO_WINDOW | DETACHED_PROCESS
            else:
                subprocess.Popen([ollama_path, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            logger.info("[Ollama] Ollama 'serve' arka planda basariyla baslatildi.")
            return True
        except Exception as err:
            logger.warning(f"[Ollama] Ollama otomatik baslatilamadi: {err}")
    else:
        logger.warning("[Ollama] Ollama calistirilabilir dosyasi bulunamadi.")
    return False

# ==================== SHADOWCAT CORE BASLATMA ====================

if CORE_AVAILABLE:
    try:
        core = get_core()
        logger.info(f"Shadowcat Core baslatildi: {core.toolformer.registry.count() if core.toolformer else 0} arac")
    except Exception as e:
        logger.warning(f"Shadowcat Core baslatilamadi: {e}")


# ==================== VOICE CHAT API ====================

from voice_chat import get_voice_chat, TTS_AVAILABLE, STT_AVAILABLE

@app.get("/api/voice/status")
async def voice_status():
    """Ses sistemi durumu"""
    voice = get_voice_chat()
    return JSONResponse(voice.get_status())

@app.post("/api/voice/speak")
async def voice_speak(request: Request):
    """Text-to-Speech: Metni sese dönüştür"""
    data = await request.json()
    text = data.get("text", "")
    provider = data.get("provider", None)
    if not text:
        raise HTTPException(status_code=400, detail="text gerekli")
    voice = get_voice_chat()
    result = voice.speak(text, provider)
    return JSONResponse(result)

@app.post("/api/voice/listen")
async def voice_listen(request: Request):
    """Speech-to-Text: Mikrofon dinle"""
    data = await request.json()
    timeout = data.get("timeout", 10)
    voice = get_voice_chat()
    result = voice.listen(timeout)
    return JSONResponse(result)

@app.post("/api/voice/toggle")
async def voice_toggle(request: Request):
    """Ses aç/kapat"""
    data = await request.json()
    enabled = data.get("enabled", None)
    voice = get_voice_chat()
    state = voice.toggle(enabled)
    return JSONResponse({"enabled": state})

@app.post("/api/voice/provider")
async def voice_set_provider(request: Request):
    """TTS provider değiştir (gtts, pyttsx3, edge)"""
    data = await request.json()
    provider = data.get("provider", "gtts")
    voice = get_voice_chat()
    success = voice.set_provider(provider)
    return JSONResponse({"success": success, "provider": provider})

@app.post("/api/voice/chat")
async def voice_chat(request: Request):
    """Sesli sohbet: Konuş -> Dinle -> Yanıt -> Konuş"""
    data = await request.json()
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="text gerekli")

    # AI yanıtı üret
    if CORE_AVAILABLE:
        core = get_core()
        result = core.process_message(text)
        response_text = result.response
    else:
        response_text = "Shadowcat Core aktif değil"

    # Sese dönüştür
    voice = get_voice_chat()
    voice_result = voice.speak(response_text)

    return JSONResponse({
        "user_text": text,
        "ai_response": response_text,
        "voice": voice_result
    })

# ==================== YENI OZELLIK API'LERI ====================

# 1. Sistem Monitoru
from system_monitor import get_system_monitor

@app.get("/api/system/status")
async def api_system_status():
    """Canli sistem izleme: CPU, RAM, Disk, GPU, Ag"""
    mon = get_system_monitor()
    return JSONResponse(mon.get_all())


# 2. Dashboard: Notlar + istatistik
from dashboard import get_dashboard

@app.get("/api/dashboard/notes")
async def api_list_notes(limit: int = 50):
    """Hizli notlari listele"""
    dash = get_dashboard()
    return JSONResponse({"notes": dash.list_notes(limit)})

@app.post("/api/dashboard/notes")
async def api_add_note(request: Request):
    """Yeni hizli not ekle"""
    data = await request.json()
    title = data.get("title", "Not")
    content = data.get("content", "")
    tags = data.get("tags", [])
    note = get_dashboard().add_note(title, content, tags)
    return JSONResponse({"success": True, "note": note})

@app.delete("/api/dashboard/notes/{note_id}")
async def api_delete_note(note_id: str):
    """Not sil"""
    ok = get_dashboard().delete_note(note_id)
    return JSONResponse({"success": ok})

@app.get("/api/dashboard/notes/search")
async def api_search_notes(q: str = ""):
    """Notlarda ara"""
    results = get_dashboard().search_notes(q)
    return JSONResponse({"results": results})

@app.get("/api/dashboard/stats")
async def api_get_stats():
    """Kullanim istatistikleri"""
    dash = get_dashboard()
    return JSONResponse({
        "stats": dash.get_stats(),
        "memory": dash.get_memory_summary(core.memory if CORE_AVAILABLE and 'core' in dir() else None)
    })


# 3. Sohbet disa aktarma
from chat_export import export_file

@app.post("/api/chat/export")
async def api_chat_export(request: Request):
    """Sohbeti JSON/MD/HTML olarak disa aktar"""
    data = await request.json()
    messages = data.get("messages", [])
    fmt = data.get("format", "json")
    title = data.get("title", "Shadowcat Sohbeti")
    if not messages:
        raise HTTPException(status_code=400, detail="mesaj yok")
    result = export_file(messages, fmt, title)
    return JSONResponse(result)


# 4. Sifreleme / guvenlik ipuclari
@app.get("/api/health")
async def api_health():
    """Sunucu saglik kontrolu"""
    return JSONResponse({"status": "ok", "time": __import__("time").strftime("%Y-%m-%d %H:%M:%S")})

if __name__ == "__main__":
    import uvicorn
    ensure_ollama_running()
    # FastAPI motorunu 8000 portuna taşıyoruz, 5000 portu Web Arayüzü (Flask) için ayrıldı.
    uvicorn.run(app, host="0.0.0.0", port=8000)

