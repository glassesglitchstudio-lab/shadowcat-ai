# -*- coding: utf-8 -*-
"""
Storage Adapter - Shadowcat veri katmani soyutlamasi.

Amac: Kod icindeki tum veri erisimleri bu adapter uzerinden yapilir.
Ileride Firebase/Firestore'a gecmek istedigimizde sadece bu dosyadaki
backend sinifini degistirmek yeterli olur, geri kalan kod degismez.

Kullanim:
    from storage_adapter import storage
    storage.save_user("ali", {...})
    user = storage.get_user("ali")

    storage.save_conversation("c1", [{"role":"user","content":"..."}])
    convs = storage.list_conversations("ali")
"""
import os
import json
from typing import Optional, Dict, Any, List

# Aktif backend: "json" (dosya tabanli) veya ileride "firestore"
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "json")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "data")


class JsonBackend:
    """JSON dosya tabanli backend - su anki varsayilan."""

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)

    def _path(self, collection: str, key: str = "") -> str:
        safe_key = key.replace("/", "_").replace("\\", "_")
        return os.path.join(DATA_DIR, f"{collection}_{safe_key}.json") if safe_key else os.path.join(DATA_DIR, f"{collection}.json")

    def _read(self, collection: str, key: str = "") -> Any:
        p = self._path(collection, key)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write(self, collection: str, key: str, data: Any):
        with open(self._path(collection, key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save(self, collection: str, key: str, data: Any) -> bool:
        self._write(collection, key, data)
        return True

    def get(self, collection: str, key: str) -> Optional[Any]:
        return self._read(collection, key)

    def delete(self, collection: str, key: str) -> bool:
        p = self._path(collection, key)
        if os.path.exists(p):
            os.remove(p)
        return True

    def list(self, collection: str, prefix: str = "") -> List[Dict]:
        out = []
        for fn in os.listdir(DATA_DIR):
            if not fn.startswith(f"{collection}_") or not fn.endswith(".json"):
                continue
            if prefix and not fn[len(collection) + 1 :].startswith(prefix):
                continue
            try:
                with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception:
                continue
        return out


class StorageAdapter:
    """Uygulama icin yuksek seviye API. Backend'i sarmalar."""

    def __init__(self):
        self._backend = JsonBackend()

    # Kullanicilar
    def save_user(self, uid: str, data: Dict) -> bool:
        return self._backend.save("users", uid, data)

    def get_user(self, uid: str) -> Optional[Dict]:
        return self._backend.get("users", uid)

    def delete_user(self, uid: str) -> bool:
        return self._backend.delete("users", uid)

    # Sohbetler
    def save_conversation(self, conv_id: str, messages: List[Dict], username: str = "") -> bool:
        return self._backend.save("conversations", conv_id, {
            "id": conv_id,
            "username": username,
            "messages": messages,
            "updated_at": __import__("datetime").datetime.now().isoformat(),
        })

    def get_conversation(self, conv_id: str) -> Optional[Dict]:
        return self._backend.get("conversations", conv_id)

    def list_conversations(self, username: str = "") -> List[Dict]:
        return self._backend.list("conversations", prefix=username)

    # Kullanim/limit verisi
    def save_usage(self, key: str, data: Dict) -> bool:
        return self._backend.save("usage", key, data)

    def get_usage(self, key: str) -> Optional[Dict]:
        return self._backend.get("usage", key)

    # Geri bildirim
    def save_feedback(self, entry: Dict) -> bool:
        return self._backend.save("feedback", entry.get("time", "fb"), entry)

    # Hafiza notlari (Obsidian .md -> ileride Firestore)
    def save_note(self, note_id: str, data: Dict) -> bool:
        return self._backend.save("notes", note_id, data)

    def get_note(self, note_id: str) -> Optional[Dict]:
        return self._backend.get("notes", note_id)

    def list_notes(self) -> List[Dict]:
        return self._backend.list("notes")

    def status(self) -> Dict:
        return {
            "backend": STORAGE_BACKEND,
            "data_dir": DATA_DIR,
            "collections": ["users", "conversations", "usage", "feedback", "notes"],
        }


_storage = None


def get_storage() -> StorageAdapter:
    """Tek (singleton) storage adapter doner."""
    global _storage
    if _storage is None:
        _storage = StorageAdapter()
    return _storage


storage = get_storage()


if __name__ == "__main__":
    # Hizli smoke test
    storage.save_user("test", {"name": "Test", "role": "admin"})
    u = storage.get_user("test")
    print("user:", u)
    storage.save_conversation("c_test", [{"role": "user", "content": "merhaba"}], "test")
    print("conv:", storage.get_conversation("c_test"))
    storage.delete_user("test")
    storage._backend.delete("conversations", "c_test")
    print("status:", storage.status())
    print("OK")
