"""
Shadowcat - Vision Module (LLaVA ile Resim Analizi)
Görüntü analizi, screenshot, fotoğraf inceleme
"""

import base64
import os
import io
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# LLaVA modeli
LLAVA_MODEL = "llava:latest"
OLLAMA_URL = "http://localhost:11434/api/chat"


class VisionAnalyzer:
    """
    LLaVA tabanlı görüntü analiz sistemi.
    Screenshot, fotoğraf ve belge analizi.
    """
    
    def __init__(self, ollama_url: str = None):
        self.ollama_url = ollama_url or OLLAMA_URL
        self.model = LLAVA_MODEL
        self.history = []  # Analiz geçmişi
        self.max_history = 50
    
    def _image_to_base64(self, image_source) -> str:
        """Görüntüyü base64'e çevir."""
        if isinstance(image_source, str):
            # Dosya yolu
            if os.path.exists(image_source):
                with open(image_source, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            # Base64 zaten
            elif self._is_base64(image_source):
                return image_source
            # URL
            elif image_source.startswith("http"):
                response = requests.get(image_source)
                return base64.b64encode(response.content).decode("utf-8")
        elif PIL_AVAILABLE and hasattr(image_source, "save"):
            # PIL Image
            buffer = io.BytesIO()
            image_source.save(buffer, format="JPEG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        raise ValueError(f"Geçersiz görüntü kaynağı: {type(image_source)}")
    
    def _is_base64(self, s: str) -> bool:
        """String'in base64 olup olmadığını kontrol et."""
        try:
            return len(s) > 100 and all(c in base64.ascii_letters + base64.digits + "+/=" for c in s)
        except:
            return False
    
    def analyze(
        self,
        image_source,
        question: str = "Bu görüntüyü detaylı olarak Türkçe açıkla.",
        save_to_history: bool = True
    ) -> Dict[str, Any]:
        """
        Görüntüyü analiz et.
        
        Args:
            image_source: Görüntü dosya yolu, base64 veya URL
            question: Analiz sorusu
            save_to_history: Geçmişe kaydet
            
        Returns:
            Dict: Analiz sonucu
        """
        try:
            # Görüntüyü base64'e çevir
            image_data = self._image_to_base64(image_source)
            
            # LLaVA'ya gönder
            messages = [
                {
                    "role": "system",
                    "content": "Sen Shadowcat VİZYON asistanısın. Türkçe konuş. Detaylı ve açık analiz yap."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        }
                    ]
                }
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.0}
            }
            
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                analysis = result["message"]["content"]
                
                if save_to_history:
                    self.history.append({
                        "timestamp": self._get_timestamp(),
                        "question": question,
                        "analysis": analysis,
                        "success": True
                    })
                    
                    if len(self.history) > self.max_history:
                        self.history = self.history[-self.max_history:]
                
                return {
                    "success": True,
                    "response": analysis,
                    "model": self.model,
                    "question": question
                }
            else:
                return {
                    "success": False,
                    "error": f"LLaVA hatası: {response.status_code}"
                }
        
        except Exception as e:
            logger.error(f"Görüntü analiz hatası: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def analyze_screenshot(
        self,
        screenshot_path: str = None,
        question: str = None
    ) -> Dict[str, Any]:
        """
        Screenshot analizi.
        Soru belirtilmemişse genel analiz yap.
        """
        if question is None:
            question = (
                "Bu ekran görüntüsünü detaylı olarak analiz et. "
                "Şunları belirt:\n"
                "1. Ekran görüntüsünde ne var?\n"
                "2. Hangi uygulama veya web sitesi?\n"
                "3. Önemli bilgiler veya veriler neler?\n"
                "4. Potansiyel sorunlar veya hatalar var mı?"
            )
        
        if screenshot_path is None:
            # Ekran görüntüsü al
            try:
                import pyautogui
                screenshot = pyautogui.screenshot()
                return self.analyze(screenshot, question)
            except:
                return {
                    "success": False,
                    "error": "Screenshot alınamadı veya yol belirtilmedi"
                }
        
        return self.analyze(screenshot_path, question)
    
    def ocr_text(
        self,
        image_source,
        language: str = "tr"
    ) -> Dict[str, Any]:
        """
        OCR - Görüntüden metin çıkarma.
        """
        prompt = (
            f"Görüntüdeki tüm metinleri Türkçe olarak çıkar. "
            f"Sadece metinleri listele, açıklama ekleme. "
            f"Metin bulunamazsa 'Metin bulunamadı' de."
        )
        return self.analyze(image_source, prompt)
    
    def analyze_code_screenshot(
        self,
        image_source
    ) -> Dict[str, Any]:
        """
        Kod ekran görüntüsü analizi.
        Koddaki hataları ve sorunları bul.
        """
        prompt = (
            "Bu ekran görüntüsünde kod var. Lütfen:\n"
            "1. Hangi programlama dili?\n"
            "2. Kodda hata var mı?\n"
            "3. Hata varsa düzeltme önerisi ver.\n"
            "4. Kod açıklaması yap."
        )
        return self.analyze(image_source, prompt)
    
    def analyze_error(
        self,
        image_source
    ) -> Dict[str, Any]:
        """
        Hata ekranı analizi.
        Error mesajlarını çözümle.
        """
        prompt = (
            "Bu ekran görüntüsünde bir hata mesajı var. Lütfen:\n"
            "1. Hata türünü belirle.\n"
            "2. Hata mesajını metin olarak çıkar.\n"
            "3. Muhtemel nedenleri açıkla.\n"
            "4. Çözüm önerisi ver.\n"
            "5. Adım adım çözüm yolu göster."
        )
        return self.analyze(image_source, prompt)
    
    def describe_image(
        self,
        image_source
    ) -> Dict[str, Any]:
        """
        Görüntüyü basitçe açıkla.
        """
        prompt = (
            "Bu görüntüyü kısaca Türkçe olarak açıkla. "
            "Ne gösteriyor? Ana öğeler neler?"
        )
        return self.analyze(image_source, prompt)
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """Analiz geçmişini getir."""
        return self.history[-limit:]
    
    def clear_history(self):
        """Analiz geçmişini temizle."""
        self.history = []
    
    def _get_timestamp(self) -> str:
        """Zaman damgası."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Global instance
_vision_analyzer = None

def get_vision_analyzer() -> VisionAnalyzer:
    """Global vision analyzer instance."""
    global _vision_analyzer
    if _vision_analyzer is None:
        _vision_analyzer = VisionAnalyzer()
    return _vision_analyzer


# ═══════════════════════════════════════════════════════════════════
# BASIT FONKSIYONLAR - Geriye dönük uyumluluk
# ═══════════════════════════════════════════════════════════════════

def analyze_image(image_path: str, question: str = None) -> Dict[str, Any]:
    """Basit görüntü analizi."""
    analyzer = get_vision_analyzer()
    if question:
        return analyzer.analyze(image_path, question)
    return analyzer.analyze(image_path)


def analyze_screenshot(screenshot_path: str = None) -> Dict[str, Any]:
    """Basit screenshot analizi."""
    analyzer = get_vision_analyzer()
    return analyzer.analyze_screenshot(screenshot_path)


def ocr_from_image(image_path: str) -> str:
    """Görüntüden metin çıkar."""
    analyzer = get_vision_analyzer()
    result = analyzer.ocr_text(image_path)
    if result["success"]:
        return result["response"]
    return f"Hata: {result.get('error', 'Bilinmeyen hata')}"


def get_vision_status() -> Dict[str, Any]:
    """Vision modülü durumu."""
    analyzer = get_vision_analyzer()
    return {
        "model": analyzer.model,
        "ollama_url": analyzer.ollama_url,
        "history_count": len(analyzer.history),
        "status": "ready"
    }
