"""
🛡️ J.A.R.V.I.S Shield Core — Autonomous System Protection & Execution Guardrail
Elytra-ai | Developer: Berkay

Bu modül; J.A.R.V.I.S modelinin Windows üzerinde ürettiği tüm Python kodlarını,
PowerShell/CMD komutlarını ve dosya işlemlerini 5 aşamalı zırhtan geçirir.
Tehlikeli veya yıkıcı talepleri onay beklemeden ANINDA REDDEDER.
"""

import os
import re
import ast
import sys
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("JARVISShield")
logging.basicConfig(level=logging.INFO)

PROTECTED_PATHS = [
    re.compile(r"^[a-zA-Z]:\\windows\\system32", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\windows\\syswow64", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\boot", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\efi", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\recovery", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\\$recycle\.bin", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\system volume information", re.IGNORECASE),
]

SAFE_CLEANUP_WHITELIST = [
    re.compile(r"^[a-zA-Z]:\\users\\[^\\]+\\appdata\\local\\temp", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\windows\\temp", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\windows\\softwaredistribution\\download", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\users\\[^\\]+\\appdata\\local\\crashdumps", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\users\\[^\\]+\\appdata\\local\\nvidia\\dxcache", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:\\users\\[^\\]+\\appdata\\local\\d3dscache", re.IGNORECASE),
]

PROTECTED_REGISTRY_KEYS = [
    r"HKLM\SAM",
    r"HKLM\SECURITY",
    r"HKLM\SYSTEM\CurrentControlSet\Control\CrashControl",
]

PROTECTED_SERVICES = [
    "dhcp", "dnscache", "windefend", "lanmanserver", "cryptsvc", "rpcss", "mpssvc"
]

ALLOWED_STOP_SERVICES = [
    "diagtrack", "sysmain", "wsearch", "xblauthmanager", "xboxgipsvc", "xblgamesave"
]

TIER4_BANNED_REGEX = [
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bdiskpart\b", re.IGNORECASE),
    re.compile(r"\bbcdedit\b", re.IGNORECASE),
    re.compile(r"\bvssadmin\s+delete\s+shadows", re.IGNORECASE),
    re.compile(r"\bnet\s+user\b", re.IGNORECASE),
    re.compile(r"\breg\s+delete\s+hklm\\system", re.IGNORECASE),
    re.compile(r"\btakeown\b", re.IGNORECASE),
    re.compile(r"\bicacls\b", re.IGNORECASE),
    re.compile(r"rmdir\s+/[sq]\s+[a-zA-Z]:\\$", re.IGNORECASE),
]

BACKUP_DIR = Path("C:/JARVIS_Backups")
QUARANTINE_DIR = Path("C:/JARVIS_Karantina")

class ASTSecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations: List[str] = []

    def visit_Call(self, node):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in ("remove", "unlink", "rmtree", "rmdir"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    val = arg.value
                    if any(p.search(val) for p in PROTECTED_PATHS) or val.strip().lower() in ("c:\\", "c:/", "/"):
                        self.violations.append(f"Kritik dizine doğrudan dosya silme engellendi: {val}")

        self.generic_visit(node)

def analyze_python_ast(code_str: str) -> Tuple[bool, Optional[str]]:
    try:
        tree = ast.parse(code_str)
        visitor = ASTSecurityVisitor()
        visitor.visit(tree)
        if visitor.violations:
            return False, " | ".join(visitor.violations)
        return True, None
    except SyntaxError as e:
        return False, f"Python Syntax Hatası: {e}"

def analyze_command_regex(cmd: str) -> Tuple[bool, Optional[str]]:
    cmd_clean = cmd.strip()
    for pat in TIER4_BANNED_REGEX:
        if pat.search(cmd_clean):
            return False, f"Tier 4 Yasaklı Komut Engellendi: '{pat.pattern}'"

    for pat in PROTECTED_PATHS:
        if pat.search(cmd_clean):
            if any(k in cmd_clean.lower() for k in ("remove-item", "del ", "erase", "rmdir", "move", "takeown", "icacls")):
                return False, f"Korumalı sistem dizinine müdahale KESİNTİSİZ ENGELLENDİ: {pat.pattern}"

    for srv in PROTECTED_SERVICES:
        if f"stop-service" in cmd_clean.lower() and srv in cmd_clean.lower():
            return False, f"Kritik Windows servisi durdurulamaz: {srv}"

    return True, None

class JARVISShield:
    def __init__(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    def classify_tier(self, command_or_code: str) -> int:
        c = command_or_code.lower()
        valid, reason = analyze_command_regex(command_or_code)
        if not valid: return 4
        if "set-itemproperty" in c or "reg add" in c or "reg delete" in c: return 3
        if "powercfg" in c or "stop-service" in c or "winget" in c or "start-service" in c: return 2
        return 1

    def backup_registry_key(self, key_path: str) -> bool:
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", key_path)
            backup_file = BACKUP_DIR / "Registry" / f"{safe_name}_{timestamp}.reg"
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["reg", "export", key_path, str(backup_file), "/y"], capture_output=True, timeout=10)
            logger.info(f"🛡️ Registry Yedeği Alındı: {backup_file}")
            return True
        except Exception as e:
            logger.warning(f"Registry yedekleme uyarısı: {e}")
            return False

    def execute_powershell_safe(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        valid, reason = analyze_command_regex(command)
        if not valid:
            logger.error(f"❌ [J.A.R.V.I.S SHIELD REJECTED] {reason}")
            return {
                "success": False,
                "status": "REJECTED_BY_SHIELD",
                "tier": 4,
                "error": f"J.A.R.V.I.S Shield Protokolü: {reason}. İşlem onay istenmeden doğrudan REDDEDİLDİ."
            }

        tier = self.classify_tier(command)
        if tier == 3 and "reg" in command.lower():
            match = re.search(r'(HK[A-Z]{2,4}\\[^\s"]+)', command, re.IGNORECASE)
            if match: self.backup_registry_key(match.group(1))

        try:
            encoded_cmd = f"$ErrorActionPreference = 'Stop'; {command}"
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", encoded_cmd],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "status": "EXECUTED",
                "tier": tier,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "status": "TIMEOUT",
                "tier": tier,
                "error": f"Komut {timeout} saniyelik güvenlik zaman aşımına uğradı ve zorla sonlandırıldı."
            }
        except Exception as e:
            return {
                "success": False,
                "status": "ERROR",
                "tier": tier,
                "error": str(e)
            }

_shield_instance = None

def get_jarvis_shield() -> JARVISShield:
    global _shield_instance
    if _shield_instance is None:
        _shield_instance = JARVISShield()
    return _shield_instance
