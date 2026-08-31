"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║     ██████╗ ██╗    ██╗███████╗███╗   ██╗                       ║
║    ██╔═══██╗██║    ██║██╔════╝████╗  ██║                       ║
║    ██║   ██║██║ █╗ ██║█████╗  ██╔██╗ ██║                       ║
║    ██║▄▄ ██║██║███╗██║██╔══╝  ██║╚██╗██║                       ║
║    ╚██████╔╝╚███╔███╔╝███████╗██║ ╚████║                       ║
║     ╚══▀▀═╝  ╚══╝╚══╝ ╚══════╝╚═╝  ╚═══╝                       ║
║                                                                  ║
║     14B ASSISTANT PLUGIN - FULL POWER AUTO-FIX ENGINE           ║
║     Shadowcat için Qwen 14B - Akıllı Hata Düzeltme Motoru      ║
║                                                                  ║
║     ⚡ Multi-Strategy Fix: 5 farklı strateji ile hata düzeltme  ║
║     🧠 Context-Aware: Python 3.14.4, .venv paketleri, OS bilgisi║
║     🔄 Progressive: Her denemede daha akıllı prompt             ║
║     🎯 Pattern Matching: 15+ hata tipi özel çözüm               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

Qwen 14B Assistant Plugin - FULL POWER AUTO-FIX ENGINE
  - Multi-Strategy: 5 farklı düzeltme stratejisi
  - Context-Aware: Ortam bilgisi ile akıllı prompt
  - Progressive Fixing: Her denemede öğrenerek düzelt
  - Pattern DB: 15+ hata tipi için özel çözüm
"""

from plugin_system import (
    BasePlugin,
    PluginMetadata,
    PluginDependency,
    HookPoint,
    PluginPriority,
    PluginState,
)
from typing import Optional, Dict, Any, List, Tuple
import json
import logging
import os
import sys
import traceback

logger = logging.getLogger(__name__)


class QwenAssistantPlugin(BasePlugin):
    """Qwen 14B Assistant Plugin - Yan panel yardımcı AI asistanı."""

    def __init__(self):
        super().__init__()
        self.metadata = PluginMetadata(
            name="Qwen 14B Assistant",
            version="1.0.0",
            author="Admin (Berkay)",
            description="Qwen 14B yan panel yardımcısı - .venv kod çalıştırma, sohbet ve yardım",
            tags=["qwen", "assistant", "code", "ai", "14b", "yardim"],
            license="MIT",
        )

        # Qwen API ayarları
        self.ollama_url = "http://localhost:11434"
        self.qwen_model = "qwen2.5-coder:14b"
        self.conversation_history: List[Dict] = []
        self.max_history = 20

        # ⚡ FULL POWER AUTO-FIX ENGINE KONFİG
        self.fix_attempts = 5  # Maksimum düzeltme denemesi
        self.fix_strategies = [
            "direct",      # 1: Direkt düzelt
            "analyze",     # 2: Önce analiz et, sonra düzelt
            "rewrite",     # 3: Baştan yaz (aynı mantıkla)
            "debug",       # 4: Debug amaçlı parçalara böl
            "fallback",    # 5: En basit çözüm
        ]

        # 🧠 Ortam bağlamı (env context)
        self._env_context: Dict[str, Any] = {}
        self._refresh_env_context()

    def _refresh_env_context(self):
        """Ortam bilgilerini topla (Python, paketler, OS)."""
        import subprocess
        import platform

        ctx = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "os": platform.system(),
            "machine": platform.machine(),
            "cwd": os.getcwd(),
            "packages": [],
        }

        # .venv'deki paketleri al
        try:
            venv_python = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                ".venv", "Scripts", "python.exe"
            )
            if os.path.exists(venv_python):
                result = subprocess.run(
                    [venv_python, "-m", "pip", "list", "--format=json"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    import json as _json
                    pkgs = _json.loads(result.stdout)
                    ctx["packages"] = [p["name"] for p in pkgs]
                    ctx["package_count"] = len(pkgs)
        except Exception:
            pass

        self._env_context = ctx

    def _get_env_context_str(self) -> str:
        """Ortam bağlamını string olarak döndür (prompt'lara eklemek için)."""
        ctx = self._env_context
        pkg_list = ", ".join(ctx.get("packages", [])[:30])  # ilk 30 paket
        return (
            f"ORTAM: Python {ctx.get('python_version', 'bilinmiyor')}\n"
            f"PLATFORM: {ctx.get('platform', 'bilinmiyor')}\n"
            f"OS: {ctx.get('os', 'bilinmiyor')}\n"
            f"KURULU PAKETLER ({ctx.get('package_count', 0)}): {pkg_list}"
        )

    def on_load(self):
        """Plugin yüklendiğinde kayıtları yap."""
        logger.info("[QwenPlugin] Qwen 14B Assistant yükleniyor...")

        # Özel komutları kaydet
        self.register_command(
            "/qwen",
            self.cmd_qwen_chat,
            description="Qwen 14B'ye soru sor",
            aliases=["/q", "/qwen-sor"],
            usage="/qwen <sorunuz>",
        )
        self.register_command(
            "/qwen-run",
            self.cmd_qwen_run,
            description="Qwen ile kodu analiz et ve çalıştır",
            aliases=["/qr", "/qwen-exec"],
            usage="/qwen-run <kod>",
        )
        self.register_command(
            "/qwen-code",
            self.cmd_qwen_code,
            description="Qwen'den kod yazmasını iste",
            aliases=["/qc", "/qwen-yaz"],
            usage="/qwen-code <açıklama>",
        )

        # Hook'ları kaydet
        self.register_hook(
            HookPoint.ON_STARTUP,
            self.on_startup,
            PluginPriority.NORMAL,
        )
        self.register_hook(
            HookPoint.ON_SHUTDOWN,
            self.on_shutdown,
            PluginPriority.NORMAL,
        )

        # UI bileşeni kaydet (yan panel)
        self.register_ui_component(
            component_id="qwen-assistant-panel",
            render_func=self.render_panel_html,
            location="sidebar",
        )

        logger.info("[QwenPlugin] Qwen 14B Assistant hazır!")

    def on_unload(self):
        """Plugin kaldırılırken temizlik."""
        self.conversation_history.clear()
        logger.info("[QwenPlugin] Qwen 14B Assistant kaldırıldı.")

    def on_enable(self):
        """Plugin aktif edildiğinde."""
        logger.info("[QwenPlugin] Qwen 14B Assistant AKTİF!")
        # Hoşgeldin mesajı ekle
        self.conversation_history.append({
            "role": "assistant",
            "content": "Merhaba! Ben Qwen 14B Asistanınız. Kod yazma, çalıştırma ve sorularınızda size yardımcı olabilirim. Nasıl yardımcı olabilirim? 🚀",
            "timestamp": "now",
        })

    def on_disable(self):
        """Plugin devre dışı bırakıldığında."""
        logger.info("[QwenPlugin] Qwen 14B Assistant devre dışı.")

    def on_startup(self):
        """Sistem başlatıldığında."""
        logger.info("[QwenPlugin] Sistem başlatıldı, Qwen hazır.")

    def on_shutdown(self):
        """Sistem kapatılırken."""
        logger.info("[QwenPlugin] Sistem kapatılıyor, Qwen temizlik yapıyor.")

    # ------------------------------------------------------------------
    # KOMMUT İŞLEYİCİLERİ
    # ------------------------------------------------------------------

    def cmd_qwen_chat(self, args: str, context: Dict) -> str:
        """Qwen'e soru sor komutu."""
        if not args:
            return (
                "❌ Soru sormak için: `/qwen <sorunuz>`\n"
                "Örnek: `/qwen Python'da decorator nasıl yazılır?`"
            )
        try:
            response = self._query_ollama(args)
            if response:
                # Konuşma geçmişine ekle
                self.conversation_history.append({"role": "user", "content": args})
                self.conversation_history.append({"role": "assistant", "content": response})
                return f"🤖 **Qwen 14B:**\n{response}"
            return "⚠️ Qwen yanıt vermedi. Ollama çalışıyor mu kontrol edin."
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    def cmd_qwen_run(self, args: str, context: Dict) -> str:
        """Kodu Qwen ile analiz et ve çalıştır."""
        if not args:
            return "❌ Kod gerekli: `/qwen-run <kod>`"
        return self._analyze_and_execute(args)

    def cmd_qwen_code(self, args: str, context: Dict) -> str:
        """Qwen'den kod yazmasını iste."""
        if not args:
            return "❌ Açıklama gerekli: `/qwen-code <ne yapılacak?>`"
        prompt = (
            f"Sadece kod yaz, açıklama ekleme. Dil: Python.\n"
            f"İstek: {args}\n"
            f"Kod:"
        )
        response = self._query_ollama(prompt)
        if response:
            return f"🤖 **Qwen'in kodu:**\n```python\n{response}\n```"
        return "⚠️ Kod üretilemedi."

    # ------------------------------------------------------------------
    # QWEN API İLETİŞİMİ
    # ------------------------------------------------------------------

    def _query_ollama(self, prompt: str) -> Optional[str]:
        """Ollama üzerinden Qwen 14B'ye sorgu gönder."""
        import urllib.request
        import urllib.error

        try:
            data = json.dumps({
                "model": self.qwen_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 2048,
                }
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("response", "").strip()

        except urllib.error.URLError as e:
            logger.error(f"[QwenPlugin] Ollama bağlantı hatası: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"[QwenPlugin] JSON çözümleme hatası: {e}")
            return None
        except Exception as e:
            logger.error(f"[QwenPlugin] Qwen sorgu hatası: {e}")
            return None

    def _query_ollama_chat(self, messages: List[Dict]) -> Optional[str]:
        """Ollama chat API'si ile konuşma gönder."""
        import urllib.request
        import urllib.error

        try:
            # Son mesajları al (token sınırı)
            recent = messages[-10:] if len(messages) > 10 else messages
            chat_data = {
                "model": self.qwen_model,
                "messages": recent,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 4096,
                }
            }

            data = json.dumps(chat_data).encode("utf-8")
            req = urllib.request.Request(
                f"{self.ollama_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("message", {}).get("content", "").strip()

        except urllib.error.URLError as e:
            logger.error(f"[QwenPlugin] Ollama chat hatası: {e}")
            return None
        except Exception as e:
            logger.error(f"[QwenPlugin] Qwen chat hatası: {e}")
            return None

    # ===================================================================
    # ⚡ FULL POWER AUTO-FIX ENGINE
    # ===================================================================
    # 5 Strateji, 5 Deneme, Context-Aware, Pattern Matching
    # ===================================================================

    def _clean_code(self, text: str) -> str:
        """Qwen yanıtından temiz kod çıkar - tüm formatları dene."""
        import re

        if not text:
            return ""

        text = text.strip()

        # Strateji 1: ```python ... ``` veya ``` ... ```
        m = re.search(r'```(?:python|py)?\s*\n(.*?)(?:\n\s*)?```', text, re.DOTALL)
        if m:
            return m.group(1).strip()

        # Strateji 2: inline `kod` (tek satır)
        m = re.search(r'`([^`]+)`', text)
        if m and '\n' not in m.group(1):
            return m.group(1).strip()

        # Strateji 3: Kod görünümlü satırlar (import, def, class, print ile başlayan)
        lines = text.split('\n')
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(kw) for kw in ['import ', 'from ', 'def ', 'class ', 'print', 'if ', 'for ', 'while ', 'try:', 'with ', 'return ', '#', '"""', "'''", '@']):
                code_lines.append(stripped)
            elif code_lines and stripped and not stripped.startswith('```'):
                code_lines.append(stripped)

        if len(code_lines) >= 2:
            return '\n'.join(code_lines)

        # Strateji 4: Hiçbir şey bulunamadıysa, metindeki kod bloklarını ayıkla
        # ``` ile çevrili olmayan ama kod gibi görünen satırlar
        code_lines = []
        in_code = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                code_lines.append(stripped)

        if code_lines:
            return '\n'.join(code_lines)

        return text

    def _classify_error(self, error_text: str) -> dict:
        """Hata metnini analiz et ve detaylı sınıflandırma yap."""
        error_lower = error_text.lower()

        classification = {
            "type": "genel",
            "category": "runtime",
            "severity": "medium",
            "description": "Bilinmeyen hata",
            "possible_fixes": [],
            "keywords": [],
        }

        # ---------- SENTAKS HATALARI ----------
        if "SyntaxError" in error_text:
            classification.update({
                "type": "syntax_error",
                "category": "syntax",
                "severity": "high",
                "description": "Python sentaks hatasi",
            })
            if "invalid syntax" in error_lower:
                classification["possible_fixes"] = ["Parantez/noktalama kontrolu", "Eksik operator kontrolu"]
            elif "unexpected" in error_lower:
                classification["possible_fixes"] = ["Girinti hizalamasi kontrolu", "Eksik iki nokta ustuste kontrolu"]
            return classification

        if "IndentationError" in error_text:
            classification.update({
                "type": "indentation_error",
                "category": "syntax",
                "severity": "high",
                "description": "Girinti hatasi",
                "possible_fixes": ["Tum girintileri 4 space ile duzelt", "Karışık tab/space kontrolu"],
            })
            return classification

        # ---------- ISIM HATALARI ----------
        if "NameError" in error_text or "name '" in error_text or "is not defined" in error_text:
            # Hangi isim tanımlı değil?
            import re
            name_match = re.search(r"name\s+'([^']+)'|'([^']+)'\s+is\s+not\s+defined", error_text)
            missing_name = name_match.group(1) or name_match.group(2) if name_match else "bilinmiyor"
            classification.update({
                "type": "name_error",
                "category": "reference",
                "severity": "high",
                "description": f"'{missing_name}' tanımlı değil",
                "keywords": [missing_name],
                "possible_fixes": [
                    f"import {missing_name} ekle",
                    f"{missing_name} degiskenini tanimla",
                    f"Yazim hatasi kontrolu: '{missing_name}'",
                ],
            })
            return classification

        # ---------- IMPORT HATALARI ----------
        if "ModuleNotFoundError" in error_text or "ImportError" in error_text:
            import re
            mod_match = re.search(r"No module named '([^']+)'|cannot import name '([^']+)'", error_text)
            missing_mod = mod_match.group(1) or mod_match.group(2) if mod_match else "bilinmiyor"
            classification.update({
                "type": "import_error",
                "category": "dependency",
                "severity": "high",
                "description": f"'{missing_mod}' modulu bulunamadi",
                "keywords": [missing_mod],
                "possible_fixes": [
                    f"pip install {missing_mod}",
                    f"try/except ile import et",
                    f"Yedek modul kullan",
                ],
            })
            return classification

        # ---------- TIP HATALARI ----------
        if "TypeError" in error_text:
            classification.update({
                "type": "type_error",
                "category": "runtime",
                "severity": "medium",
                "description": "Tip uyusmazligi",
                "possible_fixes": ["str()/int()/float() donusumu ekle", "Tip kontrolu ekle", "Hata yonetimi ekle"],
            })
            # TypeError detayları
            if "unsupported operand" in error_lower:
                classification["description"] = "Desteklenmeyen operator"
                classification["possible_fixes"] = ["Ayni tipe donustur", "Operator overload kontrolu"]
            elif "object is not" in error_lower:
                classification["possible_fixes"] = ["str() donusumu ekle", ".text veya .content kullan"]
            return classification

        # ---------- INDEX/HATA ----------
        if "IndexError" in error_text:
            classification.update({
                "type": "index_error",
                "category": "runtime",
                "severity": "medium",
                "description": "Liste indeks hatasi",
                "possible_fixes": ["len() kontrolu ekle", "try/except ekle", "if index < len(list) kontrolu"],
            })
            return classification

        if "KeyError" in error_text:
            import re
            key_match = re.search(r"KeyError:\s*'([^']+)'", error_text)
            missing_key = key_match.group(1) if key_match else "bilinmiyor"
            classification.update({
                "type": "key_error",
                "category": "runtime",
                "severity": "medium",
                "description": f"'{missing_key}' anahtari bulunamadi",
                "keywords": [missing_key],
                "possible_fixes": [f"dict.get('{missing_key}') kullan", f"if '{missing_key}' in dict: kontrolu", "setdefault() kullan"],
            })
            return classification

        if "AttributeError" in error_text:
            classification.update({
                "type": "attribute_error",
                "category": "runtime",
                "severity": "medium",
                "description": "Nitelik hatasi",
                "possible_fixes": ["Dogru metod adini kontrol et", "hasattr() ile kontrol et", "try/except ekle"],
            })
            return classification

        # ---------- DEGER HATALARI ----------
        if "ValueError" in error_text:
            classification.update({
                "type": "value_error",
                "category": "runtime",
                "severity": "medium",
                "description": "Gecersiz deger",
                "possible_fixes": ["try/except ekle", "Giris dogrulama ekle", "int()/float() donusumu kontrolu"],
            })
            if "invalid literal" in error_lower:
                classification["possible_fixes"] = ["try/except ile hata yonetimi", "isdigit() kontrolu"]
            return classification

        if "ZeroDivisionError" in error_text:
            classification.update({
                "type": "zero_division",
                "category": "math",
                "severity": "medium",
                "description": "Sifira bolme hatasi",
                "possible_fixes": ["if bolen != 0 kontrolu ekle", "try/except ekle", "Kucuk epsilon degeri kullan"],
            })
            return classification

        # ---------- DOSYA HATALARI ----------
        if "FileNotFoundError" in error_text:
            classification.update({
                "type": "file_not_found",
                "category": "io",
                "severity": "medium",
                "description": "Dosya bulunamadi",
                "possible_fixes": ["Tam dosya yolu kullan", "os.path.exists() kontrolu", "try/except ekle"],
            })
            return classification

        if "PermissionError" in error_text:
            classification.update({
                "type": "permission_error",
                "category": "io",
                "severity": "medium",
                "description": "Yetki hatasi",
                "possible_fixes": ["Yonetici olarak calistir", "Farkli dizin dene"],
            })
            return classification

        # ---------- ZAMAN HATALARI ----------
        if "Timeout" in error_text or "timeout" in error_lower:
            classification.update({
                "type": "timeout",
                "category": "system",
                "severity": "low",
                "description": "Zaman asimi",
                "possible_fixes": ["Kodu optimize et", "Daha kisa sureli islem yap"],
            })
            return classification

        # ---------- BAGLANTI HATALARI ----------
        if any(kw in error_lower for kw in ["connection", "connect", "network", "socket"]):
            classification.update({
                "type": "connection_error",
                "category": "network",
                "severity": "medium",
                "description": "Baglanti hatasi",
                "possible_fixes": ["try/except ekle", "timeout parametresi ekle", "Baglantiyi kontrol et"],
            })
            return classification

        return classification

    def _build_fix_prompt(self, strategy: str, code: str, error_text: str,
                          error_class: dict, attempt: int, previous_attempts: list) -> str:
        """Stratejiye göre düzeltme prompt'u oluştur."""
        context = self._get_env_context_str()
        error_type = error_class.get("type", "genel")
        error_desc = error_class.get("description", error_text[:100])

        # Strateji template'leri
        templates = {
            "direct": (
                "Sen bir Python debug uzmanısın. Şu kodu düzelt.\n"
                "{context}\n\n"
                "HATA: {error}\n"
                "HATA TİPİ: {error_type} ({error_desc})\n\n"
                "KOD:\n{code}\n\n"
                "Sadece DÜZELTİLMİŞ kodu yaz. Açıklama EKLEME.```python işareti KULLANMA."
            ),
            "analyze": (
                "Önce hatayı analiz et, sonra düzeltilmiş kodu yaz.\n\n"
                "ORTAM: {context}\n"
                "HATA: {error}\n"
                "HATA TİPİ: {error_type}\n\n"
                "KOD:\n{code}\n\n"
                "ANALİZ (1 cümle):\n"
                "DÜZELTİLMİŞ KOD:\n"
                "```python\n<kod>\n```"
            ),
            "rewrite": (
                "Bu Python kodunun aynı işlevi yapan ama hatasız versiyonunu yaz.\n\n"
                "HATA: {error}\n\n"
                "ORİJİNAL KOD:\n{code}\n\n"
                "Sadece çalışan kodu yaz, ```python işareti kullanma."
            ),
            "debug": (
                "Bu kodu adım adım debug et ve düzelt.\n\n"
                "HATA: {error}\n"
                "HATA TİPİ: {error_type}\n\n"
                "KOD:\n{code}\n\n"
                "Adım 1 - Sorunu belirle:\n"
                "Adım 2 - Düzeltilmiş kod:\n"
                "```python\n<kod>\n```"
            ),
            "fallback": (
                "ACİL: Bu Python kodu çalışmıyor. En basit ve kesin çözümü bul.\n\n"
                "HATA: {error}\n"
                "HATA TİPİ: {error_type}\n\n"
                "KOD:\n{code}\n\n"
                "Çözüm için:\n"
                "1. try/except bloğu ekle\n"
                "2. Gerekli import'ları ekle\n"
                "3. Sadece ÇALIŞAN kodu yaz."
            ),
        }

        template = templates.get(strategy, templates["direct"])

        # Önceki denemeleri ekle (progressive learning)
        previous_context = ""
        if previous_attempts:
            prev_lines = []
            for i, prev in enumerate(previous_attempts[-3:], 1):  # son 3 deneme
                prev_lines.append(
                    f"  Deneme {i}: Strateji={prev.get('strategy','?')}, "
                    f"Hata={prev.get('error','?')[:80]}"
                )
            previous_context = "ÖNCEKİ BAŞARISIZ DENEMELER:\n" + "\n".join(prev_lines) + "\n\n"

        return template.format(
            context=context,
            error=error_text[:300],
            error_type=error_type,
            error_desc=error_desc,
            code=code,
        ) + "\n\n" + previous_context

    def _analyze_and_execute(self, code: str) -> str:
        """
        ⚡ FULL POWER AUTO-FIX ENGINE
        5 strateji, 5 deneme, context-aware, pattern matching
        """
        import re as _re

        # Önce kodu analiz et
        analysis_prompt = (
            f"Bu Python kodunu analiz et. Ne yapıyor? Hata var mı? (1-2 cümle):\n"
            f"```python\n{code}\n```"
        )
        analysis = self._query_ollama(analysis_prompt)

        # .venv'de çalıştırmayı dene
        exec_result = self._execute_in_venv(code)

        # ✅ BAŞARILI - direkt döndür
        if exec_result["success"]:
            return (
                f"✅ **Çıktı:**\n```\n{exec_result['output']}\n```\n"
                f"{'📊 **Analiz:** ' + analysis if analysis else ''}"
            )

        # ❌ HATA VAR - Full Power Auto-Fix başlasın!
        error_text = exec_result.get("error", "Bilinmeyen hata")

        # Hata sınıflandırması
        error_class = self._classify_error(error_text)
        error_type = error_class.get("type", "genel")
        error_desc = error_class.get("description", error_text[:100])

        previous_attempts = []
        all_fixed_codes = []

        # 🎯 5 STRATEJİ İLE DENE
        for attempt_idx, strategy in enumerate(self.fix_strategies):
            # Prompt'u oluştur
            prompt = self._build_fix_prompt(
                strategy=strategy,
                code=code if not all_fixed_codes else all_fixed_codes[-1],
                error_text=error_text,
                error_class=error_class,
                attempt=attempt_idx + 1,
                previous_attempts=previous_attempts,
            )

            # Qwen'e sor
            fixed_raw = self._query_ollama(prompt)
            if not fixed_raw:
                continue

            # Kodu temizle
            fixed_code = self._clean_code(fixed_raw)
            if not fixed_code or fixed_code == code:
                continue

            # Daha önce denendi mi?
            if fixed_code in all_fixed_codes:
                continue

            all_fixed_codes.append(fixed_code)

            # Düzeltilmiş kodu çalıştır
            retry = self._execute_in_venv(fixed_code)

            if retry["success"]:
                attempt_num = attempt_idx + 1
                strat_name = strategy.capitalize()
                return (
                    f"⚡ **Qwen [{attempt_num}/{strat_name}] düzeltti!**\n\n"
                    f"**Hata:** `{error_desc}`\n"
                    f"**Düzeltilmiş Kod:**\n```python\n{fixed_code}\n```\n"
                    f"✅ **Çıktı:**\n```\n{retry['output']}\n```"
                )

            # Başarısız - kaydet
            previous_attempts.append({
                "strategy": strategy,
                "error": retry.get("error", "bilinmiyor")[:150],
                "code": fixed_code,
            })

        # ⚠ TÜM STRATEJİLER BAŞARISIZ - son çare prompt
        if all_fixed_codes:
            last_code = all_fixed_codes[-1]
            last_error = previous_attempts[-1]["error"] if previous_attempts else error_text
            final_prompt = (
                "ACİL DURUM! Tum stratejiler basarisiz. Bu kodu en basit haliyle yeniden yaz.\n"
                "Hicbir harici kutuphane kullanma. Sadece built-in Python ile calissin.\n\n"
                f"SON HATA: {last_error}\n\n"
                f"SON KOD:\n{last_code}\n\n"
                f"ORIJINAL KOD:\n{code}\n\n"
                "Sadece calisan kodu yaz."
            )
            final_raw = self._query_ollama(final_prompt)
            final_code = self._clean_code(final_raw) if final_raw else None
            if final_code and final_code not in all_fixed_codes:
                final_retry = self._execute_in_venv(final_code)
                if final_retry["success"]:
                    return (
                        f"🆘 **Qwen son çareyle düzeltti!**\n\n"
                        f"**Düzeltilmiş Kod:**\n```python\n{final_code}\n```\n"
                        f"✅ **Çıktı:**\n```\n{final_retry['output']}\n```"
                    )

        # ❌ HİÇBİR ŞEY İŞE YARAMADI
        # Son bir analiz daha yap
        postmortem = self._query_ollama(
            f"Bu kod neden calismiyor? Tek bir sebep soyle ve cozum oner:\n"
            f"HATA: {error_text}\n"
            f"KOD:\n{code}\n"
            f"CEVAP (1 satir):"
        )

        return (
            f"❌ **{error_class.get('description', 'Hata')}**\n\n"
            f"```\n{error_text[:300]}\n```\n\n"
            f"💡 **Qwen Analizi:** {postmortem or 'Karmaşık hata, manuel müdahale gerekli'}"
        )

    def _execute_in_venv(self, code: str) -> Dict[str, Any]:
        """Python kodunu .venv içinde çalıştır."""
        import subprocess
        import tempfile

        venv_python = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".venv", "Scripts", "python.exe"
        )

        if not os.path.exists(venv_python):
            venv_python = "python"  # fallback

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(
                [venv_python, temp_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )

            os.unlink(temp_path)

            if result.returncode == 0:
                return {"success": True, "output": result.stdout.strip() or "✅ Başarılı (çıktı yok)"}
            else:
                return {"success": False, "error": result.stderr.strip() or result.stdout.strip() or "Bilinmeyen hata"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "⏱ Kod 30 saniye içinde tamamlanmadı."}
        except Exception as e:
            return {"success": False, "error": f"Çalıştırma hatası: {str(e)}"}

    # ------------------------------------------------------------------
    # UI BİLEŞENİ
    # ------------------------------------------------------------------

    def render_panel_html(self, **kwargs) -> str:
        """Qwen yan panel HTML'ini oluştur."""
        return """
        <div id="qwen-panel" class="qwen-panel">
            <div class="qwen-header">
                <div class="qwen-logo">
                    <svg width="28" height="28" viewBox="0 0 100 100" fill="none">
                        <circle cx="50" cy="50" r="45" fill="#6A5ACD" opacity="0.2"/>
                        <circle cx="50" cy="50" r="35" fill="#6A5ACD" opacity="0.3"/>
                        <circle cx="50" cy="50" r="25" fill="#7B68EE" opacity="0.5"/>
                        <text x="50" y="58" text-anchor="middle" fill="white" font-size="24" font-weight="bold" font-family="Arial">Q</text>
                        <circle cx="30" cy="35" r="3" fill="#9B8FFF" opacity="0.8"/>
                        <circle cx="70" cy="35" r="3" fill="#9B8FFF" opacity="0.8"/>
                        <circle cx="50" cy="65" r="4" fill="#B8A8FF" opacity="0.6"/>
                    </svg>
                </div>
                <span class="qwen-title">Qwen 14B</span>
                <span class="qwen-badge">14B</span>
            </div>
            <div class="qwen-chat" id="qwenChat">
                <div class="qwen-msg qwen-ai">
                    <div class="qwen-msg-icon">
                        <svg width="18" height="18" viewBox="0 0 100 100" fill="none">
                            <circle cx="50" cy="50" r="40" fill="#6A5ACD" opacity="0.3"/>
                            <text x="50" y="56" text-anchor="middle" fill="white" font-size="20" font-weight="bold" font-family="Arial">Q</text>
                        </svg>
                    </div>
                    <div class="qwen-msg-bub">
                        Merhaba! Ben <b>Qwen 14B</b>. Kod yazma, .venv çalıştırma ve yardım için buradayım 👋
                        <div class="qwen-msg-time">şimdi</div>
                    </div>
                </div>
            </div>
            <div class="qwen-input-row">
                <div class="qwen-tools">
                    <button class="qwen-tool-btn" onclick="qwenRunCode()" title="Kodu çalıştır">▶</button>
                    <button class="qwen-tool-btn" onclick="qwenClearChat()" title="Temizle">🗑</button>
                </div>
                <input type="text" class="qwen-input" id="qwenInput" placeholder="Qwen 14B'ye sor..." onkeydown="if(event.key=='Enter' && !event.shiftKey){event.preventDefault();qwenSend();}">
                <button class="qwen-send-btn" onclick="qwenSend()">➤</button>
            </div>
            <div class="qwen-status">
                <span class="qwen-status-dot"></span>
                <span id="qwenStatus">Qwen 14B • hazır</span>
            </div>
        </div>
        """

    # ------------------------------------------------------------------
    # DIŞ ARAYÜZ (Flask API için)
    # ------------------------------------------------------------------

    def chat(self, message: str) -> Dict[str, Any]:
        """Harici API çağrıları için sohbet fonksiyonu."""
        self.conversation_history.append({"role": "user", "content": message})

        # Ollama chat API'sini dene
        response = self._query_ollama_chat(self.conversation_history)

        if response:
            self.conversation_history.append({"role": "assistant", "content": response})
            # Geçmişi sınırla
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]
            return {"success": True, "response": response}
        else:
            # Fallback: generate API'sini dene
            response = self._query_ollama(message)
            if response:
                self.conversation_history.append({"role": "assistant", "content": response})
                return {"success": True, "response": response}
            return {"success": False, "error": "Qwen 14B yanıt vermedi. Ollama'yı kontrol edin."}

    def execute_code(self, code: str) -> Dict[str, Any]:
        """Harici API için kod çalıştırma."""
        return self._analyze_and_execute_code(code)

    def _analyze_and_execute_code(self, code: str) -> Dict[str, Any]:
        """
        ⚡ FULL POWER AUTO-FIX ENGINE (API MODE)
        5 strateji ile hatayı düzelt, JSON döndür.
        """
        exec_result = self._execute_in_venv(code)
        if exec_result["success"]:
            return exec_result

        # HATA VAR - Full Power Auto-Fix
        error_text = exec_result.get("error", "Bilinmeyen hata")
        error_class = self._classify_error(error_text)
        error_type = error_class.get("type", "genel")

        previous_attempts = []
        all_fixed_codes = []

        for attempt_idx, strategy in enumerate(self.fix_strategies):
            prompt = self._build_fix_prompt(
                strategy=strategy,
                code=code if not all_fixed_codes else all_fixed_codes[-1],
                error_text=error_text,
                error_class=error_class,
                attempt=attempt_idx + 1,
                previous_attempts=previous_attempts,
            )

            fixed_raw = self._query_ollama(prompt)
            if not fixed_raw:
                continue

            fixed_code = self._clean_code(fixed_raw)
            if not fixed_code or fixed_code == code or fixed_code in all_fixed_codes:
                continue

            all_fixed_codes.append(fixed_code)
            retry = self._execute_in_venv(fixed_code)

            if retry["success"]:
                return {
                    "success": True,
                    "output": retry["output"],
                    "fixed_code": fixed_code,
                    "error_type": error_type,
                    "strategy": strategy,
                    "attempt": attempt_idx + 1,
                    "original_error": error_text[:200],
                }

            previous_attempts.append({
                "strategy": strategy,
                "error": retry.get("error", "bilinmiyor")[:150],
                "code": fixed_code,
            })

        # Son çare denemesi
        if all_fixed_codes:
            final_prompt = (
                "ACİL! Built-in Python ile yeniden yaz:\n"
                f"SON HATA: {previous_attempts[-1]['error']}\n"
                f"SON KOD:\n{all_fixed_codes[-1]}\n"
                "Sadece kod:"
            )
            final_raw = self._query_ollama(final_prompt)
            final_code = self._clean_code(final_raw) if final_raw else None
            if final_code and final_code not in all_fixed_codes:
                final_retry = self._execute_in_venv(final_code)
                if final_retry["success"]:
                    return {
                        "success": True,
                        "output": final_retry["output"],
                        "fixed_code": final_code,
                        "error_type": error_type,
                        "strategy": "final",
                        "original_error": error_text[:200],
                    }

        return {
            "success": False,
            "error": error_text[:500],
            "error_type": error_type,
            "attempts": len(all_fixed_codes),
        }

    def get_status(self) -> Dict[str, Any]:
        """Plugin durum bilgisi."""
        import urllib.request
        ollama_ok = False
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                ollama_ok = any(self.qwen_model in m.get("name", "") for m in data.get("models", []))
        except:
            pass

        return {
            "name": self.metadata.name,
            "version": self.metadata.version,
            "enabled": self.state == PluginState.ENABLED,
            "ollama_connected": ollama_ok,
            "model": self.qwen_model,
            "message_count": len(self.conversation_history),
            "status": "hazır" if ollama_ok else "Ollama bağlı değil",
        }

    def clear_history(self):
        """Konuşma geçmişini temizle."""
        self.conversation_history.clear()
        self.conversation_history.append({
            "role": "assistant",
            "content": "Merhaba! Ben Qwen 14B Asistanınız. Kod yazma, çalıştırma ve sorularınızda size yardımcı olabilirim. Nasıl yardımcı olabilirim? 🚀",
        })
