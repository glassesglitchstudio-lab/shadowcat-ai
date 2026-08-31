"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   SHADOWCAT - FEEDBACK LOOP (Öğrenme Sistemi) ║
║                                                               ║
║   AI'ın etkileşimlerden öğrenmesini, hatalardan             ║
║   ders çıkarmasını ve kendini geliştirmesini sağlar.        ║
║                                                               ║
║   Özellikler:                                                 ║
║   - Etkileşim loglama (ne yapıldı, nasıl sonuçlandı)        ║
║   - Başarı/başarısızlık analizi                              ║
║   - Hata deseni tanıma (aynı hata tekrarlanıyor mu?)        ║
║   - Performans metrikleri (yanıt süresi, doğruluk)          ║
║   - Öğrenme önerileri (AI'ya geri bildirim)                 ║
║   - İstatistiksel raporlama                                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("GlassescatFeedback")

# ─────────────────────────────────────────────────────────────
# SABİTLER
# ─────────────────────────────────────────────────────────────

FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "feedback")
INTERACTIONS_FILE = "interactions.json"
ERROR_PATTERNS_FILE = "error_patterns.json"
PERFORMANCE_FILE = "performance.json"
LEARNING_FILE = "learning.json"

MAX_INTERACTIONS = 1000
PATTERN_MIN_OCCURRENCES = 3  # Bir desenin "öğrenildi" sayılması için min. tekrar


# ─────────────────────────────────────────────────────────────
# VERİ SINIFLARI
# ─────────────────────────────────────────────────────────────

@dataclass
class Interaction:
    """Bir AI etkileşim kaydı"""
    id: str
    user_input: str
    response: str
    tool_calls: List[Dict]
    success: bool
    duration: float
    error: Optional[str] = None
    user_feedback: Optional[str] = None  # positive, negative, neutral
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)


@dataclass
class ErrorPattern:
    """Tanınan bir hata deseni"""
    pattern: str
    description: str
    suggestion: str
    occurrences: int = 0
    last_seen: Optional[str] = None
    first_seen: Optional[str] = None
    auto_fixable: bool = False
    fix_command: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """Performans metrikleri"""
    total_interactions: int = 0
    successful: int = 0
    failed: int = 0
    avg_duration: float = 0.0
    total_tool_calls: int = 0
    avg_tools_per_interaction: float = 0.0
    top_used_tools: Dict = field(default_factory=dict)
    top_errors: Dict = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


# ─────────────────────────────────────────────────────────────
# FEEDBACK SYSTEM
# ─────────────────────────────────────────────────────────────

class FeedbackSystem:
    """
    Geri bildirim ve öğrenme sistemi.
    
    AI'nın her etkileşimden öğrenmesini sağlar.
    Hata desenlerini tanır, başarılı kalıpları pekiştirir.
    
    Kullanım:
        fb = FeedbackSystem()
        
        # Etkileşim kaydet
        fb.log_interaction(
            user_input="Merhaba",
            response="Merhaba! Size nasıl yardımcı olabilirim?",
            tool_calls=[],
            success=True,
            duration=1.5
        )
        
        # İstatistikler
        stats = fb.get_statistics()
        
        # Öğrenme önerileri
        tips = fb.get_learning_tips()
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # Dizin oluştur
        os.makedirs(FEEDBACK_DIR, exist_ok=True)
        
        # Veriler
        self.interactions: List[Interaction] = []
        self.error_patterns: List[ErrorPattern] = []
        self.performance = PerformanceMetrics()
        
        # Önceden tanımlı hata desenleri
        self._init_error_patterns()
        
        # Kayıtlı verileri yükle
        self._load_all()
        
        logger.info("Feedback System: başlatıldı")
    
    def _init_error_patterns(self):
        """Önceden tanımlı hata desenleri"""
        self.error_patterns = [
            ErrorPattern(
                pattern="ModuleNotFoundError|No module named",
                description="Eksik Python modülü",
                suggestion="Gerekli kütüphaneyi pip ile yükleyin",
                auto_fixable=True,
                fix_command="pip install {module}"
            ),
            ErrorPattern(
                pattern="ConnectionError|Connection refused|Timeout",
                description="Ağ bağlantı hatası",
                suggestion="İnternet bağlantısını kontrol edin veya tekrar deneyin",
                auto_fixable=False
            ),
            ErrorPattern(
                pattern="Permission denied|Access denied|EACCES",
                description="İzin reddi",
                suggestion="Yönetici olarak çalıştırmayı deneyin",
                auto_fixable=False
            ),
            ErrorPattern(
                pattern="FileNotFoundError|No such file",
                description="Dosya bulunamadı",
                suggestion="Dosya yolunu kontrol edin",
                auto_fixable=False
            ),
            ErrorPattern(
                pattern="JSONDecodeError|Expecting value",
                description="JSON ayrıştırma hatası",
                suggestion="JSON formatını kontrol edin",
                auto_fixable=False
            ),
            ErrorPattern(
                pattern="KeyError|IndexError",
                description="Eksik anahtar/dizin hatası",
                suggestion="Veri yapısını kontrol edin",
                auto_fixable=False
            ),
            ErrorPattern(
                pattern="SyntaxError|IndentationError",
                description="Python sözdizim hatası",
                suggestion="Kod yazımını kontrol edin",
                auto_fixable=False
            ),
            ErrorPattern(
                pattern="OSError|Errno 28",
                description="Disk alanı dolu",
                suggestion="Diskte yer açın",
                auto_fixable=False
            ),
            ErrorPattern(
                pattern="MemoryError|OutOfMemory",
                description="Bellek yetersiz",
                suggestion="Gereksiz işlemleri kapatın",
                auto_fixable=False
            ),
            ErrorPattern(
                pattern="401|Unauthorized",
                description="Yetkilendirme hatası",
                suggestion="API anahtarını veya giriş bilgilerini kontrol edin",
                auto_fixable=False
            ),
        ]
    
    def log_interaction(self, user_input: str, response: str, tool_calls: List[Dict],
                       success: bool, duration: float, error: str = None,
                       user_feedback: str = None) -> None:
        """
        Bir etkileşimi kaydet.
        
        Args:
            user_input: Kullanıcı girdisi
            response: AI yanıtı
            tool_calls: Kullanılan araçlar
            success: Başarılı mı?
            duration: Süre (saniye)
            error: Hata mesajı (varsa)
            user_feedback: Kullanıcı geri bildirimi (positive/negative/neutral)
        """
        import uuid
        
        interaction = Interaction(
            id=uuid.uuid4().hex[:12],
            user_input=user_input[:200],
            response=response[:200],
            tool_calls=tool_calls,
            success=success,
            duration=duration,
            error=error,
            user_feedback=user_feedback
        )
        
        with self._lock:
            self.interactions.append(interaction)
            
            # Limit kontrolü
            if len(self.interactions) > MAX_INTERACTIONS:
                self.interactions = self.interactions[-MAX_INTERACTIONS:]
            
            # Performans güncelle
            self._update_performance(interaction)
            
            # Hata deseni analizi
            if error:
                self._analyze_error(error)
            
            # Periyodik kaydet
            if len(self.interactions) % 10 == 0:
                self._save_all()
    
    def _update_performance(self, interaction: Interaction):
        """Performans metriklerini güncelle"""
        p = self.performance
        p.total_interactions += 1
        
        if interaction.success:
            p.successful += 1
        else:
            p.failed += 1
        
        # Ortalama süre (kayan ortalama)
        if p.avg_duration == 0:
            p.avg_duration = interaction.duration
        else:
            p.avg_duration = (p.avg_duration * 0.9) + (interaction.duration * 0.1)
        
        # Tool çağrıları
        for tc in interaction.tool_calls:
            p.total_tool_calls += 1
            tool_name = tc.get("tool", "unknown")
            p.top_used_tools[tool_name] = p.top_used_tools.get(tool_name, 0) + 1
        
        if p.total_tool_calls > 0:
            p.avg_tools_per_interaction = p.total_tool_calls / max(p.total_interactions, 1)
        
        # Hata sayıları
        if interaction.error:
            error_key = interaction.error[:50]
            p.top_errors[error_key] = p.top_errors.get(error_key, 0) + 1
        
        p.last_updated = datetime.now().isoformat()
    
    def _analyze_error(self, error_message: str):
        """Hata mesajını desenlerle eşleştir"""
        import re
        
        for pattern in self.error_patterns:
            if re.search(pattern.pattern, error_message, re.IGNORECASE):
                pattern.occurrences += 1
                pattern.last_seen = datetime.now().isoformat()
                if pattern.first_seen is None:
                    pattern.first_seen = datetime.now().isoformat()
                
                # Modül adını çıkar (auto-fix için)
                if pattern.auto_fixable and pattern.fix_command:
                    module_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_message)
                    if module_match:
                        pattern.fix_command = f"pip install {module_match.group(1)}"
                
                break
    
    def get_error_suggestion(self, error_message: str) -> Optional[Dict]:
        """Hata için çözüm önerisi getir"""
        import re
        
        for pattern in self.error_patterns:
            if re.search(pattern.pattern, error_message, re.IGNORECASE):
                return {
                    "pattern": pattern.pattern,
                    "description": pattern.description,
                    "suggestion": pattern.suggestion,
                    "auto_fixable": pattern.auto_fixable,
                    "fix_command": pattern.fix_command,
                    "occurrences": pattern.occurrences
                }
        
        return None
    
    def get_learning_tips(self) -> List[Dict]:
        """Öğrenme önerileri üret"""
        tips = []
        
        with self._lock:
            p = self.performance
            
            # 1. Başarı oranı düşükse
            if p.total_interactions > 10:
                success_rate = (p.successful / p.total_interactions) * 100
                if success_rate < 70:
                    tips.append({
                        "type": "warning",
                        "message": f"Başarı oranı düşük: %{success_rate:.0f}. Hata desenlerini kontrol edin.",
                        "category": "performance"
                    })
            
            # 2. Sık kullanılan araçlar
            if p.top_used_tools:
                most_used = max(p.top_used_tools, key=p.top_used_tools.get)
                tips.append({
                    "type": "info",
                    "message": f"En çok kullanılan araç: '{most_used}' ({p.top_used_tools[most_used]} kez)",
                    "category": "tools"
                })
            
            # 3. Sık tekrarlanan hatalar
            for pattern in self.error_patterns:
                if pattern.occurrences >= PATTERN_MIN_OCCURRENCES:
                    tips.append({
                        "type": "error_pattern",
                        "message": f"Sık hata: '{pattern.description}' ({pattern.occurrences} kez)",
                        "suggestion": pattern.suggestion,
                        "category": "errors"
                    })
            
            # 4. Kullanıcı geri bildirimleri
            negative_count = sum(1 for i in self.interactions[-50:] 
                               if i.user_feedback == "negative")
            if negative_count > 5:
                tips.append({
                    "type": "warning",
                    "message": f"Son 50 etkileşimde {negative_count} olumsuz geri bildirim",
                    "category": "feedback"
                })
        
        return tips
    
    def get_statistics(self) -> Dict:
        """İstatistiksel rapor"""
        with self._lock:
            p = self.performance
            
            if p.total_interactions == 0:
                return {"status": "Henüz veri yok"}
            
            success_rate = (p.successful / p.total_interactions) * 100
            
            # Son 24 saat
            recent = [
                i for i in self.interactions[-100:]
                if datetime.fromisoformat(i.timestamp) > datetime.now() - timedelta(hours=24)
            ]
            recent_success = sum(1 for i in recent if i.success)
            recent_rate = (recent_success / max(len(recent), 1)) * 100
            
            # En çok kullanılan araçlar (sıralı)
            sorted_tools = sorted(
                p.top_used_tools.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            # Sık hatalar
            sorted_errors = sorted(
                p.top_errors.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            # Hata desenleri (öğrenilenler)
            learned_patterns = [
                asdict(pat) for pat in self.error_patterns
                if pat.occurrences >= PATTERN_MIN_OCCURRENCES
            ]
            
            return {
                "total_interactions": p.total_interactions,
                "successful": p.successful,
                "failed": p.failed,
                "success_rate": f"%{success_rate:.1f}",
                "recent_24h_success_rate": f"%{recent_rate:.1f}",
                "avg_duration": f"{p.avg_duration:.2f}s",
                "total_tool_calls": p.total_tool_calls,
                "avg_tools_per_interaction": f"{p.avg_tools_per_interaction:.1f}",
                "top_tools": dict(sorted_tools),
                "top_errors": dict(sorted_errors),
                "learned_patterns": learned_patterns,
                "last_updated": p.last_updated
            }
    
    def record_user_feedback(self, interaction_id: str, feedback: str) -> bool:
        """Kullanıcı geri bildirimini kaydet"""
        with self._lock:
            for interaction in reversed(self.interactions):
                if interaction.id == interaction_id:
                    interaction.user_feedback = feedback
                    self._save_all()
                    return True
            
            # ID bulunamazsa son etkileşime ekle
            if self.interactions:
                self.interactions[-1].user_feedback = feedback
                self._save_all()
                return True
        
        return False
    
    def get_recent_interactions(self, limit: int = 20) -> List[Dict]:
        """Son etkileşimleri getir"""
        with self._lock:
            return [asdict(i) for i in self.interactions[-limit:]]
    
    # ── Veri Saklama ──
    
    def _save_all(self):
        """Tüm verileri kaydet"""
        self._save_json(INTERACTIONS_FILE, [asdict(i) for i in self.interactions[-500:]])
        self._save_json(ERROR_PATTERNS_FILE, [asdict(p) for p in self.error_patterns])
        self._save_json(PERFORMANCE_FILE, asdict(self.performance))
    
    def _load_all(self):
        """Tüm verileri yükle"""
        interactions_data = self._load_json(INTERACTIONS_FILE) or []
        self.interactions = [Interaction(**d) for d in interactions_data]
        
        patterns_data = self._load_json(ERROR_PATTERNS_FILE)
        if patterns_data:
            self.error_patterns = [ErrorPattern(**d) for d in patterns_data]
        
        perf_data = self._load_json(PERFORMANCE_FILE)
        if perf_data:
            self.performance = PerformanceMetrics(**perf_data)
    
    def _save_json(self, filename: str, data: Any) -> bool:
        """JSON dosyasına kaydet"""
        filepath = os.path.join(FEEDBACK_DIR, filename)
        with self._lock:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                logger.error(f"Feedback kaydetme hatası ({filename}): {e}")
                return False
    
    def _load_json(self, filename: str) -> Optional[Any]:
        """JSON dosyasından oku"""
        filepath = os.path.join(FEEDBACK_DIR, filename)
        with self._lock:
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
            except Exception as e:
                logger.warning(f"Feedback okuma hatası ({filename}): {e}")
        return None
    
    def reset(self):
        """Tüm verileri sıfırla"""
        with self._lock:
            self.interactions = []
            self.performance = PerformanceMetrics()
            self._init_error_patterns()
            self._save_all()
        logger.info("Feedback System sıfırlandı")


# ─────────────────────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────────────────────

_feedback_instance = None

def get_feedback_system() -> FeedbackSystem:
    """FeedbackSystem singleton instance'ını al"""
    global _feedback_instance
    if _feedback_instance is None:
        _feedback_instance = FeedbackSystem()
    return _feedback_instance


if __name__ == "__main__":
    fb = get_feedback_system()
    
    # Test
    print("=" * 50)
    print("  Shadowcat AI - Feedback Loop Test")
    print("=" * 50)
    
    # Etkileşim ekle
    for i in range(5):
        fb.log_interaction(
            user_input=f"Test {i}",
            response=f"Yanıt {i}",
            tool_calls=[{"tool": "test_tool", "success": True}],
            success=i % 2 == 0,
            duration=1.0 + i * 0.5,
            error="ModuleNotFoundError: No module named 'pygame'" if i == 2 else None
        )
    
    # İstatistikler
    stats = fb.get_statistics()
    print(f"\nİstatistikler:")
    print(f"   Toplam: {stats['total_interactions']}")
    print(f"   Başarı: %{stats['success_rate']}")
    print(f"   Ortalama süre: {stats['avg_duration']}")
    
    # Öğrenme önerileri
    tips = fb.get_learning_tips()
    print(f"\nÖğrenme önerileri ({len(tips)}):")
    for tip in tips[:3]:
        print(f"   [{tip['category']}] {tip['message'][:80]}")
    
    # Hata önerisi
    suggestion = fb.get_error_suggestion("ModuleNotFoundError: No module named 'pygame'")
    if suggestion:
        print(f"\nHata önerisi: {suggestion['suggestion']}")
        if suggestion['auto_fixable']:
            print(f"   Otomatik düzeltme: {suggestion['fix_command']}")
    
    print("\nFeedback Loop test tamamlandı!")
