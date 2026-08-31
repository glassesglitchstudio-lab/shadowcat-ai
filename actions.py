"""
Shadowcat BETA - Actions Module
Uygulama ve Oyun Başlatıcıları
Gelişmiş Bilgisayar Kontrolü
"""

import subprocess
import os
import webbrowser
import time
import shutil
from typing import Dict, Any, Optional

# Opsiyonel bağımlılıklar
try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except ImportError:
    pytesseract = None


# ============== BİLGİSAYAR KONTROL FONKSİYONLARI ==============

def mouse_control(action: str, x: int = 0, y: int = 0) -> Dict[str, Any]:
    """Mouse kontrolü"""
    if not pyautogui:
        return {'success': False, 'error': 'pyautogui kurulu değil'}
    
    try:
        if action == "move":
            pyautogui.moveTo(x, y, duration=0.5)
            return {'success': True, 'message': f'Mouse ({x}, {y}) konumuna taşındı'}
        
        elif action == "click":
            pyautogui.click()
            return {'success': True, 'message': 'Tıklandı'}
        
        elif action == "double_click":
            pyautogui.doubleClick()
            return {'success': True, 'message': 'Çift tıklandı'}
        
        elif action == "right_click":
            pyautogui.rightClick()
            return {'success': True, 'message': 'Sağ tıklandı'}
        
        elif action == "drag":
            pyautogui.dragTo(x, y, duration=1)
            return {'success': True, 'message': f'Sürüklendi ({x}, {y})'}
        
        elif action == "scroll":
            pyautogui.scroll(x)  # x > 0 yukarı, x < 0 aşağı
            return {'success': True, 'message': f'Scroll edildi: {x}'}
        
        elif action == "random":
            screen_size = pyautogui.size()
            new_x = screen_size.width // 2
            new_y = screen_size.height // 2
            pyautogui.moveTo(new_x, new_y, duration=1)
            return {'success': True, 'message': f'Rastgele konum: ({new_x}, {new_y})'}
        
        return {'success': False, 'error': 'Bilinmeyen action'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def keyboard_control(action: str, text: str = "", key: str = "") -> Dict[str, Any]:
    """Klavye kontrolü"""
    if not pyautogui:
        return {'success': False, 'error': 'pyautogui kurulu değil'}
    
    try:
        if action == "write":
            pyautogui.write(text, interval=0.05)
            return {'success': True, 'message': f'Yazıldı: {text}'}
        
        elif action == "press":
            pyautogui.press(key)
            return {'success': True, 'message': f'Tuşa basıldı: {key}'}
        
        elif action == "hotkey":
            keys = key.split("+")
            pyautogui.hotkey(*keys)
            return {'success': True, 'message': f'Hotkey çalıştı: {key}'}
        
        elif action == "type_hotkey":
            pyautogui.write(text, interval=0.05)
            pyautogui.press("enter")
            return {'success': True, 'message': f'Yazıldı ve enter basıldı: {text}'}
        
        return {'success': False, 'error': 'Bilinmeyen action'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def window_control(action: str, title: str = "") -> Dict[str, Any]:
    """Pencere kontrolü"""
    if not gw:
        return {'success': False, 'error': 'pygetwindow kurulu değil'}
    
    try:
        if action == "list":
            windows = gw.getAllTitles()
            return {'success': True, 'windows': [w for w in windows if w]}
        
        elif action == "active":
            active = gw.getActiveWindow()
            if active:
                return {'success': True, 'window': active.title}
            return {'success': False, 'error': 'Aktif pencere yok'}
        
        elif action == "focus":
            windows = gw.getAllTitles()
            for w in windows:
                if title.lower() in w.lower():
                    win = gw.Window(w)
                    win.activate()
                    return {'success': True, 'message': f'Pencere aktif edildi: {w}'}
            return {'success': False, 'error': f'Pencere bulunamadı: {title}'}
        
        elif action == "minimize":
            active = gw.getActiveWindow()
            if active:
                active.minimize()
                return {'success': True, 'message': 'Pencere küçültüldü'}
            return {'success': False, 'error': 'Aktif pencere yok'}
        
        elif action == "maximize":
            active = gw.getActiveWindow()
            if active:
                active.maximize()
                return {'success': True, 'message': 'Pencere büyütüldü'}
            return {'success': False, 'error': 'Aktif pencere yok'}
        
        elif action == "close":
            active = gw.getActiveWindow()
            if active:
                active.close()
                return {'success': True, 'message': 'Pencere kapatıldı'}
            return {'success': False, 'error': 'Aktif pencere yok'}
        
        elif action == "resize":
            active = gw.getActiveWindow()
            if active:
                active.resize(1280, 720)
                return {'success': True, 'message': 'Pencere 1280x720 yapıldı'}
            return {'success': False, 'error': 'Aktif pencere yok'}
        
        return {'success': False, 'error': 'Bilinmeyen action'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def system_control(action: str) -> Dict[str, Any]:
    """Sistem kontrolü"""
    try:
        if action == "screenshot":
            import datetime
            filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            if pyautogui:
                pyautogui.screenshot(filename)
                return {'success': True, 'message': f'Ekran görüntüsü: {filename}', 'file': filename}
            return {'success': False, 'error': 'pyautogui yok'}
        
        elif action == "volume_up":
            if pyautogui:
                for _ in range(5):
                    pyautogui.press("volumeup")
            return {'success': True, 'message': 'Ses artırıldı'}
        
        elif action == "volume_down":
            if pyautogui:
                for _ in range(5):
                    pyautogui.press("volumedown")
            return {'success': True, 'message': 'Ses azaltıldı'}
        
        elif action == "mute":
            if pyautogui:
                pyautogui.press("volumemute")
            return {'success': True, 'message': 'Ses kapatıldı/açıldı'}
        
        elif action == "play_pause":
            if pyautogui:
                pyautogui.press("playpause")
            return {'success': True, 'message': 'Play/Pause'}
        
        elif action == "shutdown":
            subprocess.run("shutdown /s /t 60", shell=True)
            return {'success': True, 'message': 'Bilgisayar 60 saniye içinde kapanacak'}
        
        elif action == "restart":
            subprocess.run("shutdown /r /t 60", shell=True)
            return {'success': True, 'message': 'Bilgisayar 60 saniye içinde yeniden başlayacak'}
        
        elif action == "sleep":
            subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return {'success': True, 'message': 'Uyku modu'}
        
        elif action == "lock":
            subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
            return {'success': True, 'message': 'Ekran kilitlendi'}
        
        return {'success': False, 'error': 'Bilinmeyen action'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def file_operations(action: str, path: str = "", new_path: str = "") -> Dict[str, Any]:
    """Dosya işlemleri"""
    try:
        if action == "open_folder":
            if os.path.exists(path):
                os.startfile(path)
                return {'success': True, 'message': f'Klasör açıldı: {path}'}
            return {'success': False, 'error': 'Klasör bulunamadı'}
        
        elif action == "create_file":
            with open(path, 'w', encoding='utf-8') as f:
                f.write("")
            return {'success': True, 'message': f'Dosya oluşturuldu: {path}'}
        
        elif action == "delete_file":
            if os.path.exists(path):
                os.remove(path)
                return {'success': True, 'message': f'Dosya silindi: {path}'}
            return {'success': False, 'error': 'Dosya bulunamadı'}
        
        elif action == "copy_file":
            shutil.copy(path, new_path)
            return {'success': True, 'message': f'Dosya kopyalandı: {path} -> {new_path}'}
        
        elif action == "move_file":
            shutil.move(path, new_path)
            return {'success': True, 'message': f'Dosya taşındı: {path} -> {new_path}'}
        
        return {'success': False, 'error': 'Bilinmeyen action'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def web_control(action: str, url: str = "") -> Dict[str, Any]:
    """Web kontrolü"""
    try:
        if action == "open":
            if not url.startswith("http"):
                url = "https://" + url
            webbrowser.open(url)
            return {'success': True, 'message': f'Açılıyor: {url}'}
        
        elif action == "search":
            search_url = f"https://www.google.com/search?q={url}"
            webbrowser.open(search_url)
            return {'success': True, 'message': f'Aranıyor: {url}'}
        
        elif action == "youtube_search":
            search_url = f"https://www.youtube.com/results?search_query={url}"
            webbrowser.open(search_url)
            return {'success': True, 'message': f'YouTube\'da aranıyor: {url}'}
        
        return {'success': False, 'error': 'Bilinmeyen action'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============== UYGULAMA HARİTALARI ==============

APP_MAPPINGS = {
    # Tarayıcılar
    'chrome': {'type': 'cmd', 'value': 'start chrome'},
    'google chrome': {'type': 'cmd', 'value': 'start chrome'},
    'tarayıcı': {'type': 'cmd', 'value': 'start chrome'},
    'browser': {'type': 'cmd', 'value': 'start chrome'},
    'firefox': {'type': 'exe', 'value': 'firefox'},
    'mozilla': {'type': 'exe', 'value': 'firefox'},
    'edge': {'type': 'protocol', 'value': 'microsoft-edge'},
    'microsoft edge': {'type': 'protocol', 'value': 'microsoft-edge'},
    'opera': {'type': 'exe', 'value': 'opera'},
    'brave': {'type': 'exe', 'value': 'brave'},
    
    # Web Uygulamaları
    'spotify': {'type': 'web', 'value': 'https://open.spotify.com'},
    'discord': {'type': 'web', 'value': 'https://discord.com'},
    'whatsapp': {'type': 'web', 'value': 'https://web.whatsapp.com'},
    'telegram': {'type': 'web', 'value': 'https://web.telegram.org'},
    'netflix': {'type': 'web', 'value': 'https://netflix.com'},
    'youtube': {'type': 'web', 'value': 'https://youtube.com'},
    'snapchat': {'type': 'web', 'value': 'https://snapchat.com'},
    'instagram': {'type': 'web', 'value': 'https://instagram.com'},
    'tiktok': {'type': 'web', 'value': 'https://tiktok.com'},
    'twitter': {'type': 'web', 'value': 'https://twitter.com'},
    'x': {'type': 'web', 'value': 'https://x.com'},
    'facebook': {'type': 'web', 'value': 'https://facebook.com'},
    'reddit': {'type': 'web', 'value': 'https://reddit.com'},
    'twitch': {'type': 'web', 'value': 'https://twitch.tv'},
    'linkedin': {'type': 'web', 'value': 'https://linkedin.com'},
    
    # Microsoft 365
    'word': {'type': 'protocol', 'value': 'ms-word'},
    'excel': {'type': 'protocol', 'value': 'ms-excel'},
    'powerpoint': {'type': 'protocol', 'value': 'ms-powerpoint'},
    'outlook': {'type': 'protocol', 'value': 'outlook'},
    'teams': {'type': 'protocol', 'value': 'msteams'},
    
    # Sistem uygulamaları
    'notepad': {'type': 'exe', 'value': 'notepad'},
    'cmd': {'type': 'exe', 'value': 'cmd'},
    'powershell': {'type': 'exe', 'value': 'powershell'},
    'calc': {'type': 'exe', 'value': 'calc'},
    'paint': {'type': 'exe', 'value': 'mspaint'},
    'explorer': {'type': 'exe', 'value': 'explorer'},
    'ayarlar': {'type': 'protocol', 'value': 'ms-settings'},
    
    # Popüler uygulamalar
    'steam': {'type': 'exe', 'value': 'steam'},
    'epic games': {'type': 'exe', 'value': 'epicgameslauncher'},
    'vscode': {'type': 'exe', 'value': 'code'},
    'zoom': {'type': 'exe', 'value': 'zoom'},
    'obs': {'type': 'exe', 'value': 'obs64'},
    'vlc': {'type': 'exe', 'value': 'vlc'},
    
    # Oyunlar
    'minecraft': {'type': 'exe', 'value': 'prismlauncher'},
    'valorant': {'type': 'exe', 'value': 'valorant'},
    'league of legends': {'type': 'exe', 'value': 'league of legends'},
    'lol': {'type': 'exe', 'value': 'league of legends'},
    'fortnite': {'type': 'exe', 'value': 'fortnite'},
    'csgo': {'type': 'exe', 'value': 'csgo'},
    'cs2': {'type': 'exe', 'value': 'cs2'},
    'gta': {'type': 'exe', 'value': 'gta'},
    'gta v': {'type': 'exe', 'value': 'gtav'},
    'roblox': {'type': 'exe', 'value': 'roblox'},
    
    # DevOps
    'github': {'type': 'web', 'value': 'https://github.com'},
    'gitlab': {'type': 'web', 'value': 'https://gitlab.com'},
    'docker': {'type': 'exe', 'value': 'docker'},
}


def launch_app(app_name: str) -> Dict[str, Any]:
    """Uygulama başlatma fonksiyonu"""
    original_name = app_name
    app_name = app_name.lower().strip()
    
    # Türkçe ekleri kaldır
    turkish_suffixes = [' yi', ' yı', ' yu', ' yü', ' ni', ' nı', ' nu', ' nü']
    for suffix in sorted(turkish_suffixes, key=len, reverse=True):
        if app_name.endswith(suffix):
            app_name = app_name[:-len(suffix)].strip()
            break
    
    # Uygulama eşleştirme
    app_config = APP_MAPPINGS.get(app_name)
    
    # Fuzzy matching
    if not app_config:
        from difflib import SequenceMatcher
        best_match = None
        best_score = 0
        
        for key in APP_MAPPINGS.keys():
            score = SequenceMatcher(None, app_name, key).ratio()
            if score > best_score:
                best_score = score
                best_match = key
        
        if best_match and best_score >= 0.5:
            app_config = APP_MAPPINGS[best_match]
    
    if not app_config:
        raise ValueError(f"Uygulama bulunamadı: {original_name}")
    
    try:
        if app_config['type'] == 'web':
            webbrowser.open(app_config['value'])
        elif app_config['type'] == 'cmd':
            subprocess.Popen(app_config['value'], shell=True)
        elif app_config['type'] == 'protocol':
            subprocess.Popen(f'start {app_config["value"]}:', shell=True)
        else:
            try:
                os.startfile(app_config['value'])
            except:
                subprocess.Popen(app_config['value'], shell=True)
        
        return {
            'success': True,
            'message': f'{original_name.capitalize()} başlatılıyor...',
            'app': original_name
        }
        
    except Exception as e:
        try:
            subprocess.Popen(f'start "" "{app_config["value"]}"', shell=True)
            return {
                'success': True,
                'message': f'{original_name.capitalize()} başlatılıyor...',
                'app': original_name
            }
        except Exception as e:
            raise ValueError(f"Uygulama başlatılamadı: {str(e)}")


def handle_complex_command(command: str) -> Dict[str, Any]:
    """Komut işleyici - karmaşık istekleri işler"""
    cmd = command.lower()
    
    # Mouse kontrolü
    if "mouse" in cmd or "fare" in cmd:
        if "hareket" in cmd or "git" in cmd or "move" in cmd:
            return mouse_control("random")
        elif "tıkla" in cmd or "click" in cmd:
            return mouse_control("click")
        elif "sağ" in cmd:
            return mouse_control("right_click")
        elif "çift" in cmd:
            return mouse_control("double_click")
        elif "scroll" in cmd:
            return mouse_control("scroll", -500 if "aşağı" in cmd else 500)
    
    # Klavye kontrolü
    elif "yaz" in cmd or "type" in cmd or "yazı" in cmd:
        text = command.replace("yaz", "").replace("yazı", "").strip()
        if text:
            return keyboard_control("write", text)
    
    # Pencere kontrolü
    elif "pencere" in cmd or "window" in cmd:
        if "küçült" in cmd or "minimize" in cmd:
            return window_control("minimize")
        elif "büyüt" in cmd or "maximize" in cmd:
            return window_control("maximize")
        elif "kapat" in cmd or "close" in cmd:
            return window_control("close")
        elif "boyut" in cmd or "resize" in cmd:
            return window_control("resize")
        elif "listele" in cmd or "list" in cmd:
            return window_control("list")
    
    # Sistem kontrolü
    elif "ekran" in cmd or "screenshot" in cmd:
        return system_control("screenshot")
    elif "ses" in cmd:
        if "artır" in cmd:
            return system_control("volume_up")
        elif "azalt" in cmd:
            return system_control("volume_down")
        elif "kapat" in cmd or "mute" in cmd:
            return system_control("mute")
    elif "kilit" in cmd or "lock" in cmd:
        return system_control("lock")
    elif "uyku" in cmd or "sleep" in cmd:
        return system_control("sleep")
    elif "kapat" in cmd and "bilgisayar" in cmd:
        return system_control("shutdown")
    elif "yeniden" in cmd or "restart" in cmd:
        return system_control("restart")
    
    # Web kontrolü
    elif "youtube" in cmd:
        query = command.replace("youtube", "").replace("YouTube", "").strip()
        if query:
            return web_control("youtube_search", query)
        return web_control("open", "https://youtube.com")
    
    elif "google" in cmd or "ara" in cmd:
        query = command.replace("google", "").replace("ara", "").strip()
        return web_control("search", query)
    
    # Uygulama başlatma
    for app in APP_MAPPINGS.keys():
        if app in cmd:
            return launch_app(app)
    
    return {'success': False, 'error': 'Komut anlaşılamadı'}