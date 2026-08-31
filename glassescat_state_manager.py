"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   SHADOWCAT - STATE MANAGER (Kalıcı Durum Yönetimi) ║
║                                                               ║
║   Agent'ın durumunu, tercihlerini ve çalışma bağlamını      ║
║   kalıcı olarak saklar ve yönetir.                           ║
║                                                               ║
║   Saklanan veriler:                                           ║
║   - Agent durumu (mod, istatistikler)                        ║
║   - Kullanıcı tercihleri                                     ║
║   - Oturum geçmişi                                           ║
║   - Tool çağrı geçmişi                                       ║
║   - Görev ilerlemesi (yarıda kalan görevler)                 ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger("GlassescatStateManager")

# ─────────────────────────────────────────────────────────────
# SABİTLER
# ─────────────────────────────────────────────────────────────

STATE_DIR = Path(__file__).parent / "storage" / "state"
AGENT_STATE_FILE = "agent_state.json"
USER_PREFS_FILE = "user_preferences.json"
SESSION_HISTORY_FILE = "session_history.json"
TOOL_HISTORY_FILE = "tool_history.json"
TASK_PROGRESS_FILE = "task_progress.json"

MAX_HISTORY_ITEMS = 100
MAX_TOOL_HISTORY = 200
AUTO_SAVE_INTERVAL = 60  # saniye


# ─────────────────────────────────────────────────────────────
# STATE MANAGER
# ─────────────────────────────────────────────────────────────

class StateManager:
    """
    Kalıcı durum yönetim sistemi.
    
    Agent'ın tüm kalıcı verilerini JSON dosyalarında saklar.
    Thread-safe okuma/yazma işlemleri.
    
    Kullanım:
        sm = StateManager()
        
        # Agent durumu
        sm.save_agent_state({"mode": "developer", "commands": 42})
        state = sm.load_agent_state()
        
        # Kullanıcı tercihleri
        sm.save_preference("theme", "dark")
        theme = sm.get_preference("theme", "light")
        
        # Oturum geçmişi
        sm.add_to_history({"role": "user", "content": "Merhaba"})
        history = sm.get_recent_history(10)
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._auto_save_timer = None
        self._dirty = False
        
        # Dizinleri oluştur
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Önbellek
        self._cache = {}
        
        logger.info(f"State Manager: {STATE_DIR}")
        
        # Otomatik kaydetme başlat
        self._start_auto_save()
    
    def _start_auto_save(self):
        """Otomatik kaydetme timer'ı"""
        def auto_save():
            if self._dirty:
                self.flush()
            # Yeniden başlat
            self._auto_save_timer = threading.Timer(AUTO_SAVE_INTERVAL, auto_save)
            self._auto_save_timer.daemon = True
            self._auto_save_timer.start()
        
        self._auto_save_timer = threading.Timer(AUTO_SAVE_INTERVAL, auto_save)
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()
    
    # ── Agent Durumu ──
    
    def save_agent_state(self, state: Dict) -> bool:
        """Agent durumunu kaydet"""
        return self._save_json(AGENT_STATE_FILE, {
            "last_updated": datetime.now().isoformat(),
            "state": state
        })
    
    def load_agent_state(self) -> Optional[Dict]:
        """Agent durumunu yükle"""
        data = self._load_json(AGENT_STATE_FILE)
        if data:
            return data.get("state")
        return None
    
    # ── Kullanıcı Tercihleri ──
    
    def save_preference(self, key: str, value: Any) -> bool:
        """Kullanıcı tercihi kaydet"""
        prefs = self._load_json(USER_PREFS_FILE) or {}
        prefs[key] = value
        prefs["last_updated"] = datetime.now().isoformat()
        return self._save_json(USER_PREFS_FILE, prefs)
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Kullanıcı tercihini oku"""
        prefs = self._load_json(USER_PREFS_FILE) or {}
        return prefs.get(key, default)
    
    def get_all_preferences(self) -> Dict:
        """Tüm tercihleri getir"""
        prefs = self._load_json(USER_PREFS_FILE) or {}
        return {k: v for k, v in prefs.items() if k != "last_updated"}
    
    def delete_preference(self, key: str) -> bool:
        """Tercih sil"""
        prefs = self._load_json(USER_PREFS_FILE) or {}
        if key in prefs:
            del prefs[key]
            return self._save_json(USER_PREFS_FILE, prefs)
        return False
    
    # ── Oturum Geçmişi ──
    
    def add_to_history(self, entry: Dict) -> bool:
        """Oturum geçmişine ekle"""
        history = self._load_json(SESSION_HISTORY_FILE) or []
        entry["timestamp"] = datetime.now().isoformat()
        history.append(entry)
        
        # Limit kontrolü
        if len(history) > MAX_HISTORY_ITEMS:
            history = history[-MAX_HISTORY_ITEMS:]
        
        return self._save_json(SESSION_HISTORY_FILE, history)
    
    def get_recent_history(self, limit: int = 10) -> List[Dict]:
        """Son oturum kayıtlarını getir"""
        history = self._load_json(SESSION_HISTORY_FILE) or []
        return history[-limit:]
    
    def get_history_by_type(self, entry_type: str, limit: int = 20) -> List[Dict]:
        """Tipe göre oturum geçmişi filtrele"""
        history = self._load_json(SESSION_HISTORY_FILE) or []
        filtered = [e for e in history if e.get("type") == entry_type]
        return filtered[-limit:]
    
    def clear_history(self) -> bool:
        """Geçmişi temizle"""
        return self._save_json(SESSION_HISTORY_FILE, [])
    
    # ── Tool Çağrı Geçmişi ──
    
    def log_tool_call(self, tool_name: str, arguments: Dict, result: Dict, duration: float) -> bool:
        """Tool çağrısını kaydet"""
        history = self._load_json(TOOL_HISTORY_FILE) or []
        history.append({
            "tool": tool_name,
            "arguments": arguments,
            "result": {
                "success": result.get("success", False),
                "output_preview": str(result.get("output", ""))[:100]
            },
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(history) > MAX_TOOL_HISTORY:
            history = history[-MAX_TOOL_HISTORY:]
        
        return self._save_json(TOOL_HISTORY_FILE, history)
    
    def get_tool_statistics(self) -> Dict:
        """Tool kullanım istatistikleri"""
        history = self._load_json(TOOL_HISTORY_FILE) or []
        
        if not history:
            return {"total": 0, "tools": {}}
        
        stats = {"total": len(history), "tools": {}}
        
        for entry in history:
            tool = entry.get("tool", "unknown")
            if tool not in stats["tools"]:
                stats["tools"][tool] = {
                    "count": 0,
                    "success": 0,
                    "failed": 0,
                    "total_duration": 0.0
                }
            stats["tools"][tool]["count"] += 1
            if entry.get("result", {}).get("success"):
                stats["tools"][tool]["success"] += 1
            else:
                stats["tools"][tool]["failed"] += 1
            stats["tools"][tool]["total_duration"] += entry.get("duration", 0)
        
        return stats
    
    # ── Görev İlerlemesi ──
    
    def save_task_progress(self, task_id: str, progress: Dict) -> bool:
        """Görev ilerlemesini kaydet (yarıda kalan görevler için)"""
        tasks = self._load_json(TASK_PROGRESS_FILE) or {}
        tasks[task_id] = {
            **progress,
            "last_updated": datetime.now().isoformat()
        }
        return self._save_json(TASK_PROGRESS_FILE, tasks)
    
    def get_task_progress(self, task_id: str) -> Optional[Dict]:
        """Görev ilerlemesini getir"""
        tasks = self._load_json(TASK_PROGRESS_FILE) or {}
        return tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict:
        """Tüm görevleri getir"""
        return self._load_json(TASK_PROGRESS_FILE) or {}
    
    def delete_task(self, task_id: str) -> bool:
        """Görev kaydını sil"""
        tasks = self._load_json(TASK_PROGRESS_FILE) or {}
        if task_id in tasks:
            del tasks[task_id]
            return self._save_json(TASK_PROGRESS_FILE, tasks)
        return False
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Eski görev kayıtlarını temizle"""
        tasks = self._load_json(TASK_PROGRESS_FILE) or {}
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        cleaned = 0
        
        for task_id, task in list(tasks.items()):
            updated = task.get("last_updated", "")
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated)
                    if updated_dt < cutoff:
                        del tasks[task_id]
                        cleaned += 1
                except:
                    del tasks[task_id]
                    cleaned += 1
        
        if cleaned > 0:
            self._save_json(TASK_PROGRESS_FILE, tasks)
        
        return cleaned
    
    # ── Genel Amaçlı Depolama ──
    
    def save_data(self, key: str, data: Any) -> bool:
        """Herhangi bir veriyi kaydet"""
        storage = self._load_json("custom_data.json") or {}
        storage[key] = {
            "data": data,
            "saved_at": datetime.now().isoformat()
        }
        return self._save_json("custom_data.json", storage)
    
    def load_data(self, key: str) -> Optional[Any]:
        """Kaydedilmiş veriyi yükle"""
        storage = self._load_json("custom_data.json") or {}
        if key in storage:
            return storage[key]["data"]
        return None
    
    def delete_data(self, key: str) -> bool:
        """Veriyi sil"""
        storage = self._load_json("custom_data.json") or {}
        if key in storage:
            del storage[key]
            return self._save_json("custom_data.json", storage)
        return False
    
    # ── Dosya İşlemleri ──
    
    def _save_json(self, filename: str, data: Any) -> bool:
        """JSON dosyasına kaydet (thread-safe)"""
        filepath = STATE_DIR / filename
        with self._lock:
            try:
                temp_path = filepath.with_suffix(".tmp")
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                temp_path.replace(filepath)  # Atomik yazma
                self._dirty = True
                return True
            except Exception as e:
                logger.error(f"Kaydetme hatası ({filename}): {e}")
                return False
    
    def _load_json(self, filename: str) -> Optional[Any]:
        """JSON dosyasından oku (thread-safe, önbellekli)"""
        filepath = STATE_DIR / filename
        
        # Önbellek kontrolü
        if filename in self._cache:
            return self._cache[filename]
        
        with self._lock:
            try:
                if filepath.exists():
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._cache[filename] = data
                    return data
            except Exception as e:
                logger.warning(f"Okuma hatası ({filename}): {e}")
        
        return None
    
    def invalidate_cache(self, filename: str = None):
        """Önbelleği temizle"""
        if filename:
            self._cache.pop(filename, None)
        else:
            self._cache.clear()
    
    # ── Yönetim ──
    
    def flush(self):
        """Bekleyen tüm değişiklikleri diske yaz"""
        with self._lock:
            self._dirty = False
    
    def get_storage_size(self) -> str:
        """Depolama boyutunu hesapla"""
        total = 0
        for f in STATE_DIR.glob("*.json"):
            total += f.stat().st_size
        
        for unit in ['B', 'KB', 'MB']:
            if total < 1024:
                return f"{total:.1f} {unit}"
            total /= 1024
        return f"{total:.1f} GB"
    
    def get_status(self) -> Dict:
        """Durum yöneticisi hakkında bilgi"""
        return {
            "storage_dir": str(STATE_DIR),
            "storage_size": self.get_storage_size(),
            "files": [f.name for f in STATE_DIR.glob("*.json")],
            "cache_entries": len(self._cache),
            "auto_save_interval": AUTO_SAVE_INTERVAL
        }
    
    def reset(self):
        """Tüm durumu sıfırla"""
        with self._lock:
            for f in STATE_DIR.glob("*.json"):
                f.unlink()
            self._cache.clear()
            self._dirty = False
        logger.info("State Manager sıfırlandı")


# ─────────────────────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────────────────────

_state_manager_instance = None

def get_state_manager() -> StateManager:
    """StateManager singleton instance'ını al"""
    global _state_manager_instance
    if _state_manager_instance is None:
        _state_manager_instance = StateManager()
    return _state_manager_instance


if __name__ == "__main__":
    sm = get_state_manager()
    
    # Test
    sm.save_agent_state({"mode": "test", "commands": 5})
    state = sm.load_agent_state()
    print(f"Agent state: {state}")
    
    sm.save_preference("theme", "dark")
    theme = sm.get_preference("theme", "light")
    print(f"Preference: theme = {theme}")
    
    sm.add_to_history({"type": "test", "content": "Merhaba"})
    history = sm.get_recent_history(5)
    print(f"History: {len(history)} entries")
    
    print(f"Storage: {sm.get_storage_size()}")
    print(f"Status: {sm.get_status()}")
