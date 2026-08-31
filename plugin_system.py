"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║      ██████╗ ██╗     ██╗   ██╗ ██████╗ ██╗███╗   ██╗                     ║
║      ██╔══██╗██║     ██║   ██║██╔════╝ ██║████╗  ██║                     ║
║      ██████╔╝██║     ██║   ██║██║  ███╗██║██╔██╗ ██║                     ║
║      ██╔═══╝ ██║     ██║   ██║██║   ██║██║██║╚██╗██║                     ║
║      ██║     ███████╗╚██████╔╝╚██████╔╝██║██║ ╚████║                     ║
║      ╚═╝     ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝╚═╝  ╚═══╝                     ║
║                    ███████╗██╗   ██╗███████╗████████╗                     ║
║                    ██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝                     ║
║                    █████╗   ╚████╔╝ ███████╗   ██║                        ║
║                    ██╔══╝    ╚██╔╝  ╚════██║   ██║                        ║
║                    ███████╗   ██║   ███████║   ██║                        ║
║                    ╚══════╝   ╚═╝   ╚══════╝   ╚═╝                        ║
║                                                                           ║
║              SHADOWCAT / GLASSCAT PLUGIN & EKLENTI SISTEMI                  ║
║                    Berkay Software - Lead Engineer AI                      ║
║                         Version 1.0 - SWA 1.6                            ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

Shadowcat AI Plugin Sistemi - Dinamik eklenti yukleme, yonetim ve hook altyapisi.

Kullanim:
    >>> from plugin_system import PluginManager
    >>> manager = PluginManager()
    >>> manager.discover_plugins()
    >>> manager.load_all_plugins()
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import logging
import os
import sys
import textwrap
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import Lock, RLock, Timer
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

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.tree import Tree

logger = logging.getLogger(__name__)
console = Console()

T = TypeVar("T", bound="BasePlugin")


class PluginState(Enum):
    """Eklenti durumunu belirten enum."""

    DISCOVERED = "discovered"
    LOADING = "loading"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UNLOADED = "unloaded"


class HookPoint(Enum):
    """Sistemin destekledigi tum hook noktalari."""

    ON_STARTUP = "on_startup"
    ON_SHUTDOWN = "on_shutdown"
    BEFORE_CHAT = "before_chat"
    AFTER_CHAT = "after_chat"
    BEFORE_RESPONSE = "before_response"
    AFTER_RESPONSE = "after_response"
    ON_MESSAGE = "on_message"
    ON_COMMAND = "on_command"
    ON_ERROR = "on_error"
    ON_PLUGIN_LOAD = "on_plugin_load"
    ON_PLUGIN_UNLOAD = "on_plugin_unload"
    ON_CONFIG_CHANGE = "on_config_change"
    ON_USER_INPUT = "on_user_input"
    ON_UI_RENDER = "on_ui_render"
    ON_TOOL_EXECUTE = "on_tool_execute"


class PluginPriority(Enum):
    """Hook calisma siralamasi icin oncelik seviyeleri."""

    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
    CRITICAL = 150


@dataclass
class PluginMetadata:
    """Eklenti metadata bilgileri.

    Attributes:
        name: Eklenti adi
        version: Versyon numarasi
        author: Yazar bilgisi
        description: Eklenti aciklamasi
        homepage: Proje sayfasi URL
        license: Lisans turu
        tags: Etiket listesi
        min_api_version: Gereken minimum API versiyonu
    """

    name: str = "Bilinmeyen Plugin"
    version: str = "1.0.0"
    author: str = "Bilinmiyor"
    description: str = ""
    homepage: str = ""
    license: str = "MIT"
    tags: List[str] = field(default_factory=list)
    min_api_version: str = "1.0.0"


@dataclass
class PluginDependency:
    """Eklenti bagimliligi tanimi.

    Attributes:
        name: Bagimli eklenti adi
        version: Gereken versiyon (bosluk = herhangi)
        optional: Zorunlu mu
    """

    name: str
    version: str = ""
    optional: bool = False


@dataclass
class HookRegistration:
    """Hook kayit bilgisi.

    Attributes:
        hook_point: Hook noktasi
        callback: Cagrilacak fonksiyon
        priority: Oncelik seviyesi
        plugin_name: Kaydeden eklenti adi
    """

    hook_point: HookPoint
    callback: Callable
    priority: PluginPriority = PluginPriority.NORMAL
    plugin_name: str = ""


@dataclass
class CommandRegistration:
    """Komut kayit bilgisi.

    Attributes:
        name: Komut adi (eg. /hava)
        handler: Komutu isleyecek fonksiyon
        description: Komut aciklamasi
        aliases: Takma ad listesi
        usage: Kullanim ornegi
        plugin_name: Kaydeden eklenti adi
    """

    name: str
    handler: Callable
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    usage: str = ""
    plugin_name: str = ""


@dataclass
class MiddlewareRegistration:
    """Middleware kayit bilgisi.

    Attributes:
        name: Middleware adi
        handler: Cagrilacak fonksiyon (message, context -> message, context)
        priority: Oncelik
        plugin_name: Kaydeden eklenti adi
    """

    name: str
    handler: Callable
    priority: int = 50
    plugin_name: str = ""


@dataclass
class UIComponentRegistration:
    """UI bileseni kayit bilgisi.

    Attributes:
        component_id: Benzersiz bilesen ID
        render_func: Render fonksiyonu
        location: Gosterilecek konum (sidebar, header, footer, vs.)
        plugin_name: Kaydeden eklenti adi
    """

    component_id: str
    render_func: Callable
    location: str = "sidebar"
    plugin_name: str = ""


class PluginError(Exception):
    """Plugin sistemi temel hata sinifi."""

    pass


class PluginLoadError(PluginError):
    """Eklenti yuklenirken olusan hata."""

    pass


class PluginDependencyError(PluginError):
    """Eklenti bagimliligi cozulemediginde olusan hata."""

    pass


class PluginHookError(PluginError):
    """Hook calistirilirken olusan hata."""

    pass


class PluginIsolationMeta(type):
    """Eklenti izolasyonu icin metaclass.

    Her eklenti kendi namespace'inde calisir ve bir eklentinin
    basarisizligi digerlerini etkilemez.
    """

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        try:
            instance = super().__call__(*args, **kwargs)
            return instance
        except Exception as exc:
            logger.error(
                "[PluginIsolation] %s ornegi olusturulamadi: %s",
                cls.__name__,
                exc,
            )
            raise


class BasePlugin(metaclass=PluginIsolationMeta):
    """Tum eklentilerin turemesi gereken temel sinif.

    Kullanim:
        class HavaDurumuPlugin(BasePlugin):
            def __init__(self):
                super().__init__()
                self.metadata = PluginMetadata(
                    name="Hava Durumu",
                    version="1.0.0",
                    author="Berkay",
                    description="Hava durumu bilgisi gosterir"
                )

            def on_load(self):
                self.register_command("/hava", self.hava_durumu, "Hava durumu")

            def hava_durumu(self, args: str, context: Dict) -> str:
                return "Bugun hava guzel!"
    """

    metadata: PluginMetadata = field(default_factory=PluginMetadata)
    dependencies: List[PluginDependency] = field(default_factory=list)
    state: PluginState = PluginState.DISCOVERED
    config: Dict[str, Any] = field(default_factory=dict)
    plugin_dir: str = ""
    plugin_file: str = ""

    HOOK_PRIORITY: ClassVar[PluginPriority] = PluginPriority.NORMAL

    def __init__(self) -> None:
        self._hooks: List[HookRegistration] = []
        self._commands: List[CommandRegistration] = []
        self._middlewares: List[MiddlewareRegistration] = []
        self._ui_components: List[UIComponentRegistration] = []
        self._start_time: float = 0.0
        self._error_count: int = 0

        self.metadata = PluginMetadata()
        self.dependencies = []
        self.config = {}

    def on_load(self) -> None:
        """Eklenti yuklendiginde cagrilir. Alt siniflar ezebilir."""
        pass

    def on_unload(self) -> None:
        """Eklenti kaldirilirken cagrilir. Alt siniflar ezebilir."""
        pass

    def on_enable(self) -> None:
        """Eklenti aktif edildiginde cagrilir. Alt siniflar ezebilir."""
        pass

    def on_disable(self) -> None:
        """Eklenti devre disi birakildiginda cagrilir. Alt siniflar ezebilir."""
        pass

    def on_chat(self, message: str, context: Dict[str, Any]) -> Optional[str]:
        """Sohbet mesaji islenirken cagrilir.

        Args:
            message: Kullanici mesaji
            context: Sohbet baglami

        Returns:
            Yanit metni veya None
        """
        return None

    def on_startup(self) -> None:
        """Sistem baslatildiginda cagrilir. Alt siniflar ezebilir."""
        pass

    def on_shutdown(self) -> None:
        """Sistem kapatilirken cagrilir. Alt siniflar ezebilir."""
        pass

    def before_chat(self, message: str, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """AI yanitindan once cagrilir. Mesaji degistirebilir.

        Args:
            message: Kullanici mesaji
            context: Sohbet baglami

        Returns:
            (degistirilmis_mesaj, degistirilmis_baglam)
        """
        return message, context

    def after_chat(self, response: str, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """AI yanitindan sonra cagrilir. Yaniti degistirebilir.

        Args:
            response: AI yaniti
            context: Sohbet baglami

        Returns:
            (degistirilmis_yanit, degistirilmis_baglam)
        """
        return response, context

    def on_error(self, error: Exception, context: Dict[str, Any]) -> Optional[str]:
        """Hata olustugunda cagrilir.

        Args:
            error: Olusan hata
            context: Hata baglami

        Returns:
            Hata mesaji veya None
        """
        return None

    def register_hook(
        self,
        hook_point: HookPoint,
        callback: Callable,
        priority: PluginPriority = PluginPriority.NORMAL,
    ) -> None:
        """Hook noktasina fonksiyon kaydeder.

        Args:
            hook_point: Hangi hook noktasina
            callback: Cagrilacak fonksiyon
            priority: Oncelik seviyesi
        """
        self._hooks.append(
            HookRegistration(
                hook_point=hook_point,
                callback=callback,
                priority=priority,
                plugin_name=self.metadata.name,
            )
        )

    def register_command(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        aliases: Optional[List[str]] = None,
        usage: str = "",
    ) -> None:
        """Yeni bir komut kaydeder.

        Args:
            name: Komut adi (ornek: '/hava')
            handler: Komut isleyici fonksiyon
            description: Komut aciklamasi
            aliases: Takma ad listesi
            usage: Kullanim ornegi
        """
        self._commands.append(
            CommandRegistration(
                name=name,
                handler=handler,
                description=description,
                aliases=aliases or [],
                usage=usage,
                plugin_name=self.metadata.name,
            )
        )

    def register_middleware(
        self,
        name: str,
        handler: Callable,
        priority: int = 50,
    ) -> None:
        """Middleware kaydeder.

        Middleware imzasi: (message: str, context: Dict) -> Tuple[str, Dict]

        Args:
            name: Middleware adi
            handler: Isleyici fonksiyon
            priority: Oncelik (dusuk = once calisir)
        """
        self._middlewares.append(
            MiddlewareRegistration(
                name=name,
                handler=handler,
                priority=priority,
                plugin_name=self.metadata.name,
            )
        )

    def register_ui_component(
        self,
        component_id: str,
        render_func: Callable,
        location: str = "sidebar",
    ) -> None:
        """UI bileseni kaydeder.

        Args:
            component_id: Benzersiz bilesen ID
            render_func: Render fonksiyonu
            location: Konum (sidebar, header, footer, main)
        """
        self._ui_components.append(
            UIComponentRegistration(
                component_id=component_id,
                render_func=render_func,
                location=location,
                plugin_name=self.metadata.name,
            )
        )

    def get_settings_template(self) -> Optional[Dict[str, Any]]:
        """Eklenti ayar semasini doner.

        Returns:
            Ayar semasi (JSON Schema formati) veya None
        """
        return None

    def get_hooks(self) -> List[HookRegistration]:
        """Kayitli hook'lari dondurur."""
        return list(self._hooks)

    def get_commands(self) -> List[CommandRegistration]:
        """Kayitli komutlari dondurur."""
        return list(self._commands)

    def get_middlewares(self) -> List[MiddlewareRegistration]:
        """Kayitli middleware'lari dondurur."""
        return list(self._middlewares)

    def get_ui_components(self) -> List[UIComponentRegistration]:
        """Kayitli UI bilesenlerini dondurur."""
        return list(self._ui_components)

    @property
    def uptime(self) -> float:
        """Eklentinin calisma suresini dondurur (saniye)."""
        if self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    @property
    def error_count(self) -> int:
        """Eklentinin hata sayisini dondurur."""
        return self._error_count

    def increment_error(self) -> None:
        """Hata sayacini bir artirir."""
        self._error_count += 1


class PluginLoader:
    """Eklenti dosyalarini bulma ve yukleme islemlerini yapar.

    plugins/ dizinini tarar, Python dosyalarini bulur ve
    BasePlugin turevlerini import eder.
    """

    def __init__(self, plugins_dir: str = "plugins") -> None:
        self.plugins_dir = Path(plugins_dir).resolve()
        self._loaded_modules: Dict[str, Any] = {}

    def discover_plugin_files(self) -> List[Path]:
        """plugins/ dizinindeki tum Python dosyalarini bulur.

        Returns:
            Plugin dosya yollari listesi
        """
        if not self.plugins_dir.exists():
            logger.warning(
                "[PluginLoader] Plugin dizini bulunamadi: %s",
                self.plugins_dir,
            )
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            logger.info(
                "[PluginLoader] Plugin dizini olusturuldu: %s",
                self.plugins_dir,
            )
            return []

        plugin_files = sorted(self.plugins_dir.glob("*.py"))

        plugin_files = [
            p for p in plugin_files if not p.name.startswith("_")
        ]

        logger.info(
            "[PluginLoader] %d plugin dosyasi bulundu",
            len(plugin_files),
        )
        return plugin_files

    def load_plugin_from_file(self, filepath: Path) -> Optional[Type[BasePlugin]]:
        """Bir dosyadan eklenti sinifini yukler.

        Args:
            filepath: Python dosya yolu

        Returns:
            BasePlugin turevi sinif veya None

        Raises:
            PluginLoadError: Yukleme basarisiz olursa
        """
        try:
            module_name = f"glassescat_plugin_{filepath.stem}"

            if module_name in self._loaded_modules:
                logger.debug(
                    "[PluginLoader] Modul zaten yuklu, yeniden yukleniyor: %s",
                    module_name,
                )
                del self._loaded_modules[module_name]
                if module_name in sys.modules:
                    del sys.modules[module_name]

            spec = importlib.util.spec_from_file_location(
                module_name,
                filepath,
            )
            if spec is None or spec.loader is None:
                raise PluginLoadError(
                    f"Modul spesifikasyonu olusturulamadi: {filepath}"
                )

            module = importlib.util.module_from_spec(spec)
            self._loaded_modules[module_name] = module
            sys.modules[module_name] = module

            spec.loader.exec_module(module)

            plugin_class = self._find_plugin_class(module)
            if plugin_class is None:
                logger.warning(
                    "[PluginLoader] Plugin sinifi bulunamadi: %s",
                    filepath.name,
                )
                return None

            return plugin_class

        except SyntaxError as exc:
            raise PluginLoadError(
                f"Plugin dosyasinda sentaks hatasi ({filepath.name}): {exc}"
            ) from exc
        except ImportError as exc:
            raise PluginLoadError(
                f"Plugin bagimliligi yuklenemedi ({filepath.name}): {exc}"
            ) from exc
        except Exception as exc:
            raise PluginLoadError(
                f"Plugin yuklenemedi ({filepath.name}): {exc}"
            ) from exc

    def reload_plugin_module(self, plugin_name: str) -> None:
        """Bir eklenti modulunu yeniden yukler (hot-reload).

        Args:
            plugin_name: Modul adi
        """
        module_name = f"glassescat_plugin_{plugin_name}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        if module_name in self._loaded_modules:
            del self._loaded_modules[module_name]

    def _find_plugin_class(self, module: Any) -> Optional[Type[BasePlugin]]:
        """Modul icinde BasePlugin turevi sinifi bulur.

        Args:
            module: Python modulu

        Returns:
            Ilk bulunan BasePlugin turevi veya None
        """
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BasePlugin)
                and obj is not BasePlugin
            ):
                return obj
        return None

    def validate_plugin_file(self, filepath: Path) -> Tuple[bool, str]:
        """Plugin dosyasinin gecerli olup olmadigini kontrol eder.

        Args:
            filepath: Kontrol edilecek dosya

        Returns:
            (gecerli_mi, hata_mesaji)
        """
        if not filepath.exists():
            return False, "Dosya mevcut degil"

        if filepath.suffix != ".py":
            return False, "Python dosyasi degil"

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                ast.parse(f.read())
            return True, ""
        except SyntaxError as exc:
            return False, f"Sentaks hatasi: {exc}"

    def get_plugin_dependencies_from_source(
        self, filepath: Path
    ) -> List[PluginDependency]:
        """Kaynak kod icindeki dependencies sabitini okur.

        Plugin dosyasinda su sekilde tanimlanabilir:
            __dependencies__ = [
                PluginDependency(name="hava", version=">=1.0"),
            ]

        Args:
            filepath: Python dosyasi

        Returns:
            Bagimlilik listesi
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "__dependencies__"
                        ):
                            return self._parse_dependency_ast(node.value)

            return []
        except Exception:
            return []

    def _parse_dependency_ast(self, node: ast.AST) -> List[PluginDependency]:
        """AST'den bagimliliklari ayristirir."""
        dependencies = []
        if isinstance(node, ast.List):
            for elt in node.elts:
                if isinstance(elt, ast.Call):
                    func = elt.func
                    if isinstance(func, ast.Name) and func.id == "PluginDependency":
                        dep = PluginDependency()
                        for kw in elt.keywords:
                            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                dep.name = kw.value.value
                            elif kw.arg == "version" and isinstance(kw.value, ast.Constant):
                                dep.version = kw.value.value
                            elif kw.arg == "optional" and isinstance(kw.value, ast.Constant):
                                dep.optional = bool(kw.value.value)
                        for i, arg in enumerate(elt.args):
                            if i == 0 and isinstance(arg, ast.Constant):
                                dep.name = arg.value
                            elif i == 1 and isinstance(arg, ast.Constant):
                                dep.version = arg.value
                        dependencies.append(dep)
        return dependencies


class PluginRegistry:
    """Eklenti kayit defteri. Yuklu tum eklentileri ve kayitlarini tutar.

    Merkezi repository: hook'lar, komutlar, middleware'ler ve UI
    bilesenleri burada toplanir.
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, "PluginInstance"] = {}
        self._hooks: Dict[HookPoint, List[HookRegistration]] = {}
        self._commands: Dict[str, CommandRegistration] = {}
        self._middlewares: List[MiddlewareRegistration] = []
        self._ui_components: Dict[str, UIComponentRegistration] = {}
        self._lock = Lock()

    def register_plugin(self, instance: "PluginInstance") -> None:
        """Bir eklentiyi kayit defterine ekler.

        Args:
            instance: PluginInstance nesnesi
        """
        with self._lock:
            self._plugins[instance.name] = instance

    def unregister_plugin(self, name: str) -> None:
        """Bir eklentiyi kayit defterinden kaldirir.

        Args:
            name: Eklenti adi
        """
        with self._lock:
            if name in self._plugins:
                del self._plugins[name]

            self._hooks = {
                point: [
                    h for h in hooks if h.plugin_name != name
                ]
                for point, hooks in self._hooks.items()
            }

            self._commands = {
                cmd_name: cmd
                for cmd_name, cmd in self._commands.items()
                if cmd.plugin_name != name
            }

            self._middlewares = [
                m for m in self._middlewares if m.plugin_name != name
            ]

            self._ui_components = {
                cid: comp
                for cid, comp in self._ui_components.items()
                if comp.plugin_name != name
            }

    def add_hook(self, registration: HookRegistration) -> None:
        """Hook kaydi ekler.

        Args:
            registration: HookRegistration nesnesi
        """
        with self._lock:
            if registration.hook_point not in self._hooks:
                self._hooks[registration.hook_point] = []
            self._hooks[registration.hook_point].append(registration)
            self._hooks[registration.hook_point].sort(
                key=lambda h: h.priority.value,
                reverse=True,
            )

    def add_command(self, registration: CommandRegistration) -> None:
        """Komut kaydi ekler.

        Args:
            registration: CommandRegistration nesnesi
        """
        with self._lock:
            self._commands[registration.name] = registration
            for alias in registration.aliases:
                self._commands[alias] = registration

    def add_middleware(self, registration: MiddlewareRegistration) -> None:
        """Middleware kaydi ekler.

        Args:
            registration: MiddlewareRegistration nesnesi
        """
        with self._lock:
            self._middlewares.append(registration)
            self._middlewares.sort(key=lambda m: m.priority)

    def add_ui_component(self, registration: UIComponentRegistration) -> None:
        """UI bileseni kaydi ekler.

        Args:
            registration: UIComponentRegistration nesnesi
        """
        with self._lock:
            self._ui_components[registration.component_id] = registration

    def get_plugin(self, name: str) -> Optional["PluginInstance"]:
        """Eklenti adina gore PluginInstance dondurur.

        Args:
            name: Eklenti adi

        Returns:
            PluginInstance veya None
        """
        return self._plugins.get(name)

    def get_plugins(self) -> Dict[str, "PluginInstance"]:
        """Tum kayitli eklentileri dondurur."""
        return dict(self._plugins)

    def get_hooks(self, hook_point: HookPoint) -> List[HookRegistration]:
        """Belirli bir hook noktasindaki kayitlari dondurur.

        Args:
            hook_point: HookPoint degeri

        Returns:
            HookRegistration listesi
        """
        return list(self._hooks.get(hook_point, []))

    def get_all_hooks(self) -> Dict[HookPoint, List[HookRegistration]]:
        """Tum hook kayitlarini dondurur."""
        return dict(self._hooks)

    def get_command(self, name: str) -> Optional[CommandRegistration]:
        """Komut adina gore kayit dondurur.

        Args:
            name: Komut adi

        Returns:
            CommandRegistration veya None
        """
        return self._commands.get(name)

    def get_commands(self) -> Dict[str, CommandRegistration]:
        """Tum komut kayitlarini dondurur."""
        return dict(self._commands)

    def get_middlewares(self) -> List[MiddlewareRegistration]:
        """Tum middleware kayitlarini dondurur."""
        return list(self._middlewares)

    def get_ui_components(self, location: Optional[str] = None) -> List[UIComponentRegistration]:
        """UI bilesenlerini dondurur.

        Args:
            location: Konum filtreleme (opsiyonel)

        Returns:
            UIComponentRegistration listesi
        """
        if location:
            return [
                c for c in self._ui_components.values() if c.location == location
            ]
        return list(self._ui_components.values())

    def has_plugin(self, name: str) -> bool:
        """Eklenti kayitli mi kontrol eder.

        Args:
            name: Eklenti adi

        Returns:
            bool
        """
        return name in self._plugins

    @property
    def plugin_count(self) -> int:
        """Kayitli eklenti sayisi."""
        return len(self._plugins)

    @property
    def hook_count(self) -> int:
        """Toplam hook kayit sayisi."""
        return sum(len(hooks) for hooks in self._hooks.values())

    @property
    def command_count(self) -> int:
        """Toplam komut kayit sayisi."""
        return len(self._commands)


class PluginInstance:
    """Yuklu bir eklentinin calisma ortamindaki temsilcisi.

    Eklenti ornegini, durumunu, kayitlarini ve yapilandirmasini
    bir arada tutar.
    """

    def __init__(
        self,
        plugin_class: Type[BasePlugin],
        filepath: Path,
    ) -> None:
        self._plugin_class = plugin_class
        self._filepath = filepath
        self._instance: Optional[BasePlugin] = None
        self._state = PluginState.DISCOVERED
        self._error: Optional[str] = None
        self._load_error: Optional[str] = None

    @property
    def name(self) -> str:
        """Eklenti adi."""
        if self._instance:
            return self._instance.metadata.name
        return self._plugin_class.__name__

    @property
    def state(self) -> PluginState:
        """Eklenti durumu."""
        return self._state

    @property
    def instance(self) -> Optional[BasePlugin]:
        """BasePlugin ornegi."""
        return self._instance

    @property
    def filepath(self) -> Path:
        """Eklenti dosya yolu."""
        return self._filepath

    @property
    def error(self) -> Optional[str]:
        """Son hata mesaji."""
        return self._error

    @property
    def metadata(self) -> PluginMetadata:
        """Eklenti metadata bilgisi."""
        if self._instance:
            return self._instance.metadata
        return PluginMetadata(name=self._plugin_class.__name__)

    def load(self) -> bool:
        """Eklentiyi yukler ve ornekler.

        Returns:
            Basarili mi
        """
        try:
            self._state = PluginState.LOADING

            self._instance = self._plugin_class()
            self._instance.plugin_file = str(self._filepath)
            self._instance.plugin_dir = str(self._filepath.parent)
            self._instance._start_time = time.time()

            self._instance.on_load()

            self._state = PluginState.LOADED
            return True

        except Exception as exc:
            self._state = PluginState.ERROR
            self._error = f"Yukleme hatasi: {exc}"
            self._load_error = traceback.format_exc()
            logger.error(
                "[PluginInstance] %s yuklenemedi: %s",
                self.name,
                exc,
            )
            return False

    def unload(self) -> bool:
        """Eklentiyi kaldirir.

        Returns:
            Basarili mi
        """
        try:
            if self._instance:
                self._instance.on_unload()
                self._instance = None

            self._state = PluginState.UNLOADED
            return True

        except Exception as exc:
            self._error = f"Kaldirma hatasi: {exc}"
            logger.error(
                "[PluginInstance] %s kaldirilamadi: %s",
                self.name,
                exc,
            )
            return False

    def enable(self) -> bool:
        """Eklentiyi aktif eder.

        Returns:
            Basarili mi
        """
        try:
            if self._state != PluginState.LOADED and self._state != PluginState.DISABLED:
                return False

            if self._instance is None:
                return False

            self._instance.on_enable()
            self._state = PluginState.ENABLED
            return True

        except Exception as exc:
            self._error = f"Aktif etme hatasi: {exc}"
            logger.error(
                "[PluginInstance] %s aktif edilemedi: %s",
                self.name,
                exc,
            )
            return False

    def disable(self) -> bool:
        """Eklentiyi devre disi birakir.

        Returns:
            Basarili mi
        """
        try:
            if self._state != PluginState.ENABLED:
                return False

            if self._instance is None:
                return False

            self._instance.on_disable()
            self._state = PluginState.DISABLED
            return True

        except Exception as exc:
            self._error = f"Devre disi birakma hatasi: {exc}"
            logger.error(
                "[PluginInstance] %s devre disi birakilamadi: %s",
                self.name,
                exc,
            )
            return False

    def execute_hook(
        self,
        hook_point: HookPoint,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Eklenti uzerinde bir hook calistirir.

        Args:
            hook_point: Hook noktasi
            args: Pozisyonel argumanlar
            kwargs: Anahtar argumanlar

        Returns:
            Hook sonucu
        """
        if self._instance is None:
            return None

        try:
            method = getattr(self._instance, hook_point.value, None)
            if method is None:
                return None

            result = method(*args, **kwargs)
            return result

        except Exception as exc:
            self._error = f"Hook hatasi ({hook_point.value}): {exc}"
            self._instance.increment_error()
            logger.error(
                "[PluginInstance] %s hook hatasi '%s': %s",
                self.name,
                hook_point.value,
                exc,
            )
            return None

    @property
    def is_loaded(self) -> bool:
        """Eklenti yuklu mu."""
        return self._state in (PluginState.LOADED, PluginState.ENABLED, PluginState.DISABLED)

    @property
    def is_enabled(self) -> bool:
        """Eklenti aktif mi."""
        return self._state == PluginState.ENABLED

    @property
    def has_error(self) -> bool:
        """Eklentide hata var mi."""
        return self._state == PluginState.ERROR


class PluginManager:
    """Plugin yoneticisi (Singleton).

    Tum plugin sistemini yoneten merkezi sinif. Eklentileri kesfeder,
    yukler, aktif/pasif eder, hook'lari calistirir ve hot-reload
    destegi saglar.

    Kullanim:
        >>> manager = PluginManager.get_instance()
        >>> manager.discover_plugins()
        >>> manager.load_all_plugins()
        >>> manager.enable_all_plugins()
        >>> manager.execute_hooks(HookPoint.ON_STARTUP)
    """

    _instance: Optional["PluginManager"] = None
    _instance_lock: ClassVar["RLock"] = RLock()

    def __init__(
        self,
        plugins_dir: str = "plugins",
        auto_discover: bool = True,
    ) -> None:
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self._plugins_dir = plugins_dir
        self._loader = PluginLoader(plugins_dir)
        self._registry = PluginRegistry()

        self._disabled_plugins: Set[str] = set()
        self._plugin_instances: Dict[str, PluginInstance] = {}
        self._load_order: List[str] = []

        self._config: Dict[str, Any] = {}
        self._watcher: Optional[PluginWatcher] = None
        self._metrics: PluginMetrics = PluginMetrics()

        self._logger = logging.getLogger(f"{__name__}.PluginManager")

        if auto_discover:
            self.discover_plugins()

    def __new__(cls, *args: Any, **kwargs: Any) -> "PluginManager":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(
        cls,
        plugins_dir: str = "plugins",
    ) -> "PluginManager":
        """Singleton ornegini dondurur.

        Args:
            plugins_dir: Plugin dizini

        Returns:
            PluginManager ornegi
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(plugins_dir=plugins_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Singleton ornegini sifirlar (testler icin)."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance = None

    # ----------------------------------------------------------------
    # Kesif ve Yukleme
    # ----------------------------------------------------------------

    def discover_plugins(self) -> List[str]:
        """Plugin dosyalarini kesfeder.

        plugins/ dizinini tarar ve gecerli plugin dosyalarini bulur.

        Returns:
            Kesfedilen plugin adlari listesi
        """
        plugin_files = self._loader.discover_plugin_files()

        discovered = []
        for filepath in plugin_files:
            valid, msg = self._loader.validate_plugin_file(filepath)
            if not valid:
                self._logger.warning(
                    "[PluginManager] Gecersiz plugin dosyasi: %s (%s)",
                    filepath.name,
                    msg,
                )
                continue

            plugin_class = self._loader.load_plugin_from_file(filepath)
            if plugin_class is None:
                continue

            instance = PluginInstance(plugin_class, filepath)
            name = instance.name

            if name not in self._plugin_instances:
                self._plugin_instances[name] = instance
                discovered.append(name)
                self._logger.info(
                    "[PluginManager] Plugin kesfedildi: %s (%s)",
                    name,
                    filepath.name,
                )

        self._metrics.discovered_count = len(discovered)
        return discovered

    def load_plugin(self, name: str) -> bool:
        """Bir eklentiyi yukler.

        Args:
            name: Eklenti adi

        Returns:
            Basarili mi
        """
        instance = self._plugin_instances.get(name)
        if instance is None:
            self._logger.error("[PluginManager] Plugin bulunamadi: %s", name)
            return False

        if instance.is_loaded:
            self._logger.debug(
                "[PluginManager] Plugin zaten yuklu: %s",
                name,
            )
            return True

        result = instance.load()
        if result:
            self._registry.register_plugin(instance)
            self._load_order.append(name)

            self._register_plugin_artifacts(instance)

            self._metrics.loaded_count += 1
            self._metrics.total_load_time = time.time()

            self._logger.info(
                "[PluginManager] Plugin yuklendi: %s",
                name,
            )
        else:
            self._metrics.error_count += 1
            self._logger.error(
                "[PluginManager] Plugin yuklenemedi: %s - %s",
                name,
                instance.error,
            )

        return result

    def load_all_plugins(self) -> Dict[str, bool]:
        """Tum kesfedilen eklentileri yukler.

        Returns:
            {eklenti_adi: basarili_mi} sozlugu
        """
        self._resolve_dependencies()

        results = {}
        for name in self._load_order:
            if name in self._disabled_plugins:
                self._logger.info(
                    "[PluginManager] Plugin atlaniyor (devre disi): %s",
                    name,
                )
                results[name] = False
                continue

            results[name] = self.load_plugin(name)

        not_loaded = [
            name
            for name in self._plugin_instances
            if name not in self._load_order
        ]
        for name in not_loaded:
            results[name] = self.load_plugin(name)

        return results

    def unload_plugin(self, name: str) -> bool:
        """Bir eklentiyi kaldirir.

        Args:
            name: Eklenti adi

        Returns:
            Basarili mi
        """
        instance = self._plugin_instances.get(name)
        if instance is None:
            return False

        result = instance.unload()
        if result:
            self._registry.unregister_plugin(name)
            if name in self._load_order:
                self._load_order.remove(name)
            self._metrics.loaded_count -= 1
            self._logger.info(
                "[PluginManager] Plugin kaldirildi: %s",
                name,
            )
        return result

    def reload_plugin(self, name: str) -> bool:
        """Bir eklentiyi yeniden yukler (hot-reload).

        Args:
            name: Eklenti adi

        Returns:
            Basarili mi
        """
        self._logger.info(
            "[PluginManager] Plugin yeniden yukleniyor: %s",
            name,
        )

        instance = self._plugin_instances.get(name)
        if instance is None:
            return False

        was_enabled = instance.is_enabled
        old_state = instance.state

        self.unload_plugin(name)

        self._loader.reload_plugin_module(name)

        filepath = instance.filepath
        plugin_class = self._loader.load_plugin_from_file(filepath)
        if plugin_class is None:
            self._logger.error(
                "[PluginManager] Plugin yeniden yuklenemedi: %s",
                name,
            )
            return False

        new_instance = PluginInstance(plugin_class, filepath)
        self._plugin_instances[name] = new_instance

        result = self.load_plugin(name)
        if result and was_enabled:
            self.enable_plugin(name)

        self._metrics.reload_count += 1
        self._logger.info(
            "[PluginManager] Plugin yeniden yuklendi: %s",
            name,
        )

        return result

    # ----------------------------------------------------------------
    # Aktif/Pasif Yonetimi
    # ----------------------------------------------------------------

    def enable_plugin(self, name: str) -> bool:
        """Bir eklentiyi aktif eder.

        Args:
            name: Eklenti adi

        Returns:
            Basarili mi
        """
        instance = self._plugin_instances.get(name)
        if instance is None:
            return False

        result = instance.enable()
        if result:
            self._disabled_plugins.discard(name)
            self._metrics.enabled_count += 1
            self._logger.info(
                "[PluginManager] Plugin aktif: %s",
                name,
            )
        return result

    def disable_plugin(self, name: str) -> bool:
        """Bir eklentiyi devre disi birakir.

        Args:
            name: Eklenti adi

        Returns:
            Basarili mi
        """
        instance = self._plugin_instances.get(name)
        if instance is None:
            return False

        result = instance.disable()
        if result:
            self._disabled_plugins.add(name)
            self._metrics.disabled_count += 1
            self._logger.info(
                "[PluginManager] Plugin devre disi: %s",
                name,
            )
        return result

    def enable_all_plugins(self) -> Dict[str, bool]:
        """Tum yuklu eklentileri aktif eder.

        Returns:
            {eklenti_adi: basarili_mi}
        """
        results = {}
        for name, instance in self._plugin_instances.items():
            if instance.is_loaded:
                results[name] = self.enable_plugin(name)
        return results

    def disable_all_plugins(self) -> Dict[str, bool]:
        """Tum aktif eklentileri devre disi birakir.

        Returns:
            {eklenti_adi: basarili_mi}
        """
        results = {}
        for name, instance in self._plugin_instances.items():
            if instance.is_enabled:
                results[name] = self.disable_plugin(name)
        return results

    # ----------------------------------------------------------------
    # Hook Sistemi
    # ----------------------------------------------------------------

    def execute_hooks(
        self,
        hook_point: HookPoint,
        *args: Any,
        **kwargs: Any,
    ) -> List[Any]:
        """Bir hook noktasindaki tum kayitli fonksiyonlari calistirir.

        Hata izolasyonu: Bir eklentinin hook'u basarisiz olursa
        digerlerinin calismasi etkilenmez.

        Args:
            hook_point: Calistirilacak hook noktasi
            args: Fonksiyonlara gonderilecek argumanlar
            kwargs: Fonksiyonlara gonderilecek anahtar argumanlar

        Returns:
            Sonuclar listesi
        """
        results = []
        registrations = self._registry.get_hooks(hook_point)

        if not registrations:
            return results

        self._logger.debug(
            "[PluginManager] Hook calistiriliyor: %s (%d kayit)",
            hook_point.value,
            len(registrations),
        )

        for reg in registrations:
            try:
                result = reg.callback(*args, **kwargs)
                results.append(result)
            except Exception as exc:
                self._metrics.error_count += 1
                self._logger.error(
                    "[PluginManager] Hook hatasi '%s' plugin '%s': %s",
                    hook_point.value,
                    reg.plugin_name,
                    exc,
                )

                plugin_instance = self._plugin_instances.get(reg.plugin_name)
                if plugin_instance and plugin_instance.instance:
                    plugin_instance.instance.increment_error()

        self._metrics.total_hook_executions += len(registrations)
        return results

    def execute_hook_chain(
        self,
        hook_point: HookPoint,
        initial_data: Any,
        **kwargs: Any,
    ) -> Any:
        """Zincirleme hook calistirir (her sonuc bir sonrakine gecer).

        Ozellikle before_chat/after_chat gibi veri donusturen
        hook'lar icin kullanilir.

        Args:
            hook_point: Hook noktasi
            initial_data: Baslangic verisi
            kwargs: Ek argumanlar

        Returns:
            Son donusen veri
        """
        data = initial_data
        registrations = self._registry.get_hooks(hook_point)

        for reg in registrations:
            try:
                result = reg.callback(data, **kwargs)
                if result is not None:
                    data = result
            except Exception as exc:
                self._metrics.error_count += 1
                self._logger.error(
                    "[PluginManager] Hook zincir hatasi '%s': %s",
                    hook_point.value,
                    exc,
                )

        return data

    # ----------------------------------------------------------------
    # Komut Sistemi
    # ----------------------------------------------------------------

    def execute_command(
        self,
        command_name: str,
        args: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Kayitli bir komutu calistirir.

        Args:
            command_name: Komut adi (ornek: '/hava')
            args: Komut argumanlari
            context: Komut baglami

        Returns:
            Komut sonucu veya None
        """
        command = self._registry.get_command(command_name)
        if command is None:
            return None

        try:
            result = command.handler(args, context or {})
            self._metrics.total_command_executions += 1
            return result
        except Exception as exc:
            self._metrics.error_count += 1
            self._logger.error(
                "[PluginManager] Komut hatasi '%s': %s",
                command_name,
                exc,
            )
            return f"Hata: {exc}"

    def get_command_help(self) -> str:
        """Tum kayitli komutlarin yardim metnini olusturur.

        Returns:
            Yardim metni
        """
        lines = ["\n=== Plugin Komutlari ===\n"]
        commands = self._registry.get_commands()

        sorted_cmds = sorted(commands.items(), key=lambda x: x[0])

        for cmd_name, cmd in sorted_cmds:
            plugin_tag = f"[{cmd.plugin_name}]" if cmd.plugin_name else ""
            desc = cmd.description or "Aciklama yok"
            usage = f"  Kullanim: {cmd.usage}" if cmd.usage else ""
            aliases = (
                f"  Takma ad: {', '.join(cmd.aliases)}" if cmd.aliases else ""
            )
            lines.append(f"  {cmd_name} {plugin_tag}")
            lines.append(f"    {desc}")
            if usage:
                lines.append(usage)
            if aliases:
                lines.append(aliases)

        return "\n".join(lines)

    # ----------------------------------------------------------------
    # Middleware Sistemi
    # ----------------------------------------------------------------

    def process_middlewares(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """Mesaji middleware zincirinden gecirir.

        Args:
            message: Kullanici mesaji
            context: Sohbet baglami

        Returns:
            (islenmis_mesaj, islenmis_baglam)
        """
        current_message = message
        current_context = dict(context)

        for middleware in self._registry.get_middlewares():
            try:
                result = middleware.handler(current_message, current_context)
                if isinstance(result, tuple) and len(result) == 2:
                    current_message, current_context = result
            except Exception as exc:
                self._metrics.error_count += 1
                self._logger.error(
                    "[PluginManager] Middleware hatasi '%s': %s",
                    middleware.name,
                    exc,
                )

        return current_message, current_context

    # ----------------------------------------------------------------
    # UI Bilesenleri
    # ----------------------------------------------------------------

    def render_ui_components(self, location: str, **kwargs: Any) -> List[str]:
        """Belirli bir konumdaki UI bilesenlerini render eder.

        Args:
            location: Konum (sidebar, header, footer, main)
            kwargs: Render parametreleri

        Returns:
            Render edilmis icerik listesi
        """
        results = []
        components = self._registry.get_ui_components(location)

        for component in components:
            try:
                result = component.render_func(**kwargs)
                if result is not None:
                    results.append(result)
            except Exception as exc:
                self._logger.error(
                    "[PluginManager] UI render hatasi '%s': %s",
                    component.component_id,
                    exc,
                )

        return results

    # ----------------------------------------------------------------
    # Bagimlilik Cozucu
    # ----------------------------------------------------------------

    def _resolve_dependencies(self) -> None:
        """Eklenti bagimliliklarini cozer ve yukleme sirasini belirler.

        Raises:
            PluginDependencyError: Cozulemeyen bagimlilik varsa
        """
        dependency_graph: Dict[str, List[str]] = {}
        plugin_names = set(self._plugin_instances.keys())

        for name, instance in self._plugin_instances.items():
            deps: List[str] = []
            filepath = instance.filepath

            source_deps = self._loader.get_plugin_dependencies_from_source(
                filepath
            )
            for dep in source_deps:
                if dep.name in plugin_names:
                    deps.append(dep.name)
                elif not dep.optional:
                    self._logger.warning(
                        "[PluginManager] Bagimlilik bulunamadi: %s (icin: %s, zorunlu)",
                        dep.name,
                        name,
                    )

            dependency_graph[name] = deps

        self._load_order = self._topological_sort(dependency_graph)

        self._logger.info(
            "[PluginManager] Yukleme sirasi: %s",
            " -> ".join(self._load_order),
        )

    def _topological_sort(
        self,
        graph: Dict[str, List[str]],
    ) -> List[str]:
        """Topolojik siralama ile bagimlilik sirasini cikarir.

        Kahn algoritmasi kullanir.

        Args:
            graph: Bagimlilik grafi

        Returns:
            Sirali node listesi
        """
        in_degree: Dict[str, int] = {node: 0 for node in graph}
        for node, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[node] += 1

        queue = [node for node, degree in in_degree.items() if degree == 0]
        sorted_nodes = []

        while queue:
            node = queue.pop(0)
            sorted_nodes.append(node)

            for other, deps in graph.items():
                if node in deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        remaining = set(graph.keys()) - set(sorted_nodes)
        sorted_nodes.extend(remaining)

        return sorted_nodes

    # ----------------------------------------------------------------
    # Ic Kayit
    # ----------------------------------------------------------------

    def _register_plugin_artifacts(self, instance: PluginInstance) -> None:
        """Eklentinin hook, komut, middleware ve UI kayitlarini registry'e ekler.

        Args:
            instance: PluginInstance nesnesi
        """
        if instance.instance is None:
            return

        plugin = instance.instance

        for hook in plugin.get_hooks():
            self._registry.add_hook(hook)

        for command in plugin.get_commands():
            self._registry.add_command(command)

        for middleware in plugin.get_middlewares():
            self._registry.add_middleware(middleware)

        for component in plugin.get_ui_components():
            self._registry.add_ui_component(component)

    # ----------------------------------------------------------------
    # Hot-Reload / Watch
    # ----------------------------------------------------------------

    def start_watcher(
        self,
        interval: float = 2.0,
        callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Plugin dizinini izlemeye baslar.

        Degisiklik algiladiginda ilgili eklentiyi otomatik yeniden yukler.

        Args:
            interval: Kontrol araligi (saniye)
            callback: Yeniden yukleme sonrasi cagrilacak fonksiyon
        """
        if self._watcher is not None:
            self._logger.warning("[PluginManager] Watcher zaten calisiyor")
            return

        self._watcher = PluginWatcher(
            plugins_dir=self._plugins_dir,
            plugin_instances=self._plugin_instances,
            reload_callback=self.reload_plugin,
            interval=interval,
        )
        self._watcher.start()

        self._logger.info(
            "[PluginManager] Plugin watcher baslatildi (aralik: %.1fs)",
            interval,
        )

    def stop_watcher(self) -> None:
        """Plugin dizini izlemeyi durdurur."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
            self._logger.info("[PluginManager] Plugin watcher durduruldu")

    # ----------------------------------------------------------------
    # Yapilandirma
    # ----------------------------------------------------------------

    def set_plugin_config(
        self,
        plugin_name: str,
        config: Dict[str, Any],
    ) -> bool:
        """Bir eklentinin yapilandirmasini gunceller.

        Args:
            plugin_name: Eklenti adi
            config: Yeni yapilandirma

        Returns:
            Basarili mi
        """
        instance = self._plugin_instances.get(plugin_name)
        if instance is None or instance.instance is None:
            return False

        instance.instance.config.update(config)

        self.execute_hooks(
            HookPoint.ON_CONFIG_CHANGE,
            plugin_name=plugin_name,
            config=config,
        )

        return True

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """Bir eklentinin yapilandirmasini dondurur.

        Args:
            plugin_name: Eklenti adi

        Returns:
            Yapilandirma sozlugu
        """
        instance = self._plugin_instances.get(plugin_name)
        if instance is None or instance.instance is None:
            return {}
        return dict(instance.instance.config)

    # ----------------------------------------------------------------
    # Sorgulama
    # ----------------------------------------------------------------

    def get_plugin(self, name: str) -> Optional[PluginInstance]:
        """Eklenti adina gore PluginInstance dondurur.

        Args:
            name: Eklenti adi

        Returns:
            PluginInstance veya None
        """
        return self._plugin_instances.get(name)

    def get_active_plugins(self) -> List[PluginInstance]:
        """Aktif eklentileri dondurur.

        Returns:
            PluginInstance listesi
        """
        return [
            p for p in self._plugin_instances.values() if p.is_enabled
        ]

    def get_plugin_names(self) -> List[str]:
        """Tum eklenti adlarini dondurur.

        Returns:
            Ad listesi
        """
        return list(self._plugin_instances.keys())

    def get_plugin_count(self) -> Dict[str, int]:
        """Eklenti sayilarini kategorilere gore dondurur.

        Returns:
            {kategori: sayi}
        """
        counts = {
            "total": len(self._plugin_instances),
            "loaded": 0,
            "enabled": 0,
            "disabled": 0,
            "error": 0,
        }
        for instance in self._plugin_instances.values():
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

    def get_registry(self) -> PluginRegistry:
        """PluginRegistry ornegini dondurur."""
        return self._registry

    def get_metrics(self) -> "PluginMetrics":
        """PluginMetrics ornegini dondurur."""
        return self._metrics

    # ----------------------------------------------------------------
    # Test
    # ----------------------------------------------------------------

    def run_self_test(self) -> Dict[str, Any]:
        """Plugin sisteminin kendi kendine testini calistirir.

        Returns:
            Test sonuclari
        """
        results = {
            "status": "ok",
            "plugins_discovered": len(self._plugin_instances),
            "plugins_loaded": 0,
            "plugins_enabled": 0,
            "hooks_registered": self._registry.hook_count,
            "commands_registered": self._registry.command_count,
            "errors": [],
        }

        for name, instance in self._plugin_instances.items():
            if instance.is_loaded:
                results["plugins_loaded"] += 1
            if instance.is_enabled:
                results["plugins_enabled"] += 1
            if instance.has_error:
                results["errors"].append(
                    {"plugin": name, "error": instance.error}
                )

        if results["errors"]:
            results["status"] = "warning"

        return results

    # ----------------------------------------------------------------
    # Gorsellestirme
    # ----------------------------------------------------------------

    def print_plugin_report(self) -> None:
        """Plugin durum raporunu konsola yazdirir."""
        tree = Tree("[bold blue]Plugin Sistemi Raporu[/]")

        info_branch = tree.add(f"[cyan]Bilgi[/]")
        info_branch.add(f"[white]Plugin Sayisi:[/] {len(self._plugin_instances)}")
        info_branch.add(f"[white]Hook Sayisi:[/] {self._registry.hook_count}")
        info_branch.add(f"[white]Komut Sayisi:[/] {self._registry.command_count}")
        info_branch.add(f"[white]Middleware Sayisi:[/] {len(self._registry.get_middlewares())}")
        info_branch.add(f"[white]UI Bileseni:[/] {len(self._registry.get_ui_components())}")

        status_branch = tree.add(f"[cyan]Durum[/]")
        counts = self.get_plugin_count()
        status_branch.add(f"[green]Aktif:[/] {counts['enabled']}")
        status_branch.add(f"[yellow]Pasif:[/] {counts['disabled']}")
        status_branch.add(f"[red]Hata:[/] {counts['error']}")

        if self._plugin_instances:
            plugins_branch = tree.add(f"[cyan]Eklentiler[/]")
            for name, instance in self._plugin_instances.items():
                state_colors = {
                    PluginState.ENABLED: "[green]",
                    PluginState.DISABLED: "[yellow]",
                    PluginState.ERROR: "[red]",
                    PluginState.LOADED: "[blue]",
                    PluginState.LOADING: "[cyan]",
                    PluginState.UNLOADED: "[dim]",
                    PluginState.DISCOVERED: "[dim]",
                }
                color = state_colors.get(instance.state, "[white]")
                plugins_branch.add(
                    f"{color}{name}[/] "
                    f"({instance.state.value})"
                )

        console.print(tree)

        commands = self._registry.get_commands()
        if commands:
            table = Table(title="Kayitli Komutlar")
            table.add_column("Komut", style="cyan")
            table.add_column("Aciklama", style="white")
            table.add_column("Plugin", style="blue")

            sorted_cmds = sorted(commands.items(), key=lambda x: x[0])
            for cmd_name, cmd in sorted_cmds:
                table.add_row(
                    cmd_name,
                    cmd.description[:50] if cmd.description else "-",
                    cmd.plugin_name,
                )

            console.print(table)

        metrics = self._metrics
        if metrics.total_hook_executions > 0 or metrics.total_command_executions > 0:
            metrics_branch = tree.add(f"[cyan]Metrikler[/]")
            metrics_branch.add(
                f"[white]Hook Calistirma:[/] {metrics.total_hook_executions}"
            )
            metrics_branch.add(
                f"[white]Komut Calistirma:[/] {metrics.total_command_executions}"
            )
            metrics_branch.add(f"[white]Hata Sayisi:[/] {metrics.error_count}")
            metrics_branch.add(
                f"[white]Yeniden Yukleme:[/] {metrics.reload_count}"
            )

            console.print(tree)


class PluginWatcher:
    """Plugin dizinini belirli araliklarla kontrol eden izleyici.

    Dosya degisikliklerini algilar ve ilgili eklentiyi otomatik
    yeniden yukler (hot-reload).
    """

    def __init__(
        self,
        plugins_dir: str,
        plugin_instances: Dict[str, PluginInstance],
        reload_callback: Callable[[str], bool],
        interval: float = 2.0,
    ) -> None:
        self._plugins_dir = Path(plugins_dir)
        self._instances = plugin_instances
        self._reload_callback = reload_callback
        self._interval = interval
        self._running = False
        self._timer: Optional[Timer] = None
        self._file_hashes: Dict[str, float] = {}
        self._logger = logging.getLogger(f"{__name__}.PluginWatcher")
        self._lock = Lock()

    def start(self) -> None:
        """Izlemeyi baslatir."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._build_hash_index()
            self._schedule_next()

    def stop(self) -> None:
        """Izlemeyi durdurur."""
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def _build_hash_index(self) -> None:
        """Mevcut plugin dosyalarinin hash indeksini olusturur."""
        self._file_hashes = {}
        if self._plugins_dir.exists():
            for filepath in self._plugins_dir.glob("*.py"):
                if not filepath.name.startswith("_"):
                    self._file_hashes[str(filepath)] = filepath.stat().st_mtime

    def _check_changes(self) -> None:
        """Dosya degisikliklerini kontrol eder."""
        with self._lock:
            if not self._running:
                return

            try:
                if not self._plugins_dir.exists():
                    return

                current_hashes: Dict[str, float] = {}
                changed_files: List[str] = []

                for filepath in self._plugins_dir.glob("*.py"):
                    if filepath.name.startswith("_"):
                        continue

                    path_str = str(filepath)
                    mtime = filepath.stat().st_mtime
                    current_hashes[path_str] = mtime

                    old_mtime = self._file_hashes.get(path_str)
                    if old_mtime is not None and mtime != old_mtime:
                        changed_files.append(path_str)

                self._file_hashes = current_hashes

                for filepath in changed_files:
                    self._logger.info(
                        "[PluginWatcher] Degisiklik algilandi: %s",
                        Path(filepath).name,
                    )

                    plugin_name = self._find_plugin_by_file(filepath)
                    if plugin_name:
                        self._logger.info(
                            "[PluginWatcher] Plugin yeniden yukleniyor: %s",
                            plugin_name,
                        )
                        try:
                            self._reload_callback(plugin_name)
                        except Exception as exc:
                            self._logger.error(
                                "[PluginWatcher] Yeniden yukleme hatasi: %s",
                                exc,
                            )

            except Exception as exc:
                self._logger.error(
                    "[PluginWatcher] Kontrol hatasi: %s",
                    exc,
                )
            finally:
                if self._running:
                    self._schedule_next()

    def _schedule_next(self) -> None:
        """Bir sonraki kontrolli zamanlar."""
        self._timer = Timer(self._interval, self._check_changes)
        self._timer.daemon = True
        self._timer.start()

    def _find_plugin_by_file(self, filepath: str) -> Optional[str]:
        """Bir dosya yoluna karsilik gelen eklenti adini bulur.

        Args:
            filepath: Dosya yolu

        Returns:
            Eklenti adi veya None
        """
        filepath_obj = Path(filepath)
        for name, instance in self._instances.items():
            if Path(instance.filepath).resolve() == filepath_obj.resolve():
                return name
        return None


class PluginMetrics:
    """Plugin sistemi metriklerini toplar.

    Attributes:
        discovered_count: Kesfedilen plugin sayisi
        loaded_count: Yuklenen plugin sayisi
        enabled_count: Aktif plugin sayisi
        disabled_count: Pasif plugin sayisi
        error_count: Toplam hata sayisi
        reload_count: Yeniden yukleme sayisi
        total_hook_executions: Toplam hook calistirma sayisi
        total_command_executions: Toplam komut calistirma sayisi
        total_load_time: Toplam yukleme suresi
        start_time: Baslangic zamani
    """

    def __init__(self) -> None:
        self.discovered_count: int = 0
        self.loaded_count: int = 0
        self.enabled_count: int = 0
        self.disabled_count: int = 0
        self.error_count: int = 0
        self.reload_count: int = 0
        self.total_hook_executions: int = 0
        self.total_command_executions: int = 0
        self.total_load_time: float = 0.0
        self.start_time: float = time.time()

    @property
    def uptime(self) -> float:
        """Sistemin calisma suresi (saniye)."""
        return time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Metrikleri sozluk olarak dondurur."""
        return {
            "discovered": self.discovered_count,
            "loaded": self.loaded_count,
            "enabled": self.enabled_count,
            "disabled": self.disabled_count,
            "errors": self.error_count,
            "reloads": self.reload_count,
            "hook_executions": self.total_hook_executions,
            "command_executions": self.total_command_executions,
            "uptime_seconds": self.uptime,
        }

    def reset(self) -> None:
        """Metrikleri sifirlar."""
        self.__init__()


# ----------------------------------------------------------------
# Plugin Sablonu - Ornek Eklenti
# ----------------------------------------------------------------

PLUGIN_TEMPLATE = '''"""
{s_name} - Shadowcat AI / Shadowcat Plugin
Version: {s_version}
Author: {s_author}
Description: {s_description}
"""

from plugin_system import BasePlugin, PluginMetadata, PluginDependency, HookPoint

__dependencies__ = []


class {s_class}(BasePlugin):
    \"\"\"{s_description}\"\"\"

    def __init__(self):
        super().__init__()
        self.metadata = PluginMetadata(
            name="{s_name}",
            version="{s_version}",
            author="{s_author}",
            description="{s_description}",
        )

    def on_load(self):
        \"\"\"Plugin yuklendiginde calisir.\"\"\"
        self.register_command("/{s_command}", self.handle_command, "{s_description}")

    def on_unload(self):
        \"\"\"Plugin kaldirilirken calisir.\"\"\"
        pass

    def on_enable(self):
        \"\"\"Plugin aktif edildiginde calisir.\"\"\"
        pass

    def on_disable(self):
        \"\"\"Plugin devre disi birakildiginda calisir.\"\"\"
        pass

    def before_chat(self, message: str, context: dict) -> tuple:
        \"\"\"AI yanitindan once cagrilir.\"\"\"
        return message, context

    def after_chat(self, response: str, context: dict) -> tuple:
        \"\"\"AI yanitindan sonra cagrilir.\"\"\"
        return response, context

    def handle_command(self, args: str, context: dict) -> str:
        \"\"\"/{s_command} komutunu isler.\"\"\"
        return "{s_name} plugin calisiyor!"
'''


def create_plugin_template(
    name: str = "OrnekPlugin",
    version: str = "1.0.0",
    author: str = "Shadowcat AI",
    description: str = "Ornek plugin",
    command: str = "ornek",
) -> str:
    """Yeni bir plugin icin sablon kod olusturur.

    Args:
        name: Plugin adi
        version: Versiyon
        author: Yazar
        description: Aciklama
        command: Varsayilan komut adi

    Returns:
        Plugin Python kodu
    """
    class_name = name.replace(" ", "").replace("-", "_")
    return PLUGIN_TEMPLATE.format(
        s_name=name,
        s_version=version,
        s_author=author,
        s_description=description,
        s_class=class_name,
        s_command=command.lower().replace(" ", "_"),
    )


# ----------------------------------------------------------------
# Kisa Kullanim Fonksiyonu
# ----------------------------------------------------------------

def get_plugin_manager(plugins_dir: str = "plugins") -> PluginManager:
    """PluginManager ornegini hizlica almak icin yardimci fonksiyon.

    Args:
        plugins_dir: Plugin dizini

    Returns:
        PluginManager singleton ornegi
    """
    return PluginManager.get_instance(plugins_dir=plugins_dir)


if __name__ == "__main__":
    # ----------------------------------------------------------------
    # Test / Demo
    # ----------------------------------------------------------------
    print("=" * 60)
    print("  SHADOWCAT PLUGIN SISTEMI - Test")
    print("  Berkay Software - Lead Engineer AI")
    print("=" * 60)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    manager = PluginManager.get_instance(plugins_dir="plugins")

    discovered = manager.discover_plugins()
    print(f"\nKesfedilen pluginler: {discovered}")

    results = manager.load_all_plugins()
    loaded_count = sum(1 for r in results.values() if r)
    print(f"Yuklenen pluginler: {loaded_count}/{len(results)}")

    enable_results = manager.enable_all_plugins()
    enabled_count = sum(1 for r in enable_results.values() if r)
    print(f"Aktif pluginler: {enabled_count}/{len(enable_results)}")

    print(f"\nHook sayisi: {manager.get_registry().hook_count}")
    print(f"Komut sayisi: {manager.get_registry().command_count}")
    print(f"Middleware sayisi: {len(manager.get_registry().get_middlewares())}")

    manager.print_plugin_report()

    print("\nOrnek plugin sablonu olusturuluyor...")
    template = create_plugin_template(
        name="Hava Durumu",
        author="Berkay",
        description="Canli hava durumu bilgisi",
        command="hava",
    )

    plugins_path = Path("plugins")
    plugins_path.mkdir(exist_ok=True)

    template_path = plugins_path / "ornek_plugin.py"
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(template)
    print(f"Ornek plugin olusturuldu: {template_path}")

    print("\nPlugin sistemi hazir!")
