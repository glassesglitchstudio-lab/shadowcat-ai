"""
Shadowcat - Görev Zamanlayıcı Modülü
Cron benzeri tek seferlik ve tekrarlayan görevleri yönetir
"""

import os
import json
import time
import uuid
import queue
import logging
import threading
import subprocess
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Desteklenen görev türleri"""
    COMMAND = "command"
    NOTIFICATION = "notification"
    API_CALL = "api_call"
    WEBHOOK = "webhook"
    PYTHON_FUNC = "python_func"


class TaskStatus(Enum):
    """Görev durumları"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class RecurrenceType(Enum):
    """Tekrarlama türleri"""
    ONCE = "once"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"
    CRON = "cron"


@dataclass
class ScheduledTask:
    """Tek bir zamanlanmış görev tanımı"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    task_type: TaskType = TaskType.COMMAND
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    scheduled_at: Optional[str] = None
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    max_runs: Optional[int] = None
    recurrence: RecurrenceType = RecurrenceType.ONCE
    recurrence_interval: Optional[int] = None
    cron_expression: Optional[str] = None

    # Görev yükü - türe göre farklı alanlar
    command: Optional[str] = None
    command_args: List[str] = field(default_factory=list)
    notification_title: Optional[str] = None
    notification_message: Optional[str] = None
    api_url: Optional[str] = None
    api_method: str = "GET"
    api_headers: Dict[str, str] = field(default_factory=dict)
    api_body: Optional[Dict[str, Any]] = None
    webhook_url: Optional[str] = None
    webhook_payload: Optional[Dict[str, Any]] = None
    python_func_name: Optional[str] = None
    python_func_args: List[Any] = field(default_factory=list)
    python_func_kwargs: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    tags: List[str] = field(default_factory=list)
    description: Optional[str] = None
    error_message: Optional[str] = None
    timeout: int = 60

    def to_dict(self) -> Dict[str, Any]:
        """JSON serileştirme için sözlüğe çevir"""
        result = asdict(self)
        result['task_type'] = self.task_type.value
        result['status'] = self.status.value
        result['recurrence'] = self.recurrence.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledTask':
        """Sözlükten ScheduledTask oluştur"""
        data = data.copy()
        data['task_type'] = TaskType(data['task_type'])
        data['status'] = TaskStatus(data['status'])
        data['recurrence'] = RecurrenceType(data['recurrence'])
        return cls(**data)

    @property
    def is_recurring(self) -> bool:
        return self.recurrence != RecurrenceType.ONCE

    @property
    def is_due(self) -> bool:
        if self.status in (TaskStatus.PAUSED, TaskStatus.CANCELLED, TaskStatus.COMPLETED):
            return False
        if self.next_run is None:
            return True
        return datetime.fromisoformat(self.next_run) <= datetime.now()

    def calculate_next_run(self) -> Optional[str]:
        """Bir sonraki çalışma zamanını hesapla"""
        if self.recurrence == RecurrenceType.ONCE:
            return None

        base = datetime.now()
        if self.recurrence == RecurrenceType.MINUTES:
            next_time = base + timedelta(minutes=self.recurrence_interval or 1)
        elif self.recurrence == RecurrenceType.HOURS:
            next_time = base + timedelta(hours=self.recurrence_interval or 1)
        elif self.recurrence == RecurrenceType.DAYS:
            next_time = base + timedelta(days=self.recurrence_interval or 1)
        elif self.recurrence == RecurrenceType.CRON:
            return self._resolve_cron()
        else:
            return None

        return next_time.isoformat()

    def _resolve_cron(self) -> Optional[str]:
        """CRON ifadesini çözümle (basit)"""
        if not self.cron_expression:
            return None
        parts = self.cron_expression.strip().split()
        if len(parts) < 5:
            logger.warning(f"Geçersiz CRON ifadesi: {self.cron_expression}")
            return None
        now = datetime.now()
        try:
            cron_minute = int(parts[0])
            cron_hour = int(parts[1])
            next_time = now.replace(hour=cron_hour, minute=cron_minute, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time.isoformat()
        except ValueError:
            logger.warning(f"CRON ayrıştırılamadı: {self.cron_expression}")
            return None


class TaskHistory:
    """Görev çalıştırma geçmişi kaydı"""

    def __init__(self, storage_dir: Path, max_entries: int = 1000):
        self.storage_dir = storage_dir
        self.max_entries = max_entries
        self.history_file = storage_dir / 'task_history.json'
        self._lock = threading.Lock()
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._entries = json.load(f)
            except:
                self._entries = []

    def _save(self):
        with self._lock:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._entries[-self.max_entries:], f, ensure_ascii=False, indent=2)

    def add_entry(self, task_id: str, task_name: str, status: str, output: Optional[str] = None, error: Optional[str] = None):
        """Geçmişe yeni kayıt ekle"""
        entry = {
            'task_id': task_id,
            'task_name': task_name,
            'status': status,
            'output': output,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]
        self._save()

    def get_history(self, task_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Görev geçmişini getir"""
        with self._lock:
            if task_id:
                entries = [e for e in self._entries if e['task_id'] == task_id]
            else:
                entries = list(self._entries)
        return entries[-limit:][::-1]

    def clear(self):
        with self._lock:
            self._entries = []
        self._save()


class TaskStore:
    """Görevlerin kalıcı JSON depolaması"""

    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'storage'
            )
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.tasks_file = self.storage_dir / 'tasks.json'
        self._lock = threading.Lock()
        self._tasks: Dict[str, ScheduledTask] = {}
        self._load()

    def _load(self):
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        task = ScheduledTask.from_dict(item)
                        self._tasks[task.id] = task
                logger.info(f"{len(self._tasks)} görev yüklendi")
            except Exception as e:
                logger.error(f"Görevler yüklenemedi: {e}")

    def _save(self):
        with self._lock:
            data = [task.to_dict() for task in self._tasks.values()]
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, task: ScheduledTask) -> ScheduledTask:
        with self._lock:
            self._tasks[task.id] = task
        self._save()
        return task

    def get(self, task_id: str) -> Optional[ScheduledTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task: ScheduledTask) -> bool:
        with self._lock:
            if task.id not in self._tasks:
                return False
            self._tasks[task.id] = task
        self._save()
        return True

    def delete(self, task_id: str) -> bool:
        with self._lock:
            if task_id not in self._tasks:
                return False
            del self._tasks[task_id]
        self._save()
        return True

    def list_all(self) -> List[ScheduledTask]:
        with self._lock:
            return list(self._tasks.values())

    def list_by_status(self, status: TaskStatus) -> List[ScheduledTask]:
        with self._lock:
            return [t for t in self._tasks.values() if t.status == status]

    def get_due_tasks(self) -> List[ScheduledTask]:
        """Zamanı gelmiş görevleri getir"""
        with self._lock:
            return [t for t in self._tasks.values() if t.is_due]


registered_functions: Dict[str, Callable] = {}

def register_function(name: str, func: Callable):
    """Zamanlanmış görevlerde kullanılmak üzere fonksiyon kaydet"""
    registered_functions[name] = func


class TaskScheduler:
    """
    Ana görev zamanlayıcı
    - Arka plan iş parçacığı ile sürekli kontrol
    - Çoklu görev türü desteği
    - Kalıcı depolama
    - Geçmiş kaydı
    """

    def __init__(self, storage_dir: str = None, check_interval: int = 5):
        self.store = TaskStore(storage_dir)
        self.history = TaskHistory(self.store.storage_dir)
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._event_queue: queue.Queue = queue.Queue()
        self._callbacks: List[Callable] = []

    def on_task_complete(self, callback: Callable):
        """Görev tamamlanma callback'i ekle"""
        self._callbacks.append(callback)

    def start(self):
        """Zamanlayıcıyı başlat - arka plan iş parçacığında çalışır"""
        if self._running:
            logger.warning("Zamanlayıcı zaten çalışıyor")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="TaskScheduler")
        self._thread.start()
        logger.info("Görev zamanlayıcı başlatıldı")

    def stop(self):
        """Zamanlayıcıyı durdur"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("Görev zamanlayıcı durduruldu")

    def _loop(self):
        """Ana kontrol döngüsü"""
        while self._running:
            try:
                self._check_due_tasks()
                self._process_event_queue()
            except Exception as e:
                logger.error(f"Zamanlayıcı döngü hatası: {e}")
            time.sleep(self.check_interval)

    def _check_due_tasks(self):
        """Zamanı gelmiş görevleri kontrol et ve çalıştır"""
        for task in self.store.get_due_tasks():
            if task.status == TaskStatus.PAUSED:
                continue
            self._execute_task(task)

    def _process_event_queue(self):
        """Kuyruktaki olayları işle"""
        try:
            while True:
                event = self._event_queue.get_nowait()
                task_id = event.get('task_id')
                action = event.get('action')
                if task_id and action == 'execute':
                    task = self.store.get(task_id)
                    if task:
                        self._execute_task(task)
        except queue.Empty:
            pass

    def _execute_task(self, task: ScheduledTask):
        """Görevi çalıştır"""
        if task.status == TaskStatus.PAUSED:
            return

        old_status = task.status
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now().isoformat()
        self.store.update(task)

        output = None
        error = None
        success = False

        try:
            if task.task_type == TaskType.COMMAND:
                output = self._run_command(task)
            elif task.task_type == TaskType.NOTIFICATION:
                output = self._send_notification(task)
            elif task.task_type == TaskType.API_CALL:
                output = self._make_api_call(task)
            elif task.task_type == TaskType.WEBHOOK:
                output = self._trigger_webhook(task)
            elif task.task_type == TaskType.PYTHON_FUNC:
                output = self._execute_python_func(task)

            success = True
            logger.info(f"Görev başarılı: {task.name} ({task.id})")

        except Exception as e:
            error = str(e)
            task.error_message = error
            logger.error(f"Görev hatası: {task.name} - {error}")

        task.run_count += 1

        if error:
            task.status = TaskStatus.FAILED
        elif task.is_recurring:
            if task.max_runs and task.run_count >= task.max_runs:
                task.status = TaskStatus.COMPLETED
            else:
                task.status = TaskStatus.PENDING
                task.next_run = task.calculate_next_run()
        else:
            task.status = TaskStatus.COMPLETED

        self.store.update(task)
        self.history.add_entry(task.id, task.name, task.status.value, output, error)

        for cb in self._callbacks:
            try:
                cb(task, success, output, error)
            except Exception as e:
                logger.error(f"Callback hatası: {e}")

    def _run_command(self, task: ScheduledTask) -> str:
        """Sistem komutu çalıştır"""
        result = subprocess.run(
            [task.command] + task.command_args,
            capture_output=True,
            text=True,
            timeout=task.timeout
        )
        if result.returncode != 0:
            raise RuntimeError(f"Komut başarısız: {result.stderr}")
        return result.stdout

    def _send_notification(self, task: ScheduledTask) -> str:
        """Windows bildirimi gönder (win32)"""
        try:
            from plyer import notification
            notification.notify(
                title=task.notification_title or task.name,
                message=task.notification_message or "",
                timeout=10
            )
        except ImportError:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, task.notification_message or "",
                task.notification_title or task.name, 0
            )
        return f"Bildirim gönderildi: {task.notification_title}"

    def _make_api_call(self, task: ScheduledTask) -> str:
        """API çağrısı yap"""
        import requests as req
        method = task.api_method.upper()
        kwargs = {
            'url': task.api_url,
            'headers': task.api_headers,
            'timeout': task.timeout
        }
        if task.api_body and method in ('POST', 'PUT', 'PATCH'):
            kwargs['json'] = task.api_body

        response = req.request(method, **kwargs)
        response.raise_for_status()
        return response.text[:500]

    def _trigger_webhook(self, task: ScheduledTask) -> str:
        """Webhook tetikle"""
        import requests as req
        response = req.post(
            task.webhook_url,
            json=task.webhook_payload or {},
            timeout=task.timeout
        )
        response.raise_for_status()
        return f"Webhook tetiklendi: {response.status_code}"

    def _execute_python_func(self, task: ScheduledTask) -> str:
        """Kayıtlı Python fonksiyonunu çalıştır"""
        func = registered_functions.get(task.python_func_name)
        if func is None:
            raise ValueError(f"Fonksiyon bulunamadı: {task.python_func_name}")
        result = func(*task.python_func_args, **task.python_func_kwargs)
        return str(result)

    # ==================== CRUD İşlemleri ====================

    def create_task(self, name: str, task_type: TaskType, scheduled_at: Optional[str] = None,
                    recurrence: RecurrenceType = RecurrenceType.ONCE,
                    recurrence_interval: Optional[int] = None,
                    **kwargs) -> ScheduledTask:
        """Yeni görev oluştur"""
        task = ScheduledTask(
            name=name,
            task_type=task_type,
            recurrence=recurrence,
            recurrence_interval=recurrence_interval,
            **kwargs
        )
        if scheduled_at:
            task.scheduled_at = scheduled_at
            task.next_run = scheduled_at
        elif recurrence == RecurrenceType.ONCE:
            task.next_run = datetime.now().isoformat()
        else:
            task.next_run = task.calculate_next_run()

        self.store.add(task)
        logger.info(f"Görev oluşturuldu: {name} ({task.id})")
        return task

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self.store.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[ScheduledTask]:
        if status:
            return self.store.list_by_status(status)
        return self.store.list_all()

    def update_task(self, task_id: str, **updates) -> Optional[ScheduledTask]:
        """Görevi güncelle"""
        task = self.store.get(task_id)
        if not task:
            return None
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        self.store.update(task)
        return task

    def delete_task(self, task_id: str) -> bool:
        result = self.store.delete(task_id)
        if result:
            logger.info(f"Görev silindi: {task_id}")
        return result

    def pause_task(self, task_id: str) -> bool:
        """Görevi duraklat"""
        task = self.store.get(task_id)
        if not task:
            return False
        task.status = TaskStatus.PAUSED
        self.store.update(task)
        logger.info(f"Görev duraklatıldı: {task.name}")
        return True

    def resume_task(self, task_id: str) -> bool:
        """Görevi devam ettir"""
        task = self.store.get(task_id)
        if not task:
            return False
        task.status = TaskStatus.PENDING
        if task.next_run is None:
            task.next_run = datetime.now().isoformat()
        self.store.update(task)
        logger.info(f"Görev devam ettirildi: {task.name}")
        return True

    def run_now(self, task_id: str) -> bool:
        """Görevi hemen çalıştır (kuyruğa ekle)"""
        task = self.store.get(task_id)
        if not task:
            return False
        self._event_queue.put({'task_id': task_id, 'action': 'execute'})
        return True

    def get_history(self, task_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return self.history.get_history(task_id, limit)

    def get_status_summary(self) -> Dict[str, Any]:
        """Zamanlayıcı durum özeti"""
        tasks = self.store.list_all()
        status_counts = {}
        for t in tasks:
            s = t.status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            'total': len(tasks),
            'by_status': status_counts,
            'running': self._running,
            'pending_count': len(self.store.list_by_status(TaskStatus.PENDING))
        }


# Global örnek
_scheduler_instance: Optional[TaskScheduler] = None

def get_scheduler() -> TaskScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TaskScheduler()
    return _scheduler_instance
