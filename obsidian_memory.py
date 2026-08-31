"""
Shadowcat AI - Obsidian Sınırsız Hafıza Sistemi (Infinite Memory)
Tüm konuşmalar, anılar ve bilgiler .md dosyalarında saklanır.
Obsidian Vault ile tam uyumlu - VSCode Obsidian eklentisi ile senkron.

Bu sistem sayesinde AI'nın hafızası SINIRSIZDIR:
- Her konuşma ayrı bir .md dosyası
- Otomatik özetler ve etiketler
- Obsidian link'leri ile birbirine bağlı notlar
- Tam metin arama (grep ile)
- Kategorik indeksleme
"""

import os
import re
import glob
import json
import time
import uuid
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path


class ObsidianMemory:
    """
    Obsidian tabanlı sınırsız hafıza sistemi.
    Tüm veriler .md formatında, Obsidian vault'unda saklanır.
    """

    def __init__(self, vault_path: str = None):
        if vault_path is None:
            vault_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'notes'
            )

        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(exist_ok=True)

        self.memories_dir = self.vault_path / 'memories'
        self.conversations_dir = self.vault_path / 'conversations'
        self.summaries_dir = self.vault_path / 'summaries'
        self.knowledge_dir = self.vault_path / 'knowledge'
        self.tags_dir = self.vault_path / 'tags'

        for d in [self.memories_dir, self.conversations_dir, self.summaries_dir, self.knowledge_dir, self.tags_dir]:
            d.mkdir(exist_ok=True)

        self.lock = threading.Lock()
        self._ensure_index()
        self._ensure_daily_note()

    def _ensure_index(self):
        """Ana indeks sayfasını oluştur"""
        index_path = self.vault_path / 'index.md'
        now = datetime.now()
        if not index_path.exists():
            content = f"""---
created: {now.isoformat()}
modified: {now.isoformat()}
type: vault-index
tags: [index, ana-sayfa, vault]
aliases: [ana-sayfa, vault-home]
cssclass: vault-index
---

# Shadowcat AI - Obsidian Hafıza Vault'u

> Sınırsız yapay zeka hafızası. Tüm konuşmalar, anılar ve bilgiler burada saklanır.

## Kategoriler

- [[memories/|Anılar ve Hatıralar]]
- [[conversations/|Konuşmalar]]
- [[summaries/|Özetler]]
- [[knowledge/|Bilgi Tabanı]]
- [[tags/|Etiketler]]

## İstatistikler

- Toplam Hafıza: {{memory_count}}
- Toplam Konuşma: {{conversation_count}}
- Son Güncelleme: {now.strftime('%Y-%m-%d %H:%M:%S')}

---
*Bu vault otomatik olarak Shadowcat AI tarafından yönetilmektedir.*
"""
            stats = self._get_stats()
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(content.format(
                    memory_count=stats['memory_count'],
                    conversation_count=stats['conversation_count']
                ))

    def _ensure_daily_note(self):
        """Günlük not sayfasını oluştur (Dataview uyumlu)"""
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        daily_dir = self.vault_path / 'daily'
        daily_dir.mkdir(exist_ok=True)
        daily_path = daily_dir / f'{today}.md'

        if not daily_path.exists():
            content = f"""---
created: {now.isoformat()}
modified: {now.isoformat()}
type: daily-note
date: {today}
week: {now.isocalendar()[1]}
year: {now.year}
month: {now.month}
day: {now.day}
tags: [daily-note, {today}, dailynote]
cssclass: daily-note
---

# Günlük Not - {today}

## Öne Çıkanlar
- 

## Konuşmalar
- 

## Hatırlanması Gerekenler
- 

## Yapılacaklar
- [ ] 

---
*Bu not otomatik oluşturulmuştur.*
"""
            with open(daily_path, 'w', encoding='utf-8') as f:
                f.write(content)

    def _get_stats(self) -> Dict:
        return {
            'memory_count': len(list(self.memories_dir.glob('*.md'))),
            'conversation_count': len(list(self.conversations_dir.glob('*.md')))
        }

    def save_memory(self, title: str, content: str, tags: List[str] = None, metadata: Dict = None) -> str:
        """Bir anıyı/hafızayı .md dosyası olarak kaydet (Dataview uyumlu)"""
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        safe_title = safe_title[:80]

        memory_id = uuid.uuid4().hex[:12]
        filename = f"{date_str}_{safe_title}_{memory_id}.md"
        filepath = self.memories_dir / filename

        if tags is None:
            tags = ['memory']

        tags_list = ', '.join(f'"{t}"' for t in tags)
        tags_yaml = '\n'.join(f'  - {t}' for t in tags)

        md_meta = ""
        if metadata:
            md_meta = "\n## Metadata\n"
            for k, v in metadata.items():
                md_meta += f"- **{k}:** {v}\n"
            meta_yaml = '\n'.join(f'{k}: "{v}"' if isinstance(v, str) else f'{k}: {v}' for k, v in metadata.items())
            meta_block = f"\n{meta_yaml}"
        else:
            meta_block = ""

        md_content = f"""---
title: "{title}"
memory_id: "{memory_id}"
created: {now.isoformat()}
modified: {now.isoformat()}
type: memory
date: {date_str}
tags:{meta_block}
{tags_yaml}
aliases: [{', '.join(f'"{t}"' for t in tags[:3])}]
cssclass: memory-note
---

# {title}

**Oluşturulma:** {date_str} {time_str}
**ID:** `{memory_id}`

---

{content}

---
## İlgili Bağlantılar
- [[daily/{date_str}|Günlük Not - {date_str}]]
"""

        if metadata:
            md_content += md_meta

        with self.lock:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)

        self._update_index()
        return str(filepath)

    def save_conversation(self, session_id: str, messages: List[Dict]) -> str:
        """Konuşmayı .md dosyasına kaydet (Dataview uyumlu)"""
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        user_msgs = sum(1 for m in messages if m.get('role') == 'user')
        assistant_msgs = sum(1 for m in messages if m.get('role') == 'assistant')
        conv_id = uuid.uuid4().hex[:8]

        filename = f"conv_{session_id[:8]}_{date_str}_{conv_id}.md"
        filepath = self.conversations_dir / filename

        md_lines = [f"""---
created: {now.isoformat()}
modified: {now.isoformat()}
type: conversation
session_id: "{session_id}"
conv_id: "{conv_id}"
date: {date_str}
message_count: {len(messages)}
user_messages: {user_msgs}
assistant_messages: {assistant_msgs}
tags:
  - conversation
  - session-{session_id[:8]}
cssclass: conversation-log
---

# Konuşma - {date_str}

**Oturum:** `{session_id}`
**Tarih:** {date_str} {time_str}
**Mesaj Sayısı:** {len(messages)} ({user_msgs} kullanıcı, {assistant_msgs} asistan)

---
## Konuşma İçeriği

"""]

        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            timestamp_msg = msg.get('timestamp', '')

            role_icon = '' if role == 'user' else '' if role == 'assistant' else ''
            md_lines.append(f'### {role_icon} Mesaj #{i+1} — {role.upper()} ({timestamp_msg})\n\n{content}\n\n---\n')

        md_lines.append(f'\n*Konuşma sonu — {time_str}*')

        with self.lock:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(md_lines))

        self._update_index()
        return str(filepath)

    def save_summary(self, session_id: str, summary_text: str, key_points: List[str] = None,
                     action_items: List[str] = None, topics: List[str] = None) -> str:
        """Konuşma özetini .md olarak kaydet (Dataview uyumlu)"""
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')

        if key_points is None:
            key_points = []
        if action_items is None:
            action_items = []
        if topics is None:
            topics = []

        summary_id = uuid.uuid4().hex[:6]
        filename = f"summary_{session_id[:12]}_{date_str}_{summary_id}.md"
        filepath = self.summaries_dir / filename

        topics_yaml = '\n'.join(f'  - {t}' for t in topics[:5])
        topics_str = ', '.join(f'"{t}"' for t in topics[:5]) if topics else '""'

        md = f"""---
created: {now.isoformat()}
modified: {now.isoformat()}
type: summary
session_id: "{session_id}"
summary_id: "{summary_id}"
date: {date_str}
key_point_count: {len(key_points)}
action_item_count: {len(action_items)}
topic_count: {len(topics)}
tags:
  - summary
{topics_yaml}
cssclass: summary-note
---

# Konuşma Özeti

**Tarih:** {date_str}
**Oturum:** `{session_id}`

## Özet

{summary_text}

"""

        if key_points:
            md += "## Önemli Noktalar\n\n"
            for kp in key_points:
                md += f"- {kp}\n"
            md += "\n"

        if action_items:
            md += "## Aksiyonlar\n\n"
            for ai in action_items:
                md += f"- [ ] {ai}\n"
            md += "\n"

        if topics:
            md += "## Konular\n\n"
            for t in topics:
                md += f"- **{t}**\n"
            md += "\n"

        md += "---\n"

        with self.lock:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md)

        self._update_index()
        return str(filepath)

    def save_knowledge(self, title: str, content: str, category: str = 'general', tags: List[str] = None) -> str:
        """Bilgi tabanına yeni bilgi ekle (Dataview uyumlu)"""
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')

        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:60]
        knowledge_id = uuid.uuid4().hex[:6]
        filename = f"{safe_title}_{knowledge_id}.md"
        filepath = self.knowledge_dir / filename

        if tags is None:
            tags = [category]

        tags_yaml = '\n'.join(f'  - {t}' for t in tags)

        md = f"""---
title: "{title}"
knowledge_id: "{knowledge_id}"
created: {now.isoformat()}
modified: {now.isoformat()}
type: knowledge
category: {category}
date: {date_str}
tags:
  - knowledge
  - {category}
{tags_yaml}
cssclass: knowledge-note
---

# {title}

**Kategori:** `{category}`
**Eklenme:** {date_str}
**ID:** `{knowledge_id}`

---

{content}

---
## İlgili Bağlantılar
- [[daily/{date_str}|Günlük Not - {date_str}]]
- [[index|Ana Sayfa]]
"""

        with self.lock:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md)

        self._update_index()
        return str(filepath)

    def recall(self, query: str, max_results: int = 10) -> List[Dict]:
        """Tüm hafızada ara - sınırsız arama (grep ile)"""
        results = []

        search_dirs = [
            self.memories_dir,
            self.conversations_dir,
            self.summaries_dir,
            self.knowledge_dir
        ]

        for search_dir in search_dirs:
            for md_file in search_dir.glob('*.md'):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if query.lower() in content.lower():
                        results.append({
                            'file': str(md_file),
                            'path': str(md_file.relative_to(self.vault_path)),
                            'content_preview': content[:500],
                            'type': md_file.parent.name,
                            'modified': datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
                        })

                        if len(results) >= max_results:
                            return results
                except:
                    continue

        return results

    def recall_recent(self, limit: int = 20) -> List[Dict]:
        """En son eklenen hafızaları getir"""
        all_files = []
        for d in [self.memories_dir, self.conversations_dir, self.summaries_dir, self.knowledge_dir]:
            for f in d.glob('*.md'):
                all_files.append(f)

        all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        results = []
        for f in all_files[:limit]:
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                results.append({
                    'file': str(f),
                    'path': str(f.relative_to(self.vault_path)),
                    'content_preview': content[:300],
                    'type': f.parent.name,
                    'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
            except:
                continue

        return results

    def get_memory_count(self) -> int:
        """Toplam hafıza dosyası sayısı"""
        count = 0
        for d in [self.memories_dir, self.conversations_dir, self.summaries_dir, self.knowledge_dir]:
            count += len(list(d.glob('*.md')))
        return count

    def get_total_size(self) -> str:
        """Toplam hafıza boyutu (insan tarafından okunabilir)"""
        total = 0
        for d in [self.memories_dir, self.conversations_dir, self.summaries_dir, self.knowledge_dir]:
            for f in d.glob('*.md'):
                total += f.stat().st_size

        for unit in ['B', 'KB', 'MB', 'GB']:
            if total < 1024:
                return f"{total:.1f} {unit}"
            total /= 1024
        return f"{total:.1f} TB"

    def _update_index(self):
        """İndeks sayfasını güncelle (Dataview uyumlu)"""
        now = datetime.now()
        index_path = self.vault_path / 'index.md'

        content = f"""---
created: {now.isoformat()}
modified: {now.isoformat()}
type: vault-index
tags: [index, ana-sayfa, vault]
aliases: [ana-sayfa, vault-home]
cssclass: vault-index
---

# Shadowcat AI - Obsidian Hafıza Vault'u

> Sınırsız yapay zeka hafızası. Tüm konuşmalar, anılar ve bilgiler burada saklanır.

## Kategoriler

- [[memories/|Anılar ve Hatıralar]]
- [[conversations/|Konuşmalar]]
- [[summaries/|Özetler]]
- [[knowledge/|Bilgi Tabanı]]
- [[tags/|Etiketler]]
- [[daily/|Günlük Notlar]]

## İstatistikler

- Toplam Hafıza Dosyası: {self.get_memory_count()}
- Toplam Boyut: {self.get_total_size()}
- Son Güncelleme: {now.strftime('%Y-%m-%d %H:%M:%S')}

## Son Eklenenler

{self._recent_files_markdown(10)}

## Dataview Sorgu Ornekleri

```dataview
TABLE created, type, file.tags as tags
FROM "memories" or "knowledge" or "conversations" or "summaries"
SORT created DESC
LIMIT 10
```

```dataview
TABLE summary_text as Ozet, key_point_count as "Onemli Nokta"
FROM "summaries"
SORT created DESC
LIMIT 5
```

---
*Bu vault otomatik olarak Shadowcat AI tarafından yönetilmektedir.*
"""
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _recent_files_markdown(self, limit: int = 10) -> str:
        """Son dosyaları markdown listesi olarak döndür"""
        all_files = []
        for d in [self.memories_dir, self.conversations_dir, self.summaries_dir, self.knowledge_dir]:
            for f in d.glob('*.md'):
                all_files.append(f)

        all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        lines = []
        for f in all_files[:limit]:
            rel = f.relative_to(self.vault_path)
            modified = datetime.fromtimestamp(f.stat().st_mtime)
            lines.append(f"- [[{rel}|{rel.stem}]] ({modified.strftime('%Y-%m-%d %H:%M')})")

        return '\n'.join(lines) if lines else '- Henüz hafıza yok'

    def get_context_for_ai(self, session_id: str = None, query: str = None, max_items: int = 5) -> str:
        """AI bağlamı için ilgili hafızaları getir"""
        parts = []

        recent = self.recall_recent(limit=3)
        if recent:
            parts.append("## Son Hafızalar\n")
            for r in recent:
                preview = r['content_preview'][:200].replace('\n', ' ').strip()
                parts.append(f"- [[{r['path']}|{r['path']}]]: {preview}...")

        if query:
            related = self.recall(query, max_results=3)
            if related:
                parts.append("\n## İlgili Hafızalar\n")
                for r in related:
                    preview = r['content_preview'][:200].replace('\n', ' ').strip()
                    parts.append(f"- [[{r['path']}|{r['path']}]]: {preview}...")

        return '\n'.join(parts)

    def export_all_as_json(self, output_path: str = None) -> Dict:
        """Tüm hafızayı JSON olarak dışa aktar"""
        data = {
            'exported_at': datetime.now().isoformat(),
            'total_files': self.get_memory_count(),
            'total_size': self.get_total_size(),
            'memories': [],
            'conversations': [],
            'summaries': [],
            'knowledge': []
        }

        category_map = {
            'memories': self.memories_dir,
            'conversations': self.conversations_dir,
            'summaries': self.summaries_dir,
            'knowledge': self.knowledge_dir
        }

        for category, directory in category_map.items():
            for md_file in directory.glob('*.md'):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        data[category].append({
                            'filename': md_file.name,
                            'content': f.read(),
                            'size': md_file.stat().st_size,
                            'modified': datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
                        })
                except:
                    continue

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        return data


# ═══════════════════════════════════════════════════════════════
# GELISMIS OZELLIKLER - Auto Context ve Konusma Ozetleme
# ═══════════════════════════════════════════════════════════════

    def auto_inject_context(self, user_input: str, max_items: int = 5) -> str:
        """
        Kullanıcı girdisine göre otomatik olarak ilgili hafızaları bulur
        ve bağlam olarak formatlar. AI çağrılarından önce kullanılır.
        
        Args:
            user_input: Kullanıcının mesajı
            max_items: Maksimum sonuç sayısı
        
        Returns:
            str: Markdown formatında bağlam metni
        """
        parts = []
        
        # 1. İlgili hafızaları ara
        related = self.recall(user_input, max_results=max_items)
        if related:
            parts.append("## Hafızamdan İlgili Kayıtlar\n")
            for r in related:
                preview = r['content_preview'][:200].replace('\n', ' ').strip()
                parts.append(f"- {r.get('type', 'bilgi')}: {preview}...")
            parts.append("")
        
        # 2. Son eklenen bilgileri ekle
        recent = self.recall_recent(limit=3)
        seen_paths = {r['path'] for r in related}
        recent_additions = [r for r in recent if r['path'] not in seen_paths]
        
        if recent_additions:
            parts.append("## Son Eklenenler\n")
            for r in recent_additions:
                preview = r['content_preview'][:100].replace('\n', ' ').strip()
                parts.append(f"- {preview}...")
            parts.append("")
        
        return '\n'.join(parts)
    
    def auto_summarize_and_save(self, session_id: str, messages: List[Dict]) -> str:
        """
        Konuşmayı otomatik özetler ve kaydeder.
        Son mesajı baz alarak başlık ve özet çıkarır.
        
        Args:
            session_id: Oturum kimliği
            messages: Konuşma mesajları
        
        Returns:
            str: Kaydedilen özet dosyasının yolu
        """
        if not messages:
            return ""
        
        # Son birkaç mesajdan özet çıkar
        recent_msgs = messages[-6:] if len(messages) > 6 else messages
        
        # Kullanıcı ve asistan mesajlarını ayır
        user_msgs = [m.get('content', '') for m in recent_msgs if m.get('role') == 'user']
        assistant_msgs = [m.get('content', '') for m in recent_msgs if m.get('role') == 'assistant']
        
        # Başlık oluştur (ilk kullanıcı mesajından)
        title = "Konuşma"
        if user_msgs:
            title = user_msgs[0][:60].replace('\n', ' ').strip()
        
        # Özet metni
        summary_parts = []
        summary_parts.append("## Konuşma Özeti\n")
        summary_parts.append(f"**Toplam Mesaj:** {len(messages)}")
        summary_parts.append(f"**Kullanıcı:** {sum(1 for m in messages if m.get('role') == 'user')}")
        summary_parts.append(f"**Asistan:** {sum(1 for m in messages if m.get('role') == 'assistant')}")
        summary_parts.append("")
        
        # Önemli noktalar (son mesajlardan)
        if assistant_msgs:
            summary_parts.append("## Önemli Noktalar\n")
            for msg in assistant_msgs[-3:]:
                # İlk 150 karakteri al
                preview = msg[:150].replace('\n', ' ').strip()
                if preview:
                    summary_parts.append(f"- {preview}...")
        
        # Anahtar kelimeler
        all_text = ' '.join(user_msgs + assistant_msgs)
        import re
        words = re.findall(r'\w+', all_text.lower())
        from collections import Counter
        common_words = [word for word in Counter(words).most_common(10) 
                       if word[0] not in ['bu', 'bir', 've', 'ile', 'için', 'ile', 'ama', 'veya']]
        
        if common_words:
            summary_parts.append("\n## Anahtar Kelimeler\n")
            keywords = [word for word, _ in common_words[:5]]
            summary_parts.append(', '.join(keywords))
        
        summary_text = '\n'.join(summary_parts)
        
        # Özet olarak kaydet
        return self.save_summary(
            session_id=session_id,
            summary_text=summary_text,
            topics=[w for w, _ in common_words[:3]] if common_words else ["general"]
        )
    
    def search_by_tag(self, tag: str, max_results: int = 20) -> List[Dict]:
        """
        Etikete göre hafızada ara.
        
        Args:
            tag: Aranacak etiket
            max_results: Maksimum sonuç sayısı
        
        Returns:
            List[Dict]: Sonuçlar
        """
        results = []
        search_dirs = [
            self.memories_dir, self.conversations_dir,
            self.summaries_dir, self.knowledge_dir
        ]
        
        for search_dir in search_dirs:
            for md_file in search_dir.glob('*.md'):
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Frontmatter'daki tags alanını kontrol et
                    if f'tags: [{tag}' in content or f'- {tag}' in content or f'"{tag}"' in content:
                        results.append({
                            'file': str(md_file),
                            'path': str(md_file.relative_to(self.vault_path)),
                            'content_preview': content[:300],
                            'type': md_file.parent.name,
                            'modified': datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
                        })
                        
                        if len(results) >= max_results:
                            return results
                except:
                    continue
        
        return results
    
    def get_daily_summary(self, date_str: str = None) -> Dict:
        """
        Belirli bir günün özetini getir.
        
        Args:
            date_str: Tarih (YYYY-MM-DD formatında, varsayılan: bugün)
        
        Returns:
            Dict: Günlük özet
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # O güne ait tüm dosyaları bul
        daily_files = []
        for d in [self.memories_dir, self.conversations_dir, self.summaries_dir, self.knowledge_dir]:
            for f in d.glob(f'*{date_str}*.md'):
                daily_files.append(f)
        
        daily_files.sort(key=lambda x: x.stat().st_mtime)
        
        summary = {
            'date': date_str,
            'total_entries': len(daily_files),
            'memories': [],
            'conversations': [],
            'summaries': [],
            'knowledge': []
        }
        
        for f in daily_files:
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                
                entry = {
                    'file': f.name,
                    'preview': content[:200].replace('\n', ' ').strip()
                }
                
                category = f.parent.name
                if category in summary:
                    summary[category].append(entry)
            except:
                continue
        
        return summary
    
    def semantic_search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Anlamsal arama (basit benzerlik skorlaması ile).
        Gerçek RAG için rag_system.py kullanılmalı.
        
        Args:
            query: Arama sorgusu
            max_results: Maksimum sonuç
        
        Returns:
            List[Dict]: Skorlanmış sonuçlar
        """
        results = self.recall(query, max_results=max_results * 2)
        
        # Basit skorlama: sorgudaki kelimelerin geçme sıklığı
        query_words = set(query.lower().split())
        
        scored = []
        for r in results:
            content_lower = r['content_preview'].lower()
            score = sum(1 for word in query_words if word in content_lower)
            scored.append((score, r))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [r for score, r in scored[:max_results]]
    
    def batch_save(self, entries: List[Dict]) -> List[str]:
        """
        Toplu hafıza kaydı.
        
        Args:
            entries: Kaydedilecek girdiler listesi
                    Her girdi: {title, content, tags, type}
        
        Returns:
            List[str]: Kaydedilen dosya yolları
        """
        paths = []
        for entry in entries:
            entry_type = entry.get('type', 'memory')
            
            if entry_type == 'memory':
                path = self.save_memory(
                    title=entry.get('title', 'Hafıza'),
                    content=entry.get('content', ''),
                    tags=entry.get('tags', [])
                )
            elif entry_type == 'knowledge':
                path = self.save_knowledge(
                    title=entry.get('title', 'Bilgi'),
                    content=entry.get('content', ''),
                    category=entry.get('category', 'general'),
                    tags=entry.get('tags', [])
                )
            else:
                path = self.save_memory(
                    title=entry.get('title', 'Not'),
                    content=entry.get('content', ''),
                    tags=entry.get('tags', [])
                )
            
            paths.append(path)
        
        return paths


_obsidian_memory_instance = None


def get_obsidian_memory() -> ObsidianMemory:
    global _obsidian_memory_instance
    if _obsidian_memory_instance is None:
        _obsidian_memory_instance = ObsidianMemory()
    return _obsidian_memory_instance
