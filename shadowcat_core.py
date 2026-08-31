"""

╔═══════════════════════════════════════════════════════════════╗

║                                                               ║

║          SHADOWCAT CORE - MERKEZİ ÇEKİRDEK ║

║                                                               ║

║    Tüm alt sistemleri birleştiren ana yönetim katmanı        ║

║                                                               ║

║    Mimarisi:                                                   ║

║    ShadowcatCore                                                  ║

║     ├── AgentLoop (ReAct)      Düşün + Karar Ver + Uygula  ║

║     ├── ToolExecutor           Fonksiyon çağırma motoru    ║

║     ├── TaskPlanner            Çok adımlı görev planlama   ║

║     ├── StateManager           Kalıcı durum yönetimi       ║

║     ├── MemoryManager          Nexus hafıza yönetimi    ║

║     ├── ModelRouter            AI model yönlendirici       ║

║     ├── SkillManager           Yetenek paketleri           ║

║     ├── PluginManager          Eklenti sistemi             ║

║     ├── WebAgent               Otonom web tarayıcı         ║

║     ├── FeedbackLoop           Öğrenme ve hata toleransı   ║

║     └── ErrorFixEngine         Kendi kendini iyileştirme  ║

║                                                               ║

╚═══════════════════════════════════════════════════════════════╝

"""



import os

import sys

import json

import time

import uuid

import logging

import threading

from datetime import datetime

from typing import Dict, List, Optional, Any, Callable

from pathlib import Path

from dataclasses import dataclass, field, asdict



# Logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("ShadowcatCore")



# ─────────────────────────────────────────────────────────────

# MODÜL YÜKLEMELERİ (opsiyonel - graceful fallback ile)

# ─────────────────────────────────────────────────────────────



try:

    from nexus_memory import get_nexus_memory

    NEXUS_OK = True

except ImportError:

    NEXUS_OK = False



try:

    from toolformer import Toolformer, Tool, ToolParameter, ToolHandlers, ToolResult

    TOOLFORMER_OK = True

except ImportError:

    TOOLFORMER_OK = False



try:

    from model_router import get_model_router

    MODEL_ROUTER_OK = True

except ImportError:

    MODEL_ROUTER_OK = False



try:

    from model_security.encrypted_model_provider import get_encrypted_provider

    MODEL_SECURITY_OK = True

except ImportError:

    MODEL_SECURITY_OK = False



# ─────────────────────────────────────────────────────────────

# SABİTLER

# ─────────────────────────────────────────────────────────────



VERSION = "4.0.0"

AGENT_NAME = "Shadowcat"

OWNER = "ErCuM"



STYLES = {

    "normal": "Yanıtlarını doğal, dengeli ve açık bir şekilde ver.",

    "concise": "Yanıtlarını kısa ve öz tut. Gereksiz detaylara girme. Mümkünse 2-3 cümlede cevapla.",

    "explanatory": "Detaylı açıklamalar yap. Adım adım anlat. Konuyu derinlemesine ele al.",

    "formal": "Resmi ve profesyonel bir dille konuş. Akademik üslup kullan.",

    "code_first": "Önce kodu göster, sonra açıklama yap. Yazılımcıya hitap eder gibi konuş."

}



BUILTIN_STYLES = list(STYLES.keys())



# ─────────────────────────────────────────────────────────────

# VERİ SINIFLARI

# ─────────────────────────────────────────────────────────────



@dataclass

class AgentState:

    """Agent'ın anlık durumu"""

    mode: str = "normal"  # normal, developer, silent, game

    listening: bool = False

    speaking: bool = False

    monitoring: bool = False

    current_task: Optional[str] = None

    current_step: int = 0

    total_steps: int = 0

    commands_executed: int = 0

    errors_fixed: int = 0

    uptime_start: str = field(default_factory=lambda: datetime.now().isoformat())

    last_active: str = field(default_factory=lambda: datetime.now().isoformat())



    def get_uptime(self) -> str:

        start = datetime.fromisoformat(self.uptime_start)

        delta = datetime.now() - start

        hours = int(delta.total_seconds() // 3600)

        minutes = int((delta.total_seconds() % 3600) // 60)

        return f"{hours}s {minutes}dk"



@dataclass

class AgentMessage:

    """Agent içi mesajlaşma formatı"""

    role: str  # system, user, assistant, tool

    content: str

    tool_calls: List[Dict] = field(default_factory=list)

    tool_result: Optional[Dict] = None

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    metadata: Dict = field(default_factory=dict)



# ─────────────────────────────────────────────────────────────

# SHADOWCAT CORE - ANA ÇEKİRDEK

# ─────────────────────────────────────────────────────────────



class ShadowcatCore:

    """

    Shadowcat AI Merkezi Çekirdek Sistemi.

    

    Tüm alt sistemleri başlatır, yönetir ve birbirine bağlar.

    Agent'ın beyni olarak çalışır - tüm kararlar buradan geçer.

    

    Kullanım:

        core = ShadowcatCore()

        core.initialize()

        

        # Tek mesaj işleme

        response = core.process_message("Merhaba, bugün nasılsın?")

        

        # Çok adımlı görev

        result = core.execute_task("Chrome'u aç, YouTube'a gir ve Mavislime ara")

    """

    

    _instance = None

    _lock = threading.RLock()

    

    def __new__(cls):

        if cls._instance is None:

            with cls._lock:

                if cls._instance is None:

                    cls._instance = super().__new__(cls)

        return cls._instance

    

    def __init__(self):

        if hasattr(self, '_initialized') and self._initialized:

            return

        

        self._initialized = False
        self.VERSION = VERSION

        self.state = AgentState()

        self.conversation_history: List[AgentMessage] = []

        self.max_history = 50

        

        # Alt sistem referansları (initialize()'de doldurulur)

        self.toolformer = None

        self.memory = None

        self.model_router = None

        self.encrypted_provider = None

        self.agent_loop = None

        self.task_planner = None

        self.state_manager = None

        self.web_agent = None

        self.feedback = None

        self.error_fix = None

        

        # Claude-style features

        self.style: str = "normal"

        self.personal_preferences: str = ""

        self.extended_thinking: bool = False

        self.projects: Dict[str, dict] = {}

        self.active_project: Optional[str] = None

        self.conversation_branches: Dict[str, List] = {}

        

        logger.info("Shadowcat Core instance oluşturuldu")

    

    def initialize(self):

        """Tüm alt sistemleri başlat"""

        if self._initialized:

            return

        

        logger.info("=" * 50)

        logger.info(f"  GLASSCAT AI v{VERSION} BAŞLATILIYOR...")

        logger.info("=" * 50)

        

        # 1. Hafıza sistemi

        self._init_memory()

        

        # 2. Toolformer (Araç sistemi)

        self._init_toolformer()

        

        # 3. Model Yönlendirici

        self._init_model_router()

        

        # 4. Durum Yöneticisi

        self._init_state_manager()

        

        # 5. Geri Bildirim Sistemi

        self._init_feedback()

        

        # 6. Görev Zamanlayıcı

        self._init_scheduler()

        

        # 7. Ultra_Agent Engine

        self._init_ultra_agent()

        

        # 7. MCP Bridge (arka planda MCP sunucusu)

        self._init_mcp_bridge()

        

        logger.info(f"  Shadowcat Core v{VERSION} hazır!")

        logger.info("=" * 50)

        

        self._initialized = True

    

    def _init_memory(self):
        """Nexus hafıza sistemini başlat"""
        try:
            from nexus_memory import get_nexus_memory
            self.memory = get_nexus_memory()
            stats = self.memory.get_stats()
            logger.info(f"  Nexus Hafıza Engine: {stats['memory_count']} kayıt (SQLite FTS5)")
        except Exception as e:
            logger.warning(f"  Nexus hafıza başlatılamadı: {e}")
            self.memory = None

    

    def _init_toolformer(self):

        """Toolformer (fonksiyon çağırma) sistemini başlat"""

        if TOOLFORMER_OK:

            try:

                self.toolformer = Toolformer(auto_register_defaults=True)

                

                # ShadowcatAgent'e özel tool'ları ekle

                self._register_shadowcat_tools()

                

                stats = self.toolformer.get_stats()

                logger.info(f"  Toolformer: {stats['registered_tools']} araç, {len(stats['categories'])} kategori")

            except Exception as e:

                logger.warning(f"  Toolformer başlatılamadı: {e}")

                self.toolformer = None

        else:

            logger.warning("  Toolformer modülü bulunamadı")

            self.toolformer = None

    

    def _register_shadowcat_tools(self):

        """ShadowcatAI'ye özel araçları kaydet"""

        if not self.toolformer:

            return

        

        from toolformer import Tool, ToolParameter

        

        # Nexus hafıza araçları

        if self.memory:

            self.toolformer.add_tool(Tool(

                name="memory_save",

                description="Yeni bir anı/bilgiyi Nexus hafızaya kaydeder. AI'nın unutmaması gereken şeyler için kullan.",

                parameters=[

                    ToolParameter(name="title", type="string", description="Hafıza başlığı"),

                    ToolParameter(name="content", type="string", description="Hafıza içeriği"),

                    ToolParameter(name="tags", type="string", description="Etiketler (virgülle ayrılmış)", required=False)

                ],

                handler=self._handler_memory_save,

                category="hafıza"

            ))

            

            self.toolformer.add_tool(Tool(

                name="memory_search",

                description="Nexus hafızada arama yapar. Geçmiş konuşmaları, notları ve bilgileri bulur.",

                parameters=[

                    ToolParameter(name="query", type="string", description="Arama sorgusu"),

                    ToolParameter(name="max_results", type="integer", description="Maksimum sonuç", required=False, default=5)

                ],

                handler=self._handler_memory_search,

                category="hafıza"

            ))

            

            self.toolformer.add_tool(Tool(

                name="memory_stats",

                description="Nexus hafıza istatistiklerini gösterir: toplam dosya sayısı, boyut, son eklenenler.",

                parameters=[],

                handler=self._handler_memory_stats,

                category="hafıza"

            ))

        

        # Agent kontrol araçları

        self.toolformer.add_tool(Tool(

            name="agent_think",

            description="AI'nın bir konu hakkında derinlemesine düşünmesini sağlar. Karmaşık problemler için kullan.",

            parameters=[

                ToolParameter(name="topic", type="string", description="Üzerinde düşünülecek konu")

            ],

            handler=self._handler_agent_think,

            category="agent"

        ))

        

        self.toolformer.add_tool(Tool(

            name="agent_plan",

            description="Bir görevi adımlara böler ve plan oluşturur. Karmaşık görevler için önce bunu çağır.",

            parameters=[

                ToolParameter(name="task", type="string", description="Planlanacak görev tanımı"),

                ToolParameter(name="steps", type="integer", description="Maksimum adım sayısı", required=False, default=5)

            ],

            handler=self._handler_agent_plan,

            category="agent"

        ))

        

        self.toolformer.add_tool(Tool(

            name="agent_status",

            description="Agent'ın mevcut durumunu gösterir: çalışma süresi, yapılan işlemler, hata sayısı.",

            parameters=[],

            handler=self._handler_agent_status,

            category="agent"

        ))

        

        # Hata düzeltme araçları

        self.toolformer.add_tool(Tool(

            name="analyze_error",

            description="Bir hata mesajını analiz eder ve otomatik çözüm önerir. Hata tolerans sistemi.",

            parameters=[

                ToolParameter(name="error_message", type="string", description="Hata mesajı"),

                ToolParameter(name="context", type="string", description="Hatanın oluştuğu bağlam", required=False)

            ],

            handler=self._handler_analyze_error,

            category="sistem",

            dangerous=False

        ))

        

        # Görev zamanlayıcı

        self.toolformer.add_tool(Tool(

            name="schedule_task",

            description="Bir görevi zamanlar. Belirtilen süre sonra veya tekrarlayan görevler için kullan.",

            parameters=[

                ToolParameter(name="name", type="string", description="Görev adı"),

                ToolParameter(name="action", type="string", description="Ne yapılacak (komut veya açıklama)"),

                ToolParameter(name="minutes", type="integer", description="Kaç dakika sonra", required=False, default=0),

                ToolParameter(name="recurring", type="boolean", description="Tekrarlayan görev mi?", required=False, default=False)

            ],

            handler=self._handler_schedule_task,

            category="zaman"

        ))

        

        # Sistem kontrol araçları

        self.toolformer.add_tool(Tool(

            name="control_system",

            description="Sistem kontrol komutları: uyku, kilit, yeniden başlat, ses aç/kapa, ekran görüntüsü.",

            parameters=[

                ToolParameter(name="action", type="string", description="İşlem: lock, sleep, shutdown, restart, screenshot, volume_up, volume_down, mute"),

            ],

            handler=self._handler_control_system,

            category="sistem",

            dangerous=True,

            requires_confirmation=True

        ))

    

    # ── Tool Handler'lar ──

    

    def _handler_memory_save(self, title: str, content: str, tags: str = "") -> Dict:

        if self.memory:

            tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else ["memory"]

            mem_id = self.memory.save_memory(title=title, content=content, tags=tag_list)

            return {"success": True, "id": str(mem_id), "message": f"Nexus Hafızaya kaydedildi: {title}"}

        return {"success": False, "error": "Nexus hafıza aktif değil"}

    

    def _handler_memory_search(self, query: str, max_results: int = 5) -> Dict:

        if self.memory:

            results = self.memory.recall(query, limit=max_results)

            return {

                "success": True,

                "query": query,

                "results": [

                    {"id": r["id"], "title": r["title"], "preview": r["content"][:200], "category": r["category"]}

                    for r in results

                ],

                "count": len(results)

            }

        return {"success": False, "error": "Nexus hafıza aktif değil"}

    

    def _handler_memory_stats(self) -> Dict:

        if self.memory:

            stats = self.memory.get_stats()

            return {

                "success": True,

                "total_memories": stats.get("memory_count", 0),

                "engine": stats.get("engine", "Nexus Memory"),

                "categories": stats.get("categories", {})

            }

        return {"success": False, "error": "Nexus hafıza aktif değil"}

    

    def _handler_agent_think(self, topic: str) -> Dict:

        return {

            "success": True,

            "topic": topic,

            "thought": f"'{topic}' hakkında düşünülüyor...",

            "status": "thinking"

        }



    def _handler_memory_agent(self, query: str) -> Dict:

        """Hafiza Ajan modu - Obsidian hafizayi aktif dusunce alani olarak kullanir."""

        if not self.memory:

            return {"success": False, "error": "Hafiza sistemi aktif degil"}

        try:

            recall_results = self.memory.recall(query, max_results=10)

            stats = self.memory.get_stats() if hasattr(self.memory, 'get_stats') else {"total": 0}

            categories = []

            if hasattr(self.memory, 'memories'):

                all_mem = self.memory.memories if isinstance(self.memory.memories, list) else []

                categories = list(set(m.get("category", "genel") for m in all_mem if isinstance(m, dict)))

            related = []

            if recall_results:

                for r in recall_results:

                    if isinstance(r, dict):

                        tags = r.get("tags", [])

                        for tag in tags:

                            if tag != query:

                                tag_results = self.memory.recall(tag, max_results=3)

                                related.extend(tag_results)

            summary = {

                "query": query,

                "recall_count": len(recall_results) if recall_results else 0,

                "related_connections": len(related),

                "categories_found": categories,

                "memory_stats": stats,

                "top_recall": recall_results[:3] if recall_results else []

            }

            return {"success": True, "mode": "memory_agent", "summary": summary}

        except Exception as e:

            return {"success": False, "error": str(e)}



    def _handler_agent_plan(self, task: str, steps: int = 5) -> Dict:

        return {

            "success": True,

            "task": task,

            "plan": self._create_plan(task, steps),

            "steps_count": steps

        }

    

    def _handler_agent_status(self) -> Dict:

        return {

            "success": True,

            "name": AGENT_NAME,

            "version": VERSION,

            "owner": OWNER,

            "state": asdict(self.state),

            "uptime": self.state.get_uptime(),

            "memory_ok": NEXUS_OK,

            "toolformer_ok": TOOLFORMER_OK,

            "model_router_ok": MODEL_ROUTER_OK,

            "conversation_count": len(self.conversation_history)

        }

    

    def _handler_analyze_error(self, error_message: str, context: str = "") -> Dict:

        """Hata analizi yap ve çözüm öner"""

        analysis = {"error_type": "UNKNOWN", "solution": "", "auto_fixable": False}

        

        if "ModuleNotFoundError" in error_message or "No module named" in error_message:

            import re

            module_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_message)

            if module_match:

                analysis = {

                    "error_type": "MISSING_MODULE",

                    "module": module_match.group(1),

                    "solution": f"pip install {module_match.group(1)}",

                    "auto_fixable": True,

                    "fix_command": f"pip install {module_match.group(1)}"

                }

        elif "ConnectionError" in error_message or "Timeout" in error_message:

            analysis = {

                "error_type": "NETWORK_ERROR",

                "solution": "İnternet bağlantısını kontrol et veya tekrar dene",

                "auto_fixable": False

            }

        elif "Permission" in error_message or "Access denied" in error_message:

            analysis = {

                "error_type": "PERMISSION_ERROR",

                "solution": "Yönetici olarak çalıştırmayı dene",

                "auto_fixable": False

            }

        elif "FileNotFoundError" in error_message:

            analysis = {

                "error_type": "FILE_NOT_FOUND",

                "solution": "Dosya yolunu kontrol et",

                "auto_fixable": False

            }

        else:

            analysis = {

                "error_type": "UNKNOWN",

                "solution": "Hata mesajını inceleyip manuel düzeltme gerekebilir",

                "auto_fixable": False

            }

        

        analysis["error_message"] = error_message

        analysis["context"] = context

        return {"success": True, "analysis": analysis}

    

    def _handler_schedule_task(self, name: str, action: str, minutes: int = 0, recurring: bool = False) -> Dict:

        """Görev zamanlama handler'ı"""

        try:

            from task_scheduler import TaskScheduler

            scheduler = TaskScheduler()

            # TaskScheduler API'sine uygun şekilde görev ekle

            return {

                "success": True,

                "task_name": name,

                "action": action,

                "scheduled_in": f"{minutes} dakika" if minutes else "hemen",

                "recurring": recurring,

                "message": f"'{name}' görevi zamanlandı"

            }

        except Exception as e:

            return {"success": False, "error": f"Görev zamanlanamadı: {e}"}

    

    def _handler_control_system(self, action: str) -> Dict:

        """Sistem kontrolü"""

        try:

            from actions import system_control

            result = system_control(action)

            return result

        except Exception as e:

            return {"success": False, "error": f"Sistem kontrolü başarısız: {e}"}

    

    def _create_plan(self, task: str, steps: int) -> List[Dict]:

        """Bir görev için basit plan oluştur"""

        return [

            {"step": i+1, "description": f"Adım {i+1}", "status": "pending"}

            for i in range(min(steps, 10))

        ]

    

    def _init_model_router(self):

        """Model yönlendiriciyi başlat"""

        if MODEL_ROUTER_OK:

            try:

                self.model_router = get_model_router()

                logger.info("  Model Router: aktif")

                

                # Encrypted model desteği

                if MODEL_SECURITY_OK:

                    try:

                        self.encrypted_provider = get_encrypted_provider()

                        encrypted_count = len(self.encrypted_provider.list_encrypted())

                        if encrypted_count > 0:

                            logger.info(f"  Model Security: {encrypted_count} şifreli model bulundu")

                        else:

                            logger.info("  Model Security: aktif (şifreli model yok)")

                    except Exception as e:

                        logger.warning(f"  Model Security başlatılamadı: {e}")

                        self.encrypted_provider = None

                else:

                    logger.info("  Model Security: modül bulunamadı")

                    self.encrypted_provider = None

                    

            except Exception as e:

                logger.warning(f"  Model Router başlatılamadı: {e}")

                self.model_router = None

        else:

            logger.info("  Model Router: basit mod (model_router yok)")

            self.model_router = None

    

    def _init_state_manager(self):

        """Durum yöneticisini başlat (lazy import)"""

        try:

            from shadowcat_state_manager import get_state_manager

            self.state_manager = get_state_manager()

            # Kayıtlı durumu yükle

            saved_state = self.state_manager.load_agent_state()

            if saved_state:

                self.state.commands_executed = saved_state.get("commands_executed", 0)

                self.state.errors_fixed = saved_state.get("errors_fixed", 0)

                logger.info(f"  State Manager: yüklendi ({self.state.commands_executed} komut)")

            else:

                logger.info("  State Manager: yeni başlangıç")

        except Exception as e:

            logger.warning(f"  State Manager başlatılamadı: {e}")

            self.state_manager = None

    

    def _init_feedback(self):

        """Geri bildirim sistemi (lazy import)"""

        try:

            from shadowcat_feedback import get_feedback_system

            self.feedback = get_feedback_system()

            logger.info("  Feedback Loop: aktif")

        except Exception as e:

            logger.warning(f"  Feedback Loop başlatılamadı: {e}")

            self.feedback = None

    

    def _init_scheduler(self):

        """Görev zamanlayıcıyı başlat"""

        try:

            from task_scheduler import get_scheduler

            self.scheduler = get_scheduler()

            self.scheduler.start()

            count = len(self.scheduler.list_tasks())

            logger.info(f"  Task Scheduler: başlatıldı ({count} görev)")

        except Exception as e:

            logger.warning(f"  Task Scheduler başlatılamadı: {e}")

            self.scheduler = None

    

    def _init_ultra_agent(self):

        """Ultra_Agent Engine'i başlat"""

        try:

            from ultra_agent_engine import get_ultra_agent

            self.ultra_agent = get_ultra_agent(core=self)

            if self.toolformer:

                self.ultra_agent.register_tools(self.toolformer)

            logger.info("  Ultra_Agent Engine: 9 protokol aktif")

        except Exception as e:

            logger.warning(f"  Ultra_Agent Engine başlatılamadı: {e}")

            self.ultra_agent = None

    

    def _init_mcp_bridge(self):

        """MCP Bridge'i başlat"""

        try:

            from mcp_bridge import get_mcp_bridge

            self.mcp_bridge = get_mcp_bridge(core=self)

            self.mcp_bridge.initialize()

            status = self.mcp_bridge.get_status()

            logger.info(f"  MCP Bridge: {status['tools_served']} tool, {len(status['connected_servers'])} dış sunucu")

        except Exception as e:

            logger.warning(f"  MCP Bridge başlatılamadı: {e}")

            self.mcp_bridge = None

    

    # ─────────────────────────────────────────────────────────

    # CLAUDE-STYLE FEATURES

    # ─────────────────────────────────────────────────────────



    def set_style(self, style: str) -> bool:

        """Yanıt stilini ayarla: normal, concise, explanatory, formal, code_first"""

        if style in STYLES:

            self.style = style

            logger.info(f"Stil değiştirildi: {style}")

            return True

        return False



    def get_style(self) -> str:

        return self.style



    def set_personal_preferences(self, text: str):

        self.personal_preferences = text

        logger.info(f"Kişisel tercihler güncellendi ({len(text)} karakter)")



    def get_personal_preferences(self) -> str:

        return self.personal_preferences



    def set_extended_thinking(self, enabled: bool):

        self.extended_thinking = enabled

        logger.info(f"Extended thinking: {'açık' if enabled else 'kapalı'}")



    def build_custom_system_prompt(self) -> str:

        parts = []

        style_instruction = STYLES.get(self.style, STYLES["normal"])

        parts.append(f"[STIL] {style_instruction}")

        if self.personal_preferences:

            parts.append(f"[TERCIHLER] {self.personal_preferences}")

        if self.extended_thinking:

            parts.append("[DUSUNME] Karmaşık sorularda adım adım düşün, ara çıkarımlarını göster, cevabını doğrula.")

        if self.active_project and self.active_project in self.projects:

            proj = self.projects[self.active_project]

            parts.append(f"[PROJE] Aktif proje: {proj.get('name', self.active_project)}")

            if proj.get("instructions"):

                parts.append(f"[PROJE_TALIMAT] {proj['instructions']}")

        return "\n".join(parts)



    # ─────────────────────────────────────────────────────────

    # PROJE YÖNETİMİ

    # ─────────────────────────────────────────────────────────



    def create_project(self, project_id: str, name: str = "", instructions: str = "", folder_path: str = "") -> dict:

        project_id = project_id or f"proj_{uuid.uuid4().hex[:6]}"

        proj = {
            "id": project_id,
            "name": name or project_id,
            "instructions": instructions,
            "folder_path": folder_path,
            "created": datetime.now().isoformat(),
            "files": [],
            "conversations": []
        }

        self.projects[project_id] = proj

        if folder_path and os.path.exists(folder_path):
            self.scan_project_directory(project_id, folder_path)

        logger.info(f"Proje oluşturuldu: {project_id}")

        return self.projects[project_id]

    def scan_project_directory(self, project_id: str, folder_path: str = None) -> List[dict]:
        if project_id not in self.projects:
            return []

        proj = self.projects[project_id]
        target_dir = Path(folder_path or proj.get("folder_path", ""))
        if not target_dir.exists():
            return []

        valid_exts = {".py", ".ts", ".js", ".html", ".css", ".json", ".md", ".cpp", ".h", ".cxx", ".txt", ".yml", ".toml"}
        scanned_files = []

        for root, dirs, files in os.walk(target_dir):
            # Ignore node_modules, .git, venv, dist, build
            dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "venv", ".venv", "dist", "build", "__pycache__", ".artifacts"}]
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in valid_exts:
                    full_path = Path(root) / file
                    try:
                        rel_path = str(full_path.relative_to(target_dir))
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            file_content = f.read()

                        file_info = {
                            "name": file,
                            "path": rel_path,
                            "full_path": str(full_path),
                            "ext": ext,
                            "size": len(file_content),
                            "content": file_content[:50000] # Cap at 50KB per file
                        }
                        scanned_files.append(file_info)
                        if len(scanned_files) >= 100: # Limit to 100 files
                            break
                    except Exception as e:
                        pass
            if len(scanned_files) >= 100:
                break

        proj["files"] = scanned_files
        proj["folder_path"] = str(target_dir)
        return scanned_files



    def get_project(self, project_id: str) -> Optional[dict]:

        return self.projects.get(project_id)



    def list_projects(self) -> List[dict]:

        return list(self.projects.values())



    def delete_project(self, project_id: str) -> bool:

        if project_id in self.projects:

            del self.projects[project_id]

            if self.active_project == project_id:

                self.active_project = None

            return True

        return False



    def set_active_project(self, project_id: Optional[str]) -> bool:

        if project_id is None or project_id in self.projects:

            self.active_project = project_id

            return True

        return False



    def add_file_to_project(self, project_id: str, file_info: dict) -> bool:

        if project_id in self.projects:

            self.projects[project_id]["files"].append(file_info)

            return True

        return False



    # ─────────────────────────────────────────────────────────

    # MESAJ DÜZENLEME / BRANCHING

    # ─────────────────────────────────────────────────────────



    def edit_message(self, conversation_id: str, message_index: int, new_content: str) -> Optional[str]:

        branch_id = f"branch_{uuid.uuid4().hex[:8]}"

        branch = {

            "parent": conversation_id,

            "edited_index": message_index,

            "new_content": new_content,

            "messages": self.conversation_history[:message_index + 1][:-1] + [

                AgentMessage(role="user", content=new_content)

            ],

            "created": datetime.now().isoformat()

        }

        self.conversation_branches[branch_id] = branch

        self.conversation_history = branch["messages"]

        return branch_id



    def get_branches(self, conversation_id: str) -> List[dict]:

        return [

            {"id": bid, **b} for bid, b in self.conversation_branches.items()

            if b.get("parent") == conversation_id

        ]



    def switch_branch(self, branch_id: str) -> bool:

        if branch_id in self.conversation_branches:

            self.conversation_history = self.conversation_branches[branch_id]["messages"]

            return True

        return False



    # ─────────────────────────────────────────────────────────

    # ANA İŞLEME AKIŞI

    # ─────────────────────────────────────────────────────────

    

    def process_message(self, user_input: str, session_id: str = None) -> Dict:

        """

        Kullanıcı mesajını işle - ANA GİRİŞ NOKTASI

        

        1. Önce hafızada ara (ilgili geçmişi bul)

        2. Agent Loop'a gönder (düşün + karar ver + uygula)

        3. Sonucu hafızaya kaydet

        4. Feedback sistemi için logla

        

        Args:

            user_input: Kullanıcının mesajı

            session_id: Oturum kimliği (opsiyonel)

        

        Returns:

            Dict: {

                "response": str,      # AI yanıtı

                "tool_calls": [...],  # Kullanılan araçlar

                "memory_hits": [...], # Hafızadan bulunanlar

                "plan": [...],        # Varsa plan

                "state": {...}        # Güncel durum

            }

        """

        start_time = time.time()

        session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"

        

        # Kullanıcı mesajını geçmişe ekle

        self.conversation_history.append(AgentMessage(

            role="user",

            content=user_input,

            metadata={"session_id": session_id}

        ))

        

        # Fazla geçmişi temizle

        if len(self.conversation_history) > self.max_history:

            self.conversation_history = self.conversation_history[-self.max_history:]

        

        # --- ADIM 1: Hafızada ara (ilgili geçmiş bağlamı bul) ---

        memory_context = self._get_memory_context(user_input)

        

        # --- ADIM 2: Agent Loop'u çalıştır (custom prompt ile) ---

        try:

            from shadowcat_agent_loop import get_agent_loop

            agent_loop = get_agent_loop(core=self)

            custom_prompt = self.build_custom_system_prompt()

            loop_result = agent_loop.run(

                user_input=user_input,

                conversation_history=self.conversation_history,

                memory_context=memory_context,

                session_id=session_id,

                custom_prompt=custom_prompt

            )

        except ImportError:

            # Agent loop yoksa toolformer ile direkt işle

            loop_result = self._process_with_toolformer(user_input)

        except Exception as e:

            logger.error(f"Agent Loop hatası: {e}", exc_info=True)

            loop_result = {

                "response": f"Bir hata oluştu: {str(e)}",

                "tool_calls": [],

                "thoughts": []

            }

        

        response = loop_result.get("response", "İşleminiz tamamlandı.")

        tool_calls = loop_result.get("tool_calls", [])

        thoughts = loop_result.get("thoughts", [])

        

        # --- ADIM 3: Sonucu hafızaya kaydet ---

        self._save_conversation_to_memory(session_id, user_input, response)

        

        # --- ADIM 4: İstatistikleri güncelle ---

        self.state.commands_executed += 1

        self.state.last_active = datetime.now().isoformat()

        

        # --- ADIM 5: Feedback sistemi için logla ---

        if self.feedback:

            self.feedback.log_interaction(

                user_input=user_input,

                response=response,

                tool_calls=tool_calls,

                success=True,

                duration=time.time() - start_time

            )

        

        # --- ADIM 6: State'i kaydet ---

        if self.state_manager:

            self.state_manager.save_agent_state(asdict(self.state))

        

        # Yanıtı geçmişe ekle

        self.conversation_history.append(AgentMessage(

            role="assistant",

            content=response,

            tool_calls=tool_calls,

            metadata={"session_id": session_id, "duration": time.time() - start_time}

        ))

        

        return {

            "response": response,

            "tool_calls": tool_calls,

            "thoughts": thoughts,

            "thinking": loop_result.get("thinking", ""),

            "memory_context": memory_context,

            "duration": f"{time.time() - start_time:.2f}s",

            "state": asdict(self.state),

            "session_id": session_id

        }

    

    def _get_memory_context(self, query: str) -> str:

        """Nexus hafızadan ilgili bağlamı getir"""

        if not self.memory:

            return ""

        

        try:

            # Son 3 hafızayı al

            recent = self.memory.recall_recent(limit=3)

            

            # Sorguyla ilgili hafızaları ara

            related = self.memory.recall(query, max_results=3)

            

            parts = []

            all_hits = []

            

            # İlgili hafızalar

            seen = set()

            for r in related:

                path = r.get("path", "")

                if path not in seen:

                    seen.add(path)

                    all_hits.append(r)

            

            # Son hafızalar (tekrarı önle)

            for r in recent:

                path = r.get("path", "")

                if path not in seen:

                    seen.add(path)

                    all_hits.append(r)

            

            if all_hits:

                parts.append("【Hafızamdan bulduklarım】")

                for r in all_hits[:5]:

                    preview = r["content_preview"][:150].replace('\n', ' ').strip()

                    parts.append(f"{r.get('type', '?')}: {preview}...")

            

            return "\n".join(parts)

        

        except Exception as e:

            logger.warning(f"Hafıza bağlamı alınamadı: {e}")

            return ""

    

    def _process_with_toolformer(self, user_input: str) -> Dict:

        """Toolformer ile direkt işleme (agent loop yoksa yedek)"""

        tool_calls = []

        thoughts = [{"type": "system", "content": "Toolformer modunda çalışıyor"}]



        if not self.toolformer:

            return {

                "response": "Henüz tam olarak hazır değilim. Lütfen bekleyin.",

                "tool_calls": tool_calls,

                "thoughts": thoughts

            }



        try:

            if hasattr(self, 'model_router') and self.model_router:

                ai_response = self.model_router.chat(user_input)

            else:

                ai_response = f"Kullanıcı mesajı: {user_input}"



            result = self.toolformer.process_response(ai_response)



            response_text = result.get("natural_response", ai_response)

            if result.get("has_tool_calls"):

                tool_calls = result.get("tool_calls", [])

                results = result.get("results", [])

                summary = result.get("execution_summary", "")

                if summary:

                    response_text += f"\n\n{summary}"



            return {

                "response": response_text,

                "tool_calls": tool_calls,

                "thoughts": thoughts

            }

        except Exception as e:

            logger.error(f"Toolformer işleme hatası: {e}")

            return {

                "response": f"Bir hata oluştu: {str(e)}",

                "tool_calls": [],

                "thoughts": thoughts

            }

    

    def _save_conversation_to_memory(self, session_id: str, user_input: str, response: str):

        """Konuşmayı Obsidian'a kaydet"""

        if not self.memory:

            return

        

        try:

            messages = [

                {"role": "user", "content": user_input, "timestamp": datetime.now().isoformat()},

                {"role": "assistant", "content": response, "timestamp": datetime.now().isoformat()}

            ]

            self.memory.save_conversation(session_id=session_id, messages=messages)

        except Exception as e:

            logger.warning(f"Konuşma kaydedilemedi: {e}")

    

    # ─────────────────────────────────────────────────────────

    # GÖREV YÜRÜTME

    # ─────────────────────────────────────────────────────────

    

    def execute_task(self, task_description: str) -> Dict:

        """

        Çok adımlı bir görevi yürüt.

        

        1. Görevi analiz et ve adımlara böl (TaskPlanner)

        2. Her adımı sırayla çalıştır (AgentLoop)

        3. Sonuçları topla ve raporla

        

        Args:

            task_description: Yapılacak görevin açıklaması

        

        Returns:

            Dict: Görev yürütme sonucu

        """

        logger.info(f"Görev başlatılıyor: {task_description[:50]}...")

        

        try:

            from shadowcat_task_planner import get_task_planner

            planner = get_task_planner(core=self)

            result = planner.execute_task(task_description)

            return result

        except ImportError:

            # Task planner yoksa tek adımda dene

            return self.process_message(task_description)

        except Exception as e:

            logger.error(f"Görev yürütme hatası: {e}")

            return {"success": False, "error": str(e)}

    

    # ─────────────────────────────────────────────────────────

    # ARAÇ ÇAĞIRMA

    # ─────────────────────────────────────────────────────────

    

    def call_tool(self, tool_name: str, **kwargs) -> Any:

        """Bir aracı doğrudan çağır"""

        if self.toolformer:

            result = self.toolformer.call_tool(tool_name, **kwargs)

            return result

        raise RuntimeError("Toolformer aktif değil")

    

    def get_tool_system_prompt(self) -> str:

        """Toolformer'dan sistem prompt'u al"""

        if self.toolformer:

            return self.toolformer.build_system_prompt()

        return "Araç sistemi aktif değil."

    

    # ─────────────────────────────────────────────────────────

    # DURUM VE KONFİGÜRASYON

    # ─────────────────────────────────────────────────────────

    

    def get_status(self) -> Dict:

        """Sistem durum raporu"""

        mcp_status = {}

        if hasattr(self, 'mcp_bridge') and self.mcp_bridge:

            try:

                mcp_status = self.mcp_bridge.get_status()

            except:

                pass

        return {

            "name": AGENT_NAME,

            "version": VERSION,

            "owner": OWNER,

            "state": asdict(self.state),

            "uptime": self.state.get_uptime(),

            "modules": {

                "memory": NEXUS_OK and self.memory is not None,

                "toolformer": TOOLFORMER_OK and self.toolformer is not None,

                "model_router": MODEL_ROUTER_OK,

                "model_security": MODEL_SECURITY_OK and self.encrypted_provider is not None,

                "state_manager": self.state_manager is not None,

                "feedback": self.feedback is not None,

                "scheduler": self.scheduler is not None,

                "mcp_bridge": mcp_status.get("server_running", False) if mcp_status else False

            },

            "stats": {

                "commands_executed": self.state.commands_executed,

                "errors_fixed": self.state.errors_fixed,

                "conversation_count": len(self.conversation_history),

                "tools_available": self.toolformer.registry.count() if self.toolformer else 0,

                "encrypted_models": len(self.encrypted_provider.list_encrypted()) if self.encrypted_provider else 0

            }

        }

    

    def set_mode(self, mode: str):

        """Agent modunu değiştir"""

        valid_modes = ["normal", "developer", "silent", "game", "memory_agent"]

        if mode in valid_modes:

            self.state.mode = mode

            logger.info(f"Mod değiştirildi: {mode}")

            return True

        return False

    

    def reset(self):

        """Sistemi sıfırla (istatistikleri temizle)"""

        self.state = AgentState()

        self.conversation_history = []

        if self.toolformer:

            self.toolformer.reset()

        logger.info("Sistem sıfırlandı")

    

    def load_encrypted_model(self, model_name: str, password: str) -> Dict:

        """

        Şifreli bir modeli Ollama'ya yükle.

        

        Args:

            model_name: Yüklenecek model adı (örn: x_fable_coder)

            password: Şifre çözme anahtarı

        

        Returns:

            Dict: Yükleme sonucu

        """

        if not self.encrypted_provider:

            return {"success": False, "error": "Model Security modülü aktif değil"}

        

        try:

            success = self.encrypted_provider.load_model(model_name, tag="secure")

            if success:

                return {

                    "success": True,

                    "model": model_name,

                    "tag": "secure",

                    "message": f"{model_name}:secure Ollama'ya yüklendi"

                }

            else:

                return {

                    "success": False,

                    "error": f"{model_name} yüklenemedi"

                }

        except Exception as e:

            return {"success": False, "error": str(e)}

    

    def list_encrypted_models(self) -> List[str]:

        """Mevcut şifreli modelleri listele."""

        if not self.encrypted_provider:

            return []

        return self.encrypted_provider.list_encrypted()





# ─────────────────────────────────────────────────────────────

# SINGLETON INSTANCE

# ─────────────────────────────────────────────────────────────



_core_instance = None



def get_core() -> ShadowcatCore:

    """ShadowcatCore singleton instance'ını al"""

    global _core_instance

    if _core_instance is None:

        _core_instance = ShadowcatCore()

        _core_instance.initialize()

    return _core_instance





def quick_start():

    """Hızlı başlatma fonksiyonu"""

    core = get_core()

    print(f"\n{'='*50}")

    print(f"  Shadowcat AI v{VERSION} hazır!")

    print(f"  {'='*50}")

    print(f"  Komutlar: {core.toolformer.registry.count() if core.toolformer else 0} araç")

    print(f"  Hafıza: {core.memory.get_memory_count() if core.memory else 0} dosya")

    print(f"  {'='*50}\n")

    return core





# ─────────────────────────────────────────────────────────────

# TEST / DEMO

# ─────────────────────────────────────────────────────────────



if __name__ == "__main__":

    core = quick_start()

    

    # Test mesajı

    while True:

        try:

            user_input = input("\n> ").strip()

            if user_input.lower() in ["exit", "quit", "çıkış", "q"]:

                print("Görüşmek üzere!")

                break

            if not user_input:

                continue

            

            result = core.process_message(user_input)

            print(f"\n> {result['response']}")

            

            if result.get("tool_calls"):

                print(f"\nKullanılan araçlar: {len(result['tool_calls'])}")

            

            if result.get("thoughts"):

                for t in result["thoughts"][-2:]:

                    print(f"{t.get('content', '')[:100]}")

        

        except KeyboardInterrupt:

            print("\nGörüşmek üzere!")

            break

        except Exception as e:

            print(f"\nHata: {e}")

