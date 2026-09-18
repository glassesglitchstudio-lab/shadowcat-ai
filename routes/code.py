from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import os
import sys
import subprocess
import time
import logging

from middleware.auth import require_auth, require_admin

logger = logging.getLogger("routes.code")
router = APIRouter()

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PATH = os.path.join(_PROJECT_ROOT, ".venv")


class CodeExecuteRequest(BaseModel):
    code: str
    language: Optional[str] = "python"


SUPPORTED_LANGUAGES = ["python", "javascript", "lua", "ruby", "go"]  # bash: shell=True RCE riski → devre dışı


def _get_lang_config():
    venv_python = os.path.join(VENV_PATH, "Scripts", "python.exe")
    return {
        "python": {
            "cmd": [venv_python, "-c"],
            "timeout": 30,
            "ext": ".py",
            "use_code_arg": True,
        },
        "javascript": {
            "cmd": ["node", "-e"],
            "timeout": 30,
            "ext": ".js",
            "use_code_arg": True,
        },
        "bash": {
            "cmd": ["powershell", "-Command"] if sys.platform == "win32" else ["bash", "-c"],
            "timeout": 30,
            "ext": ".sh",
            "use_code_arg": True,
            "shell": True,
            "disabled": True,  # shell=True ile komut enjeksiyonu → sadece sandbox içinden açılır
        },
        "lua": {
            "cmd": ["lua", "-e"],
            "timeout": 30,
            "ext": ".lua",
            "use_code_arg": True,
        },
        "ruby": {
            "cmd": ["ruby", "-e"],
            "timeout": 30,
            "ext": ".rb",
            "use_code_arg": True,
        },
        "go": {
            "cmd": None,
            "timeout": 60,
            "ext": ".go",
            "use_code_arg": False,
        },
    }


@router.post("/execute")
async def code_execute(req: CodeExecuteRequest, user=Depends(require_auth)):
    code = req.code.strip()
    language = req.language.strip().lower()

    if not code:
        raise HTTPException(status_code=400, detail="Kod bos olamaz!")

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dil: {language}. Desteklenenler: {', '.join(SUPPORTED_LANGUAGES)}",
        )

    lang_config = _get_lang_config()
    config = lang_config[language]

    if config.get("disabled"):
        raise HTTPException(
            status_code=403,
            detail=f"{language} calistirma guvenlik nedeniyle devre disi (shell injection riski)",
        )

    try:
        # Go icin ozel islem (gecici dosya)
        if language == "go":
            scripts_dir = os.path.join(_PROJECT_ROOT, "user_scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            safe_name = f"gocode_{int(time.time())}.go"
            file_path = os.path.join(scripts_dir, safe_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            try:
                result = subprocess.run(
                    ["go", "run", file_path],
                    capture_output=True,
                    text=True,
                    timeout=config["timeout"],
                    cwd=scripts_dir,
                )
                os.remove(file_path)
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr if result.stderr else None,
                    "language": language,
                }
            except subprocess.TimeoutExpired:
                os.remove(file_path)
                raise HTTPException(
                    status_code=408,
                    detail=f"Go kodu {config['timeout']}s icinde tamamlanmadi",
                )
            except FileNotFoundError:
                raise HTTPException(status_code=400, detail="Go derleyicisi bulunamadi. 'go' kurulu degil.")

        # Python kodu icin venv kullan
        if language == "python":
            try:
                result = subprocess.run(
                    config["cmd"] + [code],
                    capture_output=True,
                    text=True,
                    timeout=config["timeout"],
                    cwd=_PROJECT_ROOT,
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr if result.stderr else None,
                    "language": language,
                }
            except subprocess.TimeoutExpired:
                raise HTTPException(
                    status_code=408,
                    detail=f"Python kodu {config['timeout']}s icinde tamamlanmadi",
                )

        # JavaScript / Bash / Lua / Ruby
        use_shell = language == "bash"
        try:
            cmd = config["cmd"] + [code]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config["timeout"],
                shell=use_shell,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.stderr else None,
                "language": language,
            }
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=408,
                detail=f"{language.capitalize()} kodu {config['timeout']}s icinde tamamlanmadi",
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=400,
                detail=f"{language.capitalize()} calistiricisi bulunamadi. Sistemde kurulu oldugundan emin olun.",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calistirma hatasi: {str(e)}")
