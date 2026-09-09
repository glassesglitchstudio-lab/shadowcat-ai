# -*- coding: utf-8 -*-
"""
Shadowcat Dashboard - kullanici istatistikleri ve hizli notlar
Sohbet sayilari, arac kullanimi, hafiza kategorileri ve kisa notlar.
"""
import os, json, time, uuid
from typing import Dict, Any, List
from pathlib import Path

STORAGE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "storage" / "dashboard"
NOTES_FILE = STORAGE_DIR / "notes.json"
STATS_FILE = STORAGE_DIR / "stats.json"


def _ensure_storage():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not NOTES_FILE.exists():
        NOTES_FILE.write_text("[]", encoding="utf-8")
    if not STATS_FILE.exists():
        STATS_FILE.write_text("{}", encoding="utf-8")


class DashboardManager:
    """Pano: notlar + istatistikler + hafiza ozeti"""

    def __init__(self):
        _ensure_storage()

    # ---- Notlar ----
    def add_note(self, title: str, content: str, tags: List[str] = None) -> Dict:
        """Yeni hizli not ekle"""
        note = {
            "id": f"note_{uuid.uuid4().hex[:8]}",
            "title": title,
            "content": content,
            "tags": tags or [],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        notes = self.list_notes()
        notes.insert(0, note)
        NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        return note

    def list_notes(self, limit: int = 50) -> List[Dict]:
        """Notlari listele"""
        try:
            return json.loads(NOTES_FILE.read_text(encoding="utf-8"))[:limit]
        except Exception:
            return []

    def delete_note(self, note_id: str) -> bool:
        """Not sil"""
        notes = self.list_notes(9999)
        filtered = [n for n in notes if n["id"] != note_id]
        NOTES_FILE.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(filtered) != len(notes)

    def search_notes(self, query: str) -> List[Dict]:
        """Notlarda ara"""
        q = query.lower()
        return [n for n in self.list_notes(9999)
                if q in n["title"].lower() or q in n["content"].lower()]

    # ---- Istatistikler ----
    def track_event(self, event_type: str, data: Dict = None):
        """Bir olayi istatistik olarak kaydet"""
        try:
            stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except Exception:
            stats = {}
        day = time.strftime("%Y-%m-%d")
        stats.setdefault(day, {})
        stats[day].setdefault(event_type, 0)
        stats[day][event_type] += 1
        STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_stats(self) -> Dict[str, Any]:
        """Istatistik ozeti getir"""
        try:
            stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except Exception:
            stats = {}
        return {
            "total_days": len(stats),
            "events": stats,
            "last_7_days": list(stats.keys())[-7:],
        }

    # ---- Hafiza ozeti ----
    def get_memory_summary(self, memory=None) -> Dict:
        """Hafiza motoru ozeti (disaridan verilir)"""
        if memory is None:
            return {"available": False}
        try:
            stats = memory.get_stats()
            return {"available": True, **stats}
        except Exception as e:
            return {"available": False, "error": str(e)}


_dash_instance = None

def get_dashboard() -> DashboardManager:
    """Singleton dashboard ornegi"""
    global _dash_instance
    if _dash_instance is None:
        _dash_instance = DashboardManager()
    return _dash_instance


if __name__ == "__main__":
    d = get_dashboard()
    print("Notlar:", len(d.list_notes()))
    print("Istatistikler:", json.dumps(d.get_stats(), ensure_ascii=False))