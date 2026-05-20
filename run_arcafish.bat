@echo off
setlocal

cd /d "%~dp0"

echo.
echo ========================================
echo  ARCAFISH - servidor local
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual .venv...
    python -m venv .venv
    if errorlevel 1 goto error
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto error

echo Instalando/actualizando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 goto error

if not exist ".env" (
    echo Creando .env desde .env.example...
    copy ".env.example" ".env" >nul
)

echo.
echo Si Open-Meteo falla por certificados en este equipo, edita .env y usa:
echo HTTP_VERIFY_SSL=false
echo.
echo Abre en el navegador:
echo http://127.0.0.1:8000
echo.

start "" powershell -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:8000'"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
goto end

:error
echo.
echo No se pudo arrancar ARCAFISH. Revisa el mensaje anterior.
pause

:end
endlocal
