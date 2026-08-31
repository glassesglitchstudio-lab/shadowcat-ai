"""
Shadowcat - Sesli Yanıt Modülü (Text-to-Speech)
Yanıtları sesli olarak okuma
gTTS, pyttsx3, ve edge-tts desteği
"""

import os
import base64
import threading
import tempfile
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path

class TextToSpeech:
    """
    Text-to-Speech seslendirme sistemi
    - gTTS (Google TTS)
    - pyttsx3 (Offline)
    - Edge TTS (Microsoft)
    """
    
    def __init__(self):
        self.lock = threading.Lock()
        self.cache = {}
        self.max_cache_size = 50
        self.cache_dir = Path(tempfile.gettempdir()) / 'glassescat_tts'
        self.cache_dir.mkdir(exist_ok=True)
        
        self.current_provider = 'gtts'
        self.available_providers = ['gtts', 'pyttsx3', 'edge']
        self.voice_settings = {
            'gtts': {'lang': 'tr', 'slow': False},
            'pyttsx3': {'rate': 150, 'volume': 1.0},
            'edge': {'voice': 'tr-TR', 'speed': 0, 'pitch': 0}
        }
    
    def speak(self, text: str, provider: str = None) -> Dict:
        """
        Metni sese dönüştür
        """
        if provider is None:
            provider = self.current_provider
        
        if provider not in self.available_providers:
            provider = 'gtts'
        
        # Cache kontrolü
        cache_key = f"{provider}:{text[:50]}"
        with self.lock:
            if cache_key in self.cache:
                return self.cache[cache_key]
        
        try:
            if provider == 'gtts':
                result = self._speak_gtts(text)
            elif provider == 'pyttsx3':
                result = self._speak_pyttsx3(text)
            elif provider == 'edge':
                result = self._speak_edge(text)
            else:
                return {"success": False, "error": f"Bilinmeyen provider: {provider}"}
            
            # Cache'e kaydet
            if result.get('success'):
                with self.lock:
                    if len(self.cache) > self.max_cache_size:
                        oldest = list(self.cache.keys())[0]
                        del self.cache[oldest]
                    self.cache[cache_key] = result
            
            return result
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _speak_gtts(self, text: str) -> Dict:
        """Google TTS (gTTS)"""
        try:
            from gtts import gTTS
            
            # Türkçe karakterleri işle
            text = self._clean_text(text)
            
            # Geçici dosya
            temp_file = self.cache_dir / f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            
            tts = gTTS(text=text, lang='tr', slow=False)
            tts.save(str(temp_file))
            
            # Base64'e çevir
            with open(temp_file, 'rb') as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Geçici dosyayı sil
            try:
                os.unlink(temp_file)
            except:
                pass
            
            return {
                "success": True,
                "audio": audio_data,
                "format": "mp3",
                "provider": "gtts",
                "duration_estimate": len(text) / 10  # Yaklaşık süre
            }
        
        except ImportError:
            return {"success": False, "error": "gTTS kurulu değil. pip install gtts"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _speak_pyttsx3(self, text: str) -> Dict:
        """pyttsx3 (Offline TTS)"""
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            settings = self.voice_settings['pyttsx3']
            engine.setProperty('rate', settings['rate'])
            engine.setProperty('volume', settings['volume'])
            
            # Türkçe ses varsa ayarla
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'tr' in voice.languages or 'tur' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
            
            # Geçici dosya
            temp_file = self.cache_dir / f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            
            engine.save_to_file(text, str(temp_file))
            engine.runAndWait()
            
            # Base64'e çevir
            with open(temp_file, 'rb') as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Geçici dosyayı sil
            try:
                os.unlink(temp_file)
            except:
                pass
            
            engine.stop()
            
            return {
                "success": True,
                "audio": audio_data,
                "format": "wav",
                "provider": "pyttsx3",
                "duration_estimate": len(text) / 8
            }
        
        except ImportError:
            return {"success": False, "error": "pyttsx3 kurulu değil. pip install pyttsx3"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _speak_edge(self, text: str) -> Dict:
        """Edge TTS (Microsoft)"""
        try:
            import edge_tts
            
            settings = self.voice_settings['edge']
            
            async def _generate():
                temp_file = self.cache_dir / f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                
                communicate = edge_tts.Communicate(text, voice=settings['voice'])
                await communicate.save(str(temp_file))
                
                with open(temp_file, 'rb') as f:
                    audio_data = base64.b64encode(f.read()).decode('utf-8')
                
                try:
                    os.unlink(temp_file)
                except:
                    pass
                
                return audio_data
            
            import asyncio
            audio_data = asyncio.get_event_loop().run_until_complete(_generate())
            
            return {
                "success": True,
                "audio": audio_data,
                "format": "mp3",
                "provider": "edge",
                "duration_estimate": len(text) / 12
            }
        
        except ImportError:
            return {"success": False, "error": "edge-tts kurulu değil. pip install edge-tts"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _clean_text(self, text: str) -> str:
        """Metni TTS için temizle"""
        import re
        
        # URL'leri kaldır
        text = re.sub(r'https?://\S+', '', text)
        
        # Markdown kalıntılarını temizle
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'[#*_`~]', '', text)
        
        # Gereksiz boşlukları temizle
        text = re.sub(r'\s+', ' ', text)
        
        # Uzunluğu sınırla (TTS genellikle 5000 karakter sınırı)
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        return text.strip()
    
    def get_available_voices(self, provider: str = 'gtts') -> Dict:
        """Mevcut sesleri listele"""
        try:
            if provider == 'pyttsx3':
                import pyttsx3
                engine = pyttsx3.init()
                voices = engine.getProperty('voices')
                result = {
                    "success": True,
                    "provider": provider,
                    "voices": [
                        {"id": v.id, "name": v.name, "languages": v.languages}
                        for v in voices
                    ]
                }
                engine.stop()
                return result
            
            elif provider == 'edge':
                return {
                    "success": True,
                    "provider": provider,
                    "voices": [
                        {"id": "tr-TR", "name": "Turkish (Turkey)"},
                        {"id": "tr-TR-Female", "name": "Turkish (Turkey) Female"},
                        {"id": "tr-TR-Male", "name": "Turkish (Turkey) Male"}
                    ]
                }
            
            else:
                return {
                    "success": True,
                    "provider": provider,
                    "voices": [{"id": "tr", "name": "Turkish"}]
                }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def set_provider(self, provider: str):
        """Varsayılan sağlayıcıyı ayarla"""
        if provider in self.available_providers:
            self.current_provider = provider
    
    def clear_cache(self):
        """Önbelleği temizle"""
        with self.lock:
            self.cache.clear()
        
        # Geçici dosyaları temizle
        for f in self.cache_dir.glob('tts_*'):
            try:
                os.unlink(f)
            except:
                pass


# Global instance
_tts_instance = None

def get_tts() -> TextToSpeech:
    """Global TTS instance"""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TextToSpeech()
    return _tts_instance
