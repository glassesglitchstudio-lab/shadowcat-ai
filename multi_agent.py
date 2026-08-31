"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     SHADOWCAT — MULTI-AGENT ORKESTRASYON MOTORU                ║
║                                                               ║
║     Akıllı görev dağılımı + Paralel ajan çalıştırma          ║
║     SSE streaming + Abort desteği                            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import logging
import os
import time
from typing import AsyncGenerator, Dict, List, Optional, Any

import httpx

logger = logging.getLogger("MultiAgent")

# ═══════════════════════════════════════════════════════════════
# AJAN TANIMLARI
# ═══════════════════════════════════════════════════════════════

AGENT_REGISTRY = {
    "planner": {
        "label": "Görev Planlayıcı",
        "icon": "clipboard",
        "description": "Mesajı analiz edip alt görevlere böler",
        "always_run": True,
    },
    "analyzer": {
        "label": "Derin Analiz",
        "icon": "brain",
        "description": "Derinlemesine akıl yürütme ve sentezleme",
        "always_run": True,
    },
    "web_search": {
        "label": "Web Arama",
        "icon": "globe",
        "description": "İnternet'ten güncel bilgi toplar",
        "keywords": ["ara", "bul", "güncel", "haber", "nedir", "kimdir", "nerede",
                     "search", "find", "latest", "news", "what is", "who is",
                     "ne zaman", "kaç", "nasıl", "tarih", "fiyat", "skor"],
    },
    "memory_search": {
        "label": "Hafıza Arama",
        "icon": "database",
        "description": "Obsidian hafızadan ilgili bilgileri getirir",
        "keywords": ["hatırla", "önceki", "geçen", "daha önce", "kaydet",
                     "hafıza", "not", "memory", "remember", "previous"],
    },
    "code_gen": {
        "label": "Kod Üretici",
        "icon": "code",
        "description": "Kod yazma, hata ayıklama, refactor",
        "keywords": ["yaz", "kod", "kodla", "fonksiyon", "program", "script",
                     "python", "javascript", "html", "css", "api", "backend",
                     "frontend", "debug", "hata", "fix", "class", "function",
                     "def ", "import", "react", "vue", "node", "sql", "json"],
    },
    "translator": {
        "label": "Çevirmen",
        "icon": "languages",
        "description": "Dil algılama ve çeviri",
        "keywords": ["çevir", "çeviri", "translate", "ingilizce", "türkçe",
                     "english", "turkish", "almanca", "fransızca", "ispanyolca"],
    },
    "skill_matcher": {
        "label": "Yetenek Eşleştirici",
        "icon": "sparkles",
        "description": "En uygun skill paketini bulur",
        "keywords": ["site", "web sitesi", "arayüz", "tasarım", "tailwind",
                     "animasyon", "glassmorphism", "ui", "ux", "responsive"],
    },
}


# ═══════════════════════════════════════════════════════════════
# MULTI-AGENT ENGINE
# ═══════════════════════════════════════════════════════════════

class MultiAgentEngine:
    """Çok ajanlı orkestrasyon motoru — paralel çalışma, SSE streaming, abort desteği"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.default_model = os.getenv("DEFAULT_MODEL", "glassesglitchstudio/x_opus:V1_X_OPUS")
        self._active_sessions: Dict[str, asyncio.Event] = {}
        logger.info("MultiAgentEngine başlatıldı")

    # ─── GÖREV SINIFLANDIRMA ───────────────────────────────────

    def classify_task(self, message: str) -> List[str]:
        """Mesajı analiz edip hangi ajanların çalışması gerektiğini belirle"""
        msg_lower = message.lower()
        agents = []

        for agent_id, config in AGENT_REGISTRY.items():
            if config.get("always_run"):
                agents.append(agent_id)
            elif "keywords" in config:
                if any(kw in msg_lower for kw in config["keywords"]):
                    agents.append(agent_id)

        # En az planner + analyzer her zaman çalışsın
        for required in ["planner", "analyzer"]:
            if required not in agents:
                agents.append(required)

        return agents

    # ─── ANA ORKESTRASYON ──────────────────────────────────────

    async def run(
        self,
        message: str,
        session_id: str = "default",
        model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Multi-Agent orkestrasyon — SSE event stream döner.
        
        Events:
          {"type":"plan","agents":[...]}
          {"type":"agent_start","agent":"...","label":"..."}
          {"type":"agent_done","agent":"...","result":"...","elapsed":1.2}
          {"type":"token","content":"..."}
          {"type":"done","full_response":"..."}
          {"type":"error","message":"..."}
        """
        abort_event = asyncio.Event()
        self._active_sessions[session_id] = abort_event
        use_model = model or self.default_model

        try:
            # 1) Görev sınıflandırma
            selected_agents = self.classify_task(message)
            agent_infos = []
            for aid in selected_agents:
                reg = AGENT_REGISTRY.get(aid, {})
                agent_infos.append({
                    "id": aid,
                    "label": reg.get("label", aid),
                    "icon": reg.get("icon", "bot"),
                })
            yield self._sse({"type": "plan", "agents": agent_infos})

            if abort_event.is_set():
                yield self._sse({"type": "error", "message": "İptal edildi"})
                return

            # 2) Ajanları paralel çalıştır
            tasks = {}
            for aid in selected_agents:
                reg = AGENT_REGISTRY.get(aid, {})
                yield self._sse({
                    "type": "agent_start",
                    "agent": aid,
                    "label": reg.get("label", aid),
                })
                tasks[aid] = self._run_agent(aid, message, use_model, abort_event)

            # Paralel çalıştır
            results_list = await asyncio.gather(
                *[tasks[aid] for aid in selected_agents],
                return_exceptions=True
            )

            # 3) Sonuçları topla ve progress event'leri gönder
            results = {}
            for aid, result in zip(selected_agents, results_list):
                if abort_event.is_set():
                    yield self._sse({"type": "error", "message": "İptal edildi"})
                    return

                if isinstance(result, Exception):
                    logger.warning(f"Ajan {aid} hata: {result}")
                    results[aid] = ""
                    yield self._sse({
                        "type": "agent_done",
                        "agent": aid,
                        "result": "",
                        "error": str(result),
                        "elapsed": 0,
                    })
                else:
                    results[aid] = result.get("text", "")
                    yield self._sse({
                        "type": "agent_done",
                        "agent": aid,
                        "result": result.get("text", "")[:200],
                        "elapsed": result.get("elapsed", 0),
                    })

            if abort_event.is_set():
                yield self._sse({"type": "error", "message": "İptal edildi"})
                return

            # 4) Sonuçları birleştir ve token-by-token stream et
            combined = await self._combine_results(message, results, use_model, abort_event)

            if abort_event.is_set():
                yield self._sse({"type": "error", "message": "İptal edildi"})
                return

            # Token-by-token streaming
            full_response = ""
            async for token in self._stream_text(combined, use_model, abort_event):
                if abort_event.is_set():
                    break
                full_response += token
                yield self._sse({"type": "token", "content": token})

            if not full_response:
                full_response = combined

            yield self._sse({"type": "done", "full_response": full_response})

        except asyncio.CancelledError:
            yield self._sse({"type": "error", "message": "İptal edildi"})
        except Exception as e:
            logger.error(f"MultiAgent orkestrasyon hatası: {e}")
            yield self._sse({"type": "error", "message": str(e)})
        finally:
            self._active_sessions.pop(session_id, None)

    # ─── ABORT ─────────────────────────────────────────────────

    def abort(self, session_id: str = "default") -> bool:
        """Çalışan bir multi-agent oturumunu iptal et"""
        event = self._active_sessions.get(session_id)
        if event:
            event.set()
            logger.info(f"Multi-agent session {session_id} iptal edildi")
            return True
        return False

    # ─── AJAN ÇALIŞTIRICILAR ───────────────────────────────────

    async def _run_agent(
        self,
        agent_id: str,
        message: str,
        model: str,
        abort_event: asyncio.Event
    ) -> dict:
        """Tek bir ajanı çalıştır"""
        start = time.time()

        runner_map = {
            "planner": self._agent_planner,
            "analyzer": self._agent_analyzer,
            "web_search": self._agent_web_search,
            "memory_search": self._agent_memory_search,
            "code_gen": self._agent_code_gen,
            "translator": self._agent_translator,
            "skill_matcher": self._agent_skill_matcher,
        }

        runner = runner_map.get(agent_id, self._agent_fallback)
        text = await runner(message, model, abort_event)
        elapsed = round(time.time() - start, 2)

        return {"text": text, "elapsed": elapsed, "agent": agent_id}

    async def _agent_planner(self, message: str, model: str, abort: asyncio.Event) -> str:
        """Görev planlayıcı — mesajı alt görevlere böler"""
        prompt = (
            f'Kullanıcı mesajı: "{message}"\n\n'
            "Bu mesajı kısaca analiz et:\n"
            "1. Ne tür bir istek/soru?\n"
            "2. Hangi adımlar gerekli?\n"
            "3. Kısa plan (2-3 madde)\n\n"
            "Kısa ve öz yanıt ver (3-4 cümle)."
        )
        return await self._ollama_generate(prompt, model, abort, num_predict=300)

    async def _agent_analyzer(self, message: str, model: str, abort: asyncio.Event) -> str:
        """Derin analiz ajanı"""
        prompt = (
            f'Kullanıcı şunu sordu: "{message}"\n\n'
            "Detaylı ve faydalı bir yanıt ver. "
            "Türkçe yanıt ver, açık ve anlaşılır ol. "
            "Gerekiyorsa örnekler ver."
        )
        return await self._ollama_generate(prompt, model, abort, num_predict=1500)

    async def _agent_web_search(self, message: str, model: str, abort: asyncio.Event) -> str:
        """Web arama ajanı — DuckDuckGo"""
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": message, "format": "json", "no_html": 1, "skip_disambig": 1},
                    headers={"User-Agent": "ShadowcatAI-MultiAgent/2.0"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = data.get("AbstractText", "") or ""
                    source = data.get("AbstractSource", "") or ""
                    if abstract:
                        result = abstract[:600]
                        if source:
                            result += f"\nKaynak: {source}"
                        return result

                    topics = data.get("RelatedTopics", [])
                    if topics:
                        lines = []
                        for t in topics[:3]:
                            if isinstance(t, dict):
                                text = t.get("Text", "") or t.get("Result", "") or ""
                                if text:
                                    lines.append(text[:200])
                        if lines:
                            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Web search hatası: {e}")
        return ""

    async def _agent_memory_search(self, message: str, model: str, abort: asyncio.Event) -> str:
        """Hafıza arama ajanı — Obsidian Memory"""
        try:
            from shadowcat_core import get_core
            core = get_core()
            if core.memory:
                results = core.memory.recall(message, max_results=5)
                if results:
                    parts = []
                    seen = set()
                    for r in results:
                        path = r.get("path", "")
                        if path in seen:
                            continue
                        seen.add(path)
                        preview = r.get("content_preview", "")[:200].replace("\n", " ").strip()
                        if preview:
                            parts.append(preview)
                    if parts:
                        return "\n".join(parts[:3])
        except Exception as e:
            logger.warning(f"Memory search hatası: {e}")
        return ""

    async def _agent_code_gen(self, message: str, model: str, abort: asyncio.Event) -> str:
        """Kod üretim ajanı"""
        prompt = (
            f'Kullanıcı istedi: "{message}"\n\n'
            "Sadece kod üret. Kısa açıklama ekle.\n"
            "Uygun dilde (python, javascript, html vb.) ```kod bloğu``` içinde döndür."
        )
        return await self._ollama_generate(prompt, model, abort, num_predict=1200)

    async def _agent_translator(self, message: str, model: str, abort: asyncio.Event) -> str:
        """Çeviri ajanı"""
        prompt = (
            f'Kullanıcı mesajı: "{message}"\n\n'
            "1. Kaynak ve hedef dili tespit et\n"
            "2. Çeviriyi yap\n"
            "3. Sadece çevrilen metni döndür"
        )
        return await self._ollama_generate(prompt, model, abort, num_predict=500)

    async def _agent_skill_matcher(self, message: str, model: str, abort: asyncio.Event) -> str:
        """Skill eşleştirme ajanı"""
        msg_lower = message.lower()
        skills_db = [
            ("site-builder", ["site", "web sitesi", "web sayfası", "arayüz", "tasarım"], "Web sitesi ve arayüz geliştirme"),
            ("tailwind-css", ["tailwind", "responsive tasarım", "css framework"], "Utility-first CSS framework"),
            ("ui-pro-max", ["animasyon", "glassmorphism", "neon stil", "ui"], "Animasyon motorları"),
            ("ui-ux-pro-max", ["ui/ux", "tasarım zekası", "kullanıcı deneyimi"], "Tasarım zekası"),
        ]
        matches = []
        for sid, keywords, desc in skills_db:
            if any(k in msg_lower for k in keywords):
                matches.append(f"**{sid}** — {desc}")
        if matches:
            return "Eşleşen skill'ler:\n" + "\n".join(matches[:3])
        return ""

    async def _agent_fallback(self, message: str, model: str, abort: asyncio.Event) -> str:
        """Bilinmeyen ajan tipi için fallback"""
        return ""

    # ─── SONUÇ BİRLEŞTİRME ────────────────────────────────────

    async def _combine_results(
        self,
        message: str,
        results: Dict[str, str],
        model: str,
        abort_event: asyncio.Event
    ) -> str:
        """Alt ajan sonuçlarını birleştirip tutarlı yanıta dönüştür"""

        # Boş olmayan sonuçları topla
        non_empty = {k: v for k, v in results.items() if v and v.strip()}

        if not non_empty:
            # Hiçbir ajan sonuç döndürmediyse doğrudan AI'ya sor
            return await self._ollama_generate(message, model, abort_event, num_predict=1500)

        # Analyzer sonucu ana yanıt olarak kullan
        analyzer_result = non_empty.get("analyzer", "")

        # Eğer sadece analyzer varsa, direkt döndür
        if len(non_empty) == 1 and "analyzer" in non_empty:
            return analyzer_result

        # Birden fazla ajan sonucu varsa, sentezle
        context_parts = []

        if "planner" in non_empty:
            context_parts.append(f"**Plan:** {non_empty['planner'][:300]}")

        if "web_search" in non_empty:
            context_parts.append(f"**Web'den:** {non_empty['web_search'][:400]}")

        if "memory_search" in non_empty:
            context_parts.append(f"**Hafızadan:** {non_empty['memory_search'][:300]}")

        if "code_gen" in non_empty:
            context_parts.append(f"**Kod:**\n{non_empty['code_gen'][:600]}")

        if "translator" in non_empty:
            context_parts.append(f"**Çeviri:** {non_empty['translator'][:400]}")

        if "skill_matcher" in non_empty:
            context_parts.append(f"**Skill:** {non_empty['skill_matcher'][:200]}")

        context = "\n\n".join(context_parts)

        # Sentez prompt
        synthesis_prompt = (
            f'Kullanıcı sorusu: "{message}"\n\n'
            f"Alt ajanlardan gelen bilgiler:\n{context}\n\n"
            "Yukarıdaki bilgileri sentezleyerek kullanıcıya tek, tutarlı, doğal bir yanıt yaz. "
            "Markdown formatı kullan. Türkçe yanıt ver. "
            "Gereksiz tekrarlardan kaçın, özlü ve faydalı ol."
        )

        synthesized = await self._ollama_generate(
            synthesis_prompt, model, abort_event, num_predict=2000
        )

        return synthesized if synthesized else analyzer_result

    # ─── OLLAMA İLETİŞİM ──────────────────────────────────────

    async def _ollama_generate(
        self,
        prompt: str,
        model: str,
        abort_event: asyncio.Event,
        num_predict: int = 1500
    ) -> str:
        """Ollama'ya senkron (non-streaming) istek gönder"""
        if abort_event.is_set():
            return ""

        try:
            base_url = (self.ollama_url or "http://localhost:11434").strip().rstrip("/")
            if base_url.endswith("/api/chat"):
                base_url = base_url[:-9]
            elif base_url.endswith("/api/generate"):
                base_url = base_url[:-13]
            target_url = f"{base_url.rstrip('/')}/api/chat"

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    target_url,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"num_predict": num_predict, "temperature": 0.7},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.warning(f"Ollama generate hatası: {e}")
        return ""

    async def _stream_text(
        self,
        text: str,
        model: str,
        abort_event: asyncio.Event
    ) -> AsyncGenerator[str, None]:
        """Önceden üretilmiş metni token-by-token stream et
        
        Not: Sentez sonucu zaten hazır olduğu için burada metni
        küçük parçalara bölerek frontend'e akıtıyoruz.
        Gerçek Ollama streaming /chat endpoint'inde yapılıyor.
        """
        words = text.split(" ")
        for i, word in enumerate(words):
            if abort_event.is_set():
                return
            token = word if i == 0 else " " + word
            yield token
            await asyncio.sleep(0.008)

    # ─── YARDIMCI ──────────────────────────────────────────────

    @staticmethod
    def _sse(data: dict) -> str:
        """SSE formatında event string döndür"""
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─── SINGLETON ERİŞİMCİ ───────────────────────────────────────

_engine: Optional[MultiAgentEngine] = None


def get_multi_agent_engine() -> MultiAgentEngine:
    """MultiAgentEngine singleton instance'ını döndür"""
    global _engine
    if _engine is None:
        _engine = MultiAgentEngine()
    return _engine
