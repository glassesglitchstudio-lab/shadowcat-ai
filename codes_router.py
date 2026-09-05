"""
CodeS Router — Shadowcat.AI ticari model yönlendiricisi

Plan B2: kural tabanlı sınıflandırma + fallback zinciri + loglama.
Geliştirici model adları (x_opus, glitch_opus, x_fable_coder) sadece burada;
arayüz yalnızca ticari adları (CodeS Lite/Flash/Pro/Expert) görür.
"""

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional

import requests

logger = logging.getLogger("CodeSRouter")

OLLAMA_BASE = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_TAGS = f"{OLLAMA_BASE}/api/tags"

# ── Gerçek model havuzu (geliştirici adları) ────────────────────────────────
M_XOPUS = "glassesglitchstudio/x_opus:V1_X_OPUS"
M_GOPUS = "glassesglitchstudio/glitch_opus:X_GLITCH_OPUS"
M_FABLE = "glassesglitchstudio/x_fable_coder:V1"
M_LOCAL = "gulmezcetiner-max-plus:latest"
M_QWEN35 = "qwen3.5:9b"
M_CODER14 = "qwen2.5-coder:14b"
M_R1 = "deepseek-r1:14b"

# ── Ticari kademe → tercih zinciri (kurulu ilk model seçilir) ───────────────
TIER_CHAINS: Dict[str, Optional[List[str]]] = {
    "CODES_LITE":   [M_LOCAL, M_GOPUS, M_XOPUS],
    "CODES_FLASH":  [M_QWEN35, M_LOCAL, M_XOPUS],
    "CODES_PRO":    [M_CODER14, M_FABLE, M_QWEN35, M_LOCAL],
    "CODES_EXPERT": [M_R1, M_CODER14, M_FABLE, M_LOCAL],
    "CODES":        None,   # otomatik: kategoriye göre zincir
    "MAXCODE":      [M_XOPUS, M_FABLE],
    "MAXP":         [M_LOCAL],
    "R1_14B":       [M_R1, M_LOCAL],
    "CODER_14B":    [M_CODER14, M_FABLE, M_LOCAL],
}

# ── Kategori → tercih zinciri ───────────────────────────────────────────────
CATEGORY_CHAINS: Dict[str, List[str]] = {
    "quick":    [M_GOPUS, M_XOPUS],
    "chat":     [M_XOPUS, M_GOPUS],
    "code":     [M_FABLE, M_XOPUS],
    "big":      [M_FABLE, M_XOPUS],
    "cyber":    [M_XOPUS, M_FABLE],
    "analysis": [M_XOPUS, M_GOPUS],
}

TIER_LABELS = {
    "CODES_LITE": "CodeS Lite",
    "CODES_FLASH": "CodeS Flash",
    "CODES_PRO": "CodeS Pro",
    "CODES_EXPERT": "CodeS Expert",
    "CODES": "CodeS (otomatik)",
    "MAXCODE": "MaxCode",
    "MAXP": "🐾 Max+ (Yerli)",
    "R1_14B": "🧠 DeepSeek-R1 14B",
    "CODER_14B": "💻 Qwen-Coder 14B",
}

# ── Sınıflandırma sinyalleri ────────────────────────────────────────────────
CODE_MARK_RE = re.compile(
    r"```|\b(def |class |import |from \w+ import|function |const |=>|npm |pip |git |curl )",
    re.IGNORECASE,
)

BIG_KEYWORDS = [
    "refactor", "mimari", "architecture", "yeniden yaz", "büyük proje",
    "optimizasyon", "optimize", "modüler", "mikroservis", "microservice",
    "ci/cd", "deploy", "ölçeklendir", "performance", "performans",
    "tam proje", "sıfırdan", "baştan yaz",
]

# Tek başına geçtiğinde bile "cyber" sayılan güçlü sinyaller
STRONG_CYBER = [
    "nmap", "metasploit", "wireshark", "burp", "kali", "pentest",
    "exploit", "malware", "ransomware", "keylogger", "rootkit",
    "siber", "ctf", "osint", "reverse shell",
]

ANALYSIS_KEYWORDS = [
    "analiz", "karşılaştır", "neden", "açıkla", "mantık", "matematik",
    "hesapla", "özetle", "değerlendir", "strateji", "planla",
]

GREETING_PREFIXES = ("merhaba", "selam", "naber", "nasılsın", "hey", "hi", "hello")

LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "storage", "codes_router_log.jsonl"
)


def is_codes_tier(value: str) -> bool:
    return (value or "").upper() in TIER_CHAINS


class CodeSRouter:
    """Soru → kategori → model zinciri → kurulu/çalışan modele yönlendirir."""

    def __init__(self):
        self._tags_cache: set = set()
        self._tags_ts: float = 0.0

    # ── Kurulu model tespiti (60 sn önbellekli) ─────────────────────────────
    def installed_models(self) -> set:
        now = time.time()
        if self._tags_cache and now - self._tags_ts < 60:
            return self._tags_cache
        try:
            r = requests.get(OLLAMA_TAGS, timeout=4)
            names = {m.get("name", "").lower() for m in r.json().get("models", [])}
            if names:
                self._tags_cache, self._tags_ts = names, now
        except Exception:
            pass
        return self._tags_cache

    def _available_chain(self, chain: List[str]) -> List[str]:
        installed = self.installed_models()
        if not installed:
            return list(chain)  # ollama kapalıysa zinciri olduğu gibi dene
        ready = [m for m in chain if m.lower() in installed]
        if ready:
            return ready
        if M_LOCAL.lower() in installed:
            return [M_LOCAL]          # son savunma: yerli Max+ her zaman cevap verir
        return list(chain)

    # ── Kural tabanlı sınıflandırıcı (ML yok; uzunluk + anahtar kelime + bağlam)
    def classify(self, message: str) -> str:
        m = (message or "").strip()
        ml = m.lower()
        length = len(m)
        has_code = bool(CODE_MARK_RE.search(m))

        from xopus_router import CYBER_KEYWORDS, CODE_KEYWORDS
        cyber = sum(1 for kw in CYBER_KEYWORDS if kw in ml)
        strong_cyber = any(kw in ml for kw in STRONG_CYBER)
        code = sum(1 for kw in CODE_KEYWORDS if kw in ml)
        big = sum(1 for kw in BIG_KEYWORDS if kw in ml)

        if strong_cyber or (cyber >= 2 and cyber >= code):
            return "cyber"
        if big >= 2 or (big >= 1 and (has_code or length > 400)):
            return "big"
        if code >= 1 or has_code:
            return "code"
        if length < 90 and ("?" in m or ml.startswith(GREETING_PREFIXES)):
            return "quick"
        if any(kw in ml for kw in ANALYSIS_KEYWORDS):
            return "analysis"
        return "chat"

    def resolve_chain(self, tier: str, message: str) -> List[str]:
        tier = (tier or "CODES").upper()
        chain = TIER_CHAINS.get(tier)
        category = self.classify(message) if chain is None else None
        if chain is None:
            chain = CATEGORY_CHAINS.get(category or "chat", CATEGORY_CHAINS["chat"])
        return self._available_chain(chain)

    # ── Loglama: hangi model neyi cevapladı → ileride eşleme iyileştirme ────
    def _log(self, tier: str, category: Optional[str], model: Optional[str],
             ok: bool, started: float):
        try:
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": int(time.time()),
                    "tier": tier,
                    "category": category,
                    "model": model,
                    "ok": ok,
                    "ms": int((time.time() - started) * 1000),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ── Streaming: hata durumunda zincirde sıradaki modele düşer ─────────────
    def chat_stream(self, message: str, tier: str = "CODES",
                    system_prompt: str = None, context: Optional[List[Dict]] = None):
        from xopus_router import get_xopus

        tier = (tier or "CODES").upper()
        category = self.classify(message) if tier == "CODES" else None
        chain = self.resolve_chain(tier, message)
        started = time.time()
        emitted = False
        last_err: Optional[Exception] = None

        xopus = get_xopus()
        for model in chain:
            try:
                for ch in xopus.chat_stream(message=message,
                                            system_prompt=system_prompt,
                                            model=model, context=context):
                    emitted = True
                    yield ch
                self._log(tier, category, model, True, started)
                return
            except Exception as e:
                last_err = e
                logger.warning(f"[CodeS] {model} düştü: {e}")
                if emitted:
                    # Akış başladıktan sonra model öldü → baştan yazmak yanlış olur
                    yield {"error": f"Model yanıt sırasında kesildi: {e}", "done": True}
                    self._log(tier, category, model, False, started)
                    return
                self._log(tier, category, model, False, started)
                continue

        yield {"error": f"Uygun model bulunamadı ({last_err})", "done": True}
        self._log(tier, category, None, False, started)

    # ── Non-streaming: tam fallback ─────────────────────────────────────────
    def chat(self, message: str, tier: str = "CODES",
             system_prompt: str = None, context: Optional[List[Dict]] = None) -> Dict:
        from xopus_router import get_xopus

        tier = (tier or "CODES").upper()
        category = self.classify(message) if tier == "CODES" else None
        chain = self.resolve_chain(tier, message)
        started = time.time()
        last_err = "bilinmeyen hata"

        xopus = get_xopus()
        for model in chain:
            result = xopus.chat(message=message, system_prompt=system_prompt,
                                model=model, context=context)
            if result.get("success"):
                self._log(tier, category, model, True, started)
                result["tier"] = tier
                result["category"] = category
                result["tier_label"] = TIER_LABELS.get(tier, tier)
                return result
            last_err = result.get("error", last_err)
            self._log(tier, category, model, False, started)

        return {"success": False, "error": f"{TIER_LABELS.get(tier, tier)} yanıt veremedi: {last_err}",
                "tier": tier, "category": category}

    def get_status(self) -> Dict:
        installed = self.installed_models()
        pool = [M_XOPUS, M_GOPUS, M_FABLE]
        return {
            "ollama": OLLAMA_BASE,
            "installed": {m: (m.lower() in installed if installed else None) for m in pool},
            "tiers": {t: (c or "otomatik") for t, c in TIER_CHAINS.items()},
        }


_codes_instance: Optional[CodeSRouter] = None


def get_codes_router() -> CodeSRouter:
    global _codes_instance
    if _codes_instance is None:
        _codes_instance = CodeSRouter()
    return _codes_instance
