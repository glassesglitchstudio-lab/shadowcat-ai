from fastapi import APIRouter
import psutil
import platform
from datetime import datetime

router = APIRouter()

@router.get("/status")
async def system_status():
    """Sistem durumu"""
    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "status": "online",
        "platform": platform.system(),
        "python": platform.python_version(),
        "cpu_percent": cpu,
        "memory": {
            "total_gb": round(memory.total / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "percent": memory.percent
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "percent": round(disk.percent, 1)
        },
        "uptime": datetime.now().isoformat()
    }

@router.get("/health")
async def health_check():
    """Sağlık kontrolü"""
    checks = {"core": False, "ollama": False, "memory": False}

    try:
        from shadowcat_core import get_core
        c = get_core()
        checks["core"] = True
    except:
        pass

    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        checks["ollama"] = r.status_code == 200
    except:
        pass

    try:
        from obsidian_memory import get_obsidian_memory
        m = get_obsidian_memory()
        checks["memory"] = True
    except:
        pass

    all_ok = all(checks.values())
    return {"status": "healthy" if all_ok else "degraded", "checks": checks}

@router.get("/core")
async def core_status():
    """Core modül durumu"""
    try:
        from shadowcat_core import get_core
        c = get_core()
        s = c.get_status()
        return {
            "version": s.get("version", "unknown"),
            "modules": s.get("modules", {}),
            "tools": s.get("stats", {}).get("tools_available", 0),
            "encrypted_models": s.get("stats", {}).get("encrypted_models", 0)
        }
    except Exception as e:
        return {"error": str(e)}
