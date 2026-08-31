from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import httpx
import logging
import os

logger = logging.getLogger("routes.chat")
router = APIRouter()

try:
    from codes_router import get_codes_router, is_codes_tier
except ImportError:
    def get_codes_router():
        raise RuntimeError("codes_router.py eksik")
    def is_codes_tier(value: str) -> bool:
        return False

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    model: Optional[str] = None
    stream: bool = False

def _sse(obj) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

def _codes_sse(message: str, tier: str):
    try:
        codes = get_codes_router()
        for ch in codes.chat_stream(message, tier=tier):
            yield _sse(ch)
    except Exception as e:
        yield _sse({"error": str(e), "done": True})
    yield _sse({"done": True})

def _direct_sse(message: str, model: str):
    try:
        from xopus_router import get_xopus
        for ch in get_xopus().chat_stream(message=message, model=model):
            yield _sse(ch)
    except Exception as e:
        yield _sse({"error": str(e), "done": True})
    yield _sse({"done": True})

def get_core():
    try:
        from shadowcat_core import get_core as _get_core
        return _get_core()
    except:
        return None

async def ollama_stream(message: str, model: str = None):
    """Ollama'ya streaming istek gönder"""
    core = get_core()
    if core and core.model_router:
        if not model:
            model = core.model_router.select_model(message)
        ollama_url = core.model_router.ollama_url
    else:
        model = model or os.getenv("DEFAULT_MODEL", "gulmzcetiner:latest")
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    def _clean_url(url: str) -> str:
        u = (url or "http://localhost:11434").strip().rstrip("/")
        if u.endswith("/api/chat"):
            u = u[:-9]
        elif u.endswith("/api/generate"):
            u = u[:-13]
        return u.rstrip("/")

    target_url = f"{_clean_url(ollama_url)}/api/chat"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                target_url,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": message}],
                    "stream": True
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"Ollama streaming hatası: {e}")
        yield f"Hata: {e}"

@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket ile streaming sohbet"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            message = msg.get("message", "")
            model = msg.get("model")

            if not message:
                await websocket.send_json({"type": "error", "content": "Mesaj boş olamaz"})
                continue

            await websocket.send_json({"type": "start", "content": ""})

            full_response = ""
            async for token in ollama_stream(message, model):
                full_response += token
                await websocket.send_json({"type": "token", "content": token})

            await websocket.send_json({"type": "done", "content": full_response})

    except WebSocketDisconnect:
        logger.info("WebSocket bağlantısı kesildi")
    except Exception as e:
        logger.error(f"WebSocket hatası: {e}")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except:
            pass

@router.post("/")
async def http_chat(msg: ChatMessage):
    """HTTP ile sohbet — CodeS kademeleri codes_router'a yönlendirilir."""
    model_choice = (msg.model or "").strip()

    # 1) Ticari CodeS kademesi → codeS router (sınıflandırma + fallback zinciri)
    if model_choice and is_codes_tier(model_choice):
        if msg.stream:
            return StreamingResponse(
                _codes_sse(msg.message, model_choice),
                media_type="text/event-stream",
            )
        result = await run_in_threadpool(
            lambda: get_codes_router().chat(msg.message, tier=model_choice)
        )
        if result.get("success"):
            thinking = result.get("thinking", "") or ""
            return {
                "response": result.get("response", ""),
                "thinking": thinking,
                "tool_calls": [],
                "thoughts": [thinking] if thinking else [],
                "model": result.get("model"),
                "tier": result.get("tier"),
                "tier_label": result.get("tier_label"),
                "routing": result.get("routing"),
                "success": True,
            }
        return {
            "response": "",
            "error": result.get("error", ""),
            "tool_calls": [],
            "thoughts": [],
            "success": False,
        }

    # 2) Açık geliştirici model adı verilmişse doğrudan ona git
    if model_choice and msg.stream:
        return StreamingResponse(
            _direct_sse(msg.message, model_choice),
            media_type="text/event-stream",
        )

    core = get_core()
    if core:
        result = core.process_message(msg.message, session_id=msg.session_id)
        return {
            "response": result.get("response", ""),
            "tool_calls": result.get("tool_calls", []),
            "thoughts": result.get("thoughts", [])
        }

    # Fallback: doğrudan Ollama'ya bağlan
    full_response = ""
    async for token in ollama_stream(msg.message, msg.model):
        full_response += token

    return {"response": full_response, "tool_calls": [], "thoughts": []}

@router.get("/models")
async def list_models():
    """Kullanılabilir modelleri listele"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"models": models}
    except:
        pass
    return {"models": []}

class SummarizeRequest(BaseModel):
    text: str
    level: str = "normal"

@router.post("/summarize")
async def summarize(msg: SummarizeRequest):
    """Metni özetle"""
    try:
        from conversation_summarizer import ConversationSummarizer
        summarizer = ConversationSummarizer()
    except:
        return {"success": False, "error": "Summarizer yüklü değil"}

    if not msg.text:
        return {"success": False, "error": "text gerekli"}

    try:
        messages = [{"role": "user", "content": msg.text}]
        summary = summarizer.summarize("default", messages, level=msg.level)
        return {
            "success": True,
            "summary": summary.to_dict() if hasattr(summary, 'to_dict') else str(summary)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
