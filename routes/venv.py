from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import os
import re
import sys
import subprocess
import time
import logging

from middleware.auth import require_auth

logger = logging.getLogger("routes.venv")
router = APIRouter()

# VENV yolu
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PATH = os.path.join(_PROJECT_ROOT, ".venv")


def _venv_python():
    return os.path.join(VENV_PATH, "Scripts", "python.exe")


def _venv_pip():
    return os.path.join(VENV_PATH, "Scripts", "pip.exe")


def _check_venv_exists() -> bool:
    return os.path.exists(VENV_PATH) and os.path.exists(_venv_python())


def _check_package_installed(package: str) -> bool:
    try:
        result = subprocess.run(
            [_venv_python(), "-c", f"import {package}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_python_version_compatible() -> bool:
    v = sys.version_info
    return (3, 8) <= (v.major, v.minor) <= (3, 12)


class VenvInstallRequest(BaseModel):
    pass


class VenvExecuteRequest(BaseModel):
    code: str
    filename: Optional[str] = "custom_script.py"
    auto_install: Optional[bool] = True


class VenvCreateGameRequest(BaseModel):
    description: str
    type: Optional[str] = "auto"


# ── GET /api/venv/status ──────────────────────────────────────────────────


@router.get("/status")
async def venv_status():
    try:
        exists = _check_venv_exists()
        has_pygame = _check_package_installed("pygame") if exists else False
        has_numpy = _check_package_installed("numpy") if exists else False
        has_tkinter = _check_package_installed("tkinter") if exists else True

        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        pygame_compatible = _check_python_version_compatible()

        message = None
        if exists and not has_pygame and not pygame_compatible:
            message = "Pygame kurulumu gerekli. /venv-kur komutu ile kurabilirsiniz!"

        return {
            "exists": exists,
            "hasPygame": has_pygame,
            "hasNumpy": has_numpy,
            "hasTkinter": has_tkinter,
            "pythonVersion": python_version,
            "pygameCompatible": pygame_compatible,
            "path": VENV_PATH,
            "message": message,
        }
    except Exception as e:
        return {
            "exists": False,
            "hasPygame": False,
            "hasNumpy": False,
            "hasTkinter": False,
            "pythonVersion": None,
            "pygameCompatible": False,
            "error": str(e),
        }


# ── POST /api/venv/setup ──────────────────────────────────────────────────


@router.post("/setup")
async def venv_setup(user=Depends(require_auth)):
    try:
        if _check_venv_exists():
            return {"success": True, "message": "VENV zaten mevcut!"}

        base_path = os.path.dirname(VENV_PATH)
        result = subprocess.run(
            [sys.executable, "-m", "venv", ".venv"],
            cwd=base_path,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            return {"success": True, "message": "Python sanal alani (.venv) olusturuldu!"}
        else:
            raise HTTPException(status_code=500, detail=f"VENV olusturulamadi: {result.stderr}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kurulum hatasi: {str(e)}")


# ── POST /api/venv/install ─────────────────────────────────────────────────


@router.post("/install")
async def venv_install(user=Depends(require_auth)):
    try:
        if not _check_venv_exists():
            raise HTTPException(status_code=400, detail="Once VENV olusturulmali!")

        venv_pip = _venv_pip()
        venv_python = _venv_python()

        # pip upgrade
        subprocess.run(
            [venv_python, "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            timeout=60,
        )

        # setuptools downgrade (pygame uyumluluk)
        subprocess.run(
            [venv_pip, "install", "setuptools==65.5.1", "--force-reinstall"],
            capture_output=True,
            timeout=60,
        )

        # wheel
        subprocess.run([venv_pip, "install", "wheel"], capture_output=True, timeout=30)

        # Pygame binary kurulumu
        cmds_to_try = [
            [venv_pip, "install", "pygame", "--only-binary", ":all:", "--no-cache-dir"],
            [venv_pip, "install", "pygame==2.5.2", "--only-binary", ":all:", "--no-cache-dir"],
            [venv_pip, "install", "pygame==2.4.0", "--only-binary", ":all:", "--no-cache-dir"],
            [venv_pip, "install", "pygame==2.1.3", "--only-binary", ":all:", "--no-cache-dir"],
            [venv_pip, "install", "pygame", "--prefer-binary", "--no-build-isolation"],
        ]

        for cmd in cmds_to_try:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                if result.returncode == 0 and _check_package_installed("pygame"):
                    subprocess.run(
                        [venv_pip, "install", "numpy", "--only-binary", ":all:"],
                        capture_output=True,
                        timeout=60,
                    )
                    return {"success": True, "message": "Pygame ve Numpy kuruldu!"}
            except subprocess.TimeoutExpired:
                continue

        if not _check_python_version_compatible():
            return {
                "success": True,
                "warning": True,
                "message": "Python 3.13 icin pygame destegi yok! Tkinter kullanabilirsiniz.",
                "alternative": "tkinter",
            }

        raise HTTPException(status_code=500, detail="Pygame kurulumu basarisiz. Python 3.8-3.12 onerilir.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kurulum hatasi: {str(e)}")


# ── POST /api/venv/execute ─────────────────────────────────────────────────


@router.post("/execute")
async def venv_execute(req: VenvExecuteRequest, user=Depends(require_auth)):
    try:
        code = req.code.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Kod bos olamaz!")

        if not _check_venv_exists():
            raise HTTPException(status_code=400, detail="VENV bulunamadi! Once Sanal Alani kurun.")

        scripts_dir = os.path.join(_PROJECT_ROOT, "user_scripts")
        os.makedirs(scripts_dir, exist_ok=True)

        safe_filename = os.path.basename(req.filename)
        if not safe_filename.endswith(".py"):
            safe_filename += ".py"

        file_path = os.path.join(scripts_dir, safe_filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Auto-install missing packages
        if req.auto_install:
            imports = re.findall(r"^import\s+(\w+)|^from\s+(\w+)", code, re.MULTILINE)
            builtin_modules = {
                "os", "sys", "json", "re", "time", "datetime", "random",
                "math", "collections", "itertools", "functools", "typing", "pathlib",
            }
            packages = set()
            for imp in imports:
                pkg = imp[0] or imp[1]
                if pkg not in builtin_modules:
                    packages.add(pkg)

            if packages:
                venv_pip = _venv_pip()
                for pkg in packages:
                    try:
                        subprocess.run(
                            [venv_pip, "install", pkg, "--quiet"],
                            capture_output=True,
                            timeout=60,
                        )
                    except Exception:
                        pass

        try:
            result = subprocess.run(
                [_venv_python(), file_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=scripts_dir,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.stderr else None,
                "filename": safe_filename,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Kod 30 saniye icinde tamamlanmadi (timeout)",
                "filename": safe_filename,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calistirma hatasi: {str(e)}")


# ── POST /api/venv/create-game ─────────────────────────────────────────────


@router.post("/create-game")
async def venv_create_game(req: VenvCreateGameRequest):
    try:
        description = req.description.strip()
        if not description:
            raise HTTPException(status_code=400, detail="Oyun/uygulama tanimi gerekli!")

        from model_router import get_model_router

        router_instance = get_model_router()

        prompt = (
            f'Kullanici su istegi yapti: "{description}"\n\n'
            f"Buna gore Python kodu yaz. Sadece calisir Python kodu ver, aciklama ekleme.\n"
            f"Oyun/uygulama turu: {req.type}\n\n"
            "Kurallar:\n"
            "1. Sadece Python kodu, hic aciklama ekleme\n"
            "2. pygame kullanacaksan init() unutma\n"
            "3. Dosya islemleri varsa try-except kullan\n"
            "4. Sonsuz dongu (while True) varsa quit mekanizmasi ekle (ESC veya X tusuna cikis)\n"
            "5. Kod direkt calissin, hata vermesin\n"
        )

        ai_result = router_instance.chat(prompt)
        code = ai_result.get("response", "")

        # Kod bloklarini temizle
        code = re.sub(r"```python\n?", "", code)
        code = re.sub(r"```\n?", "", code)
        code = code.strip()

        safe_name = re.sub(r"[^\w]", "_", description[:30]).lower()
        filename = f"{safe_name}_{int(time.time())}.py"

        scripts_dir = os.path.join(_PROJECT_ROOT, "user_scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        file_path = os.path.join(scripts_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Yeni pencerede baslat
        if sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/c", "start", "python", file_path],
                cwd=scripts_dir,
                shell=True,
            )
        else:
            subprocess.Popen(
                [_venv_python(), file_path],
                cwd=scripts_dir,
            )

        return {
            "success": True,
            "message": f"'{description}' olusturuldu ve baslatildi!",
            "filename": filename,
            "code_preview": code[:200] + "..." if len(code) > 200 else code,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Oyun olusturma hatasi: {str(e)}")
