"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║      ███████╗██╗  ██╗██╗██╗     ██╗     ███████╗██╗   ██╗███████╗████████╗║
║      ██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝║
║      ███████╗█████╔╝ ██║██║     ██║     █████╗   ╚████╔╝ ███████╗   ██║   ║
║      ╚════██║██╔═██╗ ██║██║     ██║     ██╔══╝    ╚██╔╝  ╚════██║   ██║   ║
║      ███████║██║  ██╗██║███████╗███████╗███████╗   ██║   ███████║   ██║   ║
║      ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝   ╚═╝   ╚══════╝   ╚═╝   ║
║                    ███████╗██╗   ██╗███████╗████████╗                     ║
║                    ██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝                     ║
║                    █████╗   ╚████╔╝ ███████╗   ██║                        ║
║                    ██╔══╝    ╚██╔╝  ╚════██║   ██║                        ║
║                    ███████╗   ██║   ███████║   ██║                        ║
║                    ╚══════╝   ╚═╝   ╚══════╝   ╚═╝                        ║
║                                                                           ║
║              SHADOWCAT / GLASSCAT SKILL SISTEMI v1.0                       ║
║           Yapay Zeka Yetenek Paketleri ve Domain Uzmanligi               ║
║                    Berkay Software - Lead Engineer AI                      ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

Glassescat AI Skill Sistemi - AI'nin domain-specific bilgi ve yetenek kazanmasini
saglayan paket yonetim sistemi.

Her skill bir pakettir ve su bilesenlerden olusur:
    - Metadata (isim, versiyon, yazar, aciklama, kategori)
    - Custom system prompt (AI davranisini sekillendirir)
    - Tool/function tanimlari (skill'e ozel yetenekler)
    - Ornek konusmalar (few-shot learning icin)
    - Bagimliliklar (diger skill'ler ve pip paketleri)

Kullanim:
    >>> from skill_system import SkillManager
    >>> manager = SkillManager.get_instance()
    >>> manager.discover_skills()
    >>> prompt = manager.get_combined_prompt(["web_scraper", "game_dev"])
    >>> tools = manager.get_combined_tools(["web_scraper", "game_dev"])
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
import importlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.tree import Tree

logger = logging.getLogger(__name__)
class _SafeConsole(Console):
    """Rich Console wrapper that handles encoding errors on legacy Windows."""
    def print(self, *args, **kwargs):
        try:
            super().print(*args, **kwargs)
        except UnicodeEncodeError:
            text = " ".join(str(a) for a in args)
            enc = sys.stdout.encoding or "utf-8"
            safe = text.encode(enc, errors="replace").decode(enc, errors="replace")
            sys.stdout.write(safe + "\n")
            sys.stdout.flush()


console = _SafeConsole()


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

class SkillCategory(str, Enum):
    """Skill kategorileri."""
    CODING = "coding"
    SECURITY = "security"
    GAMING = "gaming"
    GENERAL = "general"
    PRODUCTIVITY = "productivity"


VALID_CATEGORIES: Set[str] = {c.value for c in SkillCategory}

SKILL_DIR_NAME = "skills"
SKILL_FILE_META = "skill.json"
SKILL_FILE_PROMPT = "prompt.txt"
SKILL_FILE_TOOLS = "tools.json"
SKILL_FILE_EXAMPLES = "examples.json"


# ---------------------------------------------------------------------------
# Hata Siniflari
# ---------------------------------------------------------------------------

class SkillError(Exception):
    """Skill sistemi temel hata sinifi."""
    pass


class SkillNotFoundError(SkillError):
    """Skill bulunamadiginda firlatilir."""
    pass


class SkillDependencyError(SkillError):
    """Skill bagimliligi cozulemediginde firlatilir."""
    pass


class SkillInstallError(SkillError):
    """Skill yuklenirken hata olusursa firlatilir."""
    pass


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """Bir skill paketini temsil eden veri sinifi.

    Her skill, AI'ya belirli bir domainde uzmanlik kazandiran
    bir pakettir. Metadata, prompt, tool tanimlari ve ornek
    konusmalari bir arada tutar.

    Attributes:
        name: Skill adi (benzersiz)
        version: Semantik versiyon numarasi
        description: Skill aciklamasi
        author: Yazar bilgisi
        category: Kategori (coding, security, gaming, general, productivity)
        system_prompt: Skill aktifken inject edilecek ek system prompt
        tools: Skill'e ozel tool/function tanimlari
        examples: Ornek konusmalar (few-shot learning)
        dependencies: Gerekli diger skill adlari
        python_deps: Gerekli pip paketleri
        enabled: Varsayilan aktiflik durumu
    """
    name: str
    version: str
    description: str
    author: str
    category: str
    system_prompt: str
    tools: List[Dict[str, Any]]
    examples: List[Dict[str, Any]]
    dependencies: List[str] = field(default_factory=list)
    python_deps: List[str] = field(default_factory=list)
    enabled: bool = True

    def validate(self) -> Tuple[bool, str]:
        """Skill metadata'sini dogrular.

        Returns:
            (gecerli_mi, hata_mesaji)
        """
        if not self.name or not self.name.strip():
            return False, "Skill adi bos olamaz"
        if not self.version:
            return False, "Versiyon numarasi bos olamaz"
        if self.category not in VALID_CATEGORIES:
            return False, f"Gecersiz kategori: {self.category}. Gecerli: {', '.join(sorted(VALID_CATEGORIES))}"
        if not isinstance(self.tools, list):
            return False, "Tools bir liste olmalidir"
        if not isinstance(self.examples, list):
            return False, "Examples bir liste olmalidir"
        return True, ""

    def to_dict(self) -> Dict[str, Any]:
        """Skill'i JSON uyumlu sozluge cevirir."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "dependencies": list(self.dependencies),
            "python_deps": list(self.python_deps),
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Skill:
        """Sozlukten Skill nesnesi olusturur.

        Args:
            data: Skill metadata sozlugu

        Returns:
            Skill nesnesi (diger alanlar bos)
        """
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "0.0.1"),
            description=data.get("description", ""),
            author=data.get("author", "GlassesCat"),
            category=data.get("category", "general"),
            system_prompt="",
            tools=[],
            examples=[],
            dependencies=data.get("dependencies", []),
            python_deps=data.get("python_deps", []),
            enabled=data.get("enabled", True),
        )


# ---------------------------------------------------------------------------
# Skill Manager (Singleton)
# ---------------------------------------------------------------------------

class SkillManager:
    """Skill yoneticisi (Singleton).

    Tum skill sistemini yoneten merkezi sinif. Skill'leri kesfeder,
    yukler, aktif/pasif eder, combine prompt ve tool olusturur.

    Kullanim:
        >>> manager = SkillManager.get_instance()
        >>> manager.discover_skills()
        >>> prompt = manager.get_combined_prompt(["web_scraper", "game_dev"])
        >>> tools = manager.get_combined_tools(["web_scraper", "game_dev"])
    """

    _instance: Optional[SkillManager] = None
    _instance_lock: ClassVar[RLock] = RLock()
    _initialized: bool = False

    def __init__(
        self,
        skills_dir: str = SKILL_DIR_NAME,
        auto_discover: bool = True,
    ) -> None:
        if self._initialized:
            return

        self._skills_dir: str = skills_dir
        self._skills: Dict[str, Skill] = {}
        self._skill_paths: Dict[str, Path] = {}
        self._disabled_skills: Set[str] = set()
        self._load_errors: Dict[str, str] = {}
        self._initialized = True

        if auto_discover:
            self.discover_skills()

    def __new__(cls, *args: Any, **kwargs: Any) -> SkillManager:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(
        cls,
        skills_dir: str = SKILL_DIR_NAME,
    ) -> SkillManager:
        """Singleton ornegini dondurur.

        Args:
            skills_dir: Skill dizini

        Returns:
            SkillManager ornegi
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = cls.__new__(cls)
                    cls._instance = instance
                    instance.__init__(skills_dir=skills_dir, auto_discover=False)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Singleton ornegini sifirlar (testler icin)."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance = None

    # ------------------------------------------------------------------
    # Kesif ve Yukleme
    # ------------------------------------------------------------------

    def discover_skills(self) -> List[str]:
        """skills/ dizinini tarar ve tum skill paketlerini kesfeder.

        Her skill klasorundeki JSON dosyalarini okuyarak Skill
        nesnelerine donusturur.

        Returns:
            Kesfedilen skill adlari listesi
        """
        skills_path = Path(self._skills_dir)
        if not skills_path.exists():
            logger.info("[SkillManager] Skill dizini bulunamadi, olusturuluyor: %s", skills_path)
            skills_path.mkdir(parents=True, exist_ok=True)
            return []

        discovered: List[str] = []
        for entry in sorted(skills_path.iterdir()):
            if not entry.is_dir():
                continue

            skill_name = entry.name
            try:
                skill = self._load_skill_from_dir(entry)
                if skill is not None:
                    self._skills[skill.name] = skill
                    self._skill_paths[skill.name] = entry
                    discovered.append(skill.name)
                    logger.info("[SkillManager] Skill kesfedildi: %s v%s", skill.name, skill.version)
            except Exception as exc:
                self._load_errors[skill_name] = str(exc)
                logger.error("[SkillManager] Skill yuklenemedi '%s': %s", skill_name, exc)

        return discovered

    def _load_skill_from_dir(self, skill_dir: Path) -> Optional[Skill]:
        """Bir skill klasorundan Skill nesnesi olusturur.

        Args:
            skill_dir: Skill klasor yolu

        Returns:
            Skill nesnesi veya None
        """
        meta_path = skill_dir / SKILL_FILE_META
        prompt_path = skill_dir / SKILL_FILE_PROMPT
        tools_path = skill_dir / SKILL_FILE_TOOLS
        examples_path = skill_dir / SKILL_FILE_EXAMPLES

        if not meta_path.exists():
            logger.warning("[SkillManager] skill.json bulunamadi: %s", skill_dir)
            return None

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        skill = Skill.from_dict(meta)

        # System prompt
        if prompt_path.exists():
            skill.system_prompt = prompt_path.read_text(encoding="utf-8")

        # Tools
        if tools_path.exists():
            with open(tools_path, "r", encoding="utf-8") as f:
                skill.tools = json.load(f)

        # Examples
        if examples_path.exists():
            with open(examples_path, "r", encoding="utf-8") as f:
                skill.examples = json.load(f)

        valid, msg = skill.validate()
        if not valid:
            logger.warning("[SkillManager] Gecersiz skill '%s': %s", skill.name, msg)
            return None

        return skill

    def get_skill(self, name: str) -> Optional[Skill]:
        """Skill adina gore Skill nesnesi dondurur.

        Args:
            name: Skill adi

        Returns:
            Skill nesnesi veya None
        """
        return self._skills.get(name)

    def get_all_skills(self) -> Dict[str, Skill]:
        """Tum yuklu skill'leri dondurur."""
        return dict(self._skills)

    def get_skills_by_category(self, category: str) -> List[Skill]:
        """Kategoriye gore skill listesi dondurur.

        Args:
            category: Kategori adi

        Returns:
            Skill listesi
        """
        return [s for s in self._skills.values() if s.category == category]

    def get_enabled_skills(self) -> Dict[str, Skill]:
        """Aktif skill'leri dondurur."""
        return {
            name: skill
            for name, skill in self._skills.items()
            if name not in self._disabled_skills and skill.enabled
        }

    def skill_count(self) -> int:
        """Yuklu skill sayisi."""
        return len(self._skills)

    # ------------------------------------------------------------------
    # Prompt ve Tool Birlestirme
    # ------------------------------------------------------------------

    def get_combined_prompt(self, active_skills: List[str]) -> str:
        """Aktif skill'lerin system prompt'larini birlestirir.

        Dependency siralamasina dikkat eder: bagimli olunan skill
        once eklenir.

        Args:
            active_skills: Aktif edilecek skill adlari listesi

        Returns:
            Birlestirilmis system prompt metni
        """
        ordered = self._resolve_skill_order(active_skills)
        parts: List[str] = []

        for skill_name in ordered:
            skill = self._skills.get(skill_name)
            if skill is None:
                logger.warning("[SkillManager] Skill bulunamadi: %s", skill_name)
                continue
            if skill_name in self._disabled_skills:
                continue
            if skill.system_prompt:
                parts.append(skill.system_prompt)

        return "\n\n".join(parts)

    def get_combined_tools(self, active_skills: List[str]) -> List[Dict[str, Any]]:
        """Aktif skill'lerin tool tanimlarini birlestirir.

        Args:
            active_skills: Aktif edilecek skill adlari listesi

        Returns:
            Birlestirilmis tool tanimlari listesi
        """
        ordered = self._resolve_skill_order(active_skills)
        combined: List[Dict[str, Any]] = []
        seen_names: Set[str] = set()

        for skill_name in ordered:
            skill = self._skills.get(skill_name)
            if skill is None:
                continue
            if skill_name in self._disabled_skills:
                continue
            for tool in skill.tools:
                tool_name = tool.get("name", "")
                if tool_name and tool_name not in seen_names:
                    combined.append(tool)
                    seen_names.add(tool_name)

        return combined

    def get_combined_examples(self, active_skills: List[str]) -> List[Dict[str, Any]]:
        """Aktif skill'lerin ornek konusmalarini birlestirir.

        Args:
            active_skills: Aktif edilecek skill adlari listesi

        Returns:
            Birlestirilmis ornek konusma listesi
        """
        ordered = self._resolve_skill_order(active_skills)
        combined: List[Dict[str, Any]] = []

        for skill_name in ordered:
            skill = self._skills.get(skill_name)
            if skill is None:
                continue
            if skill_name in self._disabled_skills:
                continue
            combined.extend(skill.examples)

        return combined

    def _resolve_skill_order(self, active_skills: List[str]) -> List[str]:
        """Skill'leri dependency sirasina gore siralar.

        Bagimli olunan skill'ler once gelir. Topolojik sort kullanir.

        Args:
            active_skills: Skill adlari

        Returns:
            Siralanmis skill adlari
        """
        ordered: List[str] = []
        visited: Set[str] = set()

        def visit(name: str, path: Set[str]) -> None:
            if name in visited:
                return
            if name in path:
                logger.warning("[SkillManager] Circular dependency detected: %s", name)
                return
            skill = self._skills.get(name)
            if skill is None:
                visited.add(name)
                return
            path.add(name)
            for dep in skill.dependencies:
                visit(dep, path)
            path.remove(name)
            visited.add(name)
            if name in active_skills or name not in ordered:
                ordered.append(name)

        for skill_name in active_skills:
            visit(skill_name, set())

        remaining = [s for s in ordered if s in active_skills]
        return remaining

    # ------------------------------------------------------------------
    # Skill Yonetimi (Enable/Disable/Toggle)
    # ------------------------------------------------------------------

    def enable_skill(self, name: str) -> bool:
        """Bir skill'i aktif eder.

        Bagimli olunan skill'leri de otomatik aktif eder.
        Python paket eksikleri uyarı olarak loglanır ancak engel teşkil etmez.

        Args:
            name: Skill adi

        Returns:
            Basarili mi
        """
        skill = self._skills.get(name)
        if skill is None:
            logger.error("[SkillManager] Skill bulunamadi: %s", name)
            return False

        # Skill bagimliliklarini kontrol et (zorunlu)
        for dep in skill.dependencies:
            if dep not in self._skills:
                logger.error("[SkillManager] Eksik skill bagimliligi '%s' -> '%s'", name, dep)
                return False

        # Python paket eksikleri icin uyari (engel degil)
        missing_pkgs = [p for p in skill.python_deps if not self._is_package_installed(p)]
        if missing_pkgs:
            logger.warning(
                "[SkillManager] '%s' icin eksik pip paketleri: %s",
                name, ", ".join(missing_pkgs),
            )

        # Bagimli skill'leri de aktif et
        for dep in skill.dependencies:
            self.enable_skill(dep)

        self._disabled_skills.discard(name)
        skill.enabled = True
        self._save_skill_metadata(name)
        logger.info("[SkillManager] Skill aktif: %s", name)
        return True

    def disable_skill(self, name: str) -> bool:
        """Bir skill'i devre disi birakir.

        Bu skill'e bagimli olan diger skill'leri de uyarir.

        Args:
            name: Skill adi

        Returns:
            Basarili mi
        """
        skill = self._skills.get(name)
        if skill is None:
            return False

        dependents = self._find_dependents(name)
        if dependents:
            logger.warning(
                "[SkillManager] '%s' devre disi birakiliyor. Bagimli skill'ler: %s",
                name,
                ", ".join(dependents),
            )

        self._disabled_skills.add(name)
        skill.enabled = False
        self._save_skill_metadata(name)
        logger.info("[SkillManager] Skill devre disi: %s", name)
        return True

    def toggle_skill(self, name: str) -> bool:
        """Bir skill'in durumunu degistirir (aktifse pasif, pasifse aktif).

        Args:
            name: Skill adi

        Returns:
            Yeni durum (True=aktif, False=pasif)
        """
        skill = self._skills.get(name)
        if skill is None:
            return False

        if name in self._disabled_skills or not skill.enabled:
            self.enable_skill(name)
            return True
        else:
            self.disable_skill(name)
            return False

    def is_skill_enabled(self, name: str) -> bool:
        """Skill aktif mi kontrol eder.

        Args:
            name: Skill adi

        Returns:
            Aktif mi
        """
        skill = self._skills.get(name)
        if skill is None:
            return False
        return name not in self._disabled_skills and skill.enabled

    def _find_dependents(self, skill_name: str) -> List[str]:
        """Bir skill'e bagimli olan diger skill'leri bulur.

        Args:
            skill_name: Bagimli olunan skill adi

        Returns:
            Bagimli skill adlari
        """
        dependents: List[str] = []
        for name, skill in self._skills.items():
            if skill_name in skill.dependencies:
                dependents.append(name)
        return dependents

    # ------------------------------------------------------------------
    # Bagimlilik Kontrolu
    # ------------------------------------------------------------------

    def check_dependencies(self, name: str) -> Tuple[bool, str]:
        """Bir skill'in tum bagimliliklarini kontrol eder.

        Skill bagimliliklarini (zorunlu) ve Python paketlerini (opsiyonel)
        kontrol eder.

        Args:
            name: Skill adi

        Returns:
            (tamam_mi, mesaj)
        """
        skill = self._skills.get(name)
        if skill is None:
            return False, f"Skill bulunamadi: {name}"

        # Skill bagimliliklari (zorunlu)
        missing_deps: List[str] = []
        for dep_name in skill.dependencies:
            if dep_name not in self._skills:
                missing_deps.append(dep_name)

        if missing_deps:
            return False, f"Eksik skill bagimliliklari: {', '.join(missing_deps)}"

        # Python paket bagimliliklari (opsiyonel)
        missing_python_deps: List[str] = []
        for pkg in skill.python_deps:
            if not self._is_package_installed(pkg):
                missing_python_deps.append(pkg)

        if missing_python_deps:
            return (
                True,
                f"Eksik Python paketleri: {', '.join(missing_python_deps)}. "
                f"Komut: pip install {' '.join(missing_python_deps)}",
            )

        return True, "Tum bagimliliklar tamam"

    def install_python_deps(self, name: str) -> Tuple[bool, str]:
        """Bir skill'in Python bagimliliklarini yukler.

        Args:
            name: Skill adi

        Returns:
            (basarili_mi, mesaj)
        """
        skill = self._skills.get(name)
        if skill is None:
            return False, f"Skill bulunamadi: {name}"

        missing = [p for p in skill.python_deps if not self._is_package_installed(p)]
        if not missing:
            return True, "Tum Python paketleri zaten yuklu"

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", *missing],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return True, f"Paketler basariyla yuklendi: {', '.join(missing)}"
            else:
                return False, f"Yukleme hatasi: {result.stderr[:500]}"
        except subprocess.TimeoutExpired:
            return False, "Paket yukleme zamani asildi (120 sn)"
        except Exception as exc:
            return False, f"Paket yukleme hatasi: {exc}"

    def check_all_dependencies(self) -> Dict[str, Tuple[bool, str]]:
        """Tum skill'lerin bagimliliklarini kontrol eder.

        Returns:
            {skill_adi: (tamam_mi, mesaj)}
        """
        results: Dict[str, Tuple[bool, str]] = {}
        for name in self._skills:
            results[name] = self.check_dependencies(name)
        return results

    def install_all_python_deps(self) -> Dict[str, Tuple[bool, str]]:
        """Tum skill'lerin Python bagimliliklarini yukler.

        Returns:
            {skill_adi: (basarili_mi, mesaj)}
        """
        results: Dict[str, Tuple[bool, str]] = {}
        for name in self._skills:
            results[name] = self.install_python_deps(name)
        return results

    @staticmethod
    def _is_package_installed(package_name: str) -> bool:
        """Bir pip paketinin yuklu olup olmadigini import ile kontrol eder.

        Hizli ve guvenilir: subprocess yerine import mekanizmasi kullanir.

        Args:
            package_name: Paket adi

        Returns:
            Yuklu mu
        """
        try:
            importlib.import_module(package_name.replace("-", "_"))
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Skill Kurulumu
    # ------------------------------------------------------------------

    def install_skill(self, source: str, target_name: Optional[str] = None) -> Skill:
        """Bir skill'i git reposundan veya yerel yoldan kurar.

        Desteklenen kaynaklar:
            - Git URL'si (https://github.com/...) -> git clone
            - Yerel dizin yolu -> kopyalama
            - Yerel zip/tar dosyasi -> cikarma

        Args:
            source: Git URL'si veya yerel dosya/dizin yolu
            target_name: Skill adi (opsiyonel, varsa kaynaktan alinir)

        Returns:
            Yuklenen Skill nesnesi

        Raises:
            SkillInstallError: Kurulum basarisiz olursa
        """
        skills_dir = Path(self._skills_dir)
        skills_dir.mkdir(parents=True, exist_ok=True)

        temp_dir: Optional[Path] = None
        try:
            source = source.strip()

            # Git URL kontrolu
            if source.startswith("http") and (
                "github.com" in source or "gitlab.com" in source or "bitbucket.org" in source
            ):
                temp_dir = Path(tempfile.mkdtemp(prefix="skill_install_"))
                result = subprocess.run(
                    ["git", "clone", source, str(temp_dir)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    raise SkillInstallError(
                        f"Git clone hatasi: {result.stderr[:500]}"
                    )

                source_path = temp_dir
            else:
                source_path = Path(source)

                if not source_path.exists():
                    raise SkillInstallError(f"Kaynak bulunamadi: {source}")

                # ZIP dosyasi
                if source_path.suffix in (".zip", ".tar", ".gz"):
                    temp_dir = Path(tempfile.mkdtemp(prefix="skill_install_"))
                    shutil.unpack_archive(str(source_path), str(temp_dir))
                    contents = list(temp_dir.iterdir())
                    if len(contents) == 1 and contents[0].is_dir():
                        source_path = contents[0]
                    else:
                        source_path = temp_dir

            # Skill metadata'sini oku
            meta_file = source_path / SKILL_FILE_META
            if not meta_file.exists():
                raise SkillInstallError(
                    f"Gecersiz skill paketi: {SKILL_FILE_META} bulunamadi"
                )

            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            skill_name = target_name or meta.get("name", source_path.name)
            target_dir = skills_dir / skill_name

            if target_dir.exists():
                raise SkillInstallError(
                    f"Skill zaten mevcut: {skill_name}. Once kaldirin veya farkli isim verin."
                )

            # Kopyala
            shutil.copytree(str(source_path), str(target_dir))

            # Skill'i yukle
            skill = self._load_skill_from_dir(target_dir)
            if skill is None:
                shutil.rmtree(str(target_dir))
                raise SkillInstallError("Skill yuklenemedi, gecersiz paket.")

            self._skills[skill.name] = skill
            self._skill_paths[skill.name] = target_dir
            logger.info("[SkillManager] Skill kuruldu: %s v%s", skill.name, skill.version)

            console.print(f"[green][/green] Skill kuruldu: [bold]{skill.name}[/bold] v{skill.version}")
            return skill

        except SkillInstallError:
            raise
        except subprocess.TimeoutExpired as exc:
            raise SkillInstallError(f"Kurulum zamani asildi: {exc}") from exc
        except Exception as exc:
            raise SkillInstallError(f"Kurulum hatasi: {exc}") from exc
        finally:
            if temp_dir is not None and temp_dir.exists():
                shutil.rmtree(str(temp_dir), ignore_errors=True)

    def uninstall_skill(self, name: str) -> bool:
        """Bir skill'i kaldirir.

        Args:
            name: Skill adi

        Returns:
            Basarili mi
        """
        if name not in self._skills:
            logger.error("[SkillManager] Skill bulunamadi: %s", name)
            return False

        dependents = self._find_dependents(name)
        if dependents:
            logger.warning(
                "[SkillManager] '%s' kaldiriliyor. Bagimli skill'ler: %s",
                name,
                ", ".join(dependents),
            )

        path = self._skill_paths.get(name)
        if path and path.exists():
            shutil.rmtree(str(path))

        self._skills.pop(name, None)
        self._skill_paths.pop(name, None)
        self._disabled_skills.discard(name)
        self._load_errors.pop(name, None)

        logger.info("[SkillManager] Skill kaldirildi: %s", name)
        return True

    # ------------------------------------------------------------------
    # Skill Sablonu Olusturma
    # ------------------------------------------------------------------

    def create_skill_template(
        self,
        name: str,
        category: str = "general",
        author: str = "GlassesCat",
        description: str = "",
    ) -> Skill:
        """Yeni bir skill iskeleti olusturur.

        skills/<name>/ dizininde gerekli tum dosyalari ve
        ornek icerigi olusturur.

        Args:
            name: Skill adi
            category: Kategori (coding, security, gaming, general, productivity)
            author: Yazar adi
            description: Skill aciklamasi

        Returns:
            Olusturulan Skill nesnesi

        Raises:
            SkillError: Dizin zaten mevcutsa veya gecersiz kategori
        """
        if category not in VALID_CATEGORIES:
            raise SkillError(
                f"Gecersiz kategori: {category}. Gecerli: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        skills_dir = Path(self._skills_dir)
        skill_dir = skills_dir / name

        if skill_dir.exists():
            raise SkillError(f"Skill dizini zaten mevcut: {skill_dir}")

        skill_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "name": name,
            "version": "0.1.0",
            "description": description or f"{name} skill - henuz aciklama girilmedi",
            "author": author,
            "category": category,
            "dependencies": [],
            "python_deps": [],
            "enabled": True,
        }

        prompt_template = f"""## {name.title()} Skill - Aktif

{description or 'Bu skill henuz yapilandirilmadi.'}

### Yetenekler:
- Yetenek 1: Aciklama
- Yetenek 2: Aciklama
- Yetenek 3: Aciklama

### Kullanim:
Bu skill aktifken AI su sekilde davranir:
1. Adim 1
2. Adim 2
3. Adim 3
"""

        tools_template: List[Dict[str, Any]] = [
            {
                "name": f"{name}_example_tool",
                "description": "Ornek tool - bu skill icin bir islem yapar",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Girdi parametresi",
                        },
                    },
                    "required": ["input"],
                },
            },
        ]

        examples_template: List[Dict[str, Any]] = [
            {
                "title": "Ornek Kullanim",
                "user": f"{name} skill'ini kullanarak bir islem yap",
                "assistant": f"{name} skill'i aktif. Isleminiz gerceklestiriliyor...\n\nSonuc basariyla tamamlandi.",
            },
        ]

        # Dosyalari yaz
        with open(skill_dir / SKILL_FILE_META, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=4, ensure_ascii=False)

        with open(skill_dir / SKILL_FILE_PROMPT, "w", encoding="utf-8") as f:
            f.write(prompt_template)

        with open(skill_dir / SKILL_FILE_TOOLS, "w", encoding="utf-8") as f:
            json.dump(tools_template, f, indent=4, ensure_ascii=False)

        with open(skill_dir / SKILL_FILE_EXAMPLES, "w", encoding="utf-8") as f:
            json.dump(examples_template, f, indent=4, ensure_ascii=False)

        skill = Skill(
            name=name,
            version=meta["version"],
            description=meta["description"],
            author=meta["author"],
            category=meta["category"],
            system_prompt=prompt_template,
            tools=tools_template,
            examples=examples_template,
            dependencies=[],
            python_deps=[],
            enabled=True,
        )

        self._skills[name] = skill
        self._skill_paths[name] = skill_dir

        console.print(f"[green][/green] Skill sablonu olusturuldu: [bold]{name}[/bold]")
        console.print(f"  Dizin: {skill_dir}")
        console.print(f"  Dosyalar: {SKILL_FILE_META}, {SKILL_FILE_PROMPT}, {SKILL_FILE_TOOLS}, {SKILL_FILE_EXAMPLES}")

        return skill

    # ------------------------------------------------------------------
    # Skill Icerigini Guncelleme
    # ------------------------------------------------------------------

    def update_skill_metadata(self, name: str, **kwargs: Any) -> bool:
        """Bir skill'in metadata alanlarini gunceller.

        Args:
            name: Skill adi
            kwargs: Guncellenecek alanlar (name, version, description, etc.)

        Returns:
            Basarili mi
        """
        skill = self._skills.get(name)
        if skill is None:
            return False

        for key, value in kwargs.items():
            if hasattr(skill, key):
                setattr(skill, key, value)

        self._save_skill_metadata(name)
        logger.info("[SkillManager] Skill metadata guncellendi: %s", name)
        return True

    def _save_skill_metadata(self, name: str) -> None:
        """Skill metadata'sini skill.json dosyasina kaydeder.

        Args:
            name: Skill adi
        """
        skill = self._skills.get(name)
        path = self._skill_paths.get(name)
        if skill is None or path is None:
            return

        meta_path = path / SKILL_FILE_META
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing = {}

        existing["enabled"] = skill.enabled
        existing["name"] = skill.name
        existing["version"] = skill.version
        existing["description"] = skill.description
        existing["category"] = skill.category
        existing["dependencies"] = list(skill.dependencies)
        existing["python_deps"] = list(skill.python_deps)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Disa/inport
    # ------------------------------------------------------------------

    def export_skill(self, name: str, output_path: Optional[str] = None) -> str:
        """Bir skill'i zip dosyasi olarak disa aktarir.

        Args:
            name: Skill adi
            output_path: Cikti dosya yolu (opsiyonel)

        Returns:
            Olusturulan zip dosyasi yolu

        Raises:
            SkillNotFoundError: Skill bulunamazsa
        """
        skill = self._skills.get(name)
        path = self._skill_paths.get(name)
        if skill is None or path is None:
            raise SkillNotFoundError(f"Skill bulunamadi: {name}")

        if output_path is None:
            output_path = f"{name}_skill_v{skill.version}.zip"

        shutil.make_archive(
            str(Path(output_path).with_suffix("")),
            "zip",
            str(path),
        )

        logger.info("[SkillManager] Skill export edildi: %s -> %s", name, output_path)
        return output_path

    def import_skill(self, zip_path: str) -> Skill:
        """Bir skill zip dosyasini iceri aktarir.

        Args:
            zip_path: Zip dosya yolu

        Returns:
            Yuklenen Skill nesnesi

        Raises:
            SkillInstallError: Yukleme basarisiz olursa
        """
        return self.install_skill(zip_path)

    # ------------------------------------------------------------------
    # Gorsellestirme
    # ------------------------------------------------------------------

    def list_skills_table(self) -> str:
        """Tum skill'leri tablo olarak gosterir.

        Returns:
            Tablo metni
        """
        table = Table(title=f"Skill'ler ({self.skill_count()} adet)")
        table.add_column("Skill", style="cyan", no_wrap=True)
        table.add_column("Versiyon", style="magenta")
        table.add_column("Kategori", style="blue")
        table.add_column("Durum", style="green")
        table.add_column("Bagimlilik", style="yellow")
        table.add_column("Aciklama")

        for name, skill in sorted(self._skills.items()):
            status = "[green]Aktif[/green]" if self.is_skill_enabled(name) else "[red]Pasif[/red]"
            deps = ", ".join(skill.dependencies) if skill.dependencies else "-"
            table.add_row(
                name,
                skill.version,
                skill.category,
                status,
                deps,
                skill.description[:60] + ("..." if len(skill.description) > 60 else ""),
            )

        console.print(table)
        return ""

    def show_skill_detail(self, name: str) -> None:
        """Bir skill'in detayli bilgisini gosterir.

        Args:
            name: Skill adi
        """
        skill = self._skills.get(name)
        if skill is None:
            console.print(f"[red]Skill bulunamadi: {name}[/red]")
            return

        tree = Tree(f"[bold cyan]{skill.name}[/bold cyan] v{skill.version}")
        tree.add(f"[bold]Yazar:[/bold] {skill.author}")
        tree.add(f"[bold]Kategori:[/bold] {skill.category}")
        tree.add(f"[bold]Durum:[/bold] {'[green]Aktif[/green]' if self.is_skill_enabled(name) else '[red]Pasif[/red]'}")
        tree.add(f"[bold]Aciklama:[/bold] {skill.description}")

        if skill.dependencies:
            deps = tree.add("[bold]Skill Bagimliliklari:[/bold]")
            for dep in skill.dependencies:
                deps.add(f"[yellow]{dep}[/yellow]")
        else:
            tree.add("[bold]Skill Bagimliliklari:[/bold] Yok")

        if skill.python_deps:
            py_deps = tree.add("[bold]Python Paketleri:[/bold]")
            for pkg in skill.python_deps:
                installed = self._is_package_installed(pkg)
                icon = "[green][/green]" if installed else "[red][/red]"
                py_deps.add(f"{icon} {pkg}")
        else:
            tree.add("[bold]Python Paketleri:[/bold] Yok")

        tools_branch = tree.add(f"[bold]Tool Sayisi:[/bold] {len(skill.tools)}")
        for tool in skill.tools:
            tools_branch.add(f"[cyan]{tool.get('name', '?')}[/cyan]: {tool.get('description', '')[:80]}")

        examples_branch = tree.add(f"[bold]Ornek Sayisi:[/bold] {len(skill.examples)}")
        for ex in skill.examples:
            examples_branch.add(f"[italic]{ex.get('title', '')}[/italic]")

        prompt_len = len(skill.system_prompt) if skill.system_prompt else 0
        tree.add(f"[bold]Prompt Uzunlugu:[/bold] {prompt_len} karakter")

        console.print(tree)

    # ------------------------------------------------------------------
    # Refleks
    # ------------------------------------------------------------------

    def get_skill_summary(self) -> Dict[str, Any]:
        """Skill sistemi ozet bilgilerini dondurur.

        Returns:
            Ozet sozlugu
        """
        enabled = sum(1 for s in self._skills if self.is_skill_enabled(s))
        disabled = self.skill_count() - enabled
        categories: Dict[str, int] = {}
        for skill in self._skills.values():
            categories[skill.category] = categories.get(skill.category, 0) + 1

        return {
            "total_skills": self.skill_count(),
            "enabled": enabled,
            "disabled": disabled,
            "categories": categories,
            "skills_dir": self._skills_dir,
            "load_errors": dict(self._load_errors),
        }

    def reload_skill(self, name: str) -> bool:
        """Bir skill'i yeniden yukler (hot-reload).

        Args:
            name: Skill adi

        Returns:
            Basarili mi
        """
        path = self._skill_paths.get(name)
        if path is None:
            logger.error("[SkillManager] Skill yolu bulunamadi: %s", name)
            return False

        was_enabled = self.is_skill_enabled(name)

        try:
            skill = self._load_skill_from_dir(path)
            if skill is None:
                return False

            if was_enabled:
                skill.enabled = True
                self._disabled_skills.discard(name)
            else:
                skill.enabled = False
                self._disabled_skills.add(name)

            self._skills[name] = skill
            logger.info("[SkillManager] Skill yeniden yuklendi: %s", name)
            return True
        except Exception as exc:
            self._load_errors[name] = str(exc)
            logger.error("[SkillManager] Skill reload hatasi '%s': %s", name, exc)
            return False

    def reload_all_skills(self) -> Dict[str, bool]:
        """Tum skill'leri yeniden yukler.

        Returns:
            {skill_adi: basarili_mi}
        """
        results: Dict[str, bool] = {}
        for name in list(self._skills.keys()):
            results[name] = self.reload_skill(name)
        return results


# ---------------------------------------------------------------------------
# Module-level yardimci fonksiyonlar
# ---------------------------------------------------------------------------

def get_skill_manager() -> SkillManager:
    """SkillManager singleton ornegini dondurur (kisa yol).

    Returns:
        SkillManager ornegi
    """
    return SkillManager.get_instance()


def create_skill(
    name: str,
    category: str = "general",
    author: str = "GlassesCat",
    description: str = "",
) -> Skill:
    """Yeni bir skill sablonu olusturur (kisa yol).

    Args:
        name: Skill adi
        category: Kategori
        author: Yazar
        description: Aciklama

    Returns:
        Skill nesnesi
    """
    return get_skill_manager().create_skill_template(
        name=name,
        category=category,
        author=author,
        description=description,
    )


def list_skills() -> None:
    """Tum skill'leri tablo olarak listeler."""
    get_skill_manager().list_skills_table()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Komut satirindan skill yonetimi icin CLI giris noktasi.

    Kullanim:
        python skill_system.py discover
        python skill_system.py list
        python skill_system.py show <skill_adi>
        python skill_system.py enable <skill_adi>
        python skill_system.py disable <skill_adi>
        python skill_system.py toggle <skill_adi>
        python skill_system.py create <skill_adi> [kategori]
        python skill_system.py install <kaynak>
        python skill_system.py uninstall <skill_adi>
        python skill_system.py check-deps
        python skill_system.py install-deps
        python skill_system.py export <skill_adi> [cikti_yolu]
    """
    import argparse

    parser = argparse.ArgumentParser(description="Glassescat AI Skill Yoneticisi")
    parser.add_argument("command", help="Komut (discover, list, show, enable, disable, toggle, create, install, uninstall, check-deps, install-deps, export, reload)")
    parser.add_argument("args", nargs="*", help="Komut argumanlari")

    args = parser.parse_args()

    manager = get_skill_manager()
    manager.discover_skills()

    cmd = args.command

    if cmd == "discover":
        skills = manager.discover_skills()
        console.print(f"[green][/green] {len(skills)} skill kesfedildi: {', '.join(skills) if skills else 'skill bulunamadi'}")

    elif cmd == "list":
        manager.list_skills_table()

    elif cmd == "show":
        if not args.args:
            console.print("[red]Kullanim: show <skill_adi>[/red]")
            return
        manager.show_skill_detail(args.args[0])

    elif cmd == "enable":
        if not args.args:
            console.print("[red]Kullanim: enable <skill_adi>[/red]")
            return
        for name in args.args:
            if manager.enable_skill(name):
                console.print(f"[green][/green] {name} aktif edildi")
            else:
                console.print(f"[red][/red] {name} aktif edilemedi")

    elif cmd == "disable":
        if not args.args:
            console.print("[red]Kullanim: disable <skill_adi>[/red]")
            return
        for name in args.args:
            if manager.disable_skill(name):
                console.print(f"[green][/green] {name} devre disi birakildi")
            else:
                console.print(f"[red][/red] {name} devre disi birakilamadi")

    elif cmd == "toggle":
        if not args.args:
            console.print("[red]Kullanim: toggle <skill_adi>[/red]")
            return
        for name in args.args:
            new_state = manager.toggle_skill(name)
            state_str = "aktif" if new_state else "pasif"
            console.print(f"[green][/green] {name} -> {state_str}")

    elif cmd == "create":
        name = args.args[0] if args.args else None
        category = args.args[1] if len(args.args) > 1 else "general"
        if not name:
            console.print("[red]Kullanim: create <skill_adi> [kategori][/red]")
            return
        try:
            manager.create_skill_template(name=name, category=category)
        except SkillError as e:
            console.print(f"[red]Hata: {e}[/red]")

    elif cmd == "install":
        if not args.args:
            console.print("[red]Kullanim: install <kaynak_url_veya_yol>[/red]")
            return
        try:
            manager.install_skill(args.args[0])
        except SkillInstallError as e:
            console.print(f"[red]Hata: {e}[/red]")

    elif cmd == "uninstall":
        if not args.args:
            console.print("[red]Kullanim: uninstall <skill_adi>[/red]")
            return
        if manager.uninstall_skill(args.args[0]):
            console.print(f"[green][/green] {args.args[0]} kaldirildi")
        else:
            console.print(f"[red][/red] {args.args[0]} kaldirilamadi")

    elif cmd == "check-deps":
        results = manager.check_all_dependencies()
        for name, (ok, msg) in sorted(results.items()):
            icon = "[green][/green]" if ok else "[red][/red]"
            console.print(f"{icon} {name}: {msg}")

    elif cmd == "install-deps":
        results = manager.install_all_python_deps()
        for name, (ok, msg) in sorted(results.items()):
            icon = "[green][/green]" if ok else "[red][/red]"
            console.print(f"{icon} {name}: {msg}")

    elif cmd == "export":
        if not args.args:
            console.print("[red]Kullanim: export <skill_adi> [cikti_yolu][/red]")
            return
        try:
            path = manager.export_skill(args.args[0], args.args[1] if len(args.args) > 1 else None)
            console.print(f"[green][/green] Export: {path}")
        except SkillNotFoundError as e:
            console.print(f"[red]Hata: {e}[/red]")

    elif cmd == "reload":
        if args.args:
            for name in args.args:
                if manager.reload_skill(name):
                    console.print(f"[green][/green] {name} yeniden yuklendi")
                else:
                    console.print(f"[red][/red] {name} yeniden yuklenemedi")
        else:
            results = manager.reload_all_skills()
            for name, ok in results.items():
                icon = "[green][/green]" if ok else "[red][/red]"
                console.print(f"{icon} {name}")

    else:
        console.print(f"[red]Bilinmeyen komut: {cmd}[/red]")
        console.print("Kullanilabilir komutlar: discover, list, show, enable, disable, toggle, create, install, uninstall, check-deps, install-deps, export, reload")


if __name__ == "__main__":
    main()
