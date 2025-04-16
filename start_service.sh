#!/bin/bash

# Script para iniciar el servicio Python
# Este script instala las dependencias y ejecuta el servidor FastAPI con Uvicorn

echo "Instalando dependencias..."
py -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Error: No se pudieron instalar las dependencias."
    exit 1
fi

echo "Iniciando el servidor..."
py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# El script terminará cuando se detenga el servidor (Ctrl+C)