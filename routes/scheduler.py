from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger("routes.scheduler")
router = APIRouter()

def get_scheduler():
    try:
        from task_scheduler import TaskScheduler
        return TaskScheduler()
    except (ImportError, Exception) as e:
        logger.warning(f"Scheduler yüklenemedi: {e}")
        return None

class TaskCreate(BaseModel):
    name: str
    command: str
    task_type: str = "COMMAND"
    repeat: str = "ONCE"
    interval: Optional[int] = None
    description: Optional[str] = ""

@router.get("/tasks")
async def list_tasks():
    """Tüm görevleri listele"""
    scheduler = get_scheduler()
    if not scheduler:
        return {"tasks": [], "error": "Scheduler mevcut değil"}
    try:
        tasks = scheduler.list_tasks()
        return {"tasks": tasks}
    except Exception as e:
        return {"tasks": [], "error": str(e)}

@router.post("/tasks")
async def create_task(task: TaskCreate):
    """Yeni görev oluştur"""
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler mevcut değil")
    try:
        result = scheduler.create_task(
            name=task.name,
            command=task.command,
            task_type=task.task_type,
            repeat=task.repeat,
            interval=task.interval,
            description=task.description
        )
        return {"message": "Görev oluşturuldu", "task": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Görevi sil"""
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler mevcut değil")
    try:
        scheduler.delete_task(task_id)
        return {"message": f"Görev {task_id} silindi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/run")
async def run_task(task_id: str):
    """Görevi hemen çalıştır"""
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler mevcut değil")
    try:
        scheduler.run_now(task_id)
        return {"message": f"Görev {task_id} çalıştırıldı"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """Görevi durdur"""
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler mevcut değil")
    try:
        scheduler.pause_task(task_id)
        return {"message": f"Görev {task_id} durduruldu"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    """Görevi devam ettir"""
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler mevcut değil")
    try:
        scheduler.resume_task(task_id)
        return {"message": f"Görev {task_id} devam ettirildi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/delete")
async def delete_task_post(task_id: str):
    """Görevi sil (POST variant - Flask uyumluluk)"""
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler mevcut değil")
    try:
        scheduler.delete_task(task_id)
        return {"success": True, "message": f"Görev {task_id} silindi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Tek görev detayı"""
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler mevcut değil")
    try:
        task = scheduler.get_task(task_id)
        if task:
            return {"task": task.to_dict() if hasattr(task, 'to_dict') else task}
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    command: Optional[str] = None
    description: Optional[str] = None
    interval: Optional[int] = None

@router.put("/tasks/{task_id}")
async def update_task(task_id: str, updates: TaskUpdate):
    """Görevi güncelle"""
    scheduler = get_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler mevcut değil")
    try:
        update_data = {k: v for k, v in updates.dict().items() if v is not None}
        task = scheduler.update_task(task_id, **update_data)
        if task:
            return {"message": "Görev güncellendi", "task": task.to_dict() if hasattr(task, 'to_dict') else task}
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(task_id: Optional[str] = None, limit: int = 50):
    """Görev geçmişini listele"""
    scheduler = get_scheduler()
    if not scheduler:
        return {"history": []}
    try:
        history = scheduler.get_history(task_id=task_id, limit=limit)
        return {"history": history}
    except Exception as e:
        logger.warning(f"Geçmiş alınamadı: {e}")
        return {"history": []}

@router.get("/status")
async def scheduler_status():
    """Scheduler durumu"""
    scheduler = get_scheduler()
    if not scheduler:
        return {"available": False, "total_tasks": 0, "running": 0, "paused": 0}
    try:
        status = scheduler.get_status_summary()
        return {"available": True, **status}
    except Exception as e:
        logger.warning(f"Scheduler durumu alınamadı: {e}")
        return {"available": True, "total_tasks": 0, "running": 0, "paused": 0}
