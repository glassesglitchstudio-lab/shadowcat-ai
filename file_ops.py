"""
GlassesCat - Dosya İşlemleri Modülü
AI'ın dosya okuma/yazma/kopyalama işlemleri yapması için
Güvenli ve kontrollü dosya sistemi erişimi
"""

import os
import json
import shutil
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union

class FileOperations:
    """
    Güvenli dosya işlemleri sistemi
    - Okuma, yazma, kopyalama
    - Dizin yönetimi
    - Dosya arama
    - Meta veri yönetimi
    """
    
    # İzin verilen dizinler (güvenlik) — dinamik kullanıcı yolu
    ALLOWED_PATHS = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
    ]
    
    def __init__(self, allowed_dirs: List[str] = None):
        if allowed_dirs:
            self.allowed_dirs = [Path(d).resolve() for d in allowed_dirs]
        else:
            self.allowed_dirs = [Path(d).resolve() for d in self.ALLOWED_PATHS]
        
        self.lock = threading.Lock()
        
        # Operations log
        self.operation_log = []
        self.max_log_size = 1000
    
    def _is_path_allowed(self, path: str) -> bool:
        """Yolun izin verilip verilmediğini kontrol et"""
        try:
            resolved = Path(path).resolve()
            
            # Ana proje dizinine her zaman izin ver
            project_root = Path(__file__).parent.resolve()
            if resolved.is_relative_to(project_root):
                return True
            
            for allowed in self.allowed_dirs:
                if resolved.is_relative_to(allowed):
                    return True
            
            return False
        except:
            return False
    
    def _log_operation(self, operation: str, path: str, success: bool, details: str = ""):
        """İşlemi logla"""
        with self.lock:
            self.operation_log.append({
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "path": path,
                "success": success,
                "details": details
            })
            
            if len(self.operation_log) > self.max_log_size:
                self.operation_log = self.operation_log[-self.max_log_size:]
    
    def read_file(self, filepath: str, encoding: str = 'utf-8') -> Dict:
        """Dosya okuma"""
        if not self._is_path_allowed(filepath):
            return {"success": False, "error": "Bu dizine erişim yetkiniz yok"}
        
        try:
            path = Path(filepath)
            if not path.exists():
                return {"success": False, "error": "Dosya bulunamadı"}
            
            if not path.is_file():
                return {"success": False, "error": "Bu bir dosya değil"}
            
            # Büyük dosya kontrolü (5MB)
            if path.stat().st_size > 5 * 1024 * 1024:
                return {"success": False, "error": "Dosya çok büyük (5MB limit)"}
            
            content = path.read_text(encoding=encoding)
            self._log_operation("read", filepath, True)
            
            return {
                "success": True,
                "content": content,
                "size": path.stat().st_size,
                "lines": len(content.splitlines()),
                "encoding": encoding
            }
        except Exception as e:
            self._log_operation("read", filepath, False, str(e))
            return {"success": False, "error": str(e)}
    
    def write_file(self, filepath: str, content: str, encoding: str = 'utf-8', append: bool = False) -> Dict:
        """Dosya yazma"""
        if not self._is_path_allowed(filepath):
            return {"success": False, "error": "Bu dizine erişim yetkiniz yok"}
        
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if append else 'w'
            with open(path, mode, encoding=encoding) as f:
                f.write(content)
            
            self._log_operation("write", filepath, True)
            
            return {
                "success": True,
                "path": str(path),
                "size": path.stat().st_size,
                "mode": "append" if append else "write"
            }
        except Exception as e:
            self._log_operation("write", filepath, False, str(e))
            return {"success": False, "error": str(e)}
    
    def copy_file(self, source: str, destination: str) -> Dict:
        """Dosya kopyalama"""
        if not self._is_path_allowed(source) or not self._is_path_allowed(destination):
            return {"success": False, "error": "Dizin erişim yetkiniz yok"}
        
        try:
            src = Path(source)
            dst = Path(destination)
            
            if not src.exists():
                return {"success": False, "error": "Kaynak dosya bulunamadı"}
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            
            self._log_operation("copy", f"{source} -> {destination}", True)
            
            return {
                "success": True,
                "source": str(src),
                "destination": str(dst),
                "size": dst.stat().st_size
            }
        except Exception as e:
            self._log_operation("copy", f"{source} -> {destination}", False, str(e))
            return {"success": False, "error": str(e)}
    
    def delete_file(self, filepath: str) -> Dict:
        """Dosya silme"""
        if not self._is_path_allowed(filepath):
            return {"success": False, "error": "Bu dizine erişim yetkiniz yok"}
        
        try:
            path = Path(filepath)
            
            if not path.exists():
                return {"success": False, "error": "Dosya bulunamadı"}
            
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
            
            self._log_operation("delete", filepath, True)
            
            return {"success": True, "path": filepath}
        except Exception as e:
            self._log_operation("delete", filepath, False, str(e))
            return {"success": False, "error": str(e)}
    
    def create_directory(self, dirpath: str) -> Dict:
        """Dizin oluşturma"""
        if not self._is_path_allowed(dirpath):
            return {"success": False, "error": "Bu dizine erişim yetkiniz yok"}
        
        try:
            path = Path(dirpath)
            path.mkdir(parents=True, exist_ok=True)
            
            self._log_operation("mkdir", dirpath, True)
            
            return {"success": True, "path": str(path)}
        except Exception as e:
            self._log_operation("mkdir", dirpath, False, str(e))
            return {"success": False, "error": str(e)}
    
    def list_directory(self, dirpath: str, include_hidden: bool = False) -> Dict:
        """Dizin içeriğini listele"""
        if not self._is_path_allowed(dirpath):
            return {"success": False, "error": "Bu dizine erişim yetkiniz yok"}
        
        try:
            path = Path(dirpath)
            
            if not path.exists():
                return {"success": False, "error": "Dizin bulunamadı"}
            
            if not path.is_dir():
                return {"success": False, "error": "Bu bir dizin değil"}
            
            items = []
            for item in path.iterdir():
                if not include_hidden and item.name.startswith('.'):
                    continue
                
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "is_file": item.is_file(),
                    "is_dir": item.is_dir(),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            
            return {
                "success": True,
                "path": str(path),
                "items": items,
                "count": len(items)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def search_files(self, root_dir: str, pattern: str, recursive: bool = True) -> Dict:
        """Dosya arama"""
        if not self._is_path_allowed(root_dir):
            return {"success": False, "error": "Bu dizine erişim yetkiniz yok"}
        
        try:
            root = Path(root_dir)
            results = []
            
            # Glob pattern dönüştürme
            glob_pattern = f"*{pattern}*" if '*' not in pattern else pattern
            
            if recursive:
                for match in root.rglob(glob_pattern):
                    if match.is_file():
                        results.append({
                            "name": match.name,
                            "path": str(match),
                            "size": match.stat().st_size,
                            "extension": match.suffix
                        })
            else:
                for match in root.glob(glob_pattern):
                    if match.is_file():
                        results.append({
                            "name": match.name,
                            "path": str(match),
                            "size": match.stat().st_size,
                            "extension": match.suffix
                        })
            
            return {
                "success": True,
                "root": str(root),
                "pattern": pattern,
                "results": results[:100],  # Max 100 sonuç
                "count": len(results)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_file_info(self, filepath: str) -> Dict:
        """Dosya bilgilerini getir"""
        if not self._is_path_allowed(filepath):
            return {"success": False, "error": "Bu dizine erişim yetkiniz yok"}
        
        try:
            path = Path(filepath)
            
            if not path.exists():
                return {"success": False, "error": "Dosya bulunamadı"}
            
            stat = path.stat()
            
            info = {
                "success": True,
                "name": path.name,
                "path": str(path),
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "size": stat.st_size,
                "size_formatted": self._format_size(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "extension": path.suffix,
                "parent": str(path.parent)
            }
            
            return info
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_operation_log(self, limit: int = 50) -> List[Dict]:
        """İşlem loglarını getir"""
        with self.lock:
            return self.operation_log[-limit:]
    
    def _format_size(self, size: int) -> str:
        """Dosya boyutunu formatla"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


# Global instance
_file_ops_instance = None

def get_file_ops() -> FileOperations:
    """Global file operations instance"""
    global _file_ops_instance
    if _file_ops_instance is None:
        _file_ops_instance = FileOperations()
    return _file_ops_instance
