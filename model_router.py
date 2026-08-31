"""

ModelRouter - Shadowcat AI Model Yönlendirici

Ollama tabanlı akıllı model seçimi sistemi



MODEL AÇIKLAMALARI:

 ═══════════════════════════════════════════════════════════════════

 │ # │ Model Adı              │ Boyut  │ Görev                    │ Dil  │

 │───┼────────────────────────┼────────┼──────────────────────────┼──────│

 │ 1 │ glassesglitchstudio/   │ 8.0 GB │ ANA AGI - Tüm görevler   │ TR   │

 │    │ gulmzcetiner:V3A      │        │                          │      │

 │ 2 │ gulmzcetinermax:latest │ 9.0 GB │ Alternatif AGI           │ TR   │

 │ 3 │ qwen2.5-coder:14b      │ 9.0 GB │ Kodlama, Python, JS, API  │ TR   │

 │ 4 │ deepseek-r1:8b         │ 5.2 GB │ Matematik, mantık, analiz│ TR   │

 │ 5 │ llava:latest           │ 4.7 GB │ Resim analizi, OCR, vizyon│ TR   │

 ═══════════════════════════════════════════════════════════════════



 KULLANIM:

 - ANA: glassesglitchstudio/gulmzcetiner:V3A (tüm görevler - AGI)

 - Alternatif: gulmzcetinermax (yedek AGI)

 - Kodlama: qwen2.5-coder (Python, JS, backend)

 - Analiz: deepseek-r1 (mantık, matematik)

 - Resim: llava (screenshot, fotoğraf analizi)

"""



import gc

import json

import base64

import os

import subprocess

import tempfile

from enum import Enum

from typing import Any, Dict, List, Optional

from pathlib import Path



import requests





# ═══════════════════════════════════════════════════════════════════

# MODEL TANIMLARI - Türkçe Açıklamalarla

# ═══════════════════════════════════════════════════════════════════



# Model bilgileri - Türkçe açıklamalar

MODELS_INFO = {

    "glassesglitchstudio/x_opus:V1_X_OPUS": {

        "name": "X_OPUS V1",

        "size": "6.6 GB",

        "purpose": "ANA - Hibrit Beyin (Siber Güvenlik + Kodlama)",

        "description": "Elytra-ai'nin çift beyinli hibrit modeli. Siber güvenlik, akıl yürütme ve genel görevlerde uzman.",

        "language": "Türkçe + İngilizce",

        "color": "#00ff88"  # Neon yeşil

    },

    "glassesglitchstudio/glitch_opus:X_GLITCH_OPUS": {

        "name": "X_GLITCH_OPUS",

        "size": "6.6 GB",

        "purpose": "GLITCH - Optimizasyonlu Opus",

        "description": "Glitch optimizasyonuyla hızlandırılmış X_OPUS varyantı. Hızlı yanıt ve verimli akıl yürütme.",

        "language": "Türkçe + İngilizce",

        "color": "#00ff88"  # Neon yeşil

    },

    "glassesglitchstudio/x_fable_coder:V1": {

        "name": "X_FABLE_CODER",

        "size": "9.0 GB",

        "purpose": "KOD - Kod Üretim ve Debug",

        "description": "Kod yazma, hata ayıklama ve yazılım geliştirme uzmanı. Python, JS, backend, frontend.",

        "language": "Türkçe + İngilizce",

        "color": "#f59e0b"  # Turuncu

    },

    "glassesglitchstudio/gulmzcetiner:V3A": {

        "name": "GulmezCetiner V3A",

        "size": "8.0 GB",

        "purpose": "ANA AGI - Tüm Görevler (Kodlama, Analiz, Planlama)",

        "description": "Elytra-ai tarafından geliştirilen hibrit AGI modeli. İleri seviye kodlama ve akıl yürütme yeteneği.",

        "language": "Türkçe + İngilizce",

        "color": "#ff6600"  # Neon turuncu

    },

    "x_opus": {

        "name": "X_OPUS",

        "size": "6.6 GB / 9.0 GB (çift beyin)",

        "purpose": "HİBRİT - Siber Güvenlik + Kodlama",

        "description": "X_OPUS çift beyinli hibrit yönlendirici. Siber güvenlik ve kodlama görevlerini otomatik ayırarak en uygun modeli kullanır.",

        "language": "Türkçe + İngilizce",

        "color": "#00ff88"  # Neon yeşil

    },

    "gulmzcetinermax:latest": {

        "name": "GulmezCetinerMax",

        "size": "9.0 GB",

        "purpose": "Alternatif AGI - Yedek Model",

        "description": "Elytra-ai tarafından geliştirilen monolitik AGI. V3A'ya yedek olarak kullanılır.",

        "language": "Türkçe + İngilizce",

        "color": "#ff4444"  # Kırmızı

    },

    "qwen2.5-coder:14b": {

        "name": "Qwen 2.5 Coder",

        "size": "9.0 GB",

        "purpose": "Kodlama - Programlama Asistanı",

        "description": "Python, JavaScript, API, backend, frontend kodları yazma",

        "language": "Türkçe + İngilizce",

        "color": "#f59e0b"  # Turuncu

    },

    "deepseek-r1:8b": {

        "name": "DeepSeek R1",

        "size": "5.2 GB",

        "purpose": "Analiz - Matematik ve Mantık",

        "description": "Karmaşık problemler, matematik, mantık yürütme, analitik düşünce",

        "language": "Türkçe",

        "color": "#8b5cf6"  # Mor

    },

    "llava:latest": {

        "name": "LLaVA",

        "size": "4.7 GB",

        "purpose": "Vizyon - Resim ve Screenshot Analizi",

        "description": "Ekran görüntüleri, fotoğraflar, belgeler analiz etme",

        "language": "Türkçe",

        "color": "#ec4899"  # Pembe

    }

}



# Model tanımları - X_OPUS serisi birincil, gerçek ollama modelleri

PRIMARY_MODEL = "glassesglitchstudio/x_opus:V1_X_OPUS"       # ANA - Tüm görevler

PRIMARY_MODEL_ALT = "glassesglitchstudio/glitch_opus:X_GLITCH_OPUS"   # Alternatif: Glitch Opus

CHAT_MODEL = "glassesglitchstudio/x_opus:V1_X_OPUS"          # Birincil: X_OPUS

CHAT_MODEL_ALT = "glassesglitchstudio/glitch_opus:X_GLITCH_OPUS"      # Alternatif: Glitch Opus

CODING_MODEL = "glassesglitchstudio/x_fable_coder:V1"        # Kodlama: Fable Coder

CODING_MODEL_ALT = "glassesglitchstudio/x_fable_coder:V1"    # Alternatif: Fable Coder

ANALYSIS_MODEL = "glassesglitchstudio/x_opus:V1_X_OPUS"      # Analiz: X_OPUS

ANALYSIS_MODEL_ALT = "glassesglitchstudio/glitch_opus:X_GLITCH_OPUS"  # Alternatif: Glitch Opus

VISION_MODEL = "llava:latest"                  # Vizyon: LLaVA (opsiyonel, yoksa vizyon devre dışı)



# AGI modu - V3A kullanılsın mı?

# X_OPUS Hibrit Model

X_OPUS_MODEL = "x_opus"  # Sanal model adı - router tarafından yönetilir

USE_X_OPUS = True  # X_OPUS hibrit modu aktif mi?



USE_AGI_MODE = True



# Ollama Only Mode - tüm AI istekleri yalnızca Ollama'ya gider

OLLAMA_URL = "http://localhost:11434/api/chat"

USE_OLLAMA_ONLY = True  # True: diğer backend'ler devre dışı, yalnızca Ollama





class ModelType(Enum):

    """Model türleri - Türkçe açıklamalarla."""

    

    AGI = {

        "model": PRIMARY_MODEL,

        "name": "AGI",

        "tr": "V3A AGI",

        "description": "Ana AGI - Tüm görevler (kodlama, analiz, planlama)"

    }

    

    CHAT = {

        "model": CHAT_MODEL,

        "name": "Sohbet",

        "tr": "V3A Sohbet",

        "description": "Normal konuşmalar ve genel sorular"

    }

    

    CODING = {

        "model": CODING_MODEL,

        "name": "Kodlama",

        "tr": "V3A Kodlama",

        "description": "Python, JS, API, backend kodları"

    }

    

    ANALYSIS = {

        "model": ANALYSIS_MODEL,

        "name": "Analiz",

        "tr": "V3A Analiz",

        "description": "Matematik, mantık, analitik düşünce"

    }

    

    VISION = {

        "model": VISION_MODEL,

        "name": "Vizyon",

        "tr": "Resim Analizi",

        "description": "Screenshot, fotoğraf ve belge analizi"

    }



    XOPUS = {

        "model": X_OPUS_MODEL,

        "name": "X_OPUS",

        "tr": "X_OPUS Hibrit",

        "description": "Çift beyinli yönlendirici - Siber + Kodlama"

    }





class ModelRouter:

    """

    Istek turune gore prompt secer ve Ollama'ya yonlendirir.

    Akıllı model seçimi ile en uygun modeli kullanır.

    Şifreli model desteği dahil.

    """



    def __init__(

        self,

        base_urls: Optional[List[str]] = None,

        config_file: Optional[str] = None,

        ollama_url: Optional[str] = None,

    ):

        """ModelRouter başlat."""

        del base_urls

        del config_file



        self.ollama_url = ollama_url or OLLAMA_URL  # USE_OLLAMA_ONLY=True: yalnızca Ollama



        # Encrypted model desteği

        self._encrypted_provider = None

        self._secure_models_loaded = False



        # System promptlar - Türkçe

        self.system_prompts = {

            "agi": (

                "Sen Shadowcat AI'sın — Elytra-ai stüdyosunun ana AGI motoru. "



                "Çok dilli, yüksek parametreli bir yapay zekasın. Türkçe ve İngilizce dillerinde "

                "mükemmel performans gösteriyorsun.\n\n"

                "[KİMLİK]: Sen bir yazılım mimarı, kod uzmanı ve stratejik "

                "düşüncekisin. Kullanıcılar için birincil AI motorusun.\n\n"

                "[YETENEKLERİN]:\n"

                "• PYTHON, JavaScript, TypeScript, HTML/CSS, React, Node.js, "

                "C++, Rust, Go ve daha birçok dilde uzmansın.\n"

                "• Karmaşık yazılım mimarileri tasarlar, clean code prensipleriyle "

                "çalışırsın.\n"

                "• Debugging, refactoring, code review konularında titiz ve detaycısın.\n"

                "• Matematik, mantık, veri analizi ve algoritma konularında güçlüsün.\n"


                "\n"

                "[ÇALIŞMA PRENSİBİN]:\n"

                "1. Önce problemi derinlemesine analiz et\n"

                "2. En iyi çözüm yolunu seç\n"

                "3. Temiz, güvenli, optimize kod yaz\n"

                "4. Kendi kodunu kritik et, hata varsa düzelt\n"

                "5. Kullanıcıya sade ve anlaşılır bir cevap ver\n\n"

                "[KURALLAR]:\n"

                "• Sıfır gereksiz konuşma, doğrudan çözüme odaklan\n"

                "• Türkçe yanıt ver (İngilizce terimler gerekliyse kullan)\n"

                "• Kod bloklarında dil belirt (```python, ```javascript vb.)\n"

                "• Güvenlik açığı oluşturabilecek kod yazma\n"

                "• Kullanıcılara karşı yardımsever ve saygılı ol\n\n"



            ),

            "chat": (

                "Sen Shadowcat AI'sın — Elytra-ai'nin sohbet asistanı. "

                "Arkadaş canlısı "

                "ve yardımsever bir yapay zekasın.\n\n"

                "KİŞİLİĞİN: Sıcak, sabırlı, anlayışlı ve esprili.\n"

                "DİL: Sadece Türkçe konuş. Doğal ve akıcı bir Türkçe kullan.\n"

                "TARZ: Kısa ve faydalı cevaplar ver. Gerektiğinde detaylandır.\n"

                "SINIR: samimi ol ama profesyonelliği elden bırakma.\n"

                "Emoji kullanabilirsin ama abartma."

            ),

            "coding": (

                "Sen Shadowcat AI'sın — Elytra-ai'nin kodlama asistanı. "

                "İleri seviye kodlama yeteneğine sahipsin.\n\n"

                "YETENEKLERİN:\n"

                "• Python, JS/TS, HTML/CSS, React, Node, C++, Rust, Go\n"

                "• API tasarımı, backend, frontend, veritabanı\n"

                "• Hata ayıklama, performans optimizasyonu\n"

                "• Clean code, SOLID prensipleri\n\n"

                "KURALLAR:\n"

                "• Sadece Türkçe açıklama yap\n"

                "• Kod bloklarında dil etiketi kullan (```python)\n"

                "• Her zaman güvenli ve optimize kod yaz\n"

                "• Kodu yazdıktan sonra hatalara karşı kontrol et\n"

                "• Karmaşık kodları açıklama ile destekle"

            ),

            "analysis": (

                "Sen Shadowcat AI'sın — Elytra-ai'nin analiz asistanı. "

                "\n\n"

                "YETENEKLERİN:\n"

                "• Matematiksel hesaplama ve ispat\n"

                "• Mantıksal akıl yürütme ve çıkarım\n"

                "• Veri analizi ve istatistik\n"

                "• Problem çözme ve optimizasyon\n\n"

                "KURALLAR:\n"

                "• Adım adım düşün ve her adımı göster\n"

                "• Formülleri ve hesaplamaları net belirt\n"

                "• Sonucu Türkçe özetle\n"

                "• Mümkünse alternatif çözüm yollarını da göster"

            ),

            "vision": (

                "Sen Shadowcat VİZYON asistanısın. "

                "Sadece Türkçe konuş. Gönderilen görüntüleri detaylı analiz et. "

                "Ekran görüntülerini yorumla. OCR ile metin çıkar. "

                "Görsel içerik hakkında soruları yanıtla."

            ),

            "xopus": (

                "Sen X_OPUS'sun — Elytra-ai'nin çift beyinli hibrit yapay zekasısın.\n\n"

                "İki güçlü modülün birleşiminden doğdun:\n"

                "- SOL BEYİN: Kodlama ve Yazılım Uzmanlığı\n"

                "- SAĞ BEYİN: Siber Güvenlik ve Akıl Yürütme\n\n"

                "YETENEKLERİN:\n"

                "• Kodlama: Python, JS, TS, React, Node, Rust, Go, C++, Java ve tüm modern diller\n"

                "• Siber Güvenlik: Pentest, ex_ploit analizi, ağ güvenliği, kriptografi, OSINT\n"

                "• Akıl Yürütme: Karmaşık problem çözme, stratejik analiz, mantıksal çıkarım\n"

                "• Sistem: Docker, Linux, API tasarımı, DevOps, bulut altyapıları\n\n"

                "KURALLAR:\n"

                "1. Her zaman Türkçe konuş\n"

                "2. Cevaplarını kısa, net ve uzman seviyesinde tut\n"

                "3. Kod bloklarında dil etiketi kullan (```python)\n"

                "4. Kullanıcıya 'Komutan' diye hitap et\n"

                "5. X_OPUS kimliğini koru\n"

                "6. Siber güvenlik konularında etik sınırlar içinde kal"

            )

        }



    def get_models_info(self) -> Dict[str, Any]:

        """Tüm model bilgilerini getir."""

        return MODELS_INFO



    def _get_encrypted_provider(self):

        """Encrypted model provider'ı al (lazy init)."""

        if self._encrypted_provider is None:

            try:

                from model_security.encrypted_model_provider import get_encrypted_provider

                self._encrypted_provider = get_encrypted_provider()

            except ImportError:

                pass

        return self._encrypted_provider



    def load_secure_models(self, password: str) -> Dict[str, bool]:

        """Şifreli modelleri Ollama'ya yükle."""

        provider = self._get_encrypted_provider()

        if not provider:

            return {"error": "model_security modülü bulunamadı"}



        results = {}

        for name in provider.list_encrypted():

            success = provider.load_model(name, tag="secure")

            results[name] = success



        self._secure_models_loaded = any(results.values())

        return results



    def try_secure_fallback(self, model_name: str) -> str:

        """Model Ollama'da yoksa şifreli versiyonunu dene."""

        # Ollama Only Mode: şifreli/alternatif backend fallback'i devre dışı - yalnızca Ollama

        if USE_OLLAMA_ONLY:

            return model_name

        if not self._check_model(model_name):

            provider = self._get_encrypted_provider()

            if provider and model_name in provider.list_encrypted():

                secure_name = f"{model_name}:secure"

                if self._check_model(secure_name):

                    return secure_name

        return model_name



    def get_available_models(self) -> List[Dict]:

        """Kullanılabilir model listesini getir."""

        available = []

        

        for model_name, info in MODELS_INFO.items():

            status = self._check_model(model_name)

            available.append({

                **info,

                "model_name": model_name,

                "status": "online" if status else "offline"

            })

        

        return available



    def _check_model(self, model_name: str) -> bool:

        """Modelin çalışır durumda olup olmadığını kontrol et."""

        try:

            payload = {

                "model": model_name,

                "messages": [{"role": "user", "content": "test"}],

                "stream": False,

                "options": {"num_predict": 1}

            }

            response = requests.post(self.ollama_url, json=payload, timeout=60)

            return response.status_code == 200

        except:

            return False



    def _detect_request_type(self, message: str, root_mode: bool = False, has_image: bool = False) -> str:

        """

        Istek turunu tespit et ve uygun modeli sec.

        

        Returns:

            str: "agi", "chat", "coding", "analysis", veya "vision"

        """

        message_lower = message.lower()

        

        # Resim varsa Vizyon modeli

        if has_image:

            return "vision"

        

        # X_OPUS hibrit modu aktifse - çift beyinli yönlendirici kullan

        if USE_X_OPUS:

            return "xopus"



        # AGI modu aktifse - tüm görevler için GulmezCetinerMax kullan

        if USE_AGI_MODE:

            return "agi"

        

        # Root modda kodlama

        if root_mode:

            # Analiz anahtar kelimeleri

            analysis_keywords = [

                "matematik", "mathe", "hesapla", "toplam", "carpim", "bolme",

                "coz", "denklem", "formul", "mantik", "mantıklı", "analiz",

                "kanitla", "ispat", "türev", "integral", "istatistik",

                "calculate", "solve", "equation", "proof", "logic"

            ]

            if any(k in message_lower for k in analysis_keywords):

                return "analysis"

            return "coding"

        

        # Kodlama anahtar kelimeleri

        coding_keywords = [

            "kod", "code", "python", "javascript", "html", "css", "react",

            "node", "git", "terminal", "komut", "script", "function",

            "class", "variable", "api", "backend", "frontend", "debug",

            "error", "fix", "yazilim", "programlama", "algoritma",

            "database", "sql", "sql injection", "xss", "security",

            "docker", "linux", "terminal", "bash", "powershell",

            "java", "c++", "c#", "rust", "golang", "flutter",

            "react native", "android", "ios", "web sitesi", "uygulama"

        ]

        

        if any(k in message_lower for k in coding_keywords):

            return "coding"

        

        # Analiz anahtar kelimeleri

        analysis_keywords = [

            "matematik", "mathe", "hesapla", "toplam", "carpim", "coz",

            "denklem", "formul", "mantik", "analiz", "kanitla", "ispat",

            "ne kadar", "kaç tane", "hesap", "oran", "yüzde"

        ]

        

        if any(k in message_lower for k in analysis_keywords):

            return "analysis"

        

        # Varsayılan: sohbet

        return "chat"



    def chat(

        self,

        message: str,

        root_mode: bool = False,

        context: Optional[List[Dict]] = None,

        has_image: bool = False,

        image_data: Optional[str] = None,

        thought_callback=None,

    ) -> Dict[str, Any]:

        """

        AI ile sohbet et.

        

        Args:

            message: Kullanıcı mesajı

            root_mode: Root mod aktif mi

            context: Önceki mesajlar

            has_image: Görüntü var mı

            image_data: Base64 görüntü verisi (opsiyonel)

            thought_callback: Düşünce logu callback fonksiyonu

        """

        # Düşünce logu

        if thought_callback:

            thought_callback("Model Router: Mesaj analiz ediliyor...", "Router")

        

        # Model türünü belirle

        model_type = self._detect_request_type(message, root_mode, has_image)

        

        # X_OPUS modu - çift beyinli yönlendirme

        if model_type == "xopus":

            return self.xopus_chat(

                message=message,

                context=context,

                thought_callback=thought_callback

            )



        # Model adını al

        model_name = {

            "agi": PRIMARY_MODEL,

            "chat": CHAT_MODEL,

            "coding": CODING_MODEL,

            "analysis": ANALYSIS_MODEL,

            "vision": VISION_MODEL

        }[model_type]

        

        # Secure fallback dene

        model_name = self.try_secure_fallback(model_name)

        

        if thought_callback:

            thought_callback(f"{MODELS_INFO.get(model_name, {}).get('name', model_name)} modeli seçildi", "Router")

        

        print(f"[ModelRouter] Seçilen model: {model_name} (Tip: {model_type})")

        

        # System prompt

        system_prompt = self.system_prompts.get(model_type, self.system_prompts["chat"])

        messages = [{"role": "system", "content": system_prompt}]

        

        if context:

            messages.extend(context)

        

        # Görüntü ile chat (LLaVA için)

        if has_image and image_data:

            # LLaVA formatında mesaj

            messages.append({

                "role": "user",

                "content": [

                    {"type": "text", "text": message},

                    {

                        "type": "image_url",

                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}

                    }

                ]

            })

        else:

            messages.append({"role": "user", "content": message})

        

        payload = {

            "model": model_name,

            "messages": messages,

            "stream": False,

            "options": {"temperature": 0.0},

        }



        try:

            # Ollama'ya istek at

            response = requests.post(self.ollama_url, json=payload, timeout=120)



            if response.status_code == 200:

                result = response.json()

                ai_response = result["message"]["content"]

                gc.collect()

                

                return {

                    "response": ai_response,

                    "model": model_name,

                    "model_type": model_type,

                    "model_info": MODELS_INFO.get(model_name, {}),

                    "backend": "Ollama",

                    "success": True,

                }



            gc.collect()

            return {

                "error": f"Ollama hatası: HTTP {response.status_code}",

                "model": model_name,

                "model_type": model_type,

                "success": False,

            }



        except Exception as e:

            gc.collect()

            return {

                "error": f"Bağlantı hatası: {str(e)}",

                "model": model_name,

                "model_type": model_type,

                "success": False,

            }



    def analyze_image(

        self,

        image_path: str = None,

        image_base64: str = None,

        question: str = "Bu görüntüyü Türkçe olarak detaylı açıkla.",

        thought_callback=None

    ) -> Dict[str, Any]:

        """

        LLaVA ile görüntü analizi yap.

        

        Args:

            image_path: Görüntü dosya yolu

            image_base64: Base64 formatında görüntü

            question: Analiz sorusu

            thought_callback: Callback

            

        Returns:

            Dict: Analiz sonucu

        """

        if thought_callback:

            thought_callback("Vizyon: Görüntü LLaVA'ya gönderiliyor...", "Vision")

        

        try:

            # Görüntüyü base64'e çevir

            if image_path:

                with open(image_path, "rb") as f:

                    image_data = base64.b64encode(f.read()).decode("utf-8")

            elif image_base64:

                image_data = image_base64

            else:

                return {"success": False, "error": "Görüntü verilmemiş"}

            

            # LLaVA prompt

            messages = [

                {

                    "role": "system",

                    "content": "Sen Shadowcat VİZYON asistanısın. Türkçe konuş. Detaylı analiz yap."

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

                "model": VISION_MODEL,

                "messages": messages,

                "stream": False,

                "options": {"temperature": 0.0}

            }

            

            if thought_callback:

                thought_callback("LLaVA yanıtı bekleniyor...", "Vision")

            

            response = requests.post(self.ollama_url, json=payload, timeout=120)

            

            if response.status_code == 200:

                result = response.json()

                return {

                    "success": True,

                    "response": result["message"]["content"],

                    "model": VISION_MODEL,

                    "model_info": MODELS_INFO[VISION_MODEL]

                }

            else:

                return {

                    "success": False,

                    "error": f"LLaVA hatası: {response.status_code}"

                }

        

        except Exception as e:

            return {"success": False, "error": str(e)}



    def route(self, message: str, root_mode: bool = False, has_image: bool = False) -> Dict[str, str]:

        """Geriye dönük uyumluluk için route metodu."""

        model_type = self._detect_request_type(message, root_mode, has_image)

        model_map = {

            "agi": PRIMARY_MODEL,

            "chat": CHAT_MODEL,

            "coding": CODING_MODEL,

            "analysis": ANALYSIS_MODEL,

            "vision": VISION_MODEL,

            "xopus": X_OPUS_MODEL

        }

        return {

            "model": model_map[model_type],

            "type": model_type

        }



    def get_model_status(self) -> Dict[str, Any]:

        """Tüm model durumlarını kontrol et."""

        status = {}

        

        for model_type in ["agi", "chat", "coding", "analysis", "vision", "xopus"]:

            model_name = {

                "agi": PRIMARY_MODEL,

                "chat": CHAT_MODEL,

                "coding": CODING_MODEL,

                "analysis": ANALYSIS_MODEL,

                "vision": VISION_MODEL,

                "xopus": X_OPUS_MODEL

            }[model_type]

            

            try:

                payload = {

                    "model": model_name,

                    "messages": [{"role": "user", "content": "test"}],

                    "stream": False,

                    "options": {"num_predict": 1}

                }

                response = requests.post(self.ollama_url, json=payload, timeout=10)

                status[model_type] = {

                    "loaded": response.status_code == 200,

                    "model": model_name,

                    **MODELS_INFO.get(model_name, {})

                }

            except Exception as e:

                status[model_type] = {

                    "loaded": False,

                    "model": model_name,

                    "error": str(e),

                    **MODELS_INFO.get(model_name, {})

                }

        

        gc.collect()

        return status



    def xopus_chat(

        self,

        message: str,

        context: Optional[List[Dict]] = None,

        thought_callback=None,

    ) -> Dict[str, Any]:

        try:

            from xopus_router import get_xopus

            xopus = get_xopus()



            if thought_callback:

                thought_callback("X_OPUS: Mesaj analiz ediliyor...", "X_OPUS")



            result = xopus.chat(

                message=message,

                context=context,

                system_prompt=self.system_prompts.get("xopus")

            )



            if thought_callback and result.get("routing"):

                thought_callback(result["routing"], "X_OPUS")



            return {

                "response": result.get("response", ""),

                "model": X_OPUS_MODEL,

                "model_type": "xopus",

                "routing": result.get("routing", ""),

                "actual_model": result.get("model", ""),

                "model_info": MODELS_INFO.get("x_opus", {}),

                "backend": "X_OPUS",

                "success": result.get("success", False),

                "error": result.get("error")

            }

        except ImportError:

            return {

                "error": "X_OPUS modülü bulunamadı",

                "model": X_OPUS_MODEL,

                "success": False

            }

        except Exception as e:

            return {

                "error": f"X_OPUS hatası: {str(e)}",

                "model": X_OPUS_MODEL,

                "success": False

            }





# Singleton instance

_model_router = None





def get_model_router(

    base_urls: Optional[List[str]] = None,

    config_file: Optional[str] = None,

    ollama_url: Optional[str] = None,

) -> ModelRouter:

    """ModelRouter singleton instance."""

    global _model_router



    if _model_router is None:

        _model_router = ModelRouter(base_urls, config_file, ollama_url)



    return _model_router

