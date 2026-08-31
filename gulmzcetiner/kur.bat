@echo off
chcp 65001 >nul
echo ============================================================
echo   GULMEZCETINERMAX - Hizli Kurulum
echo   Shadowcat Software | CEO: Berkay
echo ============================================================
echo.

echo [1/3] Ollama kontrol ediliyor...
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo HATA: Ollama bulunamadi!
    echo.
    echo Ollama'yi yuklemek icin:
    echo   1. https://ollama.com/download adresine git
    echo   2. Windows surumunu indir ve yukle
    echo   3. Bu scripti tekrar calistir
    echo.
    pause
    exit /b 1
)
echo   Ollama bulundu!

echo.
echo [2/3] Base model kontrol ediliyor...
ollama list | findstr "qwen2.5-coder" >nul 2>&1
if %errorlevel% neq 0 (
    echo   qwen2.5-coder:14b indiriliyor... (bu islem uzun surebilir)
    ollama pull qwen2.5-coder:14b
) else (
    echo   qwen2.5-coder:14b zaten mevcut!
)

echo.
echo [3/3] GulmezCetinerMax Ollama'ya yukleniyor...
cd /d "%~dp0"
ollama rm gulmzcetinermax:latest >nul 2>&1
ollama create gulmzcetinermax:latest -f Modelfile

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   GULMEZCETINERMAX BASARIYLA YUKLENDI!
    echo ============================================================
    echo.
    echo   Test etmek icin: ollama run gulmzcetinermax:latest
    echo   Shadowcat AI ile kullanmak icin: python glassescat_agent.py
    echo.
) else (
    echo.
    echo HATA: Model yukleme basarisiz!
    echo.
)

pause
