@echo off
REM Script para iniciar el servicio Python
REM Este script instala las dependencias y ejecuta el servidor FastAPI con Uvicorn

echo Instalando dependencias...
py -m pip install -r requirements.txt

if %ERRORLEVEL% neq 0 (
    echo Error: No se pudieron instalar las dependencias.
    exit /b 1
)

echo Iniciando el servidor...
py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

REM El script terminará cuando se detenga el servidor (Ctrl+C)