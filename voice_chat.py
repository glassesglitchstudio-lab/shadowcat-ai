# -*- coding: utf-8 -*-
"""Shadowcat Voice Chat - Sesli Sohbet Modulu"""
import os, sys, json, base64, tempfile, threading, time, logging
from pathlib import Path
from typing import Optional, Dict, Callable
from datetime import datetime

logger = logging.getLogger("VoiceChat")

TTS_AVAILABLE = False
try:
    from tts import TextToSpeech
    TTS_AVAILABLE = True
except ImportError:
    logger.warning("TTS modulu bulunamadi")

STT_AVAILABLE = False
try:
    import speech_recognition as sr
    STT_AVAILABLE = True
except ImportError:
    logger.warning("speech_recognition kurulu degil")

PYAUDIO_AVAILABLE = False
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    logger.warning("PyAudio kurulu degil")


class VoiceChat:
    """Sesli sohbet yoneticisi"""

    def __init__(self, speak_callback=None):
        self.tts = TextToSpeech() if TTS_AVAILABLE else None
        self.recognizer = sr.Recognizer() if STT_AVAILABLE else None
        self.microphone = None
        self.is_listening = False
        self.is_speaking = False
        self.speak_callback = speak_callback
        self.voice_settings = {
            "enabled": True, "auto_speak": True, "provider": "gtts",
            "language": "tr-TR", "energy_threshold": 4000, "pause_threshold": 0.8
        }
        if STT_AVAILABLE and PYAUDIO_AVAILABLE:
            try:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                logger.info("Mikrofon hazir")
            except Exception as e:
                logger.warning(f"Mikrofon hatasi: {e}")

    def speak(self, text, provider=None):
        """Metni sese donustur"""
        if not self.tts:
            return {"success": False, "error": "TTS yok"}
        if not self.voice_settings["enabled"]:
            return {"success": False, "error": "Ses kapali"}
        self.is_speaking = True
        try:
            result = self.tts.speak(text, provider or self.voice_settings["provider"])
            if result.get("success"):
                self._play_audio(result["audio"], result["format"])
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.is_speaking = False

    def listen(self, timeout=10):
        """Mikrofon dinle - STT"""
        if not STT_AVAILABLE or not self.microphone:
            return {"success": False, "error": "STT yok"}
        self.is_listening = True
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=15)
            try:
                text = self.recognizer.recognize_google(audio, language=self.voice_settings["language"])
                return {"success": True, "text": text}
            except Exception as e:
                return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.is_listening = False

    def _play_audio(self, audio_base64, format="mp3"):
        """Sesi oynat"""
        try:
            audio_data = base64.b64decode(audio_base64)
            temp_file = Path(tempfile.gettempdir()) / f"sc_voice_{int(time.time())}.{format}"
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            if sys.platform == "win32":
                os.system(f"start /min \"\" \"{temp_file}\"")
            elif sys.platform == "darwin":
                os.system(f"afplay \"{temp_file}\" &")
            else:
                os.system(f"mpg123 \"{temp_file}\" 2>/dev/null &")
            def _cleanup():
                time.sleep(5)
                try: os.unlink(temp_file)
                except: pass
            threading.Thread(target=_cleanup, daemon=True).start()
        except Exception as e:
            logger.error(f"Ses oynatma hatasi: {e}")

    def toggle(self, enabled=None):
        if enabled is not None:
            self.voice_settings["enabled"] = enabled
        else:
            self.voice_settings["enabled"] = not self.voice_settings["enabled"]
        return self.voice_settings["enabled"]

    def set_provider(self, provider):
        if provider in ["gtts", "pyttsx3", "edge"]:
            self.voice_settings["provider"] = provider
            if self.tts:
                self.tts.current_provider = provider
            return True
        return False

    def get_status(self):
        return {
            "tts": TTS_AVAILABLE, "stt": STT_AVAILABLE,
            "pyaudio": PYAUDIO_AVAILABLE, "mic": self.microphone is not None,
            "listening": self.is_listening, "speaking": self.is_speaking,
            "settings": self.voice_settings
        }


_voice_instance = None

def get_voice_chat():
    global _voice_instance
    if _voice_instance is None:
        _voice_instance = VoiceChat()
    return _voice_instance


if __name__ == "__main__":
    v = get_voice_chat()
    print(json.dumps(v.get_status(), indent=2, ensure_ascii=False))
