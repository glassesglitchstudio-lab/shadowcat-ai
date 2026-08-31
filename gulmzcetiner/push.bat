@echo off
chcp 65001 >nul
echo ============================================================
echo   GULMEZCETINERMAX - OLLAMA LIBRARY PUSH
echo   Shadowcat Software | CEO: Berkay
echo ============================================================
echo.

set /p USERNAME="Ollama kullanici adiniz: "

if "%USERNAME%"=="" (
    echo HATA: Kullanici adi bos birakilamaz!
    pause
    exit /b 1
)

echo.
echo Model pushlaniyor: %USERNAME%/GulmezCetinerMax:latest
echo.
echo Bu islem model boyutuna gore uzun surebilir (9 GB)...
echo.

ollama push GulmezCetinerMax %USERNAME%/GulmezCetinerMax:latest

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   BASARILI! GulmezCetinerMax Ollama Library'de!
    echo ============================================================
    echo.
    echo   Herkes su komutla indirebilir:
    echo   ollama pull %USERNAME%/GulmezCetinerMax:latest
    echo.
    echo   Profil: https://ollama.com/%USERNAME%
    echo.
) else (
    echo.
    echo HATA: Push islemi basarisiz!
    echo.
    echo Olasi nedenler:
    echo   1. Ollama hesabi olusturmadiniz: https://ollama.com/signup
    echo   2. Kullanici adi yanlis
    echo   3. Internet baglantisi sorunu
    echo.
)

pause
