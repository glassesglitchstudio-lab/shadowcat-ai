"""
Shadowcat AI v4.0 - Nexus Memory Engine (Yüksek Performanslı Hibrit Hafıza)

Obsidian .md bağımlılığı yerine SQLite FTS5 (Tam Metin Arama) tabanlı,
hızlı, kategorize edilebilir ve ilişkisel hafıza motoru.

Özellikler:
- SQLite FTS5 ile milisaniyeler seviyesinde arama
- Konuşma geçmişi, anılar, bilgi tabanı ve etiket yönetimi
- Eski Obsidian .md notlarını otomatik aktarma (migration)
- Thread-safe veritabanı bağlantı havuzu
"""

import os
import re
import sqlite3
import json
import time
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class NexusMemoryEngine:
    """
    Shadowcat AI Nexus Hafıza Motoru.
    SQLite + FTS5 tam metin arama desteği ile yüksek hızlı hafıza yönetimi.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            storage_dir = os.path.join(base_dir, "storage")
            os.makedirs(storage_dir, exist_ok=True)
            db_path = os.path.join(storage_dir, "nexus_memory.db")

        self.db_path = db_path
        self._init_db()
        self._migrate_obsidian_notes()

    def _get_connection(self) -> sqlite3.Connection:
        """Veritabanı bağlantısı al (Row factory ile)"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Veritabanı tablolarını ve FTS5 indekslerini oluştur"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Ana hafıza tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Konuşma geçmişi tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # FTS5 Sanal Tablosu (Tam Metin Arama)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    id UNINDEXED,
                    title,
                    content,
                    category,
                    tags
                )
            """)

            # FTS Triggers (Ekleme, Güncelleme, Silme)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(id, title, content, category, tags)
                    VALUES (new.id, new.title, new.content, new.category, new.tags);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    DELETE FROM memories_fts WHERE id = old.id;
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    DELETE FROM memories_fts WHERE id = old.id;
                    INSERT INTO memories_fts(id, title, content, category, tags)
                    VALUES (new.id, new.title, new.content, new.category, new.tags);
                END;
            """)

            conn.commit()
            logger.info("Nexus Memory SQLite + FTS5 tabloları hazır.")

    def _migrate_obsidian_notes(self):
        """Mevcut notes/ klasöründeki Obsidian .md dosyalarını tek seferde Nexus DB'ye aktar"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        notes_dir = Path(os.path.join(base_dir, "notes"))

        if not notes_dir.exists():
            return

        md_files = list(notes_dir.rglob("*.md"))
        if not md_files:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            migrated_count = 0

            for filepath in md_files:
                try:
                    rel_path = filepath.relative_to(notes_dir)
                    category = rel_path.parts[0] if len(rel_path.parts) > 1 else "notes"
                    title = filepath.stem

                    # Zaten aktarılmış mı kontrol et
                    mem_id = f"obsidian_{filepath.name}"
                    cursor.execute("SELECT id FROM memories WHERE id = ?", (mem_id,))
                    if cursor.fetchone():
                        continue

                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().strip()

                    if not content:
                        continue

                    # Etiketleri içerikten ayıkla (#tag)
                    tags = list(set(re.findall(r"#([\w-]+)", content)))

                    cursor.execute("""
                        INSERT INTO memories (id, title, content, category, tags, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        mem_id,
                        title,
                        content,
                        category,
                        json.dumps(tags, ensure_ascii=False),
                        json.dumps({"source": "obsidian_migration", "filepath": str(filepath)}, ensure_ascii=False)
                    ))
                    migrated_count += 1
                except Exception as e:
                    logger.warning(f"Obsidian not aktarım hatası ({filepath}): {e}")

            conn.commit()
            if migrated_count > 0:
                logger.info(f"Nexus Memory: {migrated_count} Obsidian .md notu başarıyla veritabanına aktarıldı.")

    # ─────────────────────────────────────────────────────────────
    # MEMORY CRUD APIS
    # ─────────────────────────────────────────────────────────────

    def save_memory(self, title: str, content: str, category: str = "general", tags: List[str] = None, metadata: Dict[str, Any] = None) -> str:
        """Yeni bir anı / bilgi kaydet"""
        mem_id = f"mem_{uuid.uuid4().hex[:12]}"
        tags = tags or []
        metadata = metadata or {}

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memories (id, title, content, category, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                mem_id,
                title,
                content,
                category,
                json.dumps(tags, ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False)
            ))
            conn.commit()

        logger.info(f"Nexus Memory kaydedildi: [{category}] {title} (ID: {mem_id})")
        return mem_id

    def recall(self, query: str, limit: int = 10, category: str = None) -> List[Dict[str, Any]]:
        """
        FTS5 ile hızlı tam metin arama ve hatırlama.
        """
        results = []
        if not query or not query.strip():
            return results

        clean_query = query.replace("'", " ").replace('"', " ").strip()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # FTS5 araması
            try:
                if category:
                    sql = """
                        SELECT m.* FROM memories m
                        JOIN memories_fts fts ON m.id = fts.id
                        WHERE memories_fts MATCH ? AND m.category = ?
                        ORDER BY rank
                        LIMIT ?
                    """
                    cursor.execute(sql, (f"{clean_query}*", category, limit))
                else:
                    sql = """
                        SELECT m.* FROM memories m
                        JOIN memories_fts fts ON m.id = fts.id
                        WHERE memories_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                    """
                    cursor.execute(sql, (f"{clean_query}*", limit))
                
                rows = cursor.fetchall()
            except Exception:
                # FTS arama başarısız olursa LIKE aramasına düş
                like_query = f"%{clean_query}%"
                if category:
                    cursor.execute("""
                        SELECT * FROM memories
                        WHERE (title LIKE ? OR content LIKE ?) AND category = ?
                        ORDER BY updated_at DESC LIMIT ?
                    """, (like_query, like_query, category, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM memories
                        WHERE title LIKE ? OR content LIKE ?
                        ORDER BY updated_at DESC LIMIT ?
                    """, (like_query, like_query, limit))
                rows = cursor.fetchall()

            for row in rows:
                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "category": row["category"],
                    "tags": json.loads(row["tags"] or "[]"),
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })

        return results

    def save_conversation(self, session_id: str, messages: List[Dict[str, str]]):
        """Sohbet geçmişini kaydet"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for msg in messages:
                role = msg.get("role", "user")
                text = msg.get("content", "").strip()
                if text:
                    cursor.execute("""
                        INSERT INTO conversations (id, session_id, role, message)
                        VALUES (?, ?, ?, ?)
                    """, (f"conv_{uuid.uuid4().hex[:12]}", session_id, role, text))
            conn.commit()

    def get_conversation(self, session_id: str, limit: int = 50) -> List[Dict[str, str]]:
        """Bir oturuma ait sohbet geçmişini getir"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, message, created_at FROM conversations
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (session_id, limit))
            rows = cursor.fetchall()
            return [{"role": r["role"], "content": r["message"], "timestamp": r["created_at"]} for r in rows]

    def save_knowledge(self, title: str, content: str, category: str = "knowledge", tags: List[str] = None):
        """Bilgi tabanına yeni kayıt ekle"""
        return self.save_memory(title=title, content=content, category=category, tags=tags)

    def delete_memory(self, memory_id: str) -> bool:
        """Hafıza kaydını sil"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_memory_count(self) -> int:
        """Toplam hafıza sayısını dondur"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            return cursor.fetchone()[0]

    def get_stats(self) -> Dict[str, Any]:
        """Hafıza istatistiklerini getir"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            mem_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM conversations")
            conv_count = cursor.fetchone()[0]

            cursor.execute("SELECT category, COUNT(*) as cnt FROM memories GROUP BY category")
            cats = {row["category"]: row["cnt"] for row in cursor.fetchall()}

        return {
            "engine": "Nexus Memory (SQLite + FTS5)",
            "memory_count": mem_count,
            "conversation_count": conv_count,
            "categories": cats,
            "db_path": self.db_path
        }

    def recall_recent(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Son hatırlanan kayıtları getir (bağlam için)"""
        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM memories
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            for row in rows:
                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "category": row["category"],
                    "tags": json.loads(row["tags"] or "[]"),
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })
        return results

    def recall_by_category(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Kategoriye göre hatırlama"""
        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM memories
                WHERE category = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (category, limit))
            rows = cursor.fetchall()
            for row in rows:
                results.append({
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "category": row["category"],
                    "tags": json.loads(row["tags"] or "[]"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })
        return results


# Singleton Pattern
_nexus_instance: Optional[NexusMemoryEngine] = None

def get_nexus_memory() -> NexusMemoryEngine:
    global _nexus_instance
    if _nexus_instance is None:
        _nexus_instance = NexusMemoryEngine()
    return _nexus_instance



# Singleton Pattern
_nexus_instance: Optional[NexusMemoryEngine] = None

def get_nexus_memory() -> NexusMemoryEngine:
    global _nexus_instance
    if _nexus_instance is None:
        _nexus_instance = NexusMemoryEngine()
    return _nexus_instance
