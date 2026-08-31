"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   SHADOWCAT - TASK PLANNER (Çok Adımlı Planlama) ║
║                                                               ║
║   Karmaşık görevleri alt adımlara böler ve sırayla yürütür   ║
║                                                               ║
║   Özellikler:                                                 ║
║   - Görevi analiz et ve adımlara böl                         ║
║   - Adımlar arası bağımlılıkları yönet                       ║
║   - Her adımı Agent Loop ile yürüt                           ║
║   - Hata durumunda alternatif yol dene                       ║
║   - İlerleme raporu üret                                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger("GlassescatTaskPlanner")

# ─────────────────────────────────────────────────────────────
# VERİ SINIFLARI
# ─────────────────────────────────────────────────────────────

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class TaskStep:
    """Bir görev adımı"""
    id: str
    description: str
    status: StepStatus = StepStatus.PENDING
    depends_on: List[str] = field(default_factory=list)
    result: Optional[Dict] = None
    error: Optional[str] = None
    duration: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class TaskPlan:
    """Bir görev planı"""
    id: str
    description: str
    steps: List[TaskStep] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None

# ─────────────────────────────────────────────────────────────
# GÖREV ŞABLONLARI (önceden tanımlı planlar)
# ─────────────────────────────────────────────────────────────

TASK_TEMPLATES = {
    "web_arastirma": {
        "name": "Web Araştırması",
        "steps": [
            "Arama sorgusunu analiz et",
            "Web'de ara",
            "Sonuçları özetle",
            "Kullanıcıya raporla"
        ]
    },
    "uygulama_ac": {
        "name": "Uygulama Açma",
        "steps": [
            "Uygulama adını belirle",
            "Uygulamayı bul ve çalıştır",
            "Sonucu bildir"
        ]
    },
    "dosya_islem": {
        "name": "Dosya İşlemi",
        "steps": [
            "Dosya yolunu belirle",
            "Dosyayı oku/yaz",
            "İçeriği işle",
            "Sonucu bildir"
        ]
    },
    "sistem_kontrol": {
        "name": "Sistem Kontrolü",
        "steps": [
            "Sistem bilgilerini topla",
            "Kaynak kullanımını analiz et",
            "Varsa uyarıları bildir",
            "Sağlık raporu oluştur"
        ]
    },
    "hata_coz": {
        "name": "Hata Çözümü",
        "steps": [
            "Hatayı analiz et",
            "Çözüm önerisi hazırla",
            "Otomatik düzeltme dene",
            "Sonucu bildir"
        ]
    }
}


# ─────────────────────────────────────────────────────────────
# TASK PLANNER
# ─────────────────────────────────────────────────────────────

class TaskPlanner:
    """
    Çok adımlı görev planlayıcı ve yürütücü.
    
    Karmaşık görevleri alır, adımlara böler ve sırayla çalıştırır.
    Her adımda Agent Loop'u kullanır.
    
    Kullanım:
        planner = TaskPlanner(core=glassescat_core)
        result = planner.execute_task(
            "Chrome'u aç, YouTube'a gir, Mavislime ara"
        )
    """
    
    def __init__(self, core=None):
        self.core = core
        self.plans: List[TaskPlan] = []
        self.max_plans = 20
    
    def execute_task(self, task_description: str) -> Dict:
        """
        Bir görevi planla ve yürüt.

        Args:
            task_description: Yapılacak görev
        
        Returns:
            Dict: {
                "success": bool,
                "plan": {...},
                "results": [...],
                "summary": str
            }
        """
        import uuid
        
        # Plan oluştur
        plan_id = uuid.uuid4().hex[:8]
        plan = TaskPlan(
            id=plan_id,
            description=task_description,
            status="running"
        )
        
        logger.info(f"Plan oluşturuluyor: '{task_description[:50]}...'")
        
        # Adımları oluştur
        steps = self._decompose_task(task_description)
        
        for i, step_desc in enumerate(steps):
            step = TaskStep(
                id=f"step_{i+1}",
                description=step_desc,
                depends_on=[f"step_{j+1}" for j in range(i)]  # önceki adımlara bağımlı
            )
            plan.steps.append(step)
        
        # Adımları yürüt
        results = []
        all_success = True
        
        for step in plan.steps:
            step.status = StepStatus.RUNNING
            start_time = time.time()
            
            logger.info(f"  Adım {step.id}: {step.description[:50]}...")
            
            try:
                # Agent Loop ile bu adımı çalıştır
                if self.core:
                    result = self.core.process_message(step.description)
                    step.result = result
                    step.status = StepStatus.COMPLETED
                    results.append({
                        "step": step.id,
                        "description": step.description,
                        "success": True,
                        "response": result.get("response", "")[:200]
                    })
                else:
                    step.result = {"response": f"Adım simüle ediliyor: {step.description}"}
                    step.status = StepStatus.COMPLETED
                    results.append({
                        "step": step.id,
                        "description": step.description,
                        "success": True
                    })
            
            except Exception as e:
                logger.error(f"  Adım {step.id} başarısız: {e}")
                step.status = StepStatus.FAILED
                step.error = str(e)
                all_success = False
                results.append({
                    "step": step.id,
                    "description": step.description,
                    "success": False,
                    "error": str(e)
                })
                
                # Kritik hata mı?
                if self._is_critical_error(str(e)):
                    break
            
            step.duration = time.time() - start_time
        
        # Planı tamamla
        plan.status = "completed" if all_success else "failed"
        plan.completed_at = datetime.now().isoformat()
        
        # Planı geçmişe ekle
        self.plans.append(plan)
        if len(self.plans) > self.max_plans:
            self.plans.pop(0)
        
        # Özet oluştur
        summary = self._generate_summary(plan, results)
        
        logger.info(f"Plan tamamlandı: {'Başarılı' if all_success else 'Başarısız'} ({len(results)} adım)")
        
        return {
            "success": all_success,
            "plan": asdict(plan),
            "results": results,
            "summary": summary
        }
    
    def _decompose_task(self, task: str) -> List[str]:
        """Görevi adımlara böl"""
        task_lower = task.lower()
        
        # Şablon eşleştirme
        if "ara" in task_lower and ("web" in task_lower or "youtube" in task_lower or "google" in task_lower):
            return TASK_TEMPLATES["web_arastirma"]["steps"]
        
        if "ac" in task_lower or "başlat" in task_lower or task_lower.startswith(("ac", "aç")):
            return TASK_TEMPLATES["uygulama_ac"]["steps"]
        
        if "dosya" in task_lower or "oku" in task_lower or "yaz" in task_lower or "kaydet" in task_lower:
            return TASK_TEMPLATES["dosya_islem"]["steps"]
        
        if "sistem" in task_lower or "cpu" in task_lower or "ram" in task_lower or "durum" in task_lower:
            return TASK_TEMPLATES["sistem_kontrol"]["steps"]
        
        if "hata" in task_lower or "düzelt" in task_lower or "fix" in task_lower or "sorun" in task_lower:
            return TASK_TEMPLATES["hata_coz"]["steps"]
        
        # Genel: doğal dil bölümleme
        return self._natural_decompose(task)
    
    def _natural_decompose(self, task: str) -> List[str]:
        """Doğal dil görevini mantıksal adımlara böl"""
        steps = []
        
        # "ve" ile ayrılmış görevler
        if " ve " in task:
            parts = task.split(" ve ")
            for i, part in enumerate(parts):
                steps.append(f"Adım {i+1}: {part.strip()}")
        
        # Virgülle ayrılmış görevler
        elif "," in task:
            parts = task.split(",")
            for i, part in enumerate(parts):
                part = part.strip()
                if part:
                    steps.append(f"Adım {i+1}: {part}")
        
        # Tek görev
        else:
            steps = [
                f"Görevi analiz et: {task}",
                "Gerekli araçları belirle",
                "İşlemi gerçekleştir",
                "Sonucu kullanıcıya bildir"
            ]
        
        return steps
    
    def _is_critical_error(self, error: str) -> bool:
        """Kritik hata kontrolü (planı durdur)"""
        critical = [
            "modül bulunamadı",
            "izin reddedildi",
            "bağlantı hatası",
            "zaman aşımı"
        ]
        error_lower = error.lower()
        return any(c in error_lower for c in critical)
    
    def _generate_summary(self, plan: TaskPlan, results: List[Dict]) -> str:
        """Görev özeti oluştur"""
        completed = sum(1 for r in results if r.get("success"))
        failed = sum(1 for r in results if not r.get("success"))
        total_duration = sum(s.duration for s in plan.steps)
        
        summary = (
            f"Görev: {plan.description[:50]}...\n"
            f"   Adımlar: {len(results)} tamamlandı ({completed} başarılı, {failed} başarısız)\n"
            f"   Süre: {total_duration:.1f}s\n"
        )
        
        if failed > 0:
            failed_steps = [r for r in results if not r.get("success")]
            summary += "   Hatalı adımlar:\n"
            for fs in failed_steps[:3]:
                summary += f"     {fs.get('description', '?')}: {fs.get('error', '?')}\n"
        
        return summary
    
    def get_plan_history(self, limit: int = 5) -> List[Dict]:
        """Plan geçmişini getir"""
        return [asdict(p) for p in self.plans[-limit:]]
    
    def cancel_plan(self, plan_id: str) -> bool:
        """Bir planı iptal et"""
        for plan in self.plans:
            if plan.id == plan_id:
                plan.status = "cancelled"
                for step in plan.steps:
                    if step.status == StepStatus.PENDING:
                        step.status = StepStatus.SKIPPED
                return True
        return False


# ─────────────────────────────────────────────────────────────
# SINGLETON
# ─────────────────────────────────────────────────────────────

_task_planner_instance = None

def get_task_planner(core=None) -> TaskPlanner:
    """TaskPlanner singleton instance'ını al"""
    global _task_planner_instance
    if _task_planner_instance is None or core:
        _task_planner_instance = TaskPlanner(core=core)
    return _task_planner_instance


if __name__ == "__main__":
    planner = TaskPlanner()
    result = planner.execute_task("Chrome'u aç ve YouTube'a gir")
    print(result["summary"])
