# -*- coding: utf-8 -*-
"""
Shadowcat System Monitor - canli sistem izleme modulu
CPU / RAM / Disk / GPU / Ag / Islemci verilerini toplar.
"""
import os, time, platform, socket
from typing import Dict, Any


class SystemMonitor:
    """Sistem saglik verilerini toplayan sinif"""

    def __init__(self):
        self._start_time = time.time()

    def get_uptime(self) -> str:
        """Sistemin calisma suresi"""
        secs = int(time.time() - self._start_time)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}s {m}dk {s}sn"

    def get_cpu(self) -> Dict[str, Any]:
        """CPU kullanim verileri"""
        try:
            import psutil
            return {
                "percent": psutil.cpu_percent(interval=0.1),
                "cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
                "frequency_mhz": round(psutil.cpu_freq().current, 1) if psutil.cpu_freq() else None,
            }
        except ImportError:
            return {"error": "psutil yok"}

    def get_memory(self) -> Dict[str, Any]:
        """RAM kullanim verileri"""
        try:
            import psutil
            vm = psutil.virtual_memory()
            return {
                "total_gb": round(vm.total / 1024**3, 1),
                "used_gb": round(vm.used / 1024**3, 1),
                "free_gb": round(vm.free / 1024**3, 1),
                "percent": vm.percent,
                "swap_percent": psutil.swap_memory().percent,
            }
        except ImportError:
            return {"error": "psutil yok"}

    def get_disk(self) -> Dict[str, Any]:
        """Disk kullanim verileri"""
        try:
            import psutil
            parts = []
            for p in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    parts.append({
                        "mount": p.mountpoint,
                        "total_gb": round(u.total / 1024**3, 1),
                        "used_gb": round(u.used / 1024**3, 1),
                        "free_gb": round(u.free / 1024**3, 1),
                        "percent": u.percent,
                    })
                except Exception:
                    continue
            return {"partitions": parts}
        except ImportError:
            return {"error": "psutil yok"}

    def get_gpu(self) -> Dict[str, Any]:
        """GPU kullanim verileri (torch varsa)"""
        try:
            import torch
            if not torch.cuda.is_available():
                return {"available": False, "message": "CUDA yok"}
            props = []
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i)
                props.append({
                    "index": i,
                    "name": name,
                    "memory_allocated_gb": round(torch.cuda.memory_allocated(i) / 1024**3, 2),
                    "memory_reserved_gb": round(torch.cuda.memory_reserved(i) / 1024**3, 2),
                })
            return {"available": True, "devices": props}
        except ImportError:
            return {"available": False, "message": "torch yok"}

    def get_network(self) -> Dict[str, Any]:
        """Ag baglanti bilgileri"""
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return {"hostname": hostname, "ip": ip}
        except Exception as e:
            return {"error": str(e)}

    def get_top_processes(self, limit: int = 5) -> list:
        """En cok RAM kullanan surecler"""
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "memory_percent"]):
                try:
                    procs.append(p.info)
                except Exception:
                    continue
            procs.sort(key=lambda x: x.get("memory_percent", 0), reverse=True)
            return procs[:limit]
        except ImportError:
            return []

    def get_all(self) -> Dict[str, Any]:
        """Tum sistem verilerini tek seferde topla"""
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uptime": self.get_uptime(),
            "cpu": self.get_cpu(),
            "memory": self.get_memory(),
            "disk": self.get_disk(),
            "gpu": self.get_gpu(),
            "network": self.get_network(),
            "top_processes": self.get_top_processes(),
        }


_monitor_instance = None

def get_system_monitor() -> SystemMonitor:
    """Singleton monitor ornegi"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = SystemMonitor()
    return _monitor_instance


if __name__ == "__main__":
    import json
    mon = get_system_monitor()
    print(json.dumps(mon.get_all(), indent=2, ensure_ascii=False))