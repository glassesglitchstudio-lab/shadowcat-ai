"""
shadowcat/model_hub.py
HuggingFace model kesfi + indirme (LM Studio "kitaplik" ozelliginin sadelestirilmis hali).
- Sadece public modeller (token gerektirmez)
- GGUF odakli filtre (LM Studio kullanicilari icin ana format)
- Turkce oncelikli siralama
- Indirilen dosyalarin varsayilan konumu: H:\\Drive'im\\Models\\
  (kullanici Settings'ten kendi yolunu secebilir)
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Body
from huggingface_hub import HfApi, snapshot_download, hf_hub_download
from huggingface_hub.utils import HfHubHTTPError

# ---------- Model dizini kaynaklari (oncelik sirasi) ----------
# 1) ortam degiskeni SHADOWCAT_MODELS_DIR
# 2) ~/.shadowcat/config.json icindeki models_dir
# 3) fallback: H:\\Drive'im\\Models
DEFAULT_MODELS_DIR = Path(r"H:\Drive'ım\Models")
CONFIG_PATH = Path(os.environ.get("SHADOWCAT_CONFIG", Path.home() / ".shadowcat" / "config.json"))


def get_models_dir() -> Path:
    """Kullanici tarafindan ayarlanmis model dizinini dondur."""
    env = os.environ.get("SHADOWCAT_MODELS_DIR")
    if env:
        p = Path(env).expanduser()
        if p.exists() or _is_creatable(p):
            return p
    cfg = _load_config()
    if cfg.get("models_dir"):
        p = Path(cfg["models_dir"]).expanduser()
        if p.exists() or _is_creatable(p):
            return p
    # fallback: H:\Drive'im\Models varsa orayi kullan, yoksa yine de orayi dondur
    # (UI tarafinda kullanici degistirene kadar)
    if DEFAULT_MODELS_DIR.exists():
        return DEFAULT_MODELS_DIR
    return DEFAULT_MODELS_DIR


def _is_creatable(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def _load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

# Indirme durumu (basit bellek ici)
_DOWNLOADS: dict[str, dict] = {}
_DOWNLOADS_LOCK = threading.Lock()

# Arama icin oncelikli Turkce modeller (siralama ipucu)
TURKISH_HINTS = (
    "turkish", "trendyol", "turkcell", "cosmos", "kumru", "wiroai",
    "gulmezcetiner", "bert-turkish", "electra-turkish",
)


@dataclass
class ModelInfo:
    id: str
    downloads: int
    likes: int
    last_modified: Optional[str]
    gguf_files: list[str] = field(default_factory=list)
    size_mb: Optional[int] = None
    is_turkish: bool = False

    def to_dict(self):
        return asdict(self)


def _api() -> HfApi:
    return HfApi()


def _has_gguf(repo_info) -> list[str]:
    """Repo'daki .gguf dosyalarini listele (boyut olmadan, hizli)."""
    try:
        files = _api().list_repo_files(repo_info.id, repo_type="model")
        return sorted(f for f in files if f.lower().endswith(".gguf"))
    except Exception:
        return []


def search_models(query: str = "", limit: int = 30, gguf_only: bool = True) -> list[ModelInfo]:
    """HuggingFace'te model ara. Turkce oncelikli siralanir."""
    api = _api()
    # filter="gguf" HuggingFace tarafinda zaten filtreliyor
    models = api.list_models(
        search=query or None,
        filter="gguf" if gguf_only else None,
        sort="downloads",
        limit=limit * 3,  # fazla cekip sonra filtreliyoruz
    )

    out: list[ModelInfo] = []
    for m in models:
        try:
            ggufs = _has_gguf(m)
            if gguf_only and not ggufs:
                continue
            is_tr = any(h in (m.id or "").lower() for h in TURKISH_HINTS) or any(
                h in (getattr(m, "pipeline_tag", "") or "").lower() for h in TURKISH_HINTS
            )
            out.append(ModelInfo(
                id=m.id,
                downloads=m.downloads or 0,
                likes=m.likes or 0,
                last_modified=str(m.last_modified) if m.last_modified else None,
                gguf_files=ggufs[:5],  # UI icin ilk 5
                is_turkish=is_tr,
            ))
            if len(out) >= limit:
                break
        except Exception:
            continue

    # Turkce olanlari uste al
    out.sort(key=lambda x: (not x.is_turkish, -x.downloads))
    return out


def get_model_detail(model_id: str) -> dict:
    """Tek bir modelin tum GGUF dosyalarini boyutlariyla listele."""
    api = _api()
    try:
        info = api.model_info(model_id, files_metadata=True)
    except HfHubHTTPError as e:
        raise HTTPException(404, f"Model bulunamadi: {e}")

    files = []
    for f in (info.siblings or []):
        if f.rfilename and f.rfilename.lower().endswith(".gguf"):
            size_mb = round((f.size or 0) / 1e6, 1) if f.size else None
            files.append({"name": f.rfilename, "size_mb": size_mb})
    return {
        "id": model_id,
        "downloads": info.downloads or 0,
        "likes": info.likes or 0,
        "gguf_files": files,
    }


def _do_download(download_id: str, model_id: str, filename: Optional[str], dest_dir: Path):
    """Arka planda calisan indirme islemi (thread ile)."""
    try:
        with _DOWNLOADS_LOCK:
            _DOWNLOADS[download_id] = {
                "id": download_id, "model": model_id, "filename": filename,
                "status": "downloading", "progress": 0, "error": None,
                "started": time.time(),
            }
        dest_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            # Tek dosya
            local = hf_hub_download(
                repo_id=model_id, filename=filename,
                local_dir=str(dest_dir), local_dir_use_symlinks=False,
            )
        else:
            # Tum GGUF dosyalarini cek
            local = snapshot_download(
                repo_id=model_id,
                allow_patterns=["*.gguf", "*.md", "*.json"],
                local_dir=str(dest_dir), local_dir_use_symlinks=False,
            )
        with _DOWNLOADS_LOCK:
            _DOWNLOADS[download_id]["status"] = "done"
            _DOWNLOADS[download_id]["local_path"] = local
            _DOWNLOADS[download_id]["finished"] = time.time()
    except Exception as e:
        with _DOWNLOADS_LOCK:
            _DOWNLOADS[download_id]["status"] = "error"
            _DOWNLOADS[download_id]["error"] = str(e)


def list_local_models() -> list[dict]:
    """Yerel indirilen GGUF dosyalarini listele."""
    out = []
    base = get_models_dir()
    if not base.exists():
        return out
    for gguf in base.rglob("*.gguf"):
        out.append({
            "name": gguf.name,
            "path": str(gguf),
            "size_mb": round(gguf.stat().st_size / 1e6, 1),
            "parent": gguf.parent.name,
        })
    return sorted(out, key=lambda x: x["path"])


# FastAPI router
router = APIRouter(prefix="/hub", tags=["model-hub"])


@router.get("/api/settings")
def api_get_settings():
    """JSON API (UI tarafi icin)."""
    d = get_models_dir()
    return {
        "ok": True,
        "models_dir": str(d),
        "models_dir_exists": d.exists(),
        "default_dir": str(DEFAULT_MODELS_DIR),
        "config_path": str(CONFIG_PATH),
    }


@router.post("/api/settings")
def api_set_settings(body: dict = Body(...)):
    """JSON API - model dizinini kaydet."""
    new_dir = (body.get("models_dir") or "").strip()
    if not new_dir:
        raise HTTPException(400, "models_dir gerekli")
    p = Path(new_dir).expanduser()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(400, f"Klasör oluşturulamadı: {e}")
    cfg = _load_config()
    cfg["models_dir"] = str(p)
    _save_config(cfg)
    return {"ok": True, "models_dir": str(p), "exists": p.exists()}


@router.get("/search")
def api_search(q: str = "", limit: int = 30, gguf_only: bool = True):
    """HuggingFace'te model ara."""
    try:
        results = search_models(q, limit=limit, gguf_only=gguf_only)
        return {"ok": True, "count": len(results), "models": [m.to_dict() for m in results]}
    except Exception as e:
        raise HTTPException(500, f"Arama hatasi: {e}")


@router.get("/model/{model_id:path}")
def api_model_detail(model_id: str):
    return get_model_detail(model_id)


@router.post("/download")
def api_download(body: dict, bg: BackgroundTasks):
    """Model indirmeyi baslat. Filename belirtilirse sadece o dosya, yoksa tum GGUF'lar."""
    model_id = body.get("model_id", "").strip()
    filename = body.get("filename")  # opsiyonel
    if not model_id:
        raise HTTPException(400, "model_id gerekli")

    download_id = uuid.uuid4().hex[:12]
    # Modelin yerel klasoru (kullanici tarafindan ayarlanmis dizin)
    safe_name = model_id.replace("/", "_").replace("\\", "_")
    dest = get_models_dir() / safe_name
    bg.add_task(_do_download, download_id, model_id, filename, dest)

    with _DOWNLOADS_LOCK:
        _DOWNLOADS[download_id] = {
            "id": download_id, "model": model_id, "filename": filename,
            "status": "queued", "progress": 0, "error": None,
        }
    return {"ok": True, "download_id": download_id, "dest": str(dest)}


@router.get("/downloads")
def api_downloads():
    with _DOWNLOADS_LOCK:
        return {"ok": True, "downloads": list(_DOWNLOADS.values())}


@router.get("/local")
def api_local():
    return {"ok": True, "models": list_local_models()}


# ============================================================================
# Server-side Settings sayfasi (JS bagimsiz, Chrome extension yutamaz)
# ============================================================================
from fastapi.responses import HTMLResponse
from urllib.parse import quote


SETTINGS_HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>ShadowCat - Ayarlar</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  /* ---------- Design tokens ---------- */
  :root {
    --bg-0: #0a0c1a;
    --bg-1: #0f1226;
    --bg-2: #141833;
    --bg-3: #1c2147;
    --line: rgba(123, 107, 240, 0.12);
    --line-strong: rgba(123, 107, 240, 0.22);
    --text-0: #f5f7fa;
    --text-1: #c4c9d1;
    --text-2: #8a93a0;
    --text-3: #5b6470;
    --accent: #7B6BF0;
    --accent-hover: #9d8df5;
    --accent-2: #A855F7;
    --accent-blue: #5B8DEF;
    --accent-dim: rgba(123, 107, 240, 0.18);
    --accent-line: rgba(123, 107, 240, 0.5);
    --accent-glow: rgba(123, 107, 240, 0.35);
    --ok: #4ade80;
    --err: #f87171;
    --radius: 10px;
    --radius-lg: 14px;
    --shadow-card: 0 1px 0 rgba(255, 255, 255, 0.04) inset,
                   0 12px 32px -16px rgba(0, 0, 0, 0.6),
                   0 0 0 1px rgba(123, 107, 240, 0.06);
    --shadow-glow: 0 0 24px -2px var(--accent-glow);
    --t: 220ms cubic-bezier(.2, .8, .2, 1);
  }

  /* ---------- Reset ---------- */
  *, *::before, *::after { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg-0);
    color: var(--text-1);
    font-size: 14px;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    min-height: 100vh;
    background-image:
      radial-gradient(1400px 700px at 90% -20%, rgba(168, 85, 247, 0.18), transparent 60%),
      radial-gradient(1100px 600px at 5% 110%, rgba(91, 141, 239, 0.16), transparent 60%),
      radial-gradient(800px 400px at 50% 50%, rgba(123, 107, 240, 0.06), transparent 70%);
  }

  /* ---------- Layout ---------- */
  .shell { max-width: 760px; margin: 0 auto; padding: 56px 24px 80px; }

  /* ---------- Header ---------- */
  .topbar {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 36px;
  }
  .brand { display: flex; align-items: center; gap: 12px; }
  .brand-mark {
    width: 38px; height: 38px; border-radius: 10px;
    background: var(--bg-0);
    box-shadow: 0 0 0 1px var(--line-strong),
                0 8px 20px -8px rgba(0, 0, 0, 0.5);
    display: grid; place-items: center;
    overflow: hidden;
  }
  .brand-mark img { display: block; width: 26px; height: 26px; }
  .brand-text { display: flex; flex-direction: column; line-height: 1.2; }
  .brand-name { font-size: 15px; font-weight: 600; color: var(--text-0); letter-spacing: -.01em; }
  .brand-sub  { font-size: 11px; color: var(--text-3); font-family: 'Geist Mono', monospace;
                letter-spacing: .02em; margin-top: 2px; }
  .back-link {
    display: inline-flex; align-items: center; gap: 6px;
    color: var(--text-2); text-decoration: none; font-size: 13px; font-weight: 500;
    padding: 7px 12px; border-radius: 8px;
    border: 1px solid var(--line);
    background: var(--bg-1);
    transition: all var(--t);
  }
  .back-link:hover { color: var(--text-0); border-color: var(--line-strong); background: var(--bg-2); }
  .back-link svg { width: 13px; height: 13px; }

  /* ---------- Page heading ---------- */
  .page-head { margin-bottom: 28px; }
  .page-title { font-size: 28px; font-weight: 700; color: var(--text-0);
                letter-spacing: -.02em; margin: 0 0 8px; }
  .page-sub   { color: var(--text-2); font-size: 14px; margin: 0; max-width: 560px; }

  /* ---------- Section card ---------- */
  .card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    overflow: hidden;
    box-shadow: var(--shadow-card);
  }
  .card + .card { margin-top: 18px; }
  .card {
    animation: cardIn .45s cubic-bezier(.2, .8, .2, 1) backwards;
  }
  .card:nth-of-type(1) { animation-delay: 0ms; }
  .card:nth-of-type(2) { animation-delay: 100ms; }
  .card:nth-of-type(3) { animation-delay: 200ms; }
  @keyframes cardIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: none; }
  }
  .card-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 18px 22px;
    border-bottom: 1px solid var(--line);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.015), transparent);
  }
  .card-head-left { display: flex; align-items: center; gap: 10px; }
  .card-icon {
    width: 28px; height: 28px; border-radius: 7px;
    background: var(--accent-dim); color: var(--accent);
    display: grid; place-items: center;
    font-size: 14px;
    box-shadow: 0 0 0 1px var(--accent-line), 0 0 12px -4px var(--accent-glow);
  }
  .card-title { font-size: 14px; font-weight: 600; color: var(--text-0); letter-spacing: -.01em; }
  .card-body { padding: 22px; }

  /* ---------- Status pill ---------- */
  .pill {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 5px 10px; border-radius: 999px;
    font-family: 'Geist Mono', monospace; font-size: 11px;
    border: 1px solid var(--line);
    color: var(--text-2);
    background: var(--bg-2);
  }
  .pill-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-3); }
  .pill.ok   .pill-dot { background: var(--ok); box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.15); }
  .pill.ok   { color: var(--ok); border-color: rgba(74, 222, 128, 0.3); background: rgba(74, 222, 128, 0.08); }
  .pill.err  .pill-dot { background: var(--err); }
  .pill.err  { color: var(--err); border-color: rgba(248, 113, 113, 0.3); background: rgba(248, 113, 113, 0.08); }

  /* ---------- Field ---------- */
  .field { margin-bottom: 18px; }
  .field-label {
    display: block; font-size: 12px; font-weight: 600;
    color: var(--text-1); margin-bottom: 6px;
    letter-spacing: -.005em;
  }
  .field-hint { font-size: 12.5px; color: var(--text-2); margin-bottom: 10px; line-height: 1.5; }
  .input {
    width: 100%; padding: 11px 14px;
    background: var(--bg-0);
    border: 1px solid var(--line-strong);
    border-radius: var(--radius);
    color: var(--text-0);
    font-size: 13px;
    font-family: 'Geist Mono', monospace;
    outline: none;
    transition: border-color var(--t), box-shadow var(--t);
  }
  .input::placeholder { color: var(--text-3); }
  .input:hover { border-color: rgba(255, 255, 255, 0.22); }
  .input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-dim), 0 0 16px -4px var(--accent-glow);
  }

  /* ---------- Buttons ---------- */
  .actions {
    display: flex; gap: 10px; align-items: center;
    margin-top: 22px; padding-top: 20px;
    border-top: 1px solid var(--line);
  }
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 10px 16px; border-radius: 8px;
    font-family: inherit; font-size: 13px; font-weight: 500;
    border: 1px solid var(--line-strong);
    background: var(--bg-2); color: var(--text-1);
    cursor: pointer; text-decoration: none;
    transition: all var(--t);
    line-height: 1;
  }
  .btn:hover { color: var(--text-0); border-color: rgba(255, 255, 255, 0.28); background: var(--bg-3); }
  .btn:active { transform: translateY(1px); }
  .btn-primary {
    background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent) 50%, var(--accent-2) 100%);
    background-size: 200% 100%;
    color: #fff; border-color: transparent;
    font-weight: 600;
    box-shadow: 0 0 0 0 var(--accent-dim);
    position: relative; overflow: hidden;
  }
  .btn-primary::before {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(135deg, transparent 30%, rgba(255, 255, 255, 0.3) 50%, transparent 70%);
    transform: translateX(-100%);
    transition: transform .6s ease;
  }
  .btn-primary:hover::before { transform: translateX(100%); }
  .btn-primary:hover {
    background-position: 100% 0;
    box-shadow: 0 0 0 4px var(--accent-dim), var(--shadow-glow);
    transform: translateY(-1px);
  }
  .btn-ghost { background: transparent; border-color: transparent; color: var(--text-2); }
  .btn-ghost:hover { background: var(--bg-2); color: var(--text-1); border-color: transparent; }
  .btn-danger {
    color: var(--text-2); border-color: var(--line);
    background: transparent;
  }
  .btn-danger:hover {
    color: var(--err); border-color: rgba(248, 113, 113, 0.4);
    background: rgba(248, 113, 113, 0.06);
  }

  /* ---------- Models list ---------- */
  .models-list { display: flex; flex-direction: column; gap: 8px; }
  .model-row {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 14px; align-items: center;
    padding: 12px 14px;
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    transition: all var(--t);
    position: relative; overflow: hidden;
  }
  .model-row::before {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(115deg, transparent 30%, rgba(123, 107, 240, 0.15) 50%, transparent 70%);
    transform: translateX(-100%);
    transition: transform .7s ease;
    pointer-events: none;
  }
  .model-row:hover { border-color: var(--accent-line); background: var(--bg-3); transform: translateX(2px); }
  .model-row:hover::before { transform: translateX(100%); }
  .model-glyph {
    width: 32px; height: 32px; border-radius: 8px;
    background: linear-gradient(135deg, rgba(123, 107, 240, 0.20), rgba(168, 85, 247, 0.08));
    border: 1px solid var(--accent-line);
    color: var(--accent);
    display: grid; place-items: center;
    font-family: 'Geist Mono', monospace; font-weight: 600; font-size: 12px;
  }
  .model-meta { min-width: 0; }
  .model-name {
    font-size: 13.5px; font-weight: 500; color: var(--text-0);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-family: 'Geist Mono', monospace;
  }
  .model-sub { font-size: 11.5px; color: var(--text-2); margin-top: 2px; display: flex; gap: 8px; align-items: center; }
  .model-sub .dot { color: var(--text-3); }
  .model-size {
    font-family: 'Geist Mono', monospace; font-size: 12px;
    color: var(--text-1); font-weight: 500;
    padding: 4px 9px;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: 6px;
  }
  .models-empty {
    padding: 32px 20px; text-align: center;
    border: 1px dashed var(--line-strong);
    border-radius: var(--radius);
    color: var(--text-2);
  }
  .models-empty strong { color: var(--text-0); font-weight: 600; display: block; margin-bottom: 4px; }
  .list-foot {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: 14px; padding-top: 14px;
    border-top: 1px solid var(--line);
    font-size: 11.5px; color: var(--text-2);
    font-family: 'Geist Mono', monospace;
  }
  .list-foot a {
    color: var(--accent); text-decoration: none; font-weight: 500;
  }
  .list-foot a:hover { text-decoration: underline; }

  /* ---------- Status banner ---------- */
  .banner {
    margin-bottom: 18px; padding: 12px 14px;
    border-radius: var(--radius);
    font-size: 13px;
    display: flex; align-items: flex-start; gap: 10px;
    border: 1px solid var(--line);
    background: var(--bg-2);
  }
  .banner .icon {
    flex-shrink: 0; width: 18px; height: 18px;
    display: grid; place-items: center; border-radius: 5px;
    font-size: 11px; font-weight: 700;
  }
  .banner.ok  { background: rgba(74, 222, 128, 0.06); border-color: rgba(74, 222, 128, 0.3); color: var(--ok); }
  .banner.ok .icon  { background: rgba(74, 222, 128, 0.18); }
  .banner.err { background: rgba(248, 113, 113, 0.06); border-color: rgba(248, 113, 113, 0.3); color: var(--err); }
  .banner.err .icon { background: rgba(248, 113, 113, 0.18); }
  .banner.info { color: var(--text-1); }
  .banner.info .icon { background: var(--bg-3); color: var(--text-1); }
  .banner code {
    font-family: 'Geist Mono', monospace; font-size: 12px;
    background: rgba(0, 0, 0, 0.35); padding: 2px 6px; border-radius: 4px;
    color: var(--text-0);
  }

  /* ---------- Responsive ---------- */
  @media (max-width: 600px) {
    .shell { padding: 32px 16px 60px; }
    .page-title { font-size: 22px; }
    .card-head, .card-body { padding: 16px; }
    .actions { flex-wrap: wrap; }
    .btn { flex: 1; justify-content: center; }
    .topbar { flex-direction: column; gap: 16px; align-items: flex-start; }
  }
</style>
</head>
<body>
  <div class="shell">
    <div class="topbar">
      <div class="brand">
        <div class="brand-mark"><img src="/static/logo.svg" alt="ShadowCat" width="22" height="22"></div>
        <div class="brand-text">
          <div class="brand-name">ShadowCat</div>
          <div class="brand-sub">studio.local / settings</div>
        </div>
      </div>
      <a href="/app" class="back-link">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
        Studio'ya dön
      </a>
    </div>

    <div class="page-head">
      <h1 class="page-title">Ayarlar</h1>
      <p class="page-sub">Model dizinini istediğin gibi değiştirebilirsin. LM Studio gibi <code style="font-family:'Geist Mono',monospace;font-size:12px;background:var(--bg-2);padding:2px 6px;border-radius:4px;color:var(--text-1)">C:\</code>, <code style="font-family:'Geist Mono',monospace;font-size:12px;background:var(--bg-2);padding:2px 6px;border-radius:4px;color:var(--text-1)">D:\</code>, USB tüm yollar geçerli.</p>
    </div>

    {status_banner}

    <!-- Models dir card -->
    <section class="card">
      <div class="card-head">
        <div class="card-head-left">
          <div class="card-icon">&#x1F4C1;</div>
          <div class="card-title">Model dizini</div>
        </div>
        <span class="pill {dir_pill_kind}"><span class="pill-dot"></span>{dir_pill_label}</span>
      </div>
      <div class="card-body">
        <form method="post" action="/hub/settings/save">
          <div class="field">
            <div class="field-hint">GGUF dosyalarının bulunduğu klasör. Bu klasördeki <code>.gguf</code> dosyaları otomatik listelenir.</div>
            <label class="field-label" for="models_dir">Yol</label>
            <input class="input" type="text" id="models_dir" name="models_dir"
                   value="{current_dir}" placeholder="örn. C:\Users\Ben\Models"
                   spellcheck="false" autocomplete="off" required>
          </div>
          <div class="actions">
            <button type="submit" class="btn btn-primary">Kaydet</button>
            <button type="submit" formaction="/hub/settings/reset" formmethod="post" class="btn btn-danger"
                    onclick="return confirm('Varsayılan dizine dönmek istediğine emin misin?')">
              Varsayılana dön
            </button>
            <div style="flex:1"></div>
            <a href="/app" class="btn btn-ghost">İptal</a>
          </div>
        </form>
      </div>
    </section>

    <!-- Local models card -->
    <section class="card">
      <div class="card-head">
        <div class="card-head-left">
          <div class="card-icon">&#x1F4E6;</div>
          <div class="card-title">Mevcut dizindeki modeller</div>
        </div>
        <span class="pill"><span class="pill-dot"></span>{local_count} model</span>
      </div>
      <div class="card-body">
        {local_items}
        <div class="list-foot">
          <span>{local_summary}</span>
          <a href="/app#hub">Hub'dan model indir &rarr;</a>
        </div>
      </div>
    </section>
  </div>
</body>
</html>
"""


def _build_settings_html(status: str = "", status_kind: str = "info", saved_dir: str = "") -> str:
    current = get_models_dir()
    local = list_local_models()
    total_mb = sum(m.get("size_mb", 0) for m in local)

    # Local models list
    if local:
        rows = []
        for m in local:
            name = m["name"]
            parent = m.get("parent") or ""
            size_mb = m.get("size_mb", 0)
            # Glyph: ilk 2 anlamli karakter
            stem = name.rsplit(".", 1)[0]
            glyph_src = stem.replace("-", "").replace("_", "")
            glyph = (glyph_src[:2] or "??").upper()
            size_gb = size_mb / 1024.0
            if size_gb >= 1:
                size_str = f"{size_gb:.2f} GB"
            else:
                size_str = f"{size_mb:.0f} MB"
            rows.append(
                f'<div class="model-row">'
                f'  <div class="model-glyph">{html_escape(glyph)}</div>'
                f'  <div class="model-meta">'
                f'    <div class="model-name">{html_escape(name)}</div>'
                f'    <div class="model-sub">{html_escape(parent) if parent else "root"}</div>'
                f'  </div>'
                f'  <div class="model-size">{size_str}</div>'
                f'</div>'
            )
        items_html = '<div class="models-list">' + "".join(rows) + "</div>"
        summary = f"Toplam {total_mb/1024:.2f} GB kullanılıyor"
    else:
        items_html = (
            '<div class="models-empty">'
            '<strong>Henüz model yok</strong>'
            'Hub sekmesinden GGUF modeli indir, burada listelensin.'
            "</div>"
        )
        summary = "0 MB"

    # Dir pill (kart basliginda durum)
    if current.exists():
        dir_pill_kind = "ok"
        dir_pill_label = "Aktif"
    else:
        dir_pill_kind = "err"
        dir_pill_label = "Klasör yok"

    # Status banner (kart ustunde)
    if status:
        if status_kind == "ok":
            status_banner = f'<div class="banner ok"><div class="icon">&#10003;</div><div>{status}</div></div>'
        elif status_kind == "err":
            status_banner = f'<div class="banner err"><div class="icon">!</div><div>{status}</div></div>'
        else:
            status_banner = f'<div class="banner info"><div class="icon">i</div><div>{status}</div></div>'
    else:
        if current.exists():
            status_banner = (
                f'<div class="banner ok">'
                f'<div class="icon">&#10003;</div>'
                f'<div>Aktif dizin: <code>{html_escape(str(current))}</code></div>'
                f"</div>"
            )
        else:
            status_banner = (
                f'<div class="banner info">'
                f'<div class="icon">i</div>'
                f'<div>Dizin mevcut değil. Kaydet dediğinde otomatik oluşturulur: <code>{html_escape(str(current))}</code></div>'
                f"</div>"
            )

    # .replace() kullan: CSS'teki {} Python str.format ile cakismasin
    return (SETTINGS_HTML
            .replace("{current_dir}", html_escape(str(current)))
            .replace("{dir_pill_kind}", dir_pill_kind)
            .replace("{dir_pill_label}", dir_pill_label)
            .replace("{status_banner}", status_banner)
            .replace("{local_items}", items_html)
            .replace("{local_summary}", summary)
            .replace("{local_count}", str(len(local))))


def html_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


@router.get("/settings", response_class=HTMLResponse)
def page_settings():
    """Server-side settings sayfasi - JS bagimsiz, form submit ile calisir."""
    return _build_settings_html()


@router.post("/settings/save", response_class=HTMLResponse)
def page_settings_save(models_dir: str = ""):
    """Form submit handler - config'e yazar ve sayfayi yeniden render eder."""
    models_dir = (models_dir or "").strip()
    if not models_dir:
        return _build_settings_html("models_dir boş olamaz", "err")
    p = Path(models_dir).expanduser()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return _build_settings_html(f"Klasör oluşturulamadı: {e}", "err")
    cfg = _load_config()
    cfg["models_dir"] = str(p)
    _save_config(cfg)
    return _build_settings_html(f"Kaydedildi: {p} - Sayfayi yenileyebilir veya Studio'ya dönebilirsin.", "ok")


@router.post("/settings/reset", response_class=HTMLResponse)
def page_settings_reset():
    """Config'den models_dir'i siler, default'a doner."""
    cfg = _load_config()
    if "models_dir" in cfg:
        del cfg["models_dir"]
    _save_config(cfg)
    return _build_settings_html(f"Varsayılan dizine dönüldü: {DEFAULT_MODELS_DIR}", "ok")
