"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║      ██████╗ ██╗     ██╗   ██╗ ██████╗ ██╗███╗   ██╗                     ║
║      ██╔══██╗██║     ██║   ██║██╔════╝ ██║████╗  ██║                     ║
║      ██████╔╝██║     ██║   ██║██║  ███╗██║██╔██╗ ██║                     ║
║      ██╔═══╝ ██║     ██║   ██║██║   ██║██║██║╚██╗██║                     ║
║      ██║     ███████╗╚██████╔╝╚██████╔╝██║██║ ╚████║                     ║
║      ╚═╝     ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝╚═╝  ╚═══╝                     ║
║         ██████╗ ██╗   ██╗███╗   ██╗███╗   ██╗███████╗██████╗             ║
║         ██╔══██╗██║   ██║████╗  ██║████╗  ██║██╔════╝██╔══██╗            ║
║         ██████╔╝██║   ██║██╔██╗ ██║██╔██╗ ██║█████╗  ██████╔╝            ║
║         ██╔══██╗██║   ██║██║╚██╗██║██║╚██╗██║██╔══╝  ██╔══██╗            ║
║         ██║  ██║╚██████╔╝██║ ╚████║██║ ╚████║███████╗██║  ██║            ║
║         ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝            ║
║                                                                           ║
║          COKLU-DIL PLUGIN ALT SISTEMI / MULTI-LANGUAGE PLUGIN            ║
║                    Berkay Software - Lead Engineer AI                      ║
║                         Version 1.0 - SWA 1.6                            ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

Glassescat AI Coklu-Dil Plugin Altyapisi - Python disi dillerde plugin calistirma.

Kullanim:
    >>> from plugin_runner import MultiLanguagePluginManager
    >>> manager = MultiLanguagePluginManager()
    >>> manager.discover_plugins()  # .py, .js, .lua, .rb, .sh, .go
    >>> manager.load_all_plugins()
    >>> manager.execute_hooks(HookPoint.BEFORE_CHAT, message="merhaba", context={})
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from abc import ABC, abstractmethod
from asyncio.subprocess import Process
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock, Thread
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from weakref import WeakSet

from plugin_system import (
    BasePlugin,
    HookPoint,
    PluginDependency,
    PluginInstance,
    PluginLoadError,
    PluginManager,
    PluginMetadata,
    PluginPriority,
    PluginRegistry,
    PluginState,
    PluginWatcher,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

PLUGIN_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".lua": "lua",
    ".rb": "ruby",
    ".sh": "bash",
    ".go": "go",
}

DEFAULT_TIMEOUT = 30.0
HEARTBEAT_INTERVAL = 5.0
MAX_RESTART_ATTEMPTS = 3
BUFFER_SIZE = 65536

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class PluginProtocol:
    """Standart JSON protokolu - pluginler arasi IPC iletisimi.

    Mesaj formati (stdin -> plugin):
        {"action": "execute", "hook": "before_chat", "data": {...}}

    Cevap formati (plugin -> stdout):
        {"success": true, "data": {...}}

    Hata formati:
        {"success": false, "error": "Aciklama", "code": "ERROR_CODE"}
    """

    # --- Eylem Sabitleri ---
    ACTION_EXECUTE = "execute"
    ACTION_HANDSHAKE = "handshake"
    ACTION_HEARTBEAT = "heartbeat"
    ACTION_SHUTDOWN = "shutdown"
    ACTION_RELOAD = "reload"
    ACTION_PING = "ping"

    # --- Durum Kodlari ---
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNKNOWN_ACTION = "unknown_action"
    INVALID_PAYLOAD = "invalid_payload"
    RUNTIME_NOT_FOUND = "runtime_not_found"
    INTERNAL_ERROR = "internal_error"

    @staticmethod
    def create_message(
        action: str,
        hook: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> str:
        """Plugin'e gonderilecek JSON mesaji olusturur.

        Args:
            action: Eylem turu (execute, handshake, heartbeat, vs.)
            hook: Hook noktasi adi
            data: Eklentiye gonderilecek veri
            message_id: Benzersiz mesaj ID (trace icin)

        Returns:
            JSON string
        """
        payload: Dict[str, Any] = {
            "action": action,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "protocol_version": "1.0",
        }
        if hook is not None:
            payload["hook"] = hook
        if data is not None:
            payload["data"] = data
        if message_id is not None:
            payload["message_id"] = message_id
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def parse_response(raw: str) -> Dict[str, Any]:
        """Plugin'den gelen JSON yaniti cozumler.

        Args:
            raw: Ham JSON string

        Returns:
            Cozumlenmis sozluk

        Raises:
            json.JSONDecodeError: Gecersiz JSON
        """
        return json.loads(raw)

    @staticmethod
    def is_success(response: Dict[str, Any]) -> bool:
        """Yanitin basarili olup olmadigini kontrol eder."""
        return response.get("success", False) is True

    @staticmethod
    def get_error(response: Dict[str, Any]) -> str:
        """Yanitten hata mesajini alir."""
        return response.get("error", "Bilinmeyen hata")

    @staticmethod
    def create_handshake(
        plugin_name: str,
        api_version: str = "1.0",
        capabilities: Optional[List[str]] = None,
    ) -> str:
        """El sikisma mesaji olusturur."""
        return PluginProtocol.create_message(
            action=PluginProtocol.ACTION_HANDSHAKE,
            data={
                "plugin_name": plugin_name,
                "api_version": api_version,
                "capabilities": capabilities or [],
                "language": "",
                "runtime_version": "",
            },
        )

    @staticmethod
    def create_heartbeat() -> str:
        """Heartbeat (calisiyor mu) mesaji."""
        return PluginProtocol.create_message(
            action=PluginProtocol.ACTION_HEARTBEAT,
            data={"timestamp": time.time()},
        )

    @staticmethod
    def create_shutdown(reason: str = "manager_shutdown") -> str:
        """Kapatma mesaji."""
        return PluginProtocol.create_message(
            action=PluginProtocol.ACTION_SHUTDOWN,
            data={"reason": reason},
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PluginRunnerError(Exception):
    """Plugin runner temel hata sinifi."""

    pass


class RuntimeNotFoundError(PluginRunnerError):
    """Calisma ortami (runtime) bulunamadi."""

    pass


class PluginTimeoutError(PluginRunnerError):
    """Plugin zaman asimina ugradi."""

    pass


class PluginCommunicationError(PluginRunnerError):
    """Plugin iletisim hatasi."""

    pass


class PluginHandshakeError(PluginRunnerError):
    """Plugin el sikismasi basarisiz."""

    pass


# ---------------------------------------------------------------------------
# BaseLanguageRunner
# ---------------------------------------------------------------------------


class BaseLanguageRunner(ABC):
    """Dil-bazli plugin calistirici icin soyut temel sinif.

    Her dil icin alt siniflar:
        - Calisma ortaminin kurulu olup olmadigini kontrol eder
        - Alt sureci baslatir ve JSON stdin/stdout uzerinden iletisim kurar
        - Zaman asimi, hata ve heartbeat yonetimi yapar
        - Sicak yeniden baslatma (hot-reload) destegi saglar
    """

    def __init__(
        self,
        plugin_path: str,
        timeout: float = DEFAULT_TIMEOUT,
        heartbeat_interval: float = HEARTBEAT_INTERVAL,
    ) -> None:
        self._plugin_path = Path(plugin_path).resolve()
        self._timeout = timeout
        self._heartbeat_interval = heartbeat_interval
        self._process: Optional[Process] = None
        self._process_lock = Lock()
        self._running = False
        self._start_time: float = 0.0
        self._last_heartbeat: float = 0.0
        self._restart_attempts = 0
        self._max_restart_attempts = MAX_RESTART_ATTEMPTS
        self._message_id_counter = 0
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._stdout_buffer = ""
        self._stderr_buffer = ""

    # ------------------------------------------------------------------
    # Soyut ozellikler / metodlar
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Dil adi (ornek: 'python', 'javascript')."""
        ...

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Dosya uzantisi (ornek: '.py', '.js')."""
        ...

    @property
    @abstractmethod
    def runtime_command(self) -> str:
        """Calisma ortami komutu (ornek: 'node', 'lua')."""
        ...

    @abstractmethod
    def get_launch_command(self) -> List[str]:
        """Plugin'i baslatmak icin gerekli komut listesi.

        Returns:
            ['node', 'plugin.js'] veya ['go', 'run', 'plugin.go'] gibi
        """
        ...

    @abstractmethod
    def get_launch_cwd(self) -> str:
        """Calisma dizini (genellikle plugin dosyasinin bulundugu dizin)."""
        ...

    # ------------------------------------------------------------------
    # Runtime kontrol
    # ------------------------------------------------------------------

    def is_runtime_available(self) -> bool:
        """Calisma ortaminin sistemde kurulu olup olmadigini kontrol eder.

        Returns:
            bool
        """
        command = self.runtime_command

        if platform.system() == "Windows":
            cmd = ["where", command]
        else:
            cmd = ["which", command]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5.0,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def get_runtime_version(self) -> Optional[str]:
        """Calisma ortaminin versiyonunu dondurur.

        Returns:
            Versiyon stringi veya None
        """
        try:
            result = subprocess.run(
                [self.runtime_command, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5.0,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Surec yonetimi
    # ------------------------------------------------------------------

    async def start(self) -> bool:
        """Plugin alt surecini baslatir ve el sikismasi yapar.

        Returns:
            Basarili mi

        Raises:
            RuntimeNotFoundError: Runtime kurulu degilse
            PluginHandshakeError: El sikismasi basarisizsa
        """
        if not self.is_runtime_available():
            raise RuntimeNotFoundError(
                f"[{self.language_name}] Runtime bulunamadi: {self.runtime_command}"
            )

        async with self._get_process_lock():
            if self._running:
                self._logger.warning(
                    "[%s] Surec zaten calisiyor, yeniden baslatiliyor: %s",
                    self.language_name,
                    self._plugin_path.name,
                )
                await self._stop_internal()

            self._event_loop = asyncio.get_event_loop()

            launch_cmd = self.get_launch_command()
            launch_cwd = self.get_launch_cwd()

            self._logger.info(
                "[%s] Plugin baslatiliyor: %s (cmd: %s, cwd: %s)",
                self.language_name,
                self._plugin_path.name,
                launch_cmd,
                launch_cwd,
            )

            try:
                self._process = await asyncio.create_subprocess_exec(
                    *launch_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=launch_cwd,
                    env=self._get_environment(),
                )
            except FileNotFoundError as exc:
                raise RuntimeNotFoundError(
                    f"[{self.language_name}] Komut bulunamadi: {launch_cmd[0]}"
                ) from exc

            self._running = True
            self._start_time = time.time()
            self._last_heartbeat = time.time()
            self._restart_attempts = 0
            self._stdout_buffer = ""
            self._stderr_buffer = ""

            ok = await self._perform_handshake()
            if not ok:
                await self._stop_internal()
                raise PluginHandshakeError(
                    f"[{self.language_name}] El sikismasi basarisiz: "
                    f"{self._plugin_path.name}"
                )

            self._logger.info(
                "[%s] Plugin basariyla baslatildi: %s",
                self.language_name,
                self._plugin_path.name,
            )
            return True

    async def stop(self, reason: str = "kullanici_istegi") -> None:
        """Plugin alt surecini durdurur.

        Args:
            reason: Durdurma sebebi
        """
        async with self._get_process_lock():
            await self._stop_internal(reason)

    async def _stop_internal(self, reason: str = "durdurma") -> None:
        """Ic durdurma mantigi (kilit zaten alinmis olmali)."""
        if not self._running or self._process is None:
            return

        self._logger.info(
            "[%s] Plugin durduruluyor: %s (sebep: %s)",
            self.language_name,
            self._plugin_path.name,
            reason,
        )

        try:
            shutdown_msg = PluginProtocol.create_shutdown(reason)
            await self._send_raw(shutdown_msg)
        except Exception:
            pass

        try:
            if self._process.stdin:
                self._process.stdin.close()
        except Exception:
            pass

        try:
            if platform.system() == "Windows":
                if self._process.returncode is None:
                    self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                if self._process.returncode is None:
                    self._process.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as exc:
            self._logger.warning(
                "[%s] Sinyal gonderilemedi: %s",
                self.language_name,
                exc,
            )

        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._logger.warning(
                "[%s] Surec yanit vermedi, zorla kapatiliyor",
                self.language_name,
            )
            try:
                self._process.kill()
                await self._process.wait()
            except Exception:
                pass
        except Exception:
            pass

        self._running = False
        self._process = None

        for future in self._pending_responses.values():
            if not future.done():
                future.cancel()
        self._pending_responses.clear()

    async def restart(self) -> bool:
        """Plugin surecini yeniden baslatir (hot-reload).

        Returns:
            Basarili mi
        """
        self._logger.info(
            "[%s] Plugin yeniden baslatiliyor: %s",
            self.language_name,
            self._plugin_path.name,
        )

        await self.stop(reason="hot_reload")

        if self._restart_attempts >= self._max_restart_attempts:
            self._logger.error(
                "[%s] Maksimum yeniden baslatma denemesi asildi: %s",
                self.language_name,
                self._plugin_path.name,
            )
            return False

        self._restart_attempts += 1

        try:
            return await self.start()
        except Exception as exc:
            self._logger.error(
                "[%s] Yeniden baslatma hatasi: %s - %s",
                self.language_name,
                self._plugin_path.name,
                exc,
            )
            return False

    @property
    def is_running(self) -> bool:
        """Plugin sureci calisiyor mu."""
        return self._running and self._process is not None

    @property
    def uptime(self) -> float:
        """Plugin calisma suresi (saniye)."""
        if not self._running or self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    # ------------------------------------------------------------------
    # Iletisim
    # ------------------------------------------------------------------

    async def send_message(
        self,
        action: str,
        hook: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Plugin'e mesaj gonderir ve yanit bekler.

        Args:
            action: Eylem turu
            hook: Hook noktasi
            data: Veri
            timeout: Zaman asimi (None = varsayilan)

        Returns:
            Yanit sozlugu

        Raises:
            PluginTimeoutError: Zaman asimi
            PluginCommunicationError: Iletisim hatasi
        """
        if not self._running or self._process is None:
            raise PluginCommunicationError(
                f"[{self.language_name}] Surec calismiyor"
            )

        message_id = f"msg_{int(time.time() * 1000)}_{self._message_id_counter}"
        self._message_id_counter += 1

        raw = PluginProtocol.create_message(
            action=action,
            hook=hook,
            data=data,
            message_id=message_id,
        )

        future: asyncio.Future[Dict[str, Any]] = self._event_loop.create_future()
        self._pending_responses[message_id] = future

        effective_timeout = timeout if timeout is not None else self._timeout

        try:
            await self._send_raw(raw)
            response = await asyncio.wait_for(future, timeout=effective_timeout)
            return response
        except asyncio.TimeoutError as exc:
            self._pending_responses.pop(message_id, None)
            raise PluginTimeoutError(
                f"[{self.language_name}] Zaman asimi ({effective_timeout}s): "
                f"{self._plugin_path.name}"
            ) from exc
        except Exception as exc:
            self._pending_responses.pop(message_id, None)
            raise PluginCommunicationError(
                f"[{self.language_name}] Iletisim hatasi: {exc}"
            ) from exc

    async def execute_hook(
        self,
        hook: HookPoint,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Plugin uzerinde bir hook calistirir.

        Args:
            hook: Hook noktasi
            data: Hook'a gonderilecek veri
            timeout: Zaman asimi

        Returns:
            {"success": bool, "data": ...}
        """
        return await self.send_message(
            action=PluginProtocol.ACTION_EXECUTE,
            hook=hook.value,
            data=data,
            timeout=timeout,
        )

    async def _send_raw(self, raw: str) -> None:
        """Ham JSON mesajini stdin'e yazar."""
        if self._process is None or self._process.stdin is None:
            raise PluginCommunicationError("Stdin kullanilamiyor")
        try:
            self._process.stdin.write((raw + "\n").encode("utf-8"))
            await self._process.stdin.drain()
        except BrokenPipeError as exc:
            raise PluginCommunicationError(
                f"Pipe kapali: {exc}"
            ) from exc

    async def _read_line(self) -> Optional[str]:
        """Stdout'tan bir satir okur."""
        if self._process is None or self._process.stdout is None:
            return None
        try:
            line = await self._process.stdout.readline()
            if not line:
                return None
            return line.decode("utf-8").strip()
        except Exception:
            return None

    async def _perform_handshake(self) -> bool:
        """Plugin ile el sikismasi yapar.

        Handshake mesaji gonderir ve gecerli yanit bekler.

        Returns:
            Basarili mi
        """
        try:
            handshake_msg = PluginProtocol.create_handshake(
                plugin_name=self._plugin_path.stem,
                api_version="1.0",
                capabilities=[self.language_name],
            )
            await self._send_raw(handshake_msg)

            response_raw = await asyncio.wait_for(
                self._read_line(), timeout=10.0
            )
            if response_raw is None:
                return False

            response = PluginProtocol.parse_response(response_raw)
            return PluginProtocol.is_success(response)

        except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as exc:
            self._logger.warning(
                "[%s] El sikismasi hatasi: %s",
                self.language_name,
                exc,
            )
            return False

    async def _read_stdout_loop(self) -> None:
        """Stdout okuma dongusu - arka planda calisir.

        Gelen yanitlari message_id'ye gore pending_responses'a yonlendirir
        ve heartbeat yanitlarini isler.
        """
        while self._running and self._process is not None:
            try:
                line = await asyncio.wait_for(
                    self._read_line(), timeout=1.0
                )
                if line is None:
                    break

                response = PluginProtocol.parse_response(line)

                msg_id = response.get("message_id")
                if msg_id and msg_id in self._pending_responses:
                    future = self._pending_responses.pop(msg_id)
                    if not future.done():
                        future.set_result(response)
                elif response.get("action") == "heartbeat_ack":
                    self._last_heartbeat = time.time()
                else:
                    self._logger.debug(
                        "[%s] Kimliksiz yanit: %s",
                        self.language_name,
                        line[:200],
                    )

            except asyncio.TimeoutError:
                continue
            except json.JSONDecodeError:
                continue
            except Exception as exc:
                self._logger.warning(
                    "[%s] stdout okuma hatasi: %s",
                    self.language_name,
                    exc,
                )
                break

    async def _read_stderr_loop(self) -> None:
        """Stderr okuma dongusu - hata ciktilarini loglar."""
        while self._running and self._process is not None:
            try:
                line = await asyncio.wait_for(
                    self._read_stderr_line(), timeout=1.0
                )
                if line is None:
                    break
                self._stderr_buffer += line + "\n"
                if len(self._stderr_buffer) > BUFFER_SIZE:
                    self._stderr_buffer = self._stderr_buffer[-BUFFER_SIZE:]
                self._logger.warning(
                    "[%s] stderr: %s",
                    self.language_name,
                    line,
                )
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    async def _read_stderr_line(self) -> Optional[str]:
        """Stderr'den bir satir okur."""
        if self._process is None or self._process.stderr is None:
            return None
        try:
            line = await self._process.stderr.readline()
            if not line:
                return None
            return line.decode("utf-8").strip()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Yardimcilar
    # ------------------------------------------------------------------

    def _get_environment(self) -> Dict[str, str]:
        """Plugin sureci icin cevre degiskenlerini hazirlar."""
        env = dict(os.environ)
        env["SHADOWCAT_PLUGIN_DIR"] = str(self._plugin_path.parent)
        env["SHADOWCAT_PLUGIN_FILE"] = str(self._plugin_path)
        env["SHADOWCAT_PLUGIN_LANGUAGE"] = self.language_name
        env["SHADOWCAT_PROTOCOL_VERSION"] = "1.0"
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _get_process_lock(self) -> Lock:
        """Process lock erisimi (context manager uyumlu)."""
        return self._process_lock

    def get_stderr_log(self, max_chars: int = 2000) -> str:
        """Plugin hata ciktisini dondurur."""
        return self._stderr_buffer[-max_chars:]

    @property
    def plugin_path(self) -> Path:
        return self._plugin_path

    @property
    def restart_attempts(self) -> int:
        return self._restart_attempts

    @property
    def has_stderr_errors(self) -> bool:
        """Stderr'de hata var mi (kabaca kontrol)."""
        return any(
            keyword in self._stderr_buffer.lower()
            for keyword in ["error", "traceback", "exception", "failed"]
        )


# ---------------------------------------------------------------------------
# PythonRunner
# ---------------------------------------------------------------------------


class PythonRunner(BaseLanguageRunner):
    """Python plugin calistirici.

    Python plugin'leri dogrudan import edilebildigi icin subprocess
    yerine inline calistirma tercih edilir. Ancak izolasyon gerektiren
    durumlarda subprocess de kullanilabilir.
    """

    def __init__(
        self,
        plugin_path: str,
        timeout: float = DEFAULT_TIMEOUT,
        use_subprocess: bool = False,
    ) -> None:
        super().__init__(plugin_path, timeout)
        self._use_subprocess = use_subprocess
        self._module: Optional[Any] = None
        self._plugin_instance: Optional[BasePlugin] = None

    @property
    def language_name(self) -> str:
        return "python"

    @property
    def file_extension(self) -> str:
        return ".py"

    @property
    def runtime_command(self) -> str:
        return "python" if platform.system() == "Windows" else "python3"

    def get_launch_command(self) -> List[str]:
        if self._use_subprocess:
            python_cmd = self.runtime_command
            return [python_cmd, str(self._plugin_path)]
        return [sys.executable, str(self._plugin_path)]

    def get_launch_cwd(self) -> str:
        return str(self._plugin_path.parent)

    async def start(self) -> bool:
        if not self._use_subprocess:
            self._running = True
            self._start_time = time.time()
            self._logger.info(
                "[python] Plugin inline yuklendi: %s",
                self._plugin_path.name,
            )
            return True
        return await super().start()

    async def stop(self, reason: str = "kullanici_istegi") -> None:
        if not self._use_subprocess:
            self._running = False
            self._module = None
            self._plugin_instance = None
            return
        await super().stop(reason)

    async def execute_hook(
        self,
        hook: HookPoint,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self._use_subprocess and self._plugin_instance is not None:
            try:
                method = getattr(self._plugin_instance, hook.value, None)
                if method is None:
                    return {"success": False, "error": "Hook metodu bulunamadi"}
                result = method(**(data or {}))
                return {"success": True, "data": result}
            except Exception as exc:
                return {"success": False, "error": str(exc), "traceback": traceback.format_exc()}

        return await super().execute_hook(hook, data, timeout)

    def set_plugin_instance(self, instance: BasePlugin) -> None:
        self._plugin_instance = instance

    def get_plugin_instance(self) -> Optional[BasePlugin]:
        return self._plugin_instance


# ---------------------------------------------------------------------------
# JavaScriptRunner
# ---------------------------------------------------------------------------


class JavaScriptRunner(BaseLanguageRunner):
    """Node.js / JavaScript plugin calistirici."""

    @property
    def language_name(self) -> str:
        return "javascript"

    @property
    def file_extension(self) -> str:
        return ".js"

    @property
    def runtime_command(self) -> str:
        return "node"

    def get_launch_command(self) -> List[str]:
        return ["node", str(self._plugin_path)]

    def get_launch_cwd(self) -> str:
        return str(self._plugin_path.parent)

    async def start(self) -> bool:
        try:
            return await super().start()
        except RuntimeNotFoundError:
            alt = self._try_alt_runtime()
            if alt:
                self._logger.info(
                    "[javascript] Alternatif runtime kullaniliyor: %s",
                    alt,
                )
                return await alt.start()
            raise

    def _try_alt_runtime(self) -> Optional[JavaScriptRunner]:
        """Alternatif Node.js yollarini dener."""
        alt_paths = [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\njs\node.exe",
            "/usr/local/bin/node",
            "/usr/bin/node",
            "/opt/homebrew/bin/node",
        ]
        for path in alt_paths:
            if Path(path).exists():
                alt = JavaScriptRunner(str(self._plugin_path), self._timeout)
                alt._alt_node_path = path
                return alt
        return None


# ---------------------------------------------------------------------------
# LuaRunner
# ---------------------------------------------------------------------------


class LuaRunner(BaseLanguageRunner):
    """Lua plugin calistirici."""

    @property
    def language_name(self) -> str:
        return "lua"

    @property
    def file_extension(self) -> str:
        return ".lua"

    @property
    def runtime_command(self) -> str:
        return "lua"

    def get_launch_command(self) -> List[str]:
        return ["lua", str(self._plugin_path)]

    def get_launch_cwd(self) -> str:
        return str(self._plugin_path.parent)


# ---------------------------------------------------------------------------
# RubyRunner
# ---------------------------------------------------------------------------


class RubyRunner(BaseLanguageRunner):
    """Ruby plugin calistirici."""

    @property
    def language_name(self) -> str:
        return "ruby"

    @property
    def file_extension(self) -> str:
        return ".rb"

    @property
    def runtime_command(self) -> str:
        return "ruby"

    def get_launch_command(self) -> List[str]:
        return ["ruby", str(self._plugin_path)]

    def get_launch_cwd(self) -> str:
        return str(self._plugin_path.parent)


# ---------------------------------------------------------------------------
# BashRunner
# ---------------------------------------------------------------------------


class BashRunner(BaseLanguageRunner):
    """Bash script plugin calistirici."""

    @property
    def language_name(self) -> str:
        return "bash"

    @property
    def file_extension(self) -> str:
        return ".sh"

    @property
    def runtime_command(self) -> str:
        return "bash" if platform.system() != "Windows" else ""

    def get_launch_command(self) -> List[str]:
        if platform.system() == "Windows":
            bash_paths = [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files\Git\usr\bin\bash.exe",
                r"C:\msys64\usr\bin\bash.exe",
                r"C:\cygwin64\bin\bash.exe",
            ]
            for path in bash_paths:
                if Path(path).exists():
                    return [path, str(self._plugin_path)]
            sh_paths = [
                r"C:\Program Files\Git\bin\sh.exe",
                r"C:\msys64\usr\bin\sh.exe",
            ]
            for path in sh_paths:
                if Path(path).exists():
                    return [path, str(self._plugin_path)]
            return ["sh", str(self._plugin_path)]
        return ["bash", str(self._plugin_path)]

    def get_launch_cwd(self) -> str:
        return str(self._plugin_path.parent)

    @property
    def runtime_command(self) -> str:
        if platform.system() == "Windows":
            return "bash"
        return "bash"

    def is_runtime_available(self) -> bool:
        if platform.system() == "Windows":
            bash_paths = [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files\Git\usr\bin\bash.exe",
                r"C:\msys64\usr\bin\bash.exe",
                r"C:\cygwin64\bin\bash.exe",
            ]
            for path in bash_paths:
                if Path(path).exists():
                    return True
            return bool(shutil.which("sh"))
        return bool(shutil.which("bash"))


# ---------------------------------------------------------------------------
# GoRunner
# ---------------------------------------------------------------------------


class GoRunner(BaseLanguageRunner):
    """Go plugin calistirici.

    Go plugin'leri iki sekilde calistirilabilir:
    1. `go run plugin.go` ile dogrudan (yorumlanmis mod)
    2. Onceden derlenmis binary ile (pre-compiled)

    Binary, plugin.go ile ayni dizinde plugin.exe (Windows) veya
    plugin (Unix) olarak aranir.
    """

    def __init__(
        self,
        plugin_path: str,
        timeout: float = DEFAULT_TIMEOUT,
        use_precompiled: bool = False,
    ) -> None:
        super().__init__(plugin_path, timeout)
        self._use_precompiled = use_precompiled
        self._binary_path: Optional[Path] = None

    @property
    def language_name(self) -> str:
        return "go"

    @property
    def file_extension(self) -> str:
        return ".go"

    @property
    def runtime_command(self) -> str:
        return "go"

    def get_launch_command(self) -> List[str]:
        if self._use_precompiled and self._binary_path is not None:
            return [str(self._binary_path)]

        if platform.system() == "Windows":
            go_bin = shutil.which("go") or "go"
            return [go_bin, "run", str(self._plugin_path)]
        return ["go", "run", str(self._plugin_path)]

    def get_launch_cwd(self) -> str:
        return str(self._plugin_path.parent)

    def find_precompiled_binary(self) -> Optional[str]:
        """Onceden derlenmis binary dosyasini arar.

        Binary adlari:
            - plugin (Unix)
            - plugin.exe (Windows)
            - plugin_go (alternatif)
            - plugin_go.exe (alternatif Windows)

        Returns:
            Binary dosya yolu veya None
        """
        stem = self._plugin_path.stem
        parent = self._plugin_path.parent

        candidates = [stem, f"{stem}_go"]
        if platform.system() == "Windows":
            candidates = [f"{c}.exe" for c in candidates]
        else:
            candidates = candidates  # zaten dogru

        for candidate in candidates:
            candidate_path = parent / candidate
            if candidate_path.exists() and os.access(str(candidate_path), os.X_OK):
                return str(candidate_path)

        return None

    async def start(self) -> bool:
        if not self._use_precompiled:
            binary = self.find_precompiled_binary()
            if binary:
                self._logger.info(
                    "[go] Onceden derlenmis binary bulundu: %s",
                    binary,
                )
                self._use_precompiled = True
                self._binary_path = Path(binary)

        return await super().start()

    @property
    def uses_precompiled(self) -> bool:
        return self._use_precompiled


# ---------------------------------------------------------------------------
# Runner Factory
# ---------------------------------------------------------------------------


class RunnerFactory:
    """Dosya uzantisi ve dile gore uygun Runner sinifini olusturur."""

    _runner_map: Dict[str, Type[BaseLanguageRunner]] = {
        ".py": PythonRunner,
        ".js": JavaScriptRunner,
        ".lua": LuaRunner,
        ".rb": RubyRunner,
        ".sh": BashRunner,
        ".go": GoRunner,
    }

    @classmethod
    def create_runner(
        cls,
        filepath: str,
        timeout: float = DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> BaseLanguageRunner:
        """Dosya yoluna gore uygun runner'i olusturur.

        Args:
            filepath: Plugin dosya yolu
            timeout: Zaman asimi
            kwargs: Runner'a ozel ek parametreler

        Returns:
            BaseLanguageRunner turevi

        Raises:
            PluginRunnerError: Desteklenmeyen dosya turu
        """
        path = Path(filepath)
        ext = path.suffix.lower()

        runner_class = cls._runner_map.get(ext)
        if runner_class is None:
            raise PluginRunnerError(
                f"Desteklenmeyen dosya uzantisi: {ext} "
                f"(desteklenen: {', '.join(cls._runner_map.keys())})"
            )

        if runner_class is PythonRunner:
            use_subprocess = kwargs.get("use_subprocess", False)
            return PythonRunner(filepath, timeout, use_subprocess=use_subprocess)
        if runner_class is GoRunner:
            use_precompiled = kwargs.get("use_precompiled", False)
            return GoRunner(filepath, timeout, use_precompiled=use_precompiled)

        return runner_class(filepath, timeout)

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """Desteklenen dosya uzantilarini dondurur."""
        return list(cls._runner_map.keys())

    @classmethod
    def supports_extension(cls, ext: str) -> bool:
        """Belirli bir uzantinin desteklenip desteklenmedigini kontrol eder."""
        return ext.lower() in cls._runner_map


# ---------------------------------------------------------------------------
# MultiLanguagePluginInstance
# ---------------------------------------------------------------------------


class MultiLanguagePluginInstance:
    """Coklu-dil plugin ornegi.

    Her dildeki plugin icin bir ornek. Runner'i, durumu ve
    metadata bilgilerini bir arada tutar.
    """

    def __init__(
        self,
        filepath: Path,
        runner: BaseLanguageRunner,
    ) -> None:
        self._filepath = filepath
        self._runner = runner
        self._state = PluginState.DISCOVERED
        self._error: Optional[str] = None
        self._metadata = PluginMetadata(name=filepath.stem)
        self._hook_execution_count = 0
        self._last_execution_time: float = 0.0
        self._total_execution_time: float = 0.0
        self._logger = logging.getLogger(
            f"{__name__}.MultiLanguagePluginInstance"
        )

    @property
    def name(self) -> str:
        return self._metadata.name

    @property
    def filepath(self) -> Path:
        return self._filepath

    @property
    def runner(self) -> BaseLanguageRunner:
        return self._runner

    @property
    def state(self) -> PluginState:
        return self._state

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def language(self) -> str:
        return self._runner.language_name

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def load(self) -> bool:
        """Plugin'i yukler ve alt sureci baslatir.

        Returns:
            Basarili mi
        """
        try:
            self._state = PluginState.LOADING

            if not self._runner.is_runtime_available():
                raise RuntimeNotFoundError(
                    f"[{self.language}] Runtime bulunamadi: "
                    f"{self._runner.runtime_command}"
                )

            ok = await self._runner.start()
            if not ok:
                raise PluginLoadError("Plugin baslatilamadi")

            self._state = PluginState.LOADED
            self._logger.info(
                "[%s] Plugin yuklendi: %s",
                self.language,
                self.name,
            )
            return True

        except Exception as exc:
            self._state = PluginState.ERROR
            self._error = str(exc)
            self._logger.error(
                "[%s] Plugin yukleme hatasi: %s - %s",
                self.language,
                self.name,
                exc,
            )
            return False

    async def unload(self) -> bool:
        """Plugin'i kaldirir ve sureci durdurur.

        Returns:
            Basarili mi
        """
        try:
            await self._runner.stop(reason="plugin_unload")
            self._state = PluginState.UNLOADED
            self._logger.info(
                "[%s] Plugin kaldirildi: %s",
                self.language,
                self.name,
            )
            return True
        except Exception as exc:
            self._error = str(exc)
            self._logger.error(
                "[%s] Plugin kaldirma hatasi: %s - %s",
                self.language,
                self.name,
                exc,
            )
            return False

    async def reload(self) -> bool:
        """Plugin'i yeniden baslatir (hot-reload).

        Returns:
            Basarili mi
        """
        self._logger.info(
            "[%s] Plugin yeniden yukleniyor: %s",
            self.language,
            self.name,
        )
        was_loaded = self._state in (PluginState.LOADED, PluginState.ENABLED)

        await self.unload()
        result = await self.load()

        if result and was_loaded:
            self._state = PluginState.ENABLED

        return result

    async def execute_hook(
        self,
        hook: HookPoint,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Plugin uzerinde hook calistirir.

        Args:
            hook: Hook noktasi
            data: Veri
            timeout: Zaman asimi

        Returns:
            {"success": bool, "data": ..., "error": ...}
        """
        start = time.time()
        try:
            result = await self._runner.execute_hook(hook, data, timeout)
            self._hook_execution_count += 1
            self._last_execution_time = time.time()
            self._total_execution_time += (time.time() - start)
            return result
        except Exception as exc:
            self._error = str(exc)
            return {
                "success": False,
                "error": str(exc),
                "hook": hook.value,
            }

    @property
    def is_loaded(self) -> bool:
        return self._state in (PluginState.LOADED, PluginState.ENABLED)

    @property
    def is_enabled(self) -> bool:
        return self._state == PluginState.ENABLED

    @property
    def has_error(self) -> bool:
        return self._state == PluginState.ERROR

    @property
    def is_running(self) -> bool:
        return self._runner.is_running

    @property
    def uptime(self) -> float:
        return self._runner.uptime

    @property
    def runtime_version(self) -> Optional[str]:
        return self._runner.get_runtime_version()

    @property
    def hook_execution_count(self) -> int:
        return self._hook_execution_count

    def set_metadata(self, metadata: PluginMetadata) -> None:
        self._metadata = metadata


# ---------------------------------------------------------------------------
# MultiLanguagePluginManager
# ---------------------------------------------------------------------------


class MultiLanguagePluginManager:
    """PluginManager'i coklu-dil destegi ile genisletir.

    Otomatik dil algilama, alt surec yasam dongusu yonetimi,
    yedek mekanizmalar ve sicak yeniden baslatma saglar.

    Kullanim:
        >>> manager = MultiLanguagePluginManager()
        >>> await manager.discover_plugins()
        >>> await manager.load_all_plugins()
        >>> results = await manager.execute_hook(
        ...     HookPoint.BEFORE_CHAT,
        ...     data={"message": "merhaba"}
        ... )
    """

    def __init__(
        self,
        plugins_dir: str = "plugins",
        timeout: float = DEFAULT_TIMEOUT,
        heartbeat_interval: float = HEARTBEAT_INTERVAL,
        auto_start_watcher: bool = False,
        fallback_to_python: bool = True,
    ) -> None:
        self._plugins_dir = Path(plugins_dir).resolve()
        self._timeout = timeout
        self._heartbeat_interval = heartbeat_interval
        self._fallback_to_python = fallback_to_python

        self._instances: Dict[str, MultiLanguagePluginInstance] = {}
        self._python_manager: Optional[PluginManager] = None
        self._python_instances: Dict[str, PluginInstance] = {}

        self._load_order: List[str] = []
        self._disabled_plugins: Set[str] = set()
        self._error_counts: Dict[str, int] = {}

        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        self._watcher: Optional[MultiLanguageWatcher] = None
        if auto_start_watcher:
            self._start_watcher()

        self._logger = logging.getLogger(f"{__name__}.MultiLanguagePluginManager")

    # ------------------------------------------------------------------
    # Kesif
    # ------------------------------------------------------------------

    def discover_plugins(self) -> List[str]:
        """plugins/ dizinindeki tum desteklenen plugin dosyalarini kesfeder.

        Returns:
            Kesfedilen plugin adlari listesi
        """
        if not self._plugins_dir.exists():
            self._logger.warning(
                "[MultiLang] Plugin dizini bulunamadi: %s",
                self._plugins_dir,
            )
            self._plugins_dir.mkdir(parents=True, exist_ok=True)
            return []

        discovered = []
        supported_exts = RunnerFactory.get_supported_extensions()

        for ext in supported_exts:
            for filepath in sorted(self._plugins_dir.glob(f"*{ext}")):
                if filepath.name.startswith("_"):
                    continue

                name = filepath.stem
                if name in self._instances:
                    continue

                if not self._validate_plugin_file(filepath):
                    continue

                try:
                    runner = RunnerFactory.create_runner(
                        str(filepath),
                        timeout=self._timeout,
                    )

                    instance = MultiLanguagePluginInstance(filepath, runner)

                    metadata = self._detect_metadata(filepath)
                    instance.set_metadata(metadata)

                    self._instances[name] = instance
                    discovered.append(name)

                    self._logger.info(
                        "[MultiLang] Plugin kesfedildi: %s (%s, %s)",
                        name,
                        runner.language_name,
                        filepath.name,
                    )

                except Exception as exc:
                    self._logger.error(
                        "[MultiLang] Plugin kesif hatasi: %s - %s",
                        filepath.name,
                        exc,
                    )

        self._logger.info(
            "[MultiLang] %d plugin kesfedildi",
            len(discovered),
        )
        return discovered

    def _validate_plugin_file(self, filepath: Path) -> bool:
        """Plugin dosyasinin gecerli olup olmadigini kontrol eder."""
        if not filepath.exists():
            return False
        if filepath.stat().st_size == 0:
            self._logger.warning(
                "[MultiLang] Bos plugin dosyasi: %s",
                filepath.name,
            )
            return False
        return True

    def _detect_metadata(self, filepath: Path) -> PluginMetadata:
        """Dosyadan metada bilgilerini algilar.

        .py dosyalari icin import ederek metadata okumaya calisir,
        diger diller icin dosya adini kullanir.
        """
        metadata = PluginMetadata(name=filepath.stem)

        if filepath.suffix == ".py":
            try:
                from plugin_system import PluginLoader
                loader = PluginLoader(str(self._plugins_dir))
                plugin_class = loader.load_plugin_from_file(filepath)
                if plugin_class is not None:
                    temp_instance = plugin_class()
                    metadata = temp_instance.metadata
            except Exception:
                pass

        return metadata

    # ------------------------------------------------------------------
    # Yukleme
    # ------------------------------------------------------------------

    async def load_plugin(self, name: str) -> bool:
        """Bir plugin'i yukler ve alt sureci baslatir.

        Args:
            name: Plugin adi

        Returns:
            Basarili mi
        """
        instance = self._instances.get(name)
        if instance is None:
            self._logger.error(
                "[MultiLang] Plugin bulunamadi: %s",
                name,
            )
            return False

        if instance.is_loaded:
            self._logger.debug(
                "[MultiLang] Plugin zaten yuklu: %s",
                name,
            )
            return True

        if name in self._disabled_plugins:
            self._logger.info(
                "[MultiLang] Plugin atlaniyor (devre disi): %s",
                name,
            )
            return False

        self._event_loop = asyncio.get_event_loop()

        result = await instance.load()

        if result:
            if name not in self._load_order:
                self._load_order.append(name)
            self._logger.info(
                "[MultiLang] Plugin yuklendi: %s (%s)",
                name,
                instance.language,
            )
        else:
            self._error_counts[name] = self._error_counts.get(name, 0) + 1
            self._logger.error(
                "[MultiLang] Plugin yuklenemedi: %s - %s",
                name,
                instance.error,
            )

            if self._fallback_to_python and instance.language != "python":
                self._logger.info(
                    "[MultiLang] Python fallback deneniyor: %s",
                    name,
                )
                fallback_ok = await self._try_python_fallback(name, instance)
                if fallback_ok:
                    return True

        return result

    async def load_all_plugins(self) -> Dict[str, bool]:
        """Tum kesfedilen pluginleri yukler.

        Returns:
            {plugin_adi: basarili_mi}
        """
        results = {}
        for name in self._load_order:
            results[name] = await self.load_plugin(name)

        for name in self._instances:
            if name not in results:
                results[name] = await self.load_plugin(name)

        return results

    async def unload_plugin(self, name: str) -> bool:
        """Bir plugin'i kaldirir.

        Args:
            name: Plugin adi

        Returns:
            Basarili mi
        """
        instance = self._instances.get(name)
        if instance is None:
            return False

        result = await instance.unload()

        if result:
            if name in self._load_order:
                self._load_order.remove(name)
            self._logger.info(
                "[MultiLang] Plugin kaldirildi: %s",
                name,
            )
        else:
            self._logger.error(
                "[MultiLang] Plugin kaldirilamadi: %s - %s",
                name,
                instance.error,
            )

        return result

    async def reload_plugin(self, name: str) -> bool:
        """Bir plugin'i yeniden baslatir (hot-reload).

        Args:
            name: Plugin adi

        Returns:
            Basarili mi
        """
        instance = self._instances.get(name)
        if instance is None:
            return False

        self._logger.info(
            "[MultiLang] Plugin yeniden yukleniyor: %s",
            name,
        )

        result = await instance.reload()

        if result:
            self._logger.info(
                "[MultiLang] Plugin yeniden yuklendi: %s",
                name,
            )
        else:
            self._logger.error(
                "[MultiLang] Plugin yeniden yuklenemedi: %s",
                name,
            )

        return result

    # ------------------------------------------------------------------
    # Hook Calistirma
    # ------------------------------------------------------------------

    async def execute_hook(
        self,
        hook: HookPoint,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Bir hook noktasindaki tum pluginleri calistirir.

        Hata izolasyonu: Bir plugin basarisiz olursa digerleri
        calismaya devam eder.

        Args:
            hook: Hook noktasi
            data: Hook verisi
            timeout: Zaman asimi

        Returns:
            Sonuclar listesi (her plugin icin bir sonuc)
        """
        results = []

        for name in self._load_order:
            instance = self._instances.get(name)
            if instance is None or not instance.is_loaded:
                continue
            if name in self._disabled_plugins:
                continue

            try:
                result = await instance.execute_hook(hook, data, timeout)
                results.append({
                    "plugin": name,
                    "language": instance.language,
                    "result": result,
                })
            except Exception as exc:
                results.append({
                    "plugin": name,
                    "language": instance.language,
                    "result": {"success": False, "error": str(exc)},
                })
                self._logger.error(
                    "[MultiLang] Hook hatasi '%s' plugin '%s': %s",
                    hook.value,
                    name,
                    exc,
                )

        return results

    async def execute_hook_chain(
        self,
        hook: HookPoint,
        initial_data: Any,
        timeout: Optional[float] = None,
    ) -> Any:
        """Zincirleme hook calistirir (her sonuc bir sonrakine gecer).

        Args:
            hook: Hook noktasi
            initial_data: Baslangic verisi
            timeout: Zaman asimi

        Returns:
            Son donusen veri
        """
        data = initial_data

        for name in self._load_order:
            instance = self._instances.get(name)
            if instance is None or not instance.is_loaded:
                continue
            if name in self._disabled_plugins:
                continue

            try:
                result = await instance.execute_hook(hook, data, timeout)
                if result.get("success") and result.get("data") is not None:
                    data = result["data"]
            except Exception as exc:
                self._logger.error(
                    "[MultiLang] Hook zincir hatasi '%s' plugin '%s': %s",
                    hook.value,
                    name,
                    exc,
                )

        return data

    # ------------------------------------------------------------------
    # Aktif/Pasif
    # ------------------------------------------------------------------

    def enable_plugin(self, name: str) -> bool:
        """Plugin'i aktif eder."""
        instance = self._instances.get(name)
        if instance is None:
            return False

        if not instance.is_loaded:
            return False

        instance._state = PluginState.ENABLED
        self._disabled_plugins.discard(name)
        self._logger.info(
            "[MultiLang] Plugin aktif: %s",
            name,
        )
        return True

    def disable_plugin(self, name: str) -> bool:
        """Plugin'i devre disi birakir."""
        instance = self._instances.get(name)
        if instance is None:
            return False

        if not instance.is_loaded:
            return False

        instance._state = PluginState.DISABLED
        self._disabled_plugins.add(name)
        self._logger.info(
            "[MultiLang] Plugin devre disi: %s",
            name,
        )
        return True

    def enable_all_plugins(self) -> Dict[str, bool]:
        """Tum pluginleri aktif eder."""
        results = {}
        for name, instance in self._instances.items():
            if instance.is_loaded:
                results[name] = self.enable_plugin(name)
        return results

    def disable_all_plugins(self) -> Dict[str, bool]:
        """Tum pluginleri devre disi birakir."""
        results = {}
        for name, instance in self._instances.items():
            if instance.is_loaded:
                results[name] = self.disable_plugin(name)
        return results

    # ------------------------------------------------------------------
    # Python Entegrasyonu
    # ------------------------------------------------------------------

    def integrate_with_plugin_manager(
        self,
        python_manager: PluginManager,
    ) -> None:
        """Mevcut PluginManager ile entegre olur.

        Python plugin'lerini PythonRunner uzerinden yonlendirir,
        diger dilleri ise kendi runner'lari ile calistirir.

        Args:
            python_manager: plugin_system.PluginManager ornegi
        """
        self._python_manager = python_manager
        self._python_instances = python_manager._plugin_instances

        self._logger.info(
            "[MultiLang] PluginManager ile entegre olundu "
            "(%d python plugin)",
            len(self._python_instances),
        )

    async def _try_python_fallback(
        self,
        name: str,
        original_instance: MultiLanguagePluginInstance,
    ) -> bool:
        """Diger dildeki plugin basarisiz olursa Python alternatifi dener.

        Ayni isimde .py dosyasi varsa onu yuklemeyi dener.
        """
        py_file = self._plugins_dir / f"{name}.py"
        if not py_file.exists():
            return False

        try:
            runner = PythonRunner(str(py_file), timeout=self._timeout)
            fallback_instance = MultiLanguagePluginInstance(py_file, runner)
            fallback_instance.set_metadata(original_instance.metadata)

            ok = await fallback_instance.load()
            if ok:
                self._instances[name] = fallback_instance
                if name not in self._load_order:
                    self._load_order.append(name)
                self._logger.info(
                    "[MultiLang] Python fallback basarili: %s",
                    name,
                )
                return True

        except Exception as exc:
            self._logger.warning(
                "[MultiLang] Python fallback hatasi: %s - %s",
                name,
                exc,
            )

        return False

    # ------------------------------------------------------------------
    # Izleme
    # ------------------------------------------------------------------

    def _start_watcher(self) -> None:
        """Plugin dizinini izlemeye baslar."""
        if self._watcher is not None:
            return

        self._watcher = MultiLanguageWatcher(
            plugins_dir=str(self._plugins_dir),
            instances=self._instances,
            reload_callback=self.reload_plugin,
            interval=2.0,
        )
        self._watcher.start()
        self._logger.info("[MultiLang] Watcher baslatildi")

    def stop_watcher(self) -> None:
        """Plugin izlemeyi durdurur."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
            self._logger.info("[MultiLang] Watcher durduruldu")

    # ------------------------------------------------------------------
    # Sorgulama
    # ------------------------------------------------------------------

    def get_plugin(self, name: str) -> Optional[MultiLanguagePluginInstance]:
        return self._instances.get(name)

    def get_plugins(self) -> Dict[str, MultiLanguagePluginInstance]:
        return dict(self._instances)

    def get_plugin_names(self) -> List[str]:
        return list(self._instances.keys())

    def get_active_plugins(self) -> List[MultiLanguagePluginInstance]:
        return [p for p in self._instances.values() if p.is_enabled]

    def get_loaded_plugins(self) -> List[MultiLanguagePluginInstance]:
        return [p for p in self._instances.values() if p.is_loaded]

    def get_plugins_by_language(self, language: str) -> List[MultiLanguagePluginInstance]:
        """Dile gore plugin listesi."""
        return [
            p for p in self._instances.values()
            if p.language == language
        ]

    def get_plugin_count(self) -> Dict[str, int]:
        counts: Dict[str, int] = {
            "total": len(self._instances),
            "loaded": 0,
            "enabled": 0,
            "disabled": 0,
            "error": 0,
        }
        for instance in self._instances.values():
            if instance.state == PluginState.ENABLED:
                counts["enabled"] += 1
                counts["loaded"] += 1
            elif instance.state in (PluginState.LOADED, PluginState.DISABLED):
                counts["loaded"] += 1
                if instance.state == PluginState.DISABLED:
                    counts["disabled"] += 1
            elif instance.state == PluginState.ERROR:
                counts["error"] += 1
        return counts

    def get_language_distribution(self) -> Dict[str, int]:
        """Dillere gore plugin dagilimi."""
        dist: Dict[str, int] = {}
        for instance in self._instances.values():
            lang = instance.language
            dist[lang] = dist.get(lang, 0) + 1
        return dist

    def check_runtime_availability(self) -> Dict[str, bool]:
        """Tum runtime'larin kullanilabilirlik durumu."""
        runtimes = ["python", "node", "lua", "ruby", "bash", "go"]
        result = {}
        for runtime in runtimes:
            try:
                if runtime == "python":
                    result[runtime] = PythonRunner.__new__(PythonRunner).is_runtime_available()
                elif runtime == "node":
                    result[runtime] = JavaScriptRunner.__new__(JavaScriptRunner).is_runtime_available()
                elif runtime == "lua":
                    result[runtime] = LuaRunner.__new__(LuaRunner).is_runtime_available()
                elif runtime == "ruby":
                    result[runtime] = RubyRunner.__new__(RubyRunner).is_runtime_available()
                elif runtime == "bash":
                    result[runtime] = BashRunner.__new__(BashRunner).is_runtime_available()
                elif runtime == "go":
                    result[runtime] = GoRunner.__new__(GoRunner).is_runtime_available()
            except Exception:
                result[runtime] = False
        return result

    def get_error_counts(self) -> Dict[str, int]:
        return dict(self._error_counts)

    def get_summary(self) -> Dict[str, Any]:
        """Genel plugin sistemi ozeti."""
        return {
            "total_plugins": len(self._instances),
            "loaded": sum(1 for p in self._instances.values() if p.is_loaded),
            "enabled": sum(1 for p in self._instances.values() if p.is_enabled),
            "disabled": sum(1 for p in self._instances.values() if p.state == PluginState.DISABLED),
            "errors": sum(1 for p in self._instances.values() if p.has_error),
            "languages": self.get_language_distribution(),
            "runtimes": self.check_runtime_availability(),
            "load_order": list(self._load_order),
        }

    # ------------------------------------------------------------------
    # Temizlik
    # ------------------------------------------------------------------

    async def shutdown_all(self) -> None:
        """Tum pluginleri guvenli sekilde kapatir."""
        self._logger.info("[MultiLang] Tum pluginler kapatiliyor...")

        for name, instance in list(self._instances.items()):
            try:
                await instance.unload()
            except Exception as exc:
                self._logger.error(
                    "[MultiLang] Kapatma hatasi: %s - %s",
                    name,
                    exc,
                )

        if self._watcher:
            self._watcher.stop()
            self._watcher = None

        self._instances.clear()
        self._load_order.clear()
        self._logger.info("[MultiLang] Tum pluginler kapatildi")


# ---------------------------------------------------------------------------
# MultiLanguageWatcher
# ---------------------------------------------------------------------------


class MultiLanguageWatcher:
    """Coklu-dil plugin dosyalarini izleyen watcher.

    .py, .js, .lua, .rb, .sh, .go dosyalarindaki degisiklikleri
    algilar ve ilgili plugin'i otomatik yeniden baslatir.
    """

    def __init__(
        self,
        plugins_dir: str,
        instances: Dict[str, MultiLanguagePluginInstance],
        reload_callback: Callable,
        interval: float = 2.0,
    ) -> None:
        self._plugins_dir = Path(plugins_dir)
        self._instances = instances
        self._reload_callback = reload_callback
        self._interval = interval
        self._running = False
        self._timer: Optional[Thread] = None
        self._file_hashes: Dict[str, float] = {}
        self._logger = logging.getLogger(f"{__name__}.MultiLanguageWatcher")
        self._lock = Lock()

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._build_hash_index()
            self._schedule_next()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._timer and self._timer.is_alive():
                self._timer = None

    def _build_hash_index(self) -> None:
        self._file_hashes = {}
        if not self._plugins_dir.exists():
            return

        supported_exts = RunnerFactory.get_supported_extensions()
        for ext in supported_exts:
            for filepath in self._plugins_dir.glob(f"*{ext}"):
                if not filepath.name.startswith("_"):
                    try:
                        self._file_hashes[str(filepath)] = filepath.stat().st_mtime
                    except OSError:
                        pass

    def _check_changes(self) -> None:
        with self._lock:
            if not self._running:
                return

            try:
                if not self._plugins_dir.exists():
                    return

                current_hashes: Dict[str, float] = {}
                changed_files: List[str] = []

                supported_exts = RunnerFactory.get_supported_extensions()
                for ext in supported_exts:
                    for filepath in self._plugins_dir.glob(f"*{ext}"):
                        if filepath.name.startswith("_"):
                            continue

                        path_str = str(filepath)
                        try:
                            mtime = filepath.stat().st_mtime
                        except OSError:
                            continue

                        current_hashes[path_str] = mtime
                        old_mtime = self._file_hashes.get(path_str)
                        if old_mtime is not None and mtime != old_mtime:
                            changed_files.append(path_str)
                        elif old_mtime is None:
                            yeni_dosya = True
                            changed_files.append(path_str)

                self._file_hashes = current_hashes

                for filepath_str in changed_files:
                    filepath = Path(filepath_str)
                    plugin_name = filepath.stem

                    self._logger.info(
                        "[Watcher] Degisiklik algilandi: %s",
                        filepath.name,
                    )

                    if plugin_name in self._instances:
                        try:
                            asyncio.run_coroutine_threadsafe(
                                self._reload_callback(plugin_name),
                                asyncio.get_event_loop(),
                            )
                        except Exception as exc:
                            self._logger.error(
                                "[Watcher] Yeniden yukleme hatasi: %s - %s",
                                plugin_name,
                                exc,
                            )

            except Exception as exc:
                self._logger.error(
                    "[Watcher] Kontrol hatasi: %s",
                    exc,
                )
            finally:
                if self._running:
                    self._schedule_next()

    def _schedule_next(self) -> None:
        self._timer = Thread(target=self._timer_wait, daemon=True)
        self._timer.start()

    def _timer_wait(self) -> None:
        import time as _time
        _time.sleep(self._interval)
        self._check_changes()


# ---------------------------------------------------------------------------
# Yardimci Fonksiyonlar
# ---------------------------------------------------------------------------


def detect_language(filepath: str) -> Optional[str]:
    """Dosya yoluna gore dil turunu algilar.

    Args:
        filepath: Dosya yolu

    Returns:
        Dil adi ("python", "javascript", vb.) veya None
    """
    ext = Path(filepath).suffix.lower()
    return PLUGIN_EXTENSIONS.get(ext)


def create_plugin_template(
    language: str,
    name: str = "OrnekPlugin",
    version: str = "1.0.0",
    author: str = "Glassescat AI",
    description: str = "Ornek plugin",
) -> str:
    """Belirtilen dilde plugin sablonu olusturur.

    Args:
        language: Dil ("python", "javascript", "lua", "ruby", "bash", "go")
        name: Plugin adi
        version: Versiyon
        author: Yazar
        description: Aciklama

    Returns:
        Plugin kaynak kodu

    Raises:
        ValueError: Desteklenmeyen dil
    """
    templates = {
        "javascript": _js_template,
        "lua": _lua_template,
        "ruby": _rb_template,
        "bash": _sh_template,
        "go": _go_template,
    }

    template_func = templates.get(language)
    if template_func is None:
        raise ValueError(
            f"Desteklenmeyen dil: {language} "
            f"(desteklenen: {', '.join(templates.keys())})"
        )

    return template_func(name=name, version=version, author=author, description=description)


def _js_template(
    name: str = "OrnekPlugin",
    version: str = "1.0.0",
    author: str = "Glassescat AI",
    description: str = "Ornek plugin",
) -> str:
    return textwrap.dedent(f'''\
    // {name} - Glassescat AI / GlassesCat Plugin
    // Version: {version}
    // Author: {author}
    // Description: {description}

    const readline = require('readline');

    const rl = readline.createInterface({{
        input: process.stdin,
        output: process.stdout,
        terminal: false,
    }});

    // Plugin metadata
    const metadata = {{
        name: "{name}",
        version: "{version}",
        author: "{author}",
        description: "{description}",
    }};

    // Hook handlers
    const handlers = {{
        before_chat: (data) => {{
            return {{ message: data.message, context: data.context }};
        }},
        after_chat: (data) => {{
            return {{ response: data.response, context: data.context }};
        }},
        on_startup: (data) => {{
            return {{ status: "ok" }};
        }},
        on_shutdown: (data) => {{
            return {{ status: "ok" }};
        }},
    }};

    rl.on('line', (input) => {{
        try {{
            const msg = JSON.parse(input);
            const action = msg.action;

            if (action === 'handshake') {{
                console.log(JSON.stringify({{
                    success: true,
                    message_id: msg.message_id,
                    data: {{ name: metadata.name, version: metadata.version }}
                }}));
                return;
            }}

            if (action === 'heartbeat') {{
                console.log(JSON.stringify({{
                    success: true,
                    action: 'heartbeat_ack',
                    message_id: msg.message_id,
                }}));
                return;
            }}

            if (action === 'shutdown') {{
                process.exit(0);
            }}

            if (action === 'execute') {{
                const hook = msg.hook;
                const data = msg.data || {{}};
                const handler = handlers[hook];

                if (handler) {{
                    const result = handler(data);
                    console.log(JSON.stringify({{
                        success: true,
                        message_id: msg.message_id,
                        data: result,
                    }}));
                }} else {{
                    console.log(JSON.stringify({{
                        success: false,
                        message_id: msg.message_id,
                        error: `Bilinmeyen hook: ${{hook}}`,
                    }}));
                }}
                return;
            }}

            console.log(JSON.stringify({{
                success: false,
                message_id: msg.message_id,
                error: `Bilinmeyen eylem: ${{action}}`,
            }}));

        }} catch (err) {{
            console.log(JSON.stringify({{
                success: false,
                error: `JSON hatasi: ${{err.message}}`,
            }}));
        }}
    }}));
    ''')


def _lua_template(
    name: str = "OrnekPlugin",
    version: str = "1.0.0",
    author: str = "Glassescat AI",
    description: str = "Ornek plugin",
) -> str:
    return textwrap.dedent(f'''\
    -- {name} - Glassescat AI / GlassesCat Plugin
    -- Version: {version}
    -- Author: {author}
    -- Description: {description}

    local json = require("json")

    local metadata = {{
        name = "{name}",
        version = "{version}",
        author = "{author}",
        description = "{description}",
    }}

    local handlers = {{
        before_chat = function(data)
            return {{ message = data.message, context = data.context }}
        end,
        after_chat = function(data)
            return {{ response = data.response, context = data.context }}
        end,
        on_startup = function(data)
            return {{ status = "ok" }}
        end,
        on_shutdown = function(data)
            return {{ status = "ok" }}
        end,
    }}

    while true do
        local line = io.read("*line")
        if line == nil then break end

        local ok, msg = pcall(json.decode, line)
        if not ok then
            io.write(json.encode({{ success = false, error = "JSON hatasi" }}) .. "\\n")
            io.flush()
            goto continue
        end

        local action = msg.action

        if action == "handshake" then
            io.write(json.encode({{
                success = true,
                message_id = msg.message_id,
                data = {{ name = metadata.name, version = metadata.version }},
            }}) .. "\\n")
            io.flush()
            goto continue
        end

        if action == "heartbeat" then
            io.write(json.encode({{
                success = true,
                action = "heartbeat_ack",
                message_id = msg.message_id,
            }}) .. "\\n")
            io.flush()
            goto continue
        end

        if action == "shutdown" then
            os.exit(0)
        end

        if action == "execute" then
            local hook = msg.hook
            local data = msg.data or {{}}
            local handler = handlers[hook]

            if handler then
                local result = handler(data)
                io.write(json.encode({{
                    success = true,
                    message_id = msg.message_id,
                    data = result,
                }}) .. "\\n")
                io.flush()
            else
                io.write(json.encode({{
                    success = false,
                    message_id = msg.message_id,
                    error = "Bilinmeyen hook: " .. hook,
                }}) .. "\\n")
                io.flush()
            end
            goto continue
        end

        io.write(json.encode({{
            success = false,
            message_id = msg.message_id,
            error = "Bilinmeyen eylem: " .. action,
        }}) .. "\\n")
        io.flush()

        ::continue::
    end
    ''')


def _rb_template(
    name: str = "OrnekPlugin",
    version: str = "1.0.0",
    author: str = "Glassescat AI",
    description: str = "Ornek plugin",
) -> str:
    return textwrap.dedent(f'''\
    # {name} - Glassescat AI / GlassesCat Plugin
    # Version: {version}
    # Author: {author}
    # Description: {description}

    require "json"

    metadata = {{
        name: "{name}",
        version: "{version}",
        author: "{author}",
        description: "{description}",
    }}

    handlers = {{
        "before_chat" => ->(data) {{
            {{ message: data["message"], context: data["context"] }}
        }},
        "after_chat" => ->(data) {{
            {{ response: data["response"], context: data["context"] }}
        }},
        "on_startup" => ->(data) {{
            {{ status: "ok" }}
        }},
        "on_shutdown" => ->(data) {{
            {{ status: "ok" }}
        }},
    }}

    $stdin.each_line do |line|
        begin
            msg = JSON.parse(line)
            action = msg["action"]

            case action
            when "handshake"
                puts JSON.generate({{
                    success: true,
                    message_id: msg["message_id"],
                    data: {{ name: metadata[:name], version: metadata[:version] }},
                }})
                $stdout.flush

            when "heartbeat"
                puts JSON.generate({{
                    success: true,
                    action: "heartbeat_ack",
                    message_id: msg["message_id"],
                }})
                $stdout.flush

            when "shutdown"
                exit(0)

            when "execute"
                hook = msg["hook"]
                data = msg["data"] || {{}}
                handler = handlers[hook]

                if handler
                    result = handler.call(data)
                    puts JSON.generate({{
                        success: true,
                        message_id: msg["message_id"],
                        data: result,
                    }})
                else
                    puts JSON.generate({{
                        success: false,
                        message_id: msg["message_id"],
                        error: "Bilinmeyen hook: #{{hook}}",

            else
                puts JSON.generate({{
                    success: false,
                    message_id: msg["message_id"],
                    error: "Bilinmeyen eylem: #{{action}}",
                }})
                $stdout.flush
            end

        rescue JSON::ParserError => e
            puts JSON.generate({{
                success: false,
                error: "JSON hatasi: #{{e.message}}",
            }})
            $stdout.flush
        end
    end
    ''')


def _sh_template(
    name: str = "OrnekPlugin",
    version: str = "1.0.0",
    author: str = "Glassescat AI",
    description: str = "Ornek plugin",
) -> str:
    return textwrap.dedent(f'''\
    #!/usr/bin/env bash
    # {name} - Glassescat AI / GlassesCat Plugin
    # Version: {version}
    # Author: {author}
    # Description: {description}

    metadata_name="{name}"
    metadata_version="{version}"
    metadata_author="{author}"
    metadata_description="{description}"

    before_chat() {{
        local data="$1"
        echo "$data"
    }}

    after_chat() {{
        local data="$1"
        echo "$data"
    }}

    on_startup() {{
        echo '{{"status":"ok"}}'
    }}

    on_shutdown() {{
        echo '{{"status":"ok"}}'
    }}

    while IFS= read -r line; do
        action=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin).get('action',''))" 2>/dev/null)

        if [ "$action" = "handshake" ]; then
            msg_id=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message_id',''))" 2>/dev/null)
            echo "{{\\"success\\":true,\\"message_id\\":\\"$msg_id\\",\\"data\\":{{\\"name\\":\\"$metadata_name\\",\\"version\\":\\"$metadata_version\\"}}}}"
            continue
        fi

        if [ "$action" = "heartbeat" ]; then
            msg_id=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message_id',''))" 2>/dev/null)
            echo "{{\\"success\\":true,\\"action\\":\\"heartbeat_ack\\",\\"message_id\\":\\"$msg_id\\"}}"
            continue
        fi

        if [ "$action" = "shutdown" ]; then
            exit 0
        fi

        if [ "$action" = "execute" ]; then
            hook=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hook',''))" 2>/dev/null)
            msg_id=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message_id',''))" 2>/dev/null)

            case "$hook" in
                before_chat)
                    result=$(before_chat "$line")
                    echo "{{\\"success\\":true,\\"message_id\\":\\"$msg_id\\",\\"data\\":$result}}"
                    ;;
                after_chat)
                    result=$(after_chat "$line")
                    echo "{{\\"success\\":true,\\"message_id\\":\\"$msg_id\\",\\"data\\":$result}}"
                    ;;
                on_startup)
                    result=$(on_startup)
                    echo "{{\\"success\\":true,\\"message_id\\":\\"$msg_id\\",\\"data\\":$result}}"
                    ;;
                on_shutdown)
                    result=$(on_shutdown)
                    echo "{{\\"success\\":true,\\"message_id\\":\\"$msg_id\\",\\"data\\":$result}}"
                    ;;
                *)
                    echo "{{\\"success\\":false,\\"message_id\\":\\"$msg_id\\",\\"error\\":\\"Bilinmeyen hook: $hook\\"}}"
                    ;;
            esac
            continue
        fi

        msg_id=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message_id',''))" 2>/dev/null)
        echo "{{\\"success\\":false,\\"message_id\\":\\"$msg_id\\",\\"error\\":\\"Bilinmeyen eylem: $action\\"}}"

    done
    ''')


def _go_template(
    name: str = "OrnekPlugin",
    version: str = "1.0.0",
    author: str = "Glassescat AI",
    description: str = "Ornek plugin",
) -> str:
    return textwrap.dedent(f'''\
    package main

    import (
        "bufio"
        "encoding/json"
        "fmt"
        "os"
        "os/signal"
        "syscall"
    )

    // {name} - Glassescat AI / GlassesCat Plugin
    // Version: {version}
    // Author: {author}
    // Description: {description}

    type Message struct {{
        Action     string         `json:"action"`
        Hook       string         `json:"hook,omitempty"`
        Data       map[string]any `json:"data,omitempty"`
        MessageID  string         `json:"message_id,omitempty"`
        Timestamp  string         `json:"timestamp,omitempty"`
    }}

    type Response struct {{
        Success   bool           `json:"success"`
        Action    string         `json:"action,omitempty"`
        MessageID string         `json:"message_id,omitempty"`
        Data      map[string]any `json:"data,omitempty"`
        Error     string         `json:"error,omitempty"`
    }}

    type Handler func(map[string]any) map[string]any

    var metadata = map[string]string{{
        "name":        "{name}",
        "version":     "{version}",
        "author":      "{author}",
        "description": "{description}",
    }}

    var handlers = map[string]Handler{{
        "before_chat": func(data map[string]any) map[string]any {{
            return map[string]any{{"message": data["message"], "context": data["context"]}}
        }},
        "after_chat": func(data map[string]any) map[string]any {{
            return map[string]any{{"response": data["response"], "context": data["context"]}}
        }},
        "on_startup": func(data map[string]any) map[string]any {{
            return map[string]any{{"status": "ok"}}
        }},
        "on_shutdown": func(data map[string]any) map[string]any {{
            return map[string]any{{"status": "ok"}}
        }},
    }}

    func writeResponse(resp Response) {{
        data, _ := json.Marshal(resp)
        fmt.Println(string(data))
    }}

    func main() {{
        scanner := bufio.NewScanner(os.Stdin)

        sigChan := make(chan os.Signal, 1)
        signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)

        go func() {{
            <-sigChan
            os.Exit(0)
        }}()

        for scanner.Scan() {{
            line := scanner.Text()
            var msg Message

            if err := json.Unmarshal([]byte(line), &msg); err != nil {{
                writeResponse(Response{{
                    Success: false,
                    Error:   "JSON hatasi: " + err.Error(),
                }})
                continue
            }}

            switch msg.Action {{
            case "handshake":
                writeResponse(Response{{
                    Success:   true,
                    MessageID: msg.MessageID,
                    Data:      map[string]any{{"name": metadata["name"], "version": metadata["version"]}},
                }})

            case "heartbeat":
                writeResponse(Response{{
                    Success:   true,
                    Action:    "heartbeat_ack",
                    MessageID: msg.MessageID,
                }})

            case "shutdown":
                os.Exit(0)

            case "execute":
                handler, ok := handlers[msg.Hook]
                if !ok {{
                    writeResponse(Response{{
                        Success:   false,
                        MessageID: msg.MessageID,
                        Error:     "Bilinmeyen hook: " + msg.Hook,
                    }})
                    continue
                }}
                result := handler(msg.Data)
                writeResponse(Response{{
                    Success:   true,
                    MessageID: msg.MessageID,
                    Data:      result,
                }})

            default:
                writeResponse(Response{{
                    Success:   false,
                    MessageID: msg.MessageID,
                    Error:     "Bilinmeyen eylem: " + msg.Action,
                }})
            }}
        }}
    }}
    ''')


# ---------------------------------------------------------------------------
# Test / Demo
# ---------------------------------------------------------------------------


async def demo() -> None:
    """Coklu-dil plugin sistemini test eder.

    Ornek kullanim:
        python plugin_runner.py
    """
    print("=" * 60)
    print("  SHADOWCAT COKLU-DIL PLUGIN SISTEMI - Test")
    print("  Berkay Software - Lead Engineer AI")
    print("=" * 60)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    manager = MultiLanguagePluginManager(plugins_dir="plugins")

    runtime_status = manager.check_runtime_availability()
    print("\nRuntime Durumu:")
    for runtime, available in runtime_status.items():
        status = "[+] Mevcut" if available else "[-] Yok"
        print(f"  {runtime:>12}: {status}")

    discovered = manager.discover_plugins()
    print(f"\nKesfedilen pluginler ({len(discovered)}):")
    for name in discovered:
        plugin = manager.get_plugin(name)
        if plugin:
            print(f"  - {name} ({plugin.language})")

    results = await manager.load_all_plugins()
    loaded = sum(1 for r in results.values() if r)
    print(f"\nYuklenen: {loaded}/{len(results)}")

    manager.enable_all_plugins()

    print("\nPlugin Ozeti:")
    summary = manager.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print("\nCoklu-dil plugin sistemi hazir!")
    print("Kullanici kapatmasini bekleniyor (Ctrl+C)...")


if __name__ == "__main__":
    asyncio.run(demo())
