"""Shadowcat AI - Unified Core Module"""
import os, sys, json, time, uuid, logging, threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Shadowcat")

VERSION = "5.0.0"
AGENT_NAME = "Shadowcat"
OWNER = "ErCuM"


class SystemMode(Enum):
    NORMAL = "normal"
    DEVELOPER = "developer"
    SILENT = "silent"
    GAME = "game"


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


@dataclass
class AgentState:
    mode: str = "normal"
    listening: bool = False
    speaking: bool = False
    monitoring: bool = False
    current_task: Optional[str] = None
    current_step: int = 0
    total_steps: int = 0


@dataclass

# Optional module loading
NEXUS_OK = False
try:
    from nexus_memory import get_nexus_memory
    NEXUS_OK = True
except ImportError:
    pass

TOOLFORMER_OK = False
try:
    from toolformer import Toolformer, Tool, ToolParameter, ToolHandlers, ToolResult
    TOOLFORMER_OK = True
except ImportError:
    pass

MODEL_ROUTER_OK = False
try:
    from model_router import get_model_router
    MODEL_ROUTER_OK = True
except ImportError:
    pass

OBSIDIAN_OK = False
try:
    from obsidian_memory import get_obsidian_memory
    OBSIDIAN_OK = True
except ImportError:
    pass

PLUGIN_OK = False
try:
    from plugin_system import PluginManager, HookPoint
    PLUGIN_OK = True
except ImportError:

class ShadowcatCore:
    """Main Shadowcat AI core - unified from shadowcat_core.py + shadowcat_agent.py"""

    def __init__(self, config: Optional[Dict] = None):
        self._initialized = False
        self.config = config or {}
        self.state = AgentState()
        self.memory = None
        self.toolformer = None
        self.model_router = None
        self.encrypted_provider = None
        self.agent_loop = None
        self.task_planner = None
        self.state_manager = None
        self.web_agent = None
        self.feedback = None
        self.error_fix = None
        self.style: str = "normal"
        self.projects: Dict[str, dict] = {}
        self.active_project: Optional[str] = None
        logger.info("Shadowcat Core created")

    def initialize(self):
        """Initialize all subsystems"""
        if self._initialized:
            return
        logger.info(f"  Shadowcat v{VERSION} starting...")
        self._init_memory()
        self._init_toolformer()
        self._init_model_router()
        self._init_state_manager()
        self._init_feedback()
        logger.info(f"  Shadowcat v{VERSION} ready!")
        self._initialized = True

    def _init_memory(self):
        if NEXUS_OK:
            try:
                self.memory = get_nexus_memory()
                stats = self.memory.get_stats()
                logger.info(f"  Nexus Memory: {stats['memory_count']} records")
            except Exception as e:
                logger.warning(f"  Nexus memory failed: {e}")
                self.memory = None

    def _init_toolformer(self):
        if TOOLFORMER_OK:
            try:
                self.toolformer = Toolformer(auto_register_defaults=True)
                self._register_shadowcat_tools()
                stats = self.toolformer.get_stats()
                logger.info(f"  Toolformer: {stats['registered_tools']} tools")
            except Exception as e:
                logger.warning(f"  Toolformer failed: {e}")
                self.toolformer = None

    def _init_model_router(self):
        if MODEL_ROUTER_OK:
            try:
                self.model_router = get_model_router()
                logger.info("  Model Router: active")
            except Exception as e:
                logger.warning(f"  Model Router failed: {e}")
                self.model_router = None

    def _init_state_manager(self):
        state_dir = os.path.join(os.path.dirname(__file__), "storage", "state")
        os.makedirs(state_dir, exist_ok=True)
        self.state_manager = {"state_dir": state_dir, "data": {}}
        logger.info("  State Manager: active")

    def _init_feedback(self):

    def _register_shadowcat_tools(self):
        """Register Shadowcat-specific tools"""
        if not self.toolformer:
            return
        try:
            self.toolformer.register(
                name="open_app",
                description="Open an application",
                parameters=[ToolParameter(name="app_name", type="string", required=True)],
                handler=self._tool_open_app
            )
            self.toolformer.register(
                name="system_status",
                description="Get system status",
                parameters=[],
                handler=self._tool_system_status
            )
        except Exception as e:
            logger.warning(f"  Tool registration failed: {e}")

    def _tool_open_app(self, app_name: str) -> str:
        try:
            import subprocess
            subprocess.Popen(f"start {app_name}", shell=True)
            return f"Launched: {app_name}"
        except Exception as e:
            return f"Error: {e}"

    def _tool_system_status(self) -> Dict:
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
        except:
            return {"error": "psutil not available"}

    def process_message(self, user_input: str, conversation_history: Optional[List] = None) -> AgentLoopResult:
        """Process user message with ReAct loop"""
        thoughts = []
        tool_calls = []
        start_time = time.time()

        thoughts.append(Thought(step=1, type="think", content=f"Analyzing: {user_input}"))

        try:
            response = self._generate_response(user_input, conversation_history)
            thoughts.append(Thought(step=2, type="answer", content=response[:100]))
        except Exception as e:
            return AgentLoopResult(
                response=f"Error: {e}",
                thoughts=[asdict(t) for t in thoughts],
                success=False,
                error=str(e)
            )

        elapsed = time.time() - start_time
        return AgentLoopResult(
            response=response,
            thoughts=[asdict(t) for t in thoughts],
            tool_calls=tool_calls,
            iterations=len(thoughts),
            success=True
        )

    def _generate_response(self, user_input: str, history: Optional[List] = None) -> str:
        """Generate AI response via Ollama"""
        try:
            import httpx
            model = self.model_router.get_current_model() if self.model_router else "llama3"
            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": user_input, "stream": False},
                timeout=60
            )
            return response.json().get("response", "No response")
        except Exception as e:
            return f"AI unavailable: {e}"


_core_instance = None

def get_core() -> ShadowcatCore:
    """Get singleton core instance"""
    global _core_instance
    if _core_instance is None:
        _core_instance = ShadowcatCore()
    return _core_instance


if __name__ == "__main__":
    core = get_core()
    core.initialize()
    print(f"Shadowcat v{VERSION} initialized")

        self.feedback = {"enabled": True, "history": []}
        logger.info("  Feedback: active")

    pass

SKILL_OK = False
try:
    from skill_system import SkillManager
    SKILL_OK = True
except ImportError:
    pass

class Thought:
    step: int
    type: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)


@dataclass
class AgentLoopResult:
    response: str
    thoughts: List[Dict] = field(default_factory=list)
    tool_calls: List[Dict] = field(default_factory=list)
    iterations: int = 0
    success: bool = True
    error: Optional[str] = None
