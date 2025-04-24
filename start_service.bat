@echo off
REM Script para iniciar el servicio Python
REM Este script instala las dependencias y ejecuta el servidor FastAPI con Uvicorn

echo Instalando dependencias...
py -m pip install -r requirements.txt

if %ERRORLEVEL% neq 0 (
    echo Error: No se pudieron instalar las dependencias.
    exit /b 1
)

echo Limpiando archivos temporales...
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "modules\__pycache__" rmdir /s /q "modules\__pycache__"
if exist ".pytest_cache" rmdir /s /q ".pytest_cache"


echo Iniciando el servidor...
py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

REM El script terminará cuando se detenga el servidor (Ctrl+C)