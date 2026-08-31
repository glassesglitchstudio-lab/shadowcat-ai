"""

╔═══════════════════════════════════════════════════════════════╗
   DEEPER ENGINE - Cognitive Architecture Katmanları
╚═══════════════════════════════════════════════════════════════╝

Shadowcat'i statik LLM chatbot'undan goal-oriented otonom bir
cognitive system'e dönüştüren 3 katman:

  1. CriticAgent   -> Çıktıyı değerlendirir, puanlar, eleştirir
  2. SymbolicEngine-> Kural bazlı doğrulama + mantık kontrolü
  3. RewardLoop    -> Puanı hafızaya strateji olarak kaydeder, öğrenir

Kapalı döngü:
  Planner -> Orchestrator -> Execution -> Critic -> Reward -> Memory

"""

import os
import re
import json
import time
import logging
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger("DeeperEngine")

REWARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "deeper")
STRATEGIES_FILE = "strategies.json"
REWARDS_FILE = "rewards.json"


# ─────────────────────────────────────────────────────────────
# VERİ SINIFLARI
# ─────────────────────────────────────────────────────────────

@dataclass
class Critique:
    """Critic Agent'in ürettiği değerlendirme"""
    score: float = 0.0                 # 0-1
    verdict: str = "unknown"           # great | good | needs_work | fail
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    summary: str = ""
    rules_checked: int = 0


@dataclass
class Reward:
    """Reward Engine'ın kaydettiği ödül/strateji"""
    id: str
    task: str
    score: float
    strategy: Dict
    timestamp: str = ""
    memorized: bool = False


# ─────────────────────────────────────────────────────────
# SYMBOLIC ENGINE — kural bazlı doğrulama
# ─────────────────────────────────────────────────────────

class SymbolicEngine:
    """LLM çıktısını belirlenmiş kurallarla doğrular.

    Neural + Symbolic hibrit: LLM yaratır, kurallar doğrular.
    """

    RULES = [
        {"id": "empty", "desc": "Çıktı boş olmamalı"},
        {"id": "placeholder", "desc": "Çıktı açıklayıcı olmalı (placeholder değil)"},
        {"id": "code_balance", "desc": "Kod blokları dengeli"},
        {"id": "python_print", "desc": "Python çıktıları implementasyon gerektirmiyor"},
        {"id": "length", "desc": "Yanıt aşırı kısa olmamalı"},
    ]

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def validate(self, response: str) -> Dict:
        result = {
            "passed": True,
            "rules_checked": 0,
            "failures": [],
            "checks": [],
        }
        if not self.enabled:
            return result
        checks = [
            ("length", len(response.strip()) >= 4, "Yanıt aşırı kısa (en az 4 karakter)"),
            ("code_balance", response.count("```") % 2 == 0, "Kod bloklarını kapat (```)"),
            ("not_placeholder", len(response.strip()) > 3, "Yanıtı boş bırakma"),
        ]
        # İstatistik
        ok = sum(1 for _, p, _ in checks if p)
        result["rules_checked"] = len(checks)
        result["passed"] = all(p for _, p, _ in checks)
        result["failures"] = [{"id": cid, "desc": m} for cid, p, m in checks if not p]
        result["checks"] = [
            {"id": cid, "passed": p, "note": m} for cid, p, m in checks
        ]
        return result


# ─────────────────────────────────────────────────────────
# CRITIC AGENT — çıktı değerlendirme
# ─────────────────────────────────────────────────────────

def _keywords(text: str) -> List[str]:
    """Kullanıcı giriminden anlamlı anahtar kelimeleri çıkarır."""
    if not text:
        return []
    stop = {
        "a", "an", "the", "ve", "bir", "bunu", "ben", "sen", "mi", "mu", "mı",
        "ne", "nasıl", "için", "ile", "bu", "şu", "yap", "yapabilir", "nerede",
        "olur", "mısın", "söyle", "göster", "bana", "çok", "daha", "var",
        "yok", "lütfen", "lutfen", "istedigim", "istiyorum", "nedir", "degil",
    }
    words = re.findall(r'[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]{3,}', text.lower())
    kw = [w for w in words if w not in stop]
    return kw[:6]


class CriticAgent:
    """Çıktıyı hedef uyumu, kalite ve doğruluk açısından puanlar.

    İkinci değerlendirme kanallı (feedback + critic) yapı sağlar.
    """

    def __init__(self, symbolic: Optional[SymbolicEngine] = None, enabled: bool = True):
        self.symbolic = symbolic or SymbolicEngine(enabled=enabled)
        self.enabled = enabled

    def critique(self, user_input: str, response: str, tool_calls: List[Dict]) -> Critique:
        if not self.enabled:
            return Critique(score=0.5, verdict="good", summary="Değerlendirme kapalı")
        validation = self.symbolic.validate(response)
        crit = Critique(rules_checked=validation["rules_checked"])

        issues = []
        suggestions = []

        # 1. Simgesel/kural bazlı hatalar
        if not validation["passed"]:
            for f in validation["failures"]:
                if isinstance(f, dict):
                    issues.append(f.get("desc", f.get("id", str(f))))
                else:
                    issues.append(str(f))
        else:
            suggestions.append("Kural doğrulaması geçildi.")

        # 2. Hedef uyumu — anahtar kelime / soru cevap eşleşmesi
        kws = _keywords(user_input)
        qtotal = max(1, len(kws))
        # Kod/eylem içeren yanıtlarda kelime birebir eşleşmesi aranmaz (yeniden ifade edilir)
        has_action = bool(tool_calls)
        if has_action:
            qhits = qtotal
            goal_match = 1.0
        else:
            qhits = sum(1 for kw in kws if kw.lower() in response.lower())
            goal_match = qhits / qtotal
        if goal_match < 0.4 and qtotal > 2 and not has_action:
            issues.append("Yanıt, sorunun anahtar kavramlarına tam cevap vermiyor.")
        else:
            suggestions.append("Sorunun ana kapağı önemli ölçüde yanıtlanıyor.")

        # 3. Tool kullanımı değerlendirmesi
        if tool_calls:
            suggestions.append(f"{len(tool_calls)} araç kullanıldı — görev aksiyon üretti.")

        # 4. Uzunluk ve bağlam
        too_short = len(response.strip()) < 20 and qtotal > 1
        if too_short:
            issues.append("Yanıt, görevin kapsamına göre çok kısa.")

        # Skor hesaplama
        base = 0.6
        score = base + (0.25 if goal_match >= 0.5 else 0.0)
        if tool_calls:
            score += 0.1
        penalty = min(0.4, len(issues) * 0.12)
        score = max(0.0, min(1.0, score - penalty))

        crit.score = round(score, 2)
        crit.issues = issues
        crit.suggestions = suggestions
        if score >= 0.85:
            crit.verdict = "great"
        elif score >= 0.7:
            crit.verdict = "good"
        elif score >= 0.5:
            crit.verdict = "needs_work"
        else:
            crit.verdict = "fail"
        crit.summary = self._summarize(score, issues, tool_calls)
        return crit

    def _summarize(self, score: float, issues: List[str], tool_calls: List[Dict]) -> str:
        if score >= 0.85:
            return "Yanıt hedefe yönelik, kapsamlı ve doğru."
        if score >= 0.7:
            return "Yanıt iyi ancak küçük iyileştirmeler gerekli."
        if score >= 0.5:
            return "Yanıt kısmen yeterli, eksikler var."
        return "Yanıt hedefe ulaşmadı; yeniden üretilmesi önerilir."


# ─────────────────────────────────────────────────────────
# REWARD ENGINE — öğrenme döngüsü
# ─────────────────────────────────────────────────────────

class RewardEngine:
    """Santiyeyi hafızaya strateji olarak kaydeder ve öğrenme istatistiği tutar."""

    def __init__(self, enabled: bool = True, memory=None):
        self.enabled = enabled
        self.memory = memory
        self._lock = threading.RLock()
        os.makedirs(REWARD_DIR, exist_ok=True)
        self.strategies: List[Dict] = []
        self.rewards: List[Reward] = []
        self._load()

    def evaluate(self, user_input: str, task: str, score: float, critique: Critique) -> Dict:
        if not self.enabled:
            return {"memorized": False, "score": score}
        result = {"memorized": False, "score": score, "strategy": None}
        if score >= 0.7:
            strategy = self._strategy_for(task, critique)
            result["strategy"] = strategy["name"]
            if self.memory:
                try:
                    self.memory.save_knowledge(
                        title=f"Strateji: {task[:50]}",
                        content=strategy["description"],
                        tags=["deeper", "strategy"],
                        category="strategies",
                    )
                    result["memorized"] = True
                except Exception as e:
                    logger.warning(f"Strateji hafızaya yazılamadı: {e}")
        rec = Reward(
            id=f"rw_{int(time.time())}_{len(self.rewards)}",
            task=task,
            score=score,
            strategy={"name": result.get("strategy", "")},
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            memorized=result["memorized"],
        )
        with self._lock:
            self.rewards.append(rec)
            if len(self.rewards) > 200:
                self.rewards = self.rewards[-200:]
            self._save()
        return result

    def _strategy_for(self, task: str, critique: Critique) -> Dict:
        if critique.suggestions:
            return {"name": "iyilestirme", "description": " | ".join(critique.suggestions[:2])}
        return {"name": "goal_oriented", "description": "Hedef odaklı, araç destekli ve doğrulanmış cevap üret."}

    def get_statistics(self) -> Dict:
        if not self.rewards:
            return {"total": 0, "avg_score": 0, "memorized": 0, "strategies": []}
        avg = sum(r.score for r in self.rewards) / len(self.rewards)
        mem = sum(1 for r in self.rewards if r.memorized)
        return {
            "total": len(self.rewards),
            "avg_score": round(avg, 2),
            "memorized": mem,
            "strategies": [r.strategy for r in self.rewards[-5:] if r.strategy],
        }

    # ---- kalıcılık ----
    def _load(self):
        try:
            p = os.path.join(REWARD_DIR, REWARDS_FILE)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                    for row in data:
                        try:
                            self.rewards.append(Reward(**row))
                        except Exception:
                            pass
            sp = os.path.join(REWARD_DIR, STRATEGIES_FILE)
            if os.path.exists(sp):
                with open(sp, encoding="utf-8") as f:
                    self.strategies = json.load(f)
        except Exception as e:
            logger.warning(f"Reward yükleme hatası: {e}")

    def _save(self):
        try:
            with open(os.path.join(REWARD_DIR, REWARDS_FILE), "w", encoding="utf-8") as f:
                json.dump([asdict(r) for r in self.rewards], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Reward kaydetme hatası: {e}")


# -----------------------------------------------------------------
# TOP-LEVEL DEEPER ENGINE
# -----------------------------------------------------------------

@dataclass
class DeeperResult:
    active: bool = False
    layers: List[str] = field(default_factory=list)
    critique: Optional[float] = None
    critical: Dict = field(default_factory=dict)
    symbolic: Dict = field(default_factory=dict)
    reward: Dict = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["verdict_label"] = "Aktif" if self.active else "Pasif"
        return d


class DeeperEngine:
    """Shadowcat cognitive katmanlarını yönetir ve expose eder."""

    def __init__(self, enabled: bool = True, memory=None):
        self.enabled = enabled
        self.critic = CriticAgent(enabled=enabled)
        self.symbolic = SymbolicEngine(enabled=enabled)
        self.reward = RewardEngine(enabled=enabled, memory=memory)

    def run(self, user_input: str, response: str, tool_calls: List[Dict],
            task: str = "") -> DeeperResult:
        if not self.enabled:
            return DeeperResult(active=False)
        task = task or user_input
        crit = self.critic.critique(task, response, tool_calls)
        reward_result = self.reward.evaluate(user_input, task, crit.score, crit)
        sym = self.symbolic.validate(response)
        return DeeperResult(
            active=True,
            layers=["critic", "symbolic", "reward"],
            critique=crit.score,
            critical={"verdict": crit.verdict, "summary": crit.summary,
                      "issues": crit.issues[:3], "suggestions": crit.suggestions[:2]},
            symbolic={"passed": sym["passed"], "failures": sym["failures"]},
            reward=reward_result,
            summary=f"{crit.verdict} — score {crit.score:.2f}",
        )

    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "critic": self.critic.enabled,
            "symbolic": self.symbolic.enabled,
            "reward": self.reward.enabled,
            "stats": self.reward.get_statistics(),
        }

    def set_enabled(self, flag: bool):
        self.enabled = flag
        self.critic.enabled = flag
        self.symbolic.enabled = flag
        self.reward.enabled = flag


_engine = None


def get_deeper_engine(enabled: bool = True, memory=None) -> DeeperEngine:
    global _engine
    if _engine is None:
        _engine = DeeperEngine(enabled=enabled, memory=memory)
    elif memory is not None:
        _engine.reward.memory = memory
    _engine.enabled = enabled
    return _engine