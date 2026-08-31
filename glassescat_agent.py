"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          SHADOWCAT - GELISMIS PC AJANI ║
║                                                           ║
║    GlassescatCore + AgentLoop + TaskPlanner ile calisir       ║
║    Jarvis • Hermes • Friday • Edith Tarzında              ║
║                                                           ║
║    Ozellikler:                                            ║
║    - Sesli Komutlar (Konuşma)                             ║
║    - Ekran Okuma ve Analiz                                ║
║    - Uygulama Kontrolu                                    ║
║    - Web Arama ve Bilgi                                   ║
║    - Dosya Yonetimi                                       ║
║    - Sistem Bilgisi                                       ║
║    - Oyun Baslatma                                        ║
║    - Not ve Hatirlatmalar                                 ║
║    - Clipboard Yonetimi                                   ║
║    - Pencere Kontrolu                                     ║
║    - Otomatik Hata Duzeltme                               ║
║    - AI Sohbet (Ollama)                                   ║
║    - ReAct Agent Loop                                     ║
║    - Multi-Step Task Planning                             ║
║    - Obsidian Auto Hafıza                                 ║
║    - Otonom Web Agent                                     ║
║    - Feedback Loop                                        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""

import os
import sys
import subprocess
import webbrowser
import time
import json
import re
import datetime
import threading
import tempfile
import ctypes
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# Obsidian Sınırsız Hafıza
try:
    from obsidian_memory import get_obsidian_memory
    OBSIDIAN_OK = True
except ImportError:
    OBSIDIAN_OK = False

# ANSI Renkler
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Moduller
try:
    import pyautogui
    PYAUTOGUI_OK = True
except:
    PYAUTOGUI_OK = False
    print("[SHADOWCAT] pyautogui kurulu degil - bazi ozellikler calismayabilir")

try:
    import pygetwindow as gw
    PYGETWINDOW_OK = True
except:
    PYGETWINDOW_OK = False

try:
    import psutil
    PSUTIL_OK = True
except:
    PSUTIL_OK = False

# Sistem Modu
class SystemMode(Enum):
    NORMAL = "normal"
    DEVELOPER = "developer"
    SILENT = "silent"
    GAME = "game"

# ===== SHADOWCAT BRAIN - ANA BEYIN =====
@dataclass
class ShadowcatBrain:
    """Shadowcat'nun ana beyin sistemi"""
    
    name: str = "Shadowcat"
    version: str = "2.0"
    owner: str = "ErCuM"
    mode: SystemMode = SystemMode.NORMAL
    
    # Durumlar
    listening: bool = False
    speaking: bool = False
    monitoring: bool = False
    
    # Konfigurasyon
    voice_enabled: bool = True
    auto_start: bool = False
    log_level: str = "INFO"
    
    # Istatistikler
    commands_executed: int = 0
    errors_fixed: int = 0
    uptime_start: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    # Komut gecmisi
    command_history: List[Dict] = field(default_factory=list)
    
    def get_uptime(self) -> str:
        """Calisma suresini hesapla"""
        now = datetime.datetime.now()
        delta = now - self.uptime_start
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}s {minutes}dk"
    
    def add_command(self, command: str, success: bool):
        """Komut gecmisine ekle"""
        self.command_history.append({
            'time': datetime.datetime.now().strftime("%H:%M:%S"),
            'command': command,
            'success': success
        })
        if len(self.command_history) > 100:
            self.command_history.pop(0)

# ===== SES SISTEMI =====
class ShadowcatVoice:
    """Sesli yanit sistemi"""
    
    def __init__(self, brain: ShadowcatBrain):
        self.brain = brain
        self.provider = 'pyttsx3'  # Offline secenek
        self.rate = 160
        self.volume = 1.0
        
        # TTS Modulleri
        self.engine = None
        self._init_tts()
    
    def _init_tts(self):
        """TTS modulu baslat"""
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            
            # Turkce ses sec
            for voice in voices:
                if 'tr' in voice.languages or 'Turkish' in voice.name:
                    self.engine.setProperty('voice', voice.id)
                    break
            
            self.engine.setProperty('rate', self.rate)
            self.engine.setProperty('volume', self.volume)
            print(f"[SHADOWCAT] Ses sistemi hazir: {self.provider}")
            
        except Exception as e:
            print(f"[SHADOWCAT] pyttsx3 kurulu degil, alternatif cozumler kullanilacak")
            self.provider = 'gtts'
    
    def speak(self, text: str):
        """Metni seslendir"""
        if not self.brain.voice_enabled:
            return
        
        self.brain.speaking = True
        print(f"{Colors.CYAN}[SHADOWCAT]: {text}{Colors.ENDC}")
        
        if self.provider == 'pyttsx3' and self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except:
                pass
        else:
            # gTTS varsa kullan
            try:
                from gtts import gTTS
                import tempfile
                import playsound
                
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                    temp_file = f.name
                
                tts = gTTS(text=text, lang='tr', slow=False)
                tts.save(temp_file)
                playsound.playsound(temp_file)
                os.unlink(temp_file)
            except:
                pass
        
        self.brain.speaking = False
    
    def greet(self):
        """Selamlama"""
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Gunaydin"
        elif hour < 18:
            greeting = "Iyi gunler"
        else:
            greeting = "Iyi aksamlar"
        
        self.speak(f"{greeting} efendim! Shadowcat AI hazir. Size nasil yardimci olabilirim?")

# ===== SISTEM KONTROL =====
class ShadowcatSystem:
    """Sistem kontrol fonksiyonlari"""
    
    def __init__(self, brain: ShadowcatBrain):
        self.brain = brain
        self._ocr_available = False
        self._check_ocr()
    
    def _check_ocr(self):
        """OCR modullerini kontrol et (guvenlik)"""
        try:
            import pytesseract
            import cv2
            self._ocr_available = True
            print("[SHADOWCAT] OCR hazir (lokal mod)")
        except ImportError:
            self._ocr_available = False
            print("[SHADOWCAT] OCR kurulu degil")
    
    def get_system_info(self) -> Dict:
        """Sistem bilgilerini al"""
        info = {
            'platform': sys.platform,
            'python_version': sys.version.split()[0],
            'hostname': os.environ.get('COMPUTERNAME', 'Unknown'),
            'username': os.environ.get('USERNAME', 'Unknown'),
        }
        
        if PSUTIL_OK:
            info.update({
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'battery': psutil.sensors_battery().percent if psutil.sensors_battery() else None,
            })
        
        return info
    
    def get_windows(self) -> List[Dict]:
        """Acik pencereleri listele"""
        if not PYGETWINDOW_OK:
            return []
        
        windows = []
        for win in gw.getAllWindows():
            if win.title:
                windows.append({
                    'title': win.title,
                    'x': win.left,
                    'y': win.top,
                    'width': win.width,
                    'height': win.height,
                    'visible': win.isMinimized == False
                })
        return windows
    
    def get_active_window(self) -> Optional[Dict]:
        """Aktif pencereyi al"""
        if not PYGETWINDOW_OK:
            return None
        
        try:
            win = gw.getActiveWindow()
            if win:
                return {
                    'title': win.title,
                    'process': win.title.split('-')[-1].strip() if '-' in win.title else win.title
                }
        except:
            pass
        return None
    
    def take_screenshot(self, save_path: str = None) -> str:
        """Ekran goruntusu al"""
        if not PYAUTOGUI_OK:
            return "[HATA] pyautogui kurulu degil"
        
        if save_path is None:
            desktop = Path(os.path.expanduser("~")) / "Desktop"
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(desktop / f"glassescat_screenshot_{timestamp}.png")
        
        try:
            img = pyautogui.screenshot()
            img.save(save_path)
            return save_path
        except Exception as e:
            return f"[HATA] {str(e)}"
    
    def get_mouse_position(self) -> tuple:
        """Mouse pozisyonunu al"""
        if PYAUTOGUI_OK:
            return pyautogui.position()
        return (0, 0)
    
    def get_clipboard(self) -> str:
        """Panodaki veriyi al"""
        try:
            import pyperclip
            return pyperclip.paste()
        except:
            return ""
    
    def set_clipboard(self, text: str):
        """Panoya veri koy"""
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except:
            return False

# ===== UYGULAMA KONTROL =====
class GlassescatApps:
    """Uygulama baslatma ve kontrol"""
    
    # Bilinen uygulama yollari
    APP_PATHS = {
        'chrome': r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        'firefox': r"C:\Program Files\Mozilla Firefox\firefox.exe",
        'vscode': r"C:\Users\ErCuM\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        'discord': r"C:\Users\ErCuM\AppData\Local\Discord\Update.exe",
        'spotify': r"C:\Users\ErCuM\AppData\Roaming\Spotify\Spotify.exe",
        'steam': r"C:\Program Files (x86)\Steam\steam.exe",
        'notepad': r"C:\Windows\System32\notepad.exe",
        'cmd': r"C:\Windows\System32\cmd.exe",
        'powershell': r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        'explorer': r"C:\Windows\explorer.exe",
        'taskmgr': r"C:\Windows\System32\taskmgr.exe",
        'control': r"C:\Windows\System32\control.exe",
        'telegram': r"C:\Users\ErCuM\AppData\Roaming\Telegram Desktop\Telegram.exe",
        'whatsapp': r"%LocalAppData%\WhatsApp\WhatsApp.exe",
        'teams': r"%AppData%\Microsoft\Teams\Update.exe",
        'obs': r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
        'prism': r"C:\Users\ErCuM\AppData\Roaming\PrismLauncher\installed.txt",
        'minecraft': r"%AppData%\.minecraft",
    }
    
    GAMES = {
        'minecraft': r"C:\Users\ErCuM\AppData\Roaming\.minecraft\TlauncherProfiles.json",
        'valorant': r"C:\Riot Games\Valorant\VALORANT.exe",
        'csgo': r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\csgo.exe",
        'gta': r"C:\Program Files\Rockstar Games\Grand Theft Auto V\GTAV.exe",
        'fortnite': r"C:\Program Files\Epic Games\Fortnite\FortniteGame\Binaries\Win64\FortniteLauncher.exe",
        'apex': r"C:\Program Files\EA Games\Apex Legends\Legacy\Cfg\R5Apex.exe",
        'genshin': r"C:\Program Files\Genshin Impact\Genshin Impact Game\YuanShen.exe",
    }
    
    SITE_SEARCH_URLS = {
        'youtube': ('https://www.youtube.com/results?search_query=', 'https://www.youtube.com'),
        'google': ('https://www.google.com/search?q=', 'https://www.google.com'),
        'instagram': ('https://www.instagram.com/explore/tags/', 'https://www.instagram.com'),
        'twitter': ('https://twitter.com/search?q=', 'https://twitter.com'),
        'x': ('https://x.com/search?q=', 'https://x.com'),
        'facebook': ('https://www.facebook.com/search/top?q=', 'https://www.facebook.com'),
        'amazon': ('https://www.amazon.com/s?k=', 'https://www.amazon.com'),
        'github': ('https://github.com/search?q=', 'https://github.com'),
        'wikipedia': ('https://en.wikipedia.org/wiki/', 'https://en.wikipedia.org'),
        'reddit': ('https://www.reddit.com/search/?q=', 'https://www.reddit.com'),
        'linkedin': ('https://www.linkedin.com/search/results/all/?keywords=', 'https://www.linkedin.com'),
        'pinterest': ('https://www.pinterest.com/search/pins/?q=', 'https://www.pinterest.com'),
        'tiktok': ('https://www.tiktok.com/search?q=', 'https://www.tiktok.com'),
        'netflix': ('https://www.netflix.com/search?q=', 'https://www.netflix.com'),
        'spotify': ('https://open.spotify.com/search/', 'https://open.spotify.com'),
        'steam': ('https://store.steampowered.com/search/?term=', 'https://store.steampowered.com'),
        'imdb': ('https://www.imdb.com/find?q=', 'https://www.imdb.com'),
        'wikipedi': ('https://en.wikipedia.org/wiki/', 'https://en.wikipedia.org'),
        'ekşi': ('https://eksisozluk.com/?q=', 'https://eksisozluk.com'),
        'eksisozluk': ('https://eksisozluk.com/?q=', 'https://eksisozluk.com'),
        'sahibinden': ('https://www.sahibinden.com/kategori?query_text=', 'https://www.sahibinden.com'),
        'trendyol': ('https://www.trendyol.com/sr?q=', 'https://www.trendyol.com'),
        'hepsiburada': ('https://www.hepsiburada.com/ara?q=', 'https://www.hepsiburada.com'),
    }
    
    @staticmethod
    def search_windows_app(app_name: str) -> Optional[str]:
        """Windows sisteminde uygulama ara (exe, lnk, webapps dahil)"""
        common_paths = [
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            os.path.expandvars(r"%LocalAppData%"),
            os.path.expandvars(r"%AppData%"),
            r"C:\Users\ErCuM\AppData\Local",
            r"C:\Users\ErCuM\AppData\Roaming",
        ]
        
        app_lower = app_name.lower()
        extensions = ('.exe', '.lnk', '.bat', '.cmd', '.url')
        
        for base_path in common_paths:
            if not os.path.exists(base_path):
                continue
            
            try:
                for root, dirs, files in os.walk(base_path):
                    for file in files:
                        if app_lower in file.lower() and file.lower().endswith(extensions):
                            full_path = os.path.join(root, file)
                            return full_path
            except:
                continue
        
        return None
    
    @staticmethod
    def search_windows_start_menu(app_name: str) -> Optional[str]:
        """Windows Start Menu ve baslat menusunde uygulama ara (PWA/WebApp dahil)"""
        app_lower = app_name.lower()
        
        start_menu_paths = [
            os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%LocalAppData%\Microsoft\Windows\Start Menu\Programs"),
        ]
        
        for base_path in start_menu_paths:
            if not os.path.exists(base_path):
                continue
            try:
                for root, dirs, files in os.walk(base_path):
                    for file in files:
                        if app_lower in file.lower().replace('.lnk', '').replace('.url', ''):
                            full_path = os.path.join(root, file)
                            return full_path
            except:
                continue
        
        return None
    
    @staticmethod
    def search_windows_apps_folder(app_name: str) -> Optional[str]:
        """Windows Apps klasorunde (AppX/PWA) uygulama ara"""
        app_lower = app_name.lower()
        
        chrome_webapps = os.path.expandvars(r"%LocalAppData%\Google\Chrome\User Data\Default\Web Applications")
        edge_webapps = os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\User Data\Default\Web Applications")
        
        for webapp_path in [chrome_webapps, edge_webapps]:
            if not os.path.exists(webapp_path):
                continue
            try:
                for root, dirs, files in os.walk(webapp_path):
                    for dir_name in dirs:
                        if app_lower in dir_name.lower():
                            config_path = os.path.join(root, dir_name)
                            
                            for f in os.listdir(config_path):
                                if f.lower().endswith(('.lnk', '.url')):
                                    return os.path.join(config_path, f)
                            
                            return config_path
                    
                    for file in files:
                        if app_lower in file.lower() and file.lower().endswith(('.lnk', '.url')):
                            return os.path.join(root, file)
            except:
                continue
        
        return None
    
    @staticmethod
    def search_with_powershell(app_name: str) -> Optional[str]:
        """Start menu uygulamalari ve AppX paketleri icin PowerShell ile ara"""
        app_escaped = app_name.replace("'", "''")
        script = f"""
        [Console]::OutputEncoding = [Text.Encoding]::UTF8
        $apps = Get-StartApps | Where-Object {{ $_.Name -like '*{app_escaped}*' }}
        if ($apps) {{
            $app = $apps | Select-Object -First 1
            $app.AppId
        }}
        """
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', script],
                capture_output=True, timeout=15
            )
            output = result.stdout.decode('utf-8', errors='replace').strip()
            if output:
                return f"shell:AppsFolder\\{output}"
        except:
            pass
        return None
    
    @staticmethod
    def search_with_powershell(app_name: str) -> Optional[str]:
        """Start menu uygulamalari ve AppX paketleri icin PowerShell ile ara"""
        app_escaped = app_name.replace("'", "''")
        script = f"""
        $apps = Get-StartApps | Where-Object {{ $_.Name -like '*{app_escaped}*' }}
        if ($apps) {{
            $app = $apps | Select-Object -First 1
            $app.AppId
        }}
        """
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', script],
                capture_output=True, timeout=15
            )
            output = result.stdout.decode('utf-8', errors='replace').strip()
            if output and not output.startswith('?'):
                return f"shell:AppsFolder\\{output}"
        except:
            pass
        return None
    
    @staticmethod
    def list_start_menu_apps(app_name: str) -> List[Dict]:
        """Start Menu'de eslesen tum uygulamalari listele (PWA/WebApp dahil)"""
        app_escaped = app_name.replace("'", "''")
        script = f"""
        $apps = Get-StartApps | Where-Object {{ $_.Name -like '*{app_escaped}*' }}
        if ($apps) {{
            $apps | ForEach-Object {{ Write-Output ($_.Name + '||' + $_.AppId) }}
        }}
        """
        results = []
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', script],
                capture_output=True, timeout=15
            )
            raw = result.stdout.decode('utf-8', errors='replace')
            for line in raw.strip().split('\n'):
                line = line.strip().strip('\0').strip()
                if '||' in line:
                    parts = line.split('||', 1)
                    name = parts[0].strip()
                    app_id = parts[1].strip()
                    if app_id and not app_id.startswith('?'):
                        results.append({'name': name, 'app_id': app_id})
        except:
            pass
        return results
    
    @staticmethod
    def open_start_menu_search(app_name: str) -> Dict:
        """Windows Start Menu'yu ac ve arama kutusuna yaz"""
        if PYAUTOGUI_OK:
            try:
                pyautogui.hotkey('win')
                time.sleep(0.5)
                pyautogui.write(app_name, interval=0.05)
                return {'success': True, 'message': f"Start Menu'de '{app_name}' araniyor"}
            except Exception as e:
                return {'success': False, 'message': str(e)}
        return {'success': False, 'message': 'pyautogui kurulu degil'}

    @staticmethod
    def search_windows_with_start(app_name: str) -> Dict:
        """Windows Start Menu aramasini kullan (Win+Q + yaz)"""
        if PYAUTOGUI_OK:
            try:
                pyautogui.hotkey('win', 'q')
                time.sleep(0.5)
                pyautogui.write(app_name, interval=0.05)
                return {'success': True, 'message': f"Start Menu'de '{app_name}' araniyor"}
            except Exception as e:
                return {'success': False, 'message': str(e)}
        return {'success': False, 'message': 'pyautogui kurulu degil'}
    
    @staticmethod
    def open_app(app_name: str) -> Dict:
        """Uygulama ac (exe, lnk, PWA/WebApp destegi ile)"""
        app_name_clean = app_name.strip()
        app_name_clean = re.sub(r'\s+(ac|a[cç]|baslat|a[cç])$', '', app_name_clean, flags=re.IGNORECASE)
        app_name_clean = re.sub(r'^(ac|a[cç]|baslat|a[cç])\s+', '', app_name_clean, flags=re.IGNORECASE)
        
        app_lower = app_name_clean.lower().replace(' ', '')
        
        # Dogrudan yol kontrolu
        if app_lower in GlassescatApps.APP_PATHS:
            path = GlassescatApps.APP_PATHS[app_lower]
            expanded = os.path.expandvars(path)
            if os.path.exists(expanded):
                try:
                    subprocess.Popen(f'"{expanded}"')
                    return {'success': True, 'message': f"{app_name} baslatildi", 'path': expanded}
                except Exception as e:
                    return {'success': False, 'message': str(e)}
        
        # Sistem yolundan ara (where komutu)
        try:
            result = subprocess.run(['where', '/r', 'C:\\', app_lower + '.exe'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip().split('\n')[0]
                subprocess.Popen(f'"{path}"')
                return {'success': True, 'message': f"{app_name} bulundu ve baslatildi", 'path': path}
        except:
            pass
        
        # Windows'ta ara (klasor tarama - exe + lnk)
        found_path = GlassescatApps.search_windows_app(app_lower)
        if found_path:
            try:
                if found_path.lower().endswith('.lnk'):
                    os.startfile(found_path)
                else:
                    subprocess.Popen(f'"{found_path}"')
                return {'success': True, 'message': f"{app_name} Windows'ta bulundu ve baslatildi", 'path': found_path}
            except Exception as e:
                return {'success': False, 'message': str(e)}
        
        # Start Menu kisa yollarinda ara (PWA/WebApp icin)
        found_shortcut = GlassescatApps.search_windows_start_menu(app_lower)
        if found_shortcut:
            try:
                os.startfile(found_shortcut)
                return {'success': True, 'message': f"{app_name} baslatildi (WebApp)", 'path': found_shortcut}
            except Exception as e:
                return {'success': False, 'message': str(e)}
        
        # Chrome/Edge WebApps klasorunde ara
        found_webapp = GlassescatApps.search_windows_apps_folder(app_lower)
        if found_webapp:
            try:
                if found_webapp.lower().endswith(('.lnk', '.url')):
                    os.startfile(found_webapp)
                else:
                    subprocess.Popen(f'explorer "{found_webapp}"')
                return {'success': True, 'message': f"{app_name} WebApp olarak baslatildi", 'path': found_webapp}
            except Exception as e:
                return {'success': False, 'message': str(e)}
        
        # PowerShell ile AppX/StartApps ara
        ps_result = GlassescatApps.search_with_powershell(app_lower)
        if ps_result:
            try:
                subprocess.Popen(['explorer', ps_result])
                return {'success': True, 'message': f"{app_name} baslatildi (Windows App)", 'path': ps_result}
            except Exception as e:
                return {'success': False, 'message': str(e)}
        
        # Son cares: Start Menu'yu ac ve aramayi goster
        GlassescatApps.open_start_menu_search(app_name)
        
        # start komutu ile dene (Windows'un kendi aramasini kullan)
        try:
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            return {'success': True, 'message': f"{app_name} Start Menu'de araniyor...", 'search_web': True}
        except Exception as e:
            pass
        
        return {
            'success': False, 
            'message': f"{app_name} bulunamadi. Web'de aramak ister misin?",
            'search_query': app_name
        }
    
    @staticmethod
    def open_url(url: str) -> Dict:
        """URL ac"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            webbrowser.open(url)
            return {'success': True, 'message': f"URL acildi: {url}"}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def search_web(query: str) -> Dict:
        """Web'de ara"""
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return GlassescatApps.open_url(search_url)
    
    @staticmethod
    def search_on_site(site: str, query: str) -> Dict:
        """Belirli bir sitede ara (ornek: youtube'da Mavislime ara)"""
        site_lower = site.lower().strip().strip("'")
        query_encoded = query.replace(' ', '+')
        
        known_sites = GlassescatApps.SITE_SEARCH_URLS
        for key, (search_url, base_url) in known_sites.items():
            if key == site_lower or site_lower.startswith(key) or key.startswith(site_lower):
                full_url = search_url + query_encoded
                return GlassescatApps.open_url(full_url)
        
        full_url = f"https://www.google.com/search?q=site:{site_lower}+{query_encoded}"
        return GlassescatApps.open_url(full_url)
    
    @staticmethod
    def open_site(site: str) -> Dict:
        """Siteyi ac (ornek: youtube'a gir)"""
        site_lower = site.lower().strip().strip("'")
        
        known_sites = GlassescatApps.SITE_SEARCH_URLS
        for key, (search_url, base_url) in known_sites.items():
            if key == site_lower or site_lower.startswith(key) or key.startswith(site_lower):
                return GlassescatApps.open_url(base_url)
        
        return GlassescatApps.open_url(f"https://www.{site_lower}.com")
    
    @staticmethod
    def search_app_for_download(app_name: str) -> List[Dict]:
        """Web'de uygulama ara - DuckDuckGo Lite kullanir, reklamlari filtreler"""
        query = f"{app_name} download"
        
        ad_keywords = ['ads', 'sponsored', 'adclick', 'doubleclick', 'marketing', 'adservice',
                      'tracking', 'analytics', 'googlead', 'amazon-adsystem', 'scorecardresearch']
        
        results = []
        seen_urls = set()
        
        try:
            import requests as req
            resp = req.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": query},
                timeout=15,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            if resp.status_code != 200:
                return results
            
            html = resp.text
            
            for match in re.finditer(
                r'<a[^>]*href=["\'](https?://[^"\']+)["\'][^>]*>(?:<[^>]+>)*([^<]*)',
                html, re.IGNORECASE
            ):
                url = match.group(1).strip()
                title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                
                is_ad = any(kw in url.lower() for kw in ad_keywords)
                if is_ad:
                    continue
                
                if url and url not in seen_urls and not url.startswith('//'):
                    seen_urls.add(url)
                    results.append({'title': title or url, 'url': url, 'snippet': ''})
            
            return results[:20]
        
        except:
            return results
    
    @staticmethod
    def download_file(url: str, save_dir: str = None) -> Dict:
        """Dosya indir ve kaydet"""
        if save_dir is None:
            save_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        
        os.makedirs(save_dir, exist_ok=True)
        
        try:
            filename = url.split('/')[-1].split('?')[0]
            if not filename or '.' not in filename:
                filename = f"download_{int(time.time())}.exe"
            
            save_path = os.path.join(save_dir, filename)
            
            print(f"[SHADOWCAT] Indiriliyor: {url}")
            import requests as req
            response = req.get(url, stream=True, timeout=30, 
                             headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            
            if response.status_code == 200:
                total = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            percent = downloaded * 100 // total
                            print(f"\r[SHADOWCAT] Indirme: %{percent}", end='')
                
                print(f"\r[SHADOWCAT] Indirme tamam: {filename}")
                return {'success': True, 'path': save_path, 'filename': filename}
            else:
                return {'success': False, 'message': f"HTTP {response.status_code}"}
        
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def find_download_links(url: str) -> List[Dict]:
        """Sayfadaki indirme linklerini bul (reklamlari filtreler)"""
        import requests as req
        from urllib.parse import urljoin
        
        ad_keywords = ['ads', 'sponsored', 'adclick', 'doubleclick', 'marketing', 'adservice',
                      'tracking', 'analytics', 'googlead', 'amazon-adsystem', 'scorecardresearch',
                      'googlesyndication', 'googleadservices', 'facebook.com/tr']
        
        try:
            response = req.get(url, timeout=15, 
                             headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            if response.status_code != 200:
                return []
            
            html = response.text
            links = []
            download_keywords = ['download', 'indir', '.exe', '.msi', '.zip', '.dmg', 
                               '.apk', 'setup', 'installer', 'latest', 'release']
            
            for match in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html, re.IGNORECASE):
                href = match.group(1).strip()
                text = match.group(2).strip()
                full_url = urljoin(url, href)
                
                is_ad = any(kw in full_url.lower() for kw in ad_keywords)
                if is_ad:
                    continue
                
                link_text = (text + ' ' + href).lower()
                if any(kw in link_text for kw in download_keywords):
                    links.append({'url': full_url, 'text': text or href})
            
            return links[:10]
        
        except:
            return []

# ===== DOSYA YONETIMI =====
class ShadowcatFiles:
    """Dosya ve klasor islemleri"""
    
    @staticmethod
    def create_file(path: str, content: str = "") -> Dict:
        """Dosya olustur"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {'success': True, 'message': f"Dosya olusturuldu: {path}"}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def read_file(path: str) -> Dict:
        """Dosya oku"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {'success': True, 'content': content, 'message': "Dosya okundu"}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def list_directory(path: str = ".") -> Dict:
        """Klasor icerigini listele"""
        try:
            items = os.listdir(path)
            result = []
            for item in items:
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path)
                result.append({
                    'name': item,
                    'type': 'folder' if is_dir else 'file',
                    'size': os.path.getsize(full_path) if not is_dir else 0
                })
            return {'success': True, 'items': result, 'message': f"{len(result)} oge bulundu"}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def open_in_explorer(path: str):
        """Dosyayi Windows Explorer'da ac"""
        try:
            subprocess.Popen(f'explorer /select,"{path}"')
            return {'success': True, 'message': f"Explorer'da gosteriliyor: {path}"}
        except Exception as e:
            return {'success': False, 'message': str(e)}

# ===== NOT VE HATIRLATMA =====
class GlassescatNotes:
    """Not ve hatirlatma sistemi - Obsidian Sınırsız Hafıza ile"""
    
    NOTES_FILE = "glassescat_notes.txt"
    REMINDERS_FILE = "glassescat_reminders.json"
    
    @staticmethod
    def _get_obsidian():
        """ObsidianMemory instance'ini al"""
        if OBSIDIAN_OK:
            try:
                return get_obsidian_memory()
            except:
                pass
        return None
    
    @staticmethod
    def add_note(text: str) -> Dict:
        """Not ekle - Obsidian .md olarak kaydeder (sınırsız)"""
        try:
            obsidian = GlassescatNotes._get_obsidian()
            if obsidian:
                obsidian.save_memory(
                    title=f"Not - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    content=text,
                    tags=['note', 'quick-note']
                )
                return {'success': True, 'message': "Not kaydedildi (Obsidian - sınırsız)"}
            
            # Fallback: eski sistem
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(GlassescatNotes.NOTES_FILE, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {text}\n")
            return {'success': True, 'message': "Not kaydedildi"}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def get_notes(limit: int = 10) -> List[str]:
        """Notlari getir - Obsidian'dan oku (sınırsız)"""
        try:
            obsidian = GlassescatNotes._get_obsidian()
            if obsidian:
                recent = obsidian.recall_recent(limit=limit)
                notes = []
                for r in recent:
                    preview = r['content_preview'].split('---')[0].strip()[:100]
                    notes.append(f"[{r['type']}] [[{r['path']}]]: {preview}")
                return notes if notes else ["Henüz not yok"]
            
            # Fallback
            if os.path.exists(GlassescatNotes.NOTES_FILE):
                with open(GlassescatNotes.NOTES_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                return [l.strip() for l in lines[-limit:]]
            return []
        except:
            return []
    
    @staticmethod
    def search_notes(query: str) -> List[Dict]:
        """Tüm notlarda sınırsız arama"""
        obsidian = GlassescatNotes._get_obsidian()
        if obsidian:
            return obsidian.recall(query)
        return []
    
    @staticmethod
    def add_reminder(text: str, minutes: int) -> Dict:
        """Hatirlatma ekle"""
        try:
            obsidian = GlassescatNotes._get_obsidian()
            if obsidian:
                reminder_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
                obsidian.save_memory(
                    title=f"Hatırlatma: {text}",
                    content=f"**Hatırlatma Zamanı:** {reminder_time.strftime('%Y-%m-%d %H:%M')}\n\n{text}",
                    tags=['reminder', 'hatirlatma'],
                    metadata={'reminder_time': reminder_time.isoformat(), 'minutes': minutes}
                )
                return {'success': True, 'message': f"{minutes} dakika sonra hatirlatilacak: {text}"}
            
            # Fallback
            reminder_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            reminder = {
                'text': text,
                'time': reminder_time.isoformat(),
                'created': datetime.datetime.now().isoformat()
            }
            
            reminders = []
            if os.path.exists(GlassescatNotes.REMINDERS_FILE):
                with open(GlassescatNotes.REMINDERS_FILE, 'r') as f:
                    reminders = json.load(f)
            
            reminders.append(reminder)
            
            with open(GlassescatNotes.REMINDERS_FILE, 'w') as f:
                json.dump(reminders, f, indent=2)
            
            return {'success': True, 'message': f"{minutes} dakika sonra hatirlatilacak: {text}"}
        except Exception as e:
            return {'success': False, 'message': str(e)}

# ===== AI ENTEGRASYONU =====
class GlassescatAI:
    """AI sohbet sistemi (Ollama - X_OPUS serisi)"""
    
    OLLAMA_URL = "http://localhost:11434/api/generate"
    DEFAULT_MODEL = "glassesglitchstudio/x_opus:V1_X_OPUS"
    ALT_MODEL = "glassesglitchstudio/glitch_opus:X_GLITCH_OPUS"
    
    @staticmethod
    def chat(message: str, model: str = None) -> Dict:
        """AI ile sohbet et"""
        if model is None:
            model = GlassescatAI.DEFAULT_MODEL
        
        try:
            import requests
            payload = {
                "model": model,
                "prompt": message,
                "stream": False
            }
            
            response = requests.post(GlassescatAI.OLLAMA_URL, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'response': result.get('response', ''),
                    'model': model
                }
            else:
                return {'success': False, 'message': f"Ollama hatasi: {response.status_code}"}
        
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': "Ollama sunucusuna baglanilamadi. Lutfen Ollama'yi baslatin."}
        except Exception as e:
            return {'success': False, 'message': str(e)}

# ===== MOUSE/KEYBOARD KONTROL =====
class ShadowcatControl:
    """Klavye ve mouse kontrol"""
    
    @staticmethod
    def find_text_on_screen(text: str) -> Optional[tuple]:
        """Ekran goruntusunde metin ara (OCR)"""
        if not PYAUTOGUI_OK:
            return None
        
        try:
            import pytesseract
            import cv2
            import numpy as np
            
            # Ekran goruntusu al
            screenshot = pyautogui.screenshot()
            screenshot_np = np.array(screenshot)
            screenshot_bgr = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY)
            
            # Metni oku
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
            
            # Metni bul
            n_boxes = len(data['text'])
            for i in range(n_boxes):
                if data['text'][i].strip().lower() == text.lower():
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    return (x, y)
            
            # Kismi eslesme
            for i in range(n_boxes):
                if text.lower() in data['text'][i].lower():
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    return (x, y)
            
            return None
            
        except ImportError:
            return None
        except Exception:
            return None
    
    @staticmethod
    def mouse_click(x: int = None, y: int = None, button: str = 'left') -> Dict:
        """Mouse tikla"""
        if not PYAUTOGUI_OK:
            return {'success': False, 'message': 'pyautogui kurulu degil'}
        
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
            else:
                pyautogui.click(button=button)
            return {'success': True, 'message': f'Tiklandi ({x}, {y})' if x else 'Tiklandi'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def mouse_move(x: int, y: int, duration: float = 0.5) -> Dict:
        """Mouse hareket ettir"""
        if not PYAUTOGUI_OK:
            return {'success': False, 'message': 'pyautogui kurulu degil'}
        
        try:
            pyautogui.moveTo(x, y, duration=duration)
            return {'success': True, 'message': f'Mouse ({x}, {y}) konumuna tasindi'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def type_text(text: str, interval: float = 0.05) -> Dict:
        """Metin yaz"""
        if not PYAUTOGUI_OK:
            return {'success': False, 'message': 'pyautogui kurulu degil'}
        
        try:
            pyautogui.write(text, interval=interval)
            return {'success': True, 'message': f'Yazildi: {text}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def hotkey(*keys) -> Dict:
        """Kisa yol tuşlari"""
        if not PYAUTOGUI_OK:
            return {'success': False, 'message': 'pyautogui kurulu degil'}
        
        try:
            pyautogui.hotkey(*keys)
            return {'success': True, 'message': f'Kisa yol calisti: {"+".join(keys)}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

# ===== ANA SHADOWCAT SINIFI =====
class GlassescatAgent:
    """
    Shadowcat AI - Hermes Tarzi PC Ajani
    Ana sinif - tum alt sistemleri birlestirir
    """
    
    def __init__(self):
        print(f"{Colors.CYAN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.CYAN}  SHADOWCAT v2.0 - PC AJANI{' '*28}{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.ENDC}")
        
        # Alt sistemler
        self.brain = ShadowcatBrain()
        self.voice = ShadowcatVoice(self.brain)
        self.system = ShadowcatSystem(self.brain)
        self.apps = GlassescatApps
        self.files = ShadowcatFiles
        self.notes = GlassescatNotes
        self.ai = GlassescatAI
        self.control = ShadowcatControl
        
        # Komutlar
        self.commands = self._build_commands()
        
        print(f"{Colors.GREEN}[SHADOWCAT] Sistem hazir!{Colors.ENDC}\n")
    
    def _build_commands(self) -> Dict:
        """Komut sozlugunu olustur"""
        return {
            # Sistem
            r'sistem bilgi|sistem durumu|system info': self.cmd_system_info,
            r'ses kapa|sessiz|volume off': self.cmd_mute,
            r'ses ac|speaker on': self.cmd_unmute,
            r'ekran goruntusu|screenshot': self.cmd_screenshot,
            
            # Uygulamalar - acik ve kisayol komutlar
            r'^(ac|a[cç])\s+(.+)$': self.cmd_open_app,
            r'^(baslat)\s+(.+)$': self.cmd_open_app,
            r'^(calistir)\s+(.+)$': self.cmd_open_app,
            r'^(baslatma)\s+(.+)$': self.cmd_open_app,
            r'^(baslatalim)\s+(.+)$': self.cmd_open_app,
            r'^(calisma)\s+(.+)$': self.cmd_open_app,
            r'^(ac?alim?)\s+(.+)$': self.cmd_open_app,
            # "chrome ac", "chrome baslat" gibi kalip
            r'^(.+?)\s+(a[cç]|ac|baslat|calistir|a[cç]alim|baslatalim)$': self.cmd_open_app_reverse,
            r'kapat|close|exit': self.cmd_close_app,
            r'ara\s+(.+)|search\s+(.+)|google\s+(.+)': self.cmd_search,
            r'(?:uygulama\s+)?(ara|bul|search)\s+(?:uygulama\s+)?(.+)': self.cmd_search_app,
            r'youtube\s+(.+)': self.cmd_youtube,
            r'web sitesi\s+(.+)': self.cmd_open_url,
            
            # Site komutlari - "youtube'a gir Mavislime ara", "google'da Python ara" vb
            r'(youtube|instagram|twitter|x|facebook|google|amazon|github|wikipedia|reddit|linkedin|pinterest|tiktok|netflix|spotify|steam|imdb|eksi|eksisozluk|sahibinden|trendyol|hepsiburada|wikipedi)(?:\'|[\']?)(?:a|e|ya|ye|na|ne|da|de|ta|te)\s+gir\s+(?:ve\s+)?(?:ara|bul|yaz|ac)\s+(.+)': self.cmd_site_search,
            r'(youtube|instagram|twitter|x|facebook|google|amazon|github|wikipedia|reddit|linkedin|pinterest|tiktok|netflix|spotify|steam|imdb|eksi|eksisozluk|sahibinden|trendyol|hepsiburada|wikipedi)(?:\'|[\']?)(?:da|de|ta|te|ya|ye|a|e|na|ne)\s+(?:ara|bul|yaz|ac)\s+(.+)': self.cmd_site_search,
            r'(youtube|instagram|twitter|x|facebook|google|amazon|github|wikipedia|reddit|linkedin|pinterest|tiktok|netflix|spotify|steam|imdb|eksi|eksisozluk|sahibinden|trendyol|hepsiburada|wikipedi)(?:\'|[\']?)(?:a|e|ya|ye|na|ne|da|de|ta|te)\s+gir$': self.cmd_site_open,
            r'siteye\s+gir\s+(.+)': self.cmd_site_open,
            
            # Indirme komutu - "gdevelop 5 indir", "gdevelop 5 sitesine gidip indir"
            r'^(.+?)\s+sitesine\s+gidip\s+indir$': self.cmd_download_app,
            r'^(.+?)\s+(?:indir|download)\s+(?:et|yap)?$': self.cmd_download_app,
            r'^(?:indir|download)\s+(.+)$': self.cmd_download_app,
            
            # Dosyalar
            r'dosya olustur|new file|dosya olur': self.cmd_create_file,
            r'not al|not ekle|add note': self.cmd_add_note,
            r'notlarim|notes|goruntuler': self.cmd_show_notes,
            r'hazirla (.+) dakika': self.cmd_remind,
            r'(?:hafiza|hafıza|hatirla|hatırla|recall|gecmis|geçmiş|ara)\s+(.+)': self.cmd_recall,
            r'hafiza(dan|da)\s+ara\s+(.+)': self.cmd_recall,
            r'(?:hafiza|memory)\s*(?:durum|status|stats|istatistik)': self.cmd_memory_stats,
            
            # AI
            r'sor (.+)|问 (.+)| سؤال (.+)': self.cmd_ai_chat,
            r'ne dusunuyorsun|nefis|what do you think': self.cmd_think,
            
            # Mouse/Klavye
            r'tikla (.+)|click (.+)': self.cmd_mouse_click,
            r'bul ve tikla|bul ve tikla|find and click|find_text': self.cmd_find_and_click,
            r'tasima|move|move to (.+)': self.cmd_mouse_move,
            r'yaz (.+)|type (.+)': self.cmd_type_text,
            r'sec|select|选中': self.cmd_select,
            
            # Pencere
            r'pencere|window': self.cmd_window_info,
            r'kucult|minimize': self.cmd_minimize,
            r'buyut|maximize': self.cmd_maximize,
            
            # Bilgi
            r'saat kac|time|saat': self.cmd_time,
            r'tarih ne|date|bugun': self.cmd_date,
            r'hava durumu|weather': self.cmd_weather,
            r'ping|network': self.cmd_network,
            
            # GELISMIS OZELLIKLER
            
            # Masaustu temizle
            r'(?:masaustu(?:n[uv]|nu)?|desktop)\s*(?:temizle|duzenle|düzenle|topla|organize)': self.cmd_clean_desktop,
            r'(?:temizle|duzenle|düzenle)\s*(?:masaustu(?:n[uv]|nu)?|desktop)': self.cmd_clean_desktop,
            
            # Gecici dosyalari temizle
            r'(?:gecici|temp|önbellek|oneellek|cache)\s*(?:dosya|file)?\s*(?:temizle|sil)': self.cmd_clean_temp,
            r'(?:temizle|sil)\s*(?:gecici|temp|önbellek|oneellek|cache)': self.cmd_clean_temp,
            r'sistem temizligi|disk temizligi|clean system': self.cmd_clean_temp,
            
            # Toplu dosya islemleri
            r'toplu\s+(?:yeniden\s+)?adlandir|toplu\s+rename|rename\s+all|hepsini\s+(?:yeniden\s+)?adlandir': self.cmd_bulk_rename,
            r'toplu\s+(?:donustur|cevir|dönüştür|çevir)\s+(\w+)\s*(?:->|=>|to|dan)\s*(\w+)': self.cmd_bulk_convert,
            r'(?:donustur|cevir|dönüştür|çevir)\s+(\w+)\s*(?:->|=>|to)\s*(\w+)': self.cmd_bulk_convert,
            
            # Klasor izleme
            r'(?:klas(?:o|ö)r|folder|dizin)\s*(?:izle|gözlemle|takip|watch|monitor)\s+(.+)': self.cmd_watch_folder,
            r'(?:izleme|watcher|monitor)\s*(?:dur|kapa|durdur|stop)': self.cmd_stop_watch,
            
            # Kisayol olustur
            r'(?:kisayol|shortcut|kısayol)\s*(?:olustur|oluştur|yap|create)\s+(.+?)(?:\s*(?:->|=>|to|ic|iç|e|a)\s+(.+))?$': self.cmd_create_shortcut,
            
            # Yedekleme
            r'(?:yedek|backup|yede[gğ]i)\s*(?:al|olustur|oluştur|yap)\s+(.+)': self.cmd_backup,
            r'(?:yedek|backup|yede[gğ]i)\s*(?:geri|yukle|yükle|yukl|restore)\s+(.+)': self.cmd_restore,
            
            # Sistem monitor
            r'(?:sistem|system)\s*(?:monitor|monitör|izle|gözlemle)\s*(?:baslat|başlat|ac|aç|start)?': self.cmd_monitor_start,
            r'(?:monitor|monitör|izleme)\s*(?:dur|kapa|durdur|stop)': self.cmd_monitor_stop,
            r'(?:sistem|system)\s*(?:durum|status|rapor|report)': self.cmd_system_report,
            
            # Kontrol
            r'dur|stop|exit|cikis': self.cmd_exit,
            r'yardim|help|help me|komutlar': self.cmd_help,
            r'mod degistir|mode': self.cmd_change_mode,
        }
    
    # ===== KOMUTLAR =====
    
    def cmd_system_info(self, match) -> str:
        info = self.system.get_system_info()
        response = f"""
{Colors.BOLD}SISTEM BILGILERI{Colors.ENDC}
-------------------------
Bilgisayar: {info.get('hostname', '?')}
Kullanici: {info.get('username', '?')}
Platform: {info.get('platform', '?')}
Python: {info.get('python_version', '?')}
"""
        if PSUTIL_OK:
            response += f"""
CPU: %{info.get('cpu_percent', 0)}
RAM: %{info.get('memory_percent', 0)}
Disk: %{info.get('disk_percent', 0)}
"""
        if info.get('battery'):
            response += f"Pil: %{info.get('battery')}\n"
        
        response += f"\nCalisma suresi: {self.brain.get_uptime()}\n"
        response += f"Calistirilan komut: {self.brain.commands_executed}"
        
        return response
    
    def cmd_mute(self, match) -> str:
        self.brain.voice_enabled = False
        return "[OK] Ses kapatildi"
    
    def cmd_unmute(self, match) -> str:
        self.brain.voice_enabled = True
        return "[OK] Ses acildi"
    
    def cmd_screenshot(self, match) -> str:
        path = self.system.take_screenshot()
        return f"Ekran goruntusu kaydedildi: {path}"
    
    def cmd_open_app(self, match) -> str:
        app_name = match.group(2) if match.lastindex >= 2 else (match.group(1) or "uygulama")
        if not app_name:
            app_name = match.group(1) or "uygulama"
        app_name = app_name.strip()
        result = self.apps.open_app(app_name)
        return result['message']
    
    def cmd_open_app_reverse(self, match) -> str:
        app_name = match.group(1).strip()
        result = self.apps.open_app(app_name)
        return result['message']
    
    def cmd_close_app(self, match) -> str:
        active = self.system.get_active_window()
        if active:
            return f"Aktif pencere kapatilamaz. Lutfen manuel kapatin: {active.get('title', '?')}"
        return "Aktif pencere bilgisi alinamadi"
    
    def cmd_search(self, match) -> str:
        query = match.group(1) if match else ""
        result = self.apps.search_web(query)
        return result['message']
    
    def cmd_search_app(self, match) -> str:
        app_name = match.group(2) if match.lastindex >= 2 else (match.group(1) or "")
        app_name = app_name.strip()
        
        if not app_name:
            return "Aramak istediginiz uygulamanin adini soyleyin"
        
        app_lower = app_name.lower()
        results = []
        
        # Windows'ta uygulama ara (exe + lnk)
        found_path = self.apps.search_windows_app(app_lower)
        if found_path:
            try:
                if found_path.lower().endswith('.lnk'):
                    os.startfile(found_path)
                else:
                    subprocess.Popen(f'"{found_path}"')
                return f"{app_name} bulundu ve baslatildi:\n{found_path}"
            except Exception as e:
                return f"{app_name} bulundu ama acilamadi: {e}"
        
        # Start Menu kisa yollarinda ara (PWA/WebApp)
        found_shortcut = self.apps.search_windows_start_menu(app_lower)
        if found_shortcut:
            try:
                os.startfile(found_shortcut)
                return f"{app_name} WebApp olarak bulundu:\n{found_shortcut}"
            except Exception as e:
                return f"{app_name} bulundu ama acilamadi: {e}"
        
        # Chrome/Edge WebApps
        found_webapp = self.apps.search_windows_apps_folder(app_lower)
        if found_webapp:
            try:
                if found_webapp.lower().endswith(('.lnk', '.url')):
                    os.startfile(found_webapp)
                else:
                    subprocess.Popen(f'explorer "{found_webapp}"')
                return f"{app_name} WebApp olarak bulundu:\n{found_webapp}"
            except Exception as e:
                return f"{app_name} bulundu ama acilamadi: {e}"
        
        # PowerShell ile Windows Apps ara - tum sonuclari listele
        ps_results = self.apps.list_start_menu_apps(app_lower)
        
        if ps_results:
            lines = [f"{app_name} ile eslesen uygulamalar:"] + [f"  {i+1}. {r['name']}" for i, r in enumerate(ps_results[:10])]
            if len(ps_results) > 10:
                lines.append(f"  ... ve {len(ps_results) - 10} daha fazla")
            
            # Ilk sonucu dene
            first = ps_results[0]
            try:
                app_path = f"shell:AppsFolder\\{first['app_id']}"
                subprocess.Popen(['explorer', app_path])
                lines.append(f"  -> '{first['name']}' baslatiliyor...")
            except:
                pass
            
            # Start Menu'yu acip aramayi goster
            self.apps.open_start_menu_search(app_name)
            lines.append(f"  -> Start Menu'de aramada gosteriliyor...")
            
            return "\n".join(lines)
        
        # Bulunamazsa Start Menu'yu ac
        self.apps.open_start_menu_search(app_name)
        
        # Web'de de ara
        search_url = f"https://www.google.com/search?q={app_name.replace(' ', '+')}+download"
        webbrowser.open(search_url)
        return f"{app_name} Windows'ta bulunamadi. Start Menu ve Web'de araniyor..."
    
    def cmd_youtube(self, match) -> str:
        query = match.group(1) if match else ""
        result = self.apps.open_url(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
        return result['message']
    
    def cmd_open_url(self, match) -> str:
        url = match.group(1) if match else ""
        result = self.apps.open_url(url)
        return result['message']
    
    def cmd_site_search(self, match) -> str:
        site = match.group(1).strip() if match.lastindex >= 2 else ""
        query = match.group(2).strip() if match.lastindex >= 2 else (match.group(1) or "")
        result = self.apps.search_on_site(site, query)
        return result['message']
    
    def cmd_site_open(self, match) -> str:
        site = match.group(1).strip() if match else ""
        result = self.apps.open_site(site)
        return result['message']
    
    def cmd_download_app(self, match) -> str:
        app_name = match.group(1).strip() if match.lastindex >= 1 else ""
        if not app_name:
            app_name = match.group(0).strip()
            app_name = re.sub(r'^(?:indir|download)\s+', '', app_name, flags=re.IGNORECASE)
        
        print(f"\n[NAKO] '{app_name}' araniyor, web taranıyor...")
        
        results = self.apps.search_app_for_download(app_name)
        
        if not results:
            search_url = f"https://www.google.com/search?q={app_name.replace(' ', '+')}+download"
            webbrowser.open(search_url)
            return f"{app_name} icin sonuc bulunamadi. Web'de araniyor..."
        
        lines = [f"\n{Colors.BOLD}{app_name} icin bulunan sonuclar:{Colors.ENDC}"]
        for i, item in enumerate(results[:12], 1):
            title = item.get('title', '')[:70]
            snippet = item.get('snippet', '')[:80]
            url = item.get('url', '')
            lines.append(f"  {Colors.GREEN}{i}.{Colors.ENDC} {title}")
            if snippet:
                lines.append(f"     {snippet}")
            lines.append(f"     {Colors.CYAN}{url[:90]}{Colors.ENDC}")
        
        lines.append(f"\nHangi siteyi acalim? (1-{min(12, len(results))}, 0 = web'de ara): ")
        print("\n".join(lines))
        
        try:
            choice = input(f"{Colors.GREEN}> {Colors.ENDC}").strip()
            
            if not choice or choice == '0':
                search_url = f"https://www.google.com/search?q={app_name.replace(' ', '+')}+download"
                webbrowser.open(search_url)
                return "Web'de araniyor..."
            
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(results):
                    url = results[idx]['url']
                    print(f"\n[NAKO] Sayfa aciliyor: {url}")
                    webbrowser.open(url)
                    
                    print(f"[NAKO] Indirme linkleri taranıyor...")
                    indirme_linkleri = self.apps.find_download_links(url)
                    
                    if indirme_linkleri:
                        lines = [f"\n{Colors.BOLD}Sayfada bulunan indirme linkleri:{Colors.ENDC}"]
                        for i, link in enumerate(indirme_linkleri[:8], 1):
                            lines.append(f"  {Colors.GREEN}{i}.{Colors.ENDC} {link['text'][:70]}")
                            lines.append(f"     {Colors.CYAN}{link['url'][:90]}{Colors.ENDC}")
                        lines.append(f"\nHangisini indirelim? (1-{min(8, len(indirme_linkleri))}, 0 = gec): ")
                        print("\n".join(lines))
                        
                        dl_choice = input(f"{Colors.GREEN}> {Colors.ENDC}").strip()
                        if dl_choice.isdigit():
                            dl_idx = int(dl_choice) - 1
                            if 0 <= dl_idx < len(indirme_linkleri):
                                dl_url = indirme_linkleri[dl_idx]['url']
                                
                                # Download
                                print(f"\n[NAKO] Indiriliyor: {dl_url}")
                                result = self.apps.download_file(dl_url)
                                
                                if result['success']:
                                    print(f"{Colors.GREEN}[NAKO] Kaydedildi: {result['path']}{Colors.ENDC}")
                                    ac = input(f"\n[NAKO] Dosyayi acalim mi? (e/h): ").strip().lower()
                                    if ac in ('e', 'evet', 'y', 'yes'):
                                        os.startfile(result['path'])
                                        return f"{app_name} indirildi ve aciliyor: {result['filename']}"
                                    return f"{app_name} indirildi: {result['filename']}"
                                else:
                                    print(f"{Colors.RED}[NAKO] Indirme hatasi: {result['message']}{Colors.ENDC}")
                                    return f"Indirme basarisiz: {result['message']}"
                    else:
                        print(f"[NAKO] Sayfada indirme linki bulunamadi.")
                    
                    return f"{results[idx].get('title', url)} acildi"
            
            search_url = f"https://www.google.com/search?q={app_name.replace(' ', '+')}+download"
            webbrowser.open(search_url)
            return "Web'de araniyor..."
        
        except (EOFError, KeyboardInterrupt):
            pass
        
        return f"{app_name} araniyor..."
    
    # ===== GELISMIS OZELLIKLER =====
    
    def cmd_clean_desktop(self, match) -> str:
        """Masaustunu dosya turune gore duzenle"""
        desktop = Path(os.path.expanduser("~")) / "Desktop"
        if not desktop.exists():
            return "Masaustu klasoru bulunamadi"
        
        folders = {
            'Gorseller': ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico'),
            'Dokumanlar': ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md'),
            'Arsivler': ('.zip', '.rar', '.7z', '.tar', '.gz'),
            'Kurulum': ('.exe', '.msi', '.dmg', '.appimage'),
            'Ses': ('.mp3', '.wav', '.flac', '.aac', '.ogg'),
            'Video': ('.mp4', '.avi', '.mkv', '.mov', '.wmv'),
            'Kod': ('.py', '.js', '.ts', '.html', '.css', '.cpp', '.c', '.java', '.rs'),
        }
        
        moved = 0
        for item in desktop.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                for folder_name, exts in folders.items():
                    if ext in exts:
                        target = desktop / folder_name
                        target.mkdir(exist_ok=True)
                        try:
                            item.rename(target / item.name)
                            moved += 1
                        except:
                            pass
                        break
        
        return f"Masaustu duzenlendi: {moved} dosya klasorlere tasindi"
    
    def cmd_clean_temp(self, match) -> str:
        """Gecici dosyalari temizle"""
        import shutil
        
        temp_dirs = [
            os.environ.get('TEMP', ''),
            os.environ.get('TMP', ''),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
        ]
        
        total = 0
        for temp_dir in temp_dirs:
            if not temp_dir or not os.path.exists(temp_dir):
                continue
            try:
                for item in Path(temp_dir).iterdir():
                    try:
                        if item.is_file():
                            size = item.stat().st_size
                            item.unlink()
                            total += size
                        elif item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                    except:
                        pass
            except:
                pass
        
        mb = total / (1024 * 1024)
        return f"Temizlik tamam: ~{mb:.1f} MB bosaltildi"
    
    def cmd_bulk_rename(self, match) -> str:
        """Toplu dosya adlandirma"""
        from tkinter import filedialog, Tk
        
        print("[NAKO] Klasor secmek icin pencere aciliyor...")
        root = Tk()
        root.withdraw()
        folder = filedialog.askdirectory(title="Dosyalarin bulundugu klasoru sec")
        root.destroy()
        
        if not folder:
            return "Klasor secilmedi"
        
        files = [f for f in Path(folder).iterdir() if f.is_file()]
        if not files:
            return "Klasorde dosya yok"
        
        print(f"[NAKO] {len(files)} dosya bulundu.")
        prefix = input(f"{Colors.GREEN}> Dosya on-eki (ornek: 'foto' -> foto_1.jpg): {Colors.ENDC}").strip()
        if not prefix:
            prefix = "file"
        
        renamed = 0
        for i, f in enumerate(sorted(files), 1):
            new_name = f"{prefix}_{i}{f.suffix}"
            try:
                f.rename(f.parent / new_name)
                renamed += 1
            except:
                pass
        
        return f"{renamed} dosya yeniden adlandirildi: {prefix}_1 ... {prefix}_{renamed}"
    
    def cmd_bulk_convert(self, match) -> str:
        """Dosya uzantilarini toplu degistir"""
        from_ext = match.group(1).strip().lstrip('.')
        to_ext = match.group(2).strip().lstrip('.')
        
        from tkinter import filedialog, Tk
        print("[NAKO] Klasor secmek icin pencere aciliyor...")
        root = Tk()
        root.withdraw()
        folder = filedialog.askdirectory(title="Klasoru sec")
        root.destroy()
        
        if not folder:
            return "Klasor secilmedi"
        
        converted = 0
        for f in Path(folder).rglob(f"*.{from_ext}"):
            new_path = f.with_suffix(f".{to_ext}")
            try:
                f.rename(new_path)
                converted += 1
            except:
                pass
        
        return f"{converted} dosya .{from_ext} -> .{to_ext} donusturuldu"
    
    def cmd_watch_folder(self, match) -> str:
        """Klasoru izle - yeni dosyalari bildir"""
        folder = match.group(1).strip()
        folder = os.path.expandvars(folder)
        
        if not os.path.exists(folder):
            # Klasor yoksa secme penceresi ac
            from tkinter import filedialog, Tk
            print("[NAKO] Klasor secmek icin pencere aciliyor...")
            root = Tk()
            root.withdraw()
            folder = filedialog.askdirectory(title="Izlenecek klasoru sec")
            root.destroy()
        
        if not folder or not os.path.exists(folder):
            return "Gecerli bir klasor secilmedi"
        
        self._watch_folder = folder
        self._watch_running = True
        
        def watcher():
            known = set()
            for f in Path(folder).iterdir():
                if f.is_file():
                    known.add(f.name)
            
            while self._watch_running:
                time.sleep(2)
                current = set()
                for f in Path(folder).iterdir():
                    if f.is_file():
                        current.add(f.name)
                
                new_files = current - known
                for f in new_files:
                    print(f"\n{Colors.GREEN}[NAKO] Yeni dosya: {folder}\\{f}{Colors.ENDC}")
                    self.voice.speak(f"Yeni dosya: {f}")
                
                known = current
        
        thread = threading.Thread(target=watcher, daemon=True)
        thread.start()
        
        # Watcher thread'ini kaydet
        if not hasattr(self, '_watch_threads'):
            self._watch_threads = []
        self._watch_threads.append(thread)
        
        return f"Klasor izleniyor: {folder}"
    
    def cmd_stop_watch(self, match) -> str:
        self._watch_running = False
        self._watch_folder = None
        return "Klasor izleme durduruldu"
    
    def cmd_create_shortcut(self, match) -> str:
        """Windows kisayolu olustur"""
        target = match.group(1).strip()
        name = match.group(2).strip() if match.lastindex >= 2 else None
        
        # Hedef coz
        if not target.startswith(('http://', 'https://', '\\\\', 'shell:')):
            if os.path.exists(target):
                pass
            elif os.path.exists(os.path.expandvars(target)):
                target = os.path.expandvars(target)
            else:
                target = f"https://{target}"
        
        if not name:
            if target.startswith('http'):
                name = target.split('//')[-1].split('/')[0]
            else:
                name = Path(target).stem
        
        desktop = Path(os.path.expanduser("~")) / "Desktop"
        shortcut_path = desktop / f"{name}.url"
        
        try:
            with open(shortcut_path, 'w') as f:
                f.write(f"[InternetShortcut]\nURL={target}\n")
            return f"Kisayol olusturuldu: {shortcut_path}"
        except Exception as e:
            return f"Kisayol olusturulamadi: {e}"
    
    def cmd_backup(self, match) -> str:
        """Klasor yedegini al"""
        import shutil
        source = match.group(1).strip()
        source = os.path.expandvars(source)
        
        if not os.path.exists(source):
            return f"Kaynak bulunamadi: {source}"
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = Path(source).name
        backup_dir = Path(os.path.expanduser("~")) / "Backups" / f"{name}_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[NAKO] Yedekleniyor: {source}")
        print(f"[NAKO] Hedef: {backup_dir}")
        
        try:
            if Path(source).is_file():
                shutil.copy2(source, backup_dir / Path(source).name)
            else:
                shutil.copytree(source, backup_dir / name, dirs_exist_ok=True)
            return f"Yedek alindi: {backup_dir}"
        except Exception as e:
            return f"Yedek hatasi: {e}"
    
    def cmd_restore(self, match) -> str:
        """Yedekten geri yukle"""
        import shutil
        name = match.group(1).strip()
        
        backup_root = Path(os.path.expanduser("~")) / "Backups"
        if not backup_root.exists():
            return "Henuz yedek bulunmuyor"
        
        matches = []
        for p in backup_root.iterdir():
            if p.is_dir() and name.lower() in p.name.lower():
                matches.append(p)
        
        if not matches:
            return f"{name} icin yedek bulunamadi"
        
        print(f"\nBulunan yedekler:")
        for i, p in enumerate(matches, 1):
            size = sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) / (1024*1024)
            print(f"  {i}. {p.name} (~{size:.1f} MB)")
        
        try:
            choice = input(f"{Colors.GREEN}> Hangi yedegi yukleyelim? (1-{len(matches)}): {Colors.ENDC}").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(matches):
                    src = matches[idx]
                    dst = Path(os.path.expanduser("~")) / src.name.replace(f"_{src.name.split('_')[-1]}", "")
                    
                    if dst.exists():
                        over = input(f"{dst} zaten var, uzerine yazilsin mi? (e/h): ").strip().lower()
                        if over not in ('e', 'evet'):
                            return "Geri yukleme iptal edildi"
                    
                    if dst.is_file() or not dst.suffix:
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
                    
                    return f"Yedek geri yuklendi: {src} -> {dst}"
        except:
            pass
        
        return "Geri yukleme iptal edildi"
    
    def cmd_monitor_start(self, match) -> str:
        """Sistem monitoru baslat"""
        if not PSUTIL_OK:
            return "psutil kurulu degil, monitor calismaz"
        
        self._monitor_running = True
        
        def monitor():
            while self._monitor_running:
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent
                
                satir = f"[MONITOR] CPU: %{cpu} | RAM: %{ram} | Disk: %{disk}"
                print(f"\r{Colors.CYAN}{satir}{Colors.ENDC}", end='')
                
                if cpu > 90:
                    print(f"\n{Colors.RED}[UYARI] CPU cok yuksek: %{cpu}{Colors.ENDC}")
                if ram > 90:
                    print(f"\n{Colors.RED}[UYARI] RAM cok yuksek: %{ram}{Colors.ENDC}")
                
                time.sleep(3)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        return "Sistem monitoru baslatildi (3sn aralikla)"
    
    def cmd_monitor_stop(self, match) -> str:
        self._monitor_running = False
        return "Sistem monitoru durduruldu"
    
    def cmd_system_report(self, match) -> str:
        """Detayli sistem raporu"""
        if not PSUTIL_OK:
            return self.cmd_system_info(match)
        
        import datetime as dt
        
        boot = dt.datetime.fromtimestamp(psutil.boot_time())
        now = dt.datetime.now()
        uptime = now - boot
        
        cpu = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        
        report = f"""
{Colors.BOLD}SISTEM RAPORU{Colors.ENDC}
{Colors.CYAN}{'='*50}{Colors.ENDC}
Calisma: {uptime.days} gun {uptime.seconds//3600} saat
CPU: %{cpu} ({cpu_count} cekirdek)
RAM: %{ram.percent} ({ram.used//(1024**3)}GB/{ram.total//(1024**3)}GB)
Disk: %{disk.percent} ({disk.used//(1024**3)}GB/{disk.total//(1024**3)}GB)
Ag: {net.bytes_sent//(1024**2)}MB giden / {net.bytes_recv//(1024**2)}MB gelen
Islem: {len(psutil.pids())} aktif
{Colors.CYAN}{'='*50}{Colors.ENDC}"""
        return report
    
    def cmd_create_file(self, match) -> str:
        return "Dosya olusturmak icin: 'dosya olustur dosya_adi.txt icerik' yazin"
    
    def cmd_add_note(self, match) -> str:
        return "Not eklemek icin: 'not al not_metni' yazin"
    
    def cmd_show_notes(self, match) -> str:
        notes = self.notes.get_notes()
        if notes:
            return "NOTLAR:\n" + "\n".join(notes)
        return "Henuz not yok"
    
    def cmd_remind(self, match) -> str:
        if match:
            minutes = int(match.group(1))
            text = match.group(2) if match.lastindex >= 2 else "Hatirlatma"
            result = self.notes.add_reminder(text, minutes)
            return result['message']
        return "Kullanim: 'hatirla 5 dakika sonra toplanti'"
    
    def cmd_recall(self, match) -> str:
        """Obsidian sınırsız hafızada ara"""
        query = match.group(1).strip() if match and match.lastindex >= 1 else ""
        if not query:
            return "Ne aramak istiyorsun? Örn: 'hafızada python ara'"
        
        obsidian = None
        if OBSIDIAN_OK:
            try:
                from obsidian_memory import get_obsidian_memory
                obsidian = get_obsidian_memory()
            except:
                pass
        
        if obsidian:
            results = obsidian.recall(query, max_results=5)
            if results:
                lines = [f"{Colors.CYAN}Hafızada '{query}' için {len(results)} sonuç:{Colors.ENDC}"]
                for r in results:
                    preview = r['content_preview'][:150].replace('\n', ' ').strip()
                    lines.append(f"  [[{r['path']}]]")
                    lines.append(f"     {preview}...")
                return '\n'.join(lines)
            else:
                return f"Hafızada '{query}' ile ilgili bir şey bulamadım."
        
        # Fallback: session içinde ara
        results = self.notes.search_notes(query)
        if results:
            return '\n'.join([f"- {r}" for r in results[:5]])
        return f"Hafızada '{query}' için sonuç bulunamadı."
    
    def cmd_memory_stats(self, match) -> str:
        """Hafıza istatistiklerini göster"""
        if OBSIDIAN_OK:
            try:
                from obsidian_memory import get_obsidian_memory
                obsidian = get_obsidian_memory()
                count = obsidian.get_memory_count()
                size = obsidian.get_total_size()
                return f"""{Colors.GREEN}OBSIDIAN SINIRSIZ HAFIZA{Colors.ENDC}
{'-'*40}
Toplam Dosya: {count}
Toplam Boyut: {size}
Depolama: notes/ klasörü (.md dosyaları)
Obsidian: VSCode eklentisi ile senkron"""
            except:
                pass
        return "Obsidian hafıza aktif değil."
    
    def cmd_ai_chat(self, match) -> str:
        question = match.group(1) if match else ""
        result = self.ai.chat(question)
        if result['success']:
            return result['response']
        return result['message']
    
    def cmd_think(self, match) -> str:
        return "Su an su konular uzerinde calisiyorum: Makin ogrenmesi, dogal dil isleme, ve bilgisayr gorsu. Size nasil yardimci olabilirim?"
    
    def cmd_mouse_click(self, match) -> str:
        coords = match.group(1) if match else ""
        try:
            parts = coords.replace(',', ' ').split()
            x, y = int(parts[0]), int(parts[1])
            result = self.control.mouse_click(x, y)
            return result['message']
        except:
            result = self.control.mouse_click()
            return result['message']
    
    def cmd_find_and_click(self, match) -> str:
        """OCR ile ekranda metin bul ve tikla"""
        return "Kullanim: 'bul ve tikla Merhaba' veya sadece 'tikla 100 200'"
    
    def cmd_mouse_move(self, match) -> str:
        return "Kullanim: 'tasima 500 300'"
    
    def cmd_type_text(self, match) -> str:
        return "Kullanim: 'yaz Merhaba'"
    
    def cmd_select(self, match) -> str:
        return "Belge secmek icin: 'sec dosya.txt'"
    
    def cmd_window_info(self, match) -> str:
        active = self.system.get_active_window()
        if active:
            return f"Aktif pencere: {active.get('title', '?')}"
        return "Pencere bilgisi alinamadi"
    
    def cmd_minimize(self, match) -> str:
        if PYGETWINDOW_OK:
            try:
                win = gw.getActiveWindow()
                win.minimize()
                return "Pencere kucultuldu"
            except:
                pass
        return "Pencere kontrolu yapilamadi"
    
    def cmd_maximize(self, match) -> str:
        if PYGETWINDOW_OK:
            try:
                win = gw.getActiveWindow()
                win.maximize()
                return "Pencere buyutuldu"
            except:
                pass
        return "Pencere kontrolu yapilamadi"
    
    def cmd_time(self, match) -> str:
        return f"Saat: {datetime.datetime.now().strftime('%H:%M:%S')}"
    
    def cmd_date(self, match) -> str:
        return f"Tarih: {datetime.datetime.now().strftime('%Y-%m-%d %A')}"
    
    def cmd_weather(self, match) -> str:
        return "Hava durumu icin web'de arama yapilacak. Biraz bekleyin..."
    
    def cmd_network(self, match) -> str:
        try:
            result = subprocess.run(['ping', '-n', '1', 'google.com'], capture_output=True, text=True)
            if 'Reply from' in result.stdout:
                return "Internet baglantisi: AKTIF"
            return "Internet baglantisi kontrol ediliyor..."
        except:
            return "Ag kontrolu yapilamadi"
    
    def cmd_exit(self, match) -> str:
        self.brain.mode = SystemMode.SILENT
        self.voice.speak("Gorusmek uzere!")
        print(f"\n{Colors.YELLOW}Shadowcat AI kapatildi. Hosca kalin!{Colors.ENDC}\n")
        sys.exit(0)
    
    def cmd_help(self, match) -> str:
        return """
==============================================================
           SHADOWCAT - KOMUT LISTESI
==============================================================

SISTEM KOMUTLARI:
  - sistem bilgi      : Bilgisayar bilgilerini goster
  - ses kapa/ac       : Sesli yaniti ac/kapa
  - ekran goruntusu   : Screenshot al
  - saat kac          : Suanki saati goster
  - tarih ne          : Bugunun tarihini goster

UYGULAMA KOMUTLARI:
  - ac <uygulama>      : Uygulama baslat
  - <uygulama> ac      : Uygulama baslat (tersten)
  - baslat <uygulama>  : Uygulama baslat
  - ara <kelime>       : Web'de ara
  - youtube <video>   : YouTube'de ara
  - web sitesi <url>  : Web sitesi ac
  - <site>'da <sey> ara : Sitede ara (youtube'da Mavislime ara)
  - <site>'a gir       : Siteyi ac (instagram'a gir)
  - <uygulama> indir   : Indirme (gdevelop 5 indir)

DOSYA KOMUTLARI:
  - not al <metin>     : Not ekle
  - notlarim          : Notlari goster
  - hatirla <dk> <msg> : Hatirlatma ayarla

GELISMIS OZELLIKLER:
  - masaustunu temizle : Masaustunu dosya turune gore duzenle
  - gecici dosyalari temizle : Temp dosyalari sil
  - toplu adlandir     : Klasordeki dosyalari toplu yeniden adlandir
  - .py -> .txt        : Dosya uzantilarini toplu degistir
  - klasor izle <yol>  : Klasordeki yeni dosyalari izle
  - izleme dur         : Klasor izlemeyi durdur
  - kisayol olustur <hedef> : Masaustune kisayol yap
  - yedek al <kaynak>  : Dosya/klasor yedegini al
  - yedek yukle <isim> : Yedekten geri yukle
  - sistem monitor     : Canli CPU/RAM/Disk takibi baslat
  - monitor dur        : Monitoru durdur
  - sistem rapor       : Detayli sistem raporu goster

AI KOMUTLARI:
  - sor <soru>        : AI'ye sor
  - ne dusunuyorsun   : AI'nin durumunu goster

MOUSE/KLAVYE:
  - tikla <x> <y>     : Belirtilen konuma tikla
  - bul ve tikla <yazi>: Ekranda metin ara ve tikla (OCR)
  - yaz <metin>       : Metin yaz
  - kucult/buyut      : Pencereyi kucult/buyut

OZEL:
  - cikis             : Programi kapat
  - yardim            : Bu yardimi goster
"""
    
    def cmd_change_mode(self, match) -> str:
        return "Mod degistirmek icin: 'mod normal/developer/silent/game'"
    
    # ===== ANA ISLEYIS =====
    
    def process(self, input_text: str) -> str:
        """Kullanici girdisini isleyerek komutu calistir"""
        
        self.brain.commands_executed += 1
        
        # Komutlari kontrol et
        for pattern, handler in self.commands.items():
            match = re.search(pattern, input_text, re.IGNORECASE)
            if match:
                try:
                    result = handler(match)
                    self.brain.add_command(input_text, True)
                    return result
                except Exception as e:
                    self.brain.add_command(input_text, False)
                    return f"[HATA] {str(e)}"
        
        # Bilinmeyen komut - AI'ye sor
        result = self.ai.chat(input_text)
        if result['success']:
            return result['response']
        
        return "Bu komutu anlamadim. 'yardim' yazarak komut listesini gorbilirsiniz."
    
    def run_cli(self):
        """CLI modunda calistir"""
        print(f"{Colors.CYAN}CLI modu baslatildi. 'cikis' yazarak cikabilirsiniz.{Colors.ENDC}\n")
        
        while True:
            try:
                user_input = input(f"{Colors.GREEN}> {Colors.ENDC}").strip()
                
                if not user_input:
                    continue
                
                # Komutu isle
                response = self.process(user_input)
                
                # Yaniti goster
                if response:
                    print(f"\n{Colors.CYAN}{response}{Colors.ENDC}\n")
                
                # Konusmasi gerekiyorsa konus
                if self.brain.voice_enabled and self.brain.mode != SystemMode.SILENT:
                    if len(response) < 200:
                        self.voice.speak(response)
                
            except KeyboardInterrupt:
                print(f"\n\n{Colors.YELLOW}Cikis yapiliyor...{Colors.ENDC}")
                break
            except Exception as e:
                print(f"\n{Colors.RED}[HATA] {str(e)}{Colors.ENDC}\n")


# ==============================================================
# SHADOWCAT CORE AGENT - Yeni mimari ile calisan ana sinif
# ==============================================================

class GlassescatCoreAgent:
    """
    Shadowcat AI'nin yeni nesil ana sinifi.
    
    GlassescatCore + AgentLoop + TaskPlanner + WebAgent + Feedback
    tum alt sistemleri birlestirir.
    
    Eski GlassescatAgent ile geriye uyumludur.
    """
    
    def __init__(self, auto_init: bool = True):
        self.core = None
        self.agent_loop = None
        self.task_planner = None
        self.web_agent = None
        self.feedback = None
        self.state_manager = None
        
        # Eski GlassescatAgent (geriye uyumluluk)
        self._legacy = None
        
        if auto_init:
            self.initialize()
    
    def initialize(self):
        """Tum alt sistemleri baslat"""
        print(f"{Colors.CYAN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.CYAN}  SHADOWCAT CORE v3.0 - GELISMIS AJAN{' '*21}{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.ENDC}")
        
        # 1. GlassescatCore
        try:
            from glassescat_core import get_core
            self.core = get_core()
            print(f"{Colors.GREEN}[SHADOWCAT] Core baslatildi: {self.core.toolformer.registry.count() if self.core.toolformer else 0} ara{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.YELLOW}[SHADOWCAT] Core baslatilamadi, legacy mod: {e}{Colors.ENDC}")
            self.core = None
        
        # 2. Agent Loop
        try:
            from glassescat_agent_loop import get_agent_loop
            self.agent_loop = get_agent_loop(core=self.core)
            print(f"{Colors.GREEN}[SHADOWCAT] Agent Loop: ReAct modu aktif{Colors.ENDC}")
        except ImportError:
            print(f"{Colors.YELLOW}[SHADOWCAT] Agent Loop yok{Colors.ENDC}")
            self.agent_loop = None
        
        # 3. Task Planner
        try:
            from glassescat_task_planner import get_task_planner
            self.task_planner = get_task_planner(core=self.core)
            print(f"{Colors.GREEN}[SHADOWCAT] Task Planner: cok adimli planlama aktif{Colors.ENDC}")
        except ImportError:
            self.task_planner = None
        
        # 4. Web Agent
        try:
            from glassescat_web_agent import get_web_agent
            self.web_agent = get_web_agent()
            print(f"{Colors.GREEN}[SHADOWCAT] Web Agent: otonom web gezgini aktif{Colors.ENDC}")
        except ImportError:
            self.web_agent = None
        
        # 5. Feedback
        try:
            from glassescat_feedback import get_feedback_system
            self.feedback = get_feedback_system()
            print(f"{Colors.GREEN}[SHADOWCAT] Feedback Loop: ogrenme sistemi aktif{Colors.ENDC}")
        except ImportError:
            self.feedback = None
        
        # 6. State Manager
        try:
            from glassescat_state_manager import get_state_manager
            self.state_manager = get_state_manager()
            print(f"{Colors.GREEN}[SHADOWCAT] State Manager: kalici durum aktif{Colors.ENDC}")
        except ImportError:
            self.state_manager = None
        
        # 7. Legacy GlassescatAgent (opsiyonel)
        try:
            self._legacy = GlassescatAgent()
        except:
            self._legacy = None
        
        print(f"{Colors.CYAN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.GREEN}[SHADOWCAT] Shadowcat Core Agent hazir!{Colors.ENDC}")
    
    def process(self, user_input: str) -> str:
        """Kullanici girdisini isle - ONCELIKLI yeni mimari"""
        if not user_input or not user_input.strip():
            return ""
        
        # Komut analizi - özel komutlar
        cmd = user_input.lower().strip()
        
        # === OZEL KOMUTLAR ===
        if cmd in ("yardim", "help", "komutlar"):
            return self._show_help()
        
        if cmd in ("durum", "status", "sistem durumu"):
            return self._show_status()
        
        if cmd.startswith("planla ") or cmd.startswith("gorev "):
            return self._execute_task(cmd)
        
        if cmd.startswith("web ") or cmd.startswith("ara "):
            return self._web_search(cmd)
        
        if cmd.startswith("hafiza ") or cmd.startswith("memory "):
            return self._memory_command(cmd)
        
        if cmd.startswith("ogren ") or cmd.startswith("feedback "):
            return self._feedback_command(cmd)
        
        if cmd == "istatistik":
            return self._show_stats()
        
        # === YENI MİMARİ İSLEME ===
        if self.core:
            try:
                result = self.core.process_message(user_input)
                response = result.get("response", "")
                
                # Tool calls bilgisi
                tool_calls = result.get("tool_calls", [])
                if tool_calls:
                    success_count = sum(1 for tc in tool_calls if tc.get("success"))
                    response += f"\n\n_{len(tool_calls)} araç kullanıldı ({success_count} başarılı)_"
                
                return response
            except Exception as e:
                logger.error(f"Core isleme hatasi: {e}")
                # Legacy'e düş
        
        # === LEGACY MİMARİ (GERİYE UYUMLULUK) ===
        if self._legacy:
            return self._legacy.process(user_input)
        
        return "Komut anlasilamadi. 'yardim' yazarak komut listesini gorebilirsiniz."
    
    def _execute_task(self, cmd: str) -> str:
        """Cok adimli gorev yurut"""
        task_desc = cmd.replace("planla ", "").replace("gorev ", "").strip()
        
        if not task_desc:
            return "Ne yapmak istiyorsun? Ornek: 'gorev Chrome ac YouTube gir Mavislime ara'"
        
        if self.task_planner:
            result = self.task_planner.execute_task(task_desc)
            return result.get("summary", "Gorev tamamlandi.")
        elif self.core:
            result = self.core.execute_task(task_desc)
            return result.get("response", "Gorev tamamlandi.")
        
        return "Task Planner aktif degil."
    
    def _web_search(self, cmd: str) -> str:
        """Web aramasi"""
        query = cmd.replace("web ", "").replace("ara ", "").strip()
        if not query:
            return "Ne aramak istiyorsun?"
        
        if self.web_agent:
            results = self.web_agent.search(query, max_results=5)
            if results:
                lines = [f"'{query}' icin sonuclar:"]
                for r in results[:5]:
                    lines.append(f"  • {r.get('title', '?')[:60]}")
                    lines.append(f"    {r.get('url', '?')}")
                return '\n'.join(lines)
            return f"'{query}' icin sonuc bulunamadi."
        
        return "Web Agent aktif degil."
    
    def _memory_command(self, cmd: str) -> str:
        """Hafiza komutlari"""
        if not self.core or not self.core.memory:
            return "Obsidian hafiza aktif degil."
        
        if "ara" in cmd:
            query = cmd.replace("hafiza ", "").replace("memory ", "").replace("ara ", "").strip()
            if query:
                results = self.core.memory.recall(query, max_results=5)
                if results:
                    lines = [f"Hafizada '{query}' icin {len(results)} sonuc:"]
                    for r in results:
                        preview = r['content_preview'][:120].replace('\n', ' ').strip()
                        lines.append(f"  [{r.get('type', '?')}] {preview}...")
                    return '\n'.join(lines)
                return f"Hafizada '{query}' ile ilgili bir sey bulamadim."
        
        if cmd in ("hafiza", "memory", "hafiza durum", "memory status"):
            count = self.core.memory.get_memory_count()
            size = self.core.memory.get_total_size()
            return f"OBSIDIAN SINIRSIZ HAFIZA\nDosya: {count}\nBoyut: {size}"
        
        return "Kullanim: 'hafizada ara <sorgu>' veya 'hafiza durum'"
    
    def _feedback_command(self, cmd: str) -> str:
        """Feedback / ogrenme komutlari"""
        if not self.feedback:
            return "Feedback sistemi aktif degil."
        
        if cmd in ("ogren", "feedback"):
            stats = self.feedback.get_statistics()
            if stats.get("total_interactions", 0) == 0:
                return "Henuz istatistik verisi yok."
            
            return (
                f"PERFORMANS\n"
                f"Etkilesim: {stats.get('total_interactions', 0)}\n"
                f"Basari: %{stats.get('success_rate', '0')}\n"
                f"Ortalama Sure: {stats.get('avg_duration', '0')}\n"
                f"Arac: {stats.get('total_tool_calls', 0)}"
            )
        
        return "Kullanim: 'ogren' - istatistikleri goster"
    
    def _show_stats(self) -> str:
        """Detayli istatistik"""
        parts = ["SHADOWCAT ISTATISTIK"]
        
        if self.core:
            status = self.core.get_status()
            s = status.get("state", {})
            parts.append(f"Komut: {s.get('commands_executed', 0)}")
            parts.append(f"Hata: {s.get('errors_fixed', 0)}")
            parts.append(f"Calisma: {status.get('uptime', '?')}")
            parts.append(f"Mod: {s.get('mode', 'normal')}")
        
        if self.feedback:
            stats = self.feedback.get_statistics()
            if stats.get("total_interactions", 0) > 0:
                parts.append(f"")
                parts.append(f"PERFORMANS")
                parts.append(f"Etkilesim: {stats['total_interactions']}")
                parts.append(f"Basari: %{stats['success_rate']}")
                parts.append(f"Arac: {stats['total_tool_calls']}")
        
        if self.agent_loop:
            parts.append(f"")
            parts.append(f"ReAct Loop: aktif")
        
        if self.web_agent:
            parts.append(f"Web Agent: aktif")
        
        return '\n'.join(parts)
    
    def _show_status(self) -> str:
        """Sistem durumu"""
        if self.core:
            status = self.core.get_status()
            return (
                f"SHADOWCAT DURUMU\n"
                f"Versiyon: {status.get('version', '?')}\n"
                f"Calisma: {status.get('uptime', '?')}\n"
                f"Mod: {status['state'].get('mode', '?')}\n"
                f"Komut: {status['state'].get('commands_executed', 0)}\n\n"
                f"MODULLER\n"
                f"Hafiza: {'' if status['modules'].get('memory') else ''}\n"
                f"Toolformer: {'' if status['modules'].get('toolformer') else ''}\n"
                f"Model Router: {'' if status['modules'].get('model_router') else ''}\n"
                f"State: {'' if status['modules'].get('state_manager') else ''}\n"
                f"Feedback: {'' if status['modules'].get('feedback') else ''}"
            )
        return "Core aktif degil."
    
    def _show_help(self) -> str:
        """Yardim menusu"""
        return """
╔════════════════════════════════════════════════════════╗
║              SHADOWCAT v3 - KOMUT LİSTESİ               ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║  TEMEL                                             ║
║    <mesaj>         - AI'ya herhangi bir soru sor      ║
║    yardim          - Bu yardim menu                   ║
║    durum           - Sistem durumu                    ║
║    istatistik      - Performans istatistikleri        ║
║                                                        ║
║  COK ADIMLI GOREVLER                               ║
║    planla <gorev>  - Karmasik gorevleri planla       ║
║    gorev <islem>   - Ayni islem                      ║
║    Ornek: 'gorev Chrome ac, YouTube gir, Mavislime ara'║
║                                                        ║
║  WEB                                               ║
║    ara <sorgu>     - Web'de ara                      ║
║    web <sorgu>     - Web'de ara                      ║
║                                                        ║
║  HAFIZA                                            ║
║    hafiza durum    - Hafiza istatistikleri            ║
║    hafizada ara <s> - Hafizada ara                   ║
║                                                        ║
║  OGRENME                                           ║
║    ogren           - AI performans istatistikleri    ║
║                                                        ║
║  SISTEM (eski komutlar da calisir)               ║
║    ac <uygulama>   - Uygulama baslat                  ║
║    ara <kelime>    - Google'da ara                    ║
║    not al <metin>  - Not ekle                         ║
║    sistem bilgi    - Bilgisayar bilgileri             ║
║    saat kac        - Saati goster                     ║
║    cikis           - Programi kapat                   ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
"""
    
    def run_cli(self):
        """CLI modu - yeni mimari ile"""
        print(f"\n{Colors.CYAN}Shadowcat AI v3 CLI baslatildi. 'yardim' yazip komutlari gorebilirsiniz.{Colors.ENDC}\n")
        
        while True:
            try:
                user_input = input(f"{Colors.GREEN}> {Colors.ENDC}").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ("cikis", "exit", "quit", "q"):
                    print(f"\n{Colors.YELLOW}Gorusmek uzere!{Colors.ENDC}")
                    break
                
                # Isle
                response = self.process(user_input)
                
                if response:
                    print(f"\n{Colors.CYAN}{response}{Colors.ENDC}\n")
                
            except KeyboardInterrupt:
                print(f"\n\n{Colors.YELLOW}Gorusmek uzere!{Colors.ENDC}")
                break
            except Exception as e:
                print(f"\n{Colors.RED}[HATA] {str(e)}{Colors.ENDC}\n")


# ===== MAIN =====
if __name__ == "__main__":
    import sys
    
    # Yeni mimariyi dene, olmazsa legacy'e dön
    try:
        agent = GlassescatCoreAgent()
        agent.run_cli()
    except Exception as e:
        print(f"[SHADOWCAT] Yeni mimari baslatilamadi, legacy mod: {e}")
        agent = GlassescatAgent()
        agent.voice.greet()
        agent.run_cli()
