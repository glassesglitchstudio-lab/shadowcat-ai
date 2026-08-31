"""
Shadowcat BETA - Utils Module
Sistem Takibi (psutil)
"""

import psutil
import platform
from typing import Dict, Any, Optional
import logging
import asyncio

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Uyarı eşiği (%90)
WARNING_THRESHOLD = 90


def get_cpu_usage() -> float:
    """CPU kullanımını al"""
    return psutil.cpu_percent(interval=0.1)


def get_memory_usage() -> Dict[str, Any]:
    """RAM kullanımını al"""
    mem = psutil.virtual_memory()
    return {
        'total': mem.total,
        'available': mem.available,
        'used': mem.used,
        'percent': mem.percent
    }


def get_disk_usage() -> Dict[str, Any]:
    """Disk kullanımını al"""
    disk = psutil.disk_usage('/')
    return {
        'total': disk.total,
        'used': disk.used,
        'free': disk.free,
        'percent': disk.percent
    }


def get_temperature() -> Optional[Dict[str, Any]]:
    """Sıcaklık bilgilerini al (Windows için)"""
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            return {name: temps[name] for name in temps}
        return None
    except:
        return None


def get_system_status() -> Dict[str, Any]:
    """
    Sistem durumu - CPU, RAM, sıcaklık
    Uyarı mekanizması ile
    """
    cpu_percent = get_cpu_usage()
    memory_info = get_memory_usage()
    disk_info = get_disk_usage()
    temperature = get_temperature()
    
    # Uyarı kontrolü
    warnings = []
    
    if cpu_percent >= WARNING_THRESHOLD:
        warnings.append(f"CPU kullanımı yüksek: %{cpu_percent:.1f}")
    
    if memory_info['percent'] >= WARNING_THRESHOLD:
        warnings.append(f"RAM kullanımı yüksek: %{memory_info['percent']:.1f}")
    
    if disk_info['percent'] >= WARNING_THRESHOLD:
        warnings.append(f"Disk kullanımı yüksek: %{disk_info['percent']:.1f}")
    
    return {
        'cpu': {
            'percent': cpu_percent,
            'count': psutil.cpu_count(),
            'frequency': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        },
        'memory': memory_info,
        'disk': disk_info,
        'temperature': temperature,
        'warnings': warnings,
        'platform': {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor()
        },
        'status': 'warning' if warnings else 'healthy'
    }


# Ses motoru (TTS) kaldırıldı - Sadece metin tabanlı çalışma
# def speak(text: str, rate: Optional[int] = None, volume: Optional[float] = None) -> bool:
#     """Metni sesli oku (pyttsx3)"""
#     pass

# async def speak_async(text: str, rate: Optional[int] = None, volume: Optional[float] = None) -> bool:
#     """Metni sesli oku (async)"""
#     pass

# def get_available_voices() -> list:
#     """Kullanılabilir sesleri listele"""
#     pass

# def set_voice(voice_id: str) -> bool:
#     """Ses motoru için ses seç"""
#     pass


def get_network_info() -> Dict[str, Any]:
    """Ağ bilgilerini al"""
    try:
        net_io = psutil.net_io_counters()
        net_connections = psutil.net_connections()
        
        return {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'connections': len(net_connections)
        }
    except Exception as e:
        logger.error(f"Ağ bilgisi hatası: {str(e)}")
        return {}


def get_process_info() -> Dict[str, Any]:
    """İşlem bilgilerini al"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu_percent': proc.info['cpu_percent'],
                    'memory_percent': proc.info['memory_percent']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # CPU kullanımına göre sırala
        processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
        
        return {
            'total_processes': len(processes),
            'top_processes': processes[:10]  # İlk 10 işlem
        }
    except Exception as e:
        logger.error(f"İşlem bilgisi hatası: {str(e)}")
        return {}


def check_system_health() -> Dict[str, Any]:
    """
    Sistem sağlık kontrolü
    CPU ve RAM %90 üzerindeyse uyarı ver
    """
    status = get_system_status()
    
    health_check = {
        'overall_health': 'good',
        'issues': [],
        'recommendations': []
    }
    
    if status['cpu']['percent'] >= WARNING_THRESHOLD:
        health_check['overall_health'] = 'warning'
        health_check['issues'].append('CPU kullanımı kritik seviyede')
        health_check['recommendations'].append('Ağır işlemleri kapatın')
    
    if status['memory']['percent'] >= WARNING_THRESHOLD:
        health_check['overall_health'] = 'warning'
        health_check['issues'].append('RAM kullanımı kritik seviyede')
        health_check['recommendations'].append('Gereksiz uygulamaları kapatın')
    
    if status['disk']['percent'] >= WARNING_THRESHOLD:
        health_check['overall_health'] = 'warning'
        health_check['issues'].append('Disk kullanımı kritik seviyede')
        health_check['recommendations'].append('Disk temizliği yapın')
    
    if not health_check['issues']:
        health_check['overall_health'] = 'excellent'
        health_check['recommendations'].append('Sistem sağlıklı')
    
    return health_check


# ==================== RESOURCE GUARD ====================

# Resource Guard Limitleri
VRAM_LIMIT_GB = 7.0  # 8 GB limit için 7 GB sınır
RAM_LIMIT_PERCENT = 85  # %85 RAM sınır

# Arka plan işlemleri duraklatma bayrağı
background_processes_paused = False


def get_vram_usage() -> Dict[str, Any]:
    """
    GPU VRAM kullanımını al (torch ile)
    
    Returns:
        Dict: VRAM kullanım bilgileri
    """
    try:
        import torch
        if torch.cuda.is_available():
            vram_allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)  # GB
            vram_reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)  # GB
            vram_total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)  # GB
            
            return {
                'allocated_gb': vram_allocated,
                'reserved_gb': vram_reserved,
                'total_gb': vram_total,
                'percent': (vram_allocated / vram_total) * 100 if vram_total > 0 else 0,
                'available': True
            }
        else:
            return {
                'allocated_gb': 0,
                'reserved_gb': 0,
                'total_gb': 0,
                'percent': 0,
                'available': False
            }
    except Exception as e:
        logger.error(f"VRAM kontrol hatası: {str(e)}")
        return {
            'allocated_gb': 0,
            'reserved_gb': 0,
            'total_gb': 0,
            'percent': 0,
            'available': False
        }


def check_resource_limits() -> Dict[str, Any]:
    """
    Kaynak limitlerini kontrol et
    VRAM 7GB ve RAM %85 limitleri
    
    Returns:
        Dict: Kaynak durumu ve uyarılar
    """
    global background_processes_paused
    
    vram_info = get_vram_usage()
    memory_info = get_memory_usage()
    
    warnings = []
    actions_taken = []
    
    # VRAM kontrolü
    if vram_info['available'] and vram_info['allocated_gb'] > VRAM_LIMIT_GB:
        warnings.append(f"VRAM kritik: {vram_info['allocated_gb']:.2f} GB / {VRAM_LIMIT_GB} GB")
        # Sesli uyarı kaldırıldı - Sadece metin tabanlı çalışma
        actions_taken.append("VRAM uyarısı (metin)")
    
    # RAM kontrolü
    if memory_info['percent'] > RAM_LIMIT_PERCENT:
        warnings.append(f"RAM kritik: %{memory_info['percent']:.1f} / %{RAM_LIMIT_PERCENT}")
        
        # Arka plan işlemlerini duraklat
        if not background_processes_paused:
            background_processes_paused = True
            actions_taken.append("Arka plan işlemleri duraklatıldı")
            logger.warning("Arka plan işlemleri duraklatıldı (RAM limit)")
    
    elif memory_info['percent'] < (RAM_LIMIT_PERCENT - 10) and background_processes_paused:
        # RAM %75 altına düşerse işlemleri devam ettir
        background_processes_paused = False
        actions_taken.append("Arka plan işlemleri devam ettirildi")
        logger.info("Arka plan işlemleri devam ettirildi (RAM normal)")
    
    return {
        'vram': vram_info,
        'memory': memory_info,
        'warnings': warnings,
        'actions_taken': actions_taken,
        'background_paused': background_processes_paused,
        'can_proceed': len(warnings) == 0
    }


def pause_background_processes() -> bool:
    """
    Arka plan işlemlerini duraklat (vision taraması vb.)
    
    Returns:
        bool: Başarılı mı
    """
    global background_processes_paused
    background_processes_paused = True
    logger.warning("Arka plan işlemleri duraklatıldı")
    return True


def resume_background_processes() -> bool:
    """
    Arka plan işlemlerini devam ettir
    
    Returns:
        bool: Başarılı mı
    """
    global background_processes_paused
    background_processes_paused = False
    logger.info("Arka plan işlemleri devam ettirildi")
    return True


def calculate_dynamic_max_tokens(base_max_tokens: int = 2048) -> int:
    """
    Sistem yüküne göre dinamik max_tokens hesapla
    Foundry için yanıt uzunluğunu otomatik kısalt
    
    Args:
        base_max_tokens: Temel max_tokens değeri (default: 2048)
        
    Returns:
        int: Dinamik max_tokens değeri
    """
    vram_info = get_vram_usage()
    memory_info = get_memory_usage()
    cpu_percent = get_cpu_usage()
    
    # Sistem yükü skoru (0-1, yüksek = yük)
    load_score = 0.0
    
    # VRAM yükü
    if vram_info['available']:
        vram_load = vram_info['allocated_gb'] / vram_info['total_gb'] if vram_info['total_gb'] > 0 else 0
        load_score += vram_load * 0.4
    
    # RAM yükü
    ram_load = memory_info['percent'] / 100
    load_score += ram_load * 0.3
    
    # CPU yükü
    cpu_load = cpu_percent / 100
    load_score += cpu_load * 0.3
    
    # Dinamik max_tokens hesapla
    if load_score < 0.5:
        # Düşük yük - tam uzunluk
        return base_max_tokens
    elif load_score < 0.7:
        # Orta yük - %75 uzunluk
        return int(base_max_tokens * 0.75)
    elif load_score < 0.85:
        # Yüksek yük - %50 uzunluk
        return int(base_max_tokens * 0.5)
    else:
        # Kritik yük - %25 uzunluk
        return int(base_max_tokens * 0.25)


def can_launch_ai_query() -> tuple[bool, str]:
    """
    AI sorgusu başlatmadan önce kaynak kontrolü
    
    Returns:
        tuple: (başlatılabilir_mi, mesaj)
    """
    resource_status = check_resource_limits()
    
    if not resource_status['can_proceed']:
        return False, "Kaynak limitleri aşıldı, lütfen bekleyin"
    
    if resource_status['background_paused']:
        return False, "Arka plan işlemleri duraklatıldı, sistem yükü yüksek"
    
    return True, "Kaynaklar uygun, sorgu başlatılabilir"
