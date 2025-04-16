# Dynamic Microservice Runner

Este proyecto implementa un servidor FastAPI que puede cargar dinámicamente módulos de microservicios en tiempo de ejecución. Proporciona una interfaz web simple para cargar archivos Python que contienen instancias de `APIRouter` de FastAPI.

## Características

*   **Carga Dinámica de Módulos:** Sube archivos `.py` que contienen `APIRouter` a través de la interfaz web. El servidor los cargará automáticamente.
*   **Interfaz Web:** Una página HTML simple (`/`) para cargar nuevos módulos de servicio.
*   **Documentación Automática:** Accede a `/docs` para ver la documentación OpenAPI (Swagger UI) generada automáticamente para todos los endpoints cargados.
*   **Recarga Automática:** Los cambios en los archivos de módulo existentes o la adición de nuevos módulos activan una recarga del servidor (cuando se ejecuta con `uvicorn --reload`).
*   **Ejemplo Incluido:** Un servicio de ejemplo (`plot_service.py`) que genera un gráfico de onda sinusoidal accesible en `/plot_service/plot`.
*   **Soporte Docker:** Incluye `Dockerfile` y `docker-compose.yml` para facilitar la contenedorización.

## Configuración y Ejecución

### Localmente

1.  **Clonar el repositorio (si aplica):**
    ```bash
    git clone <url-repositorio>
    cd PythonService
    ```
2.  **Crear un entorno virtual (recomendado):**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Ejecutar el servidor:**
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    El servidor estará disponible en `http://localhost:8000`.

### Con Docker

1.  **Construir la imagen:**
    ```bash
    docker-compose build
    ```
2.  **Iniciar el contenedor:**
    ```bash
    docker-compose up
    ```
    El servidor estará disponible en `http://localhost:8000`.

## Uso

1.  **Accede a la Interfaz Web:** Abre `http://localhost:8000` en tu navegador.
2.  **Sube un Servicio:**
    *   Haz clic en "Choose File" y selecciona un archivo Python (`.py`) que contenga una variable llamada `router` que sea una instancia de `fastapi.APIRouter`.
    *   Haz clic en "Upload Service".
3.  **Accede a los Endpoints:**
    *   Si subiste un archivo llamado `mi_servicio.py` con un endpoint `/datos`, estará accesible en `http://localhost:8000/mi_servicio/datos`.
    *   El servicio de ejemplo `plot_service.py` está en `http://localhost:8000/plot_service/plot`.
4.  **Ver Documentación:** Navega a `http://localhost:8000/docs` para ver todos los endpoints disponibles.

## Bibliotecas Soportadas

El entorno de ejecución incluye las siguientes bibliotecas principales (ver `requirements.txt` para versiones exactas):

*   fastapi
*   uvicorn
*   python-multipart
*   matplotlib
*   numpy

## Ejecución
py -m pip install -r requirements.txt
py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

## Nueva Version
git tag v1.0.3
git push origin v1.0.3