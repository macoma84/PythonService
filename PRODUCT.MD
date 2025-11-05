# Especificación Funcional del Producto
## Dynamic Microservice Runner

**Versión:** 1.8.0
**Última actualización:** Noviembre 2025

---

## 1. Visión General del Producto

Dynamic Microservice Runner es una plataforma que permite a los usuarios crear, desplegar y gestionar microservicios de forma dinámica mediante la carga de módulos de código Python. La plataforma proporciona un entorno de ejecución controlado donde los usuarios pueden subir sus propios servicios y exponerlos como APIs REST sin necesidad de reiniciar el servidor o modificar la infraestructura base.

### 1.1 Propósito

El producto está diseñado para:
- Facilitar el desarrollo y prueba rápida de APIs y microservicios
- Permitir la gestión centralizada de múltiples servicios en un solo entorno
- Proporcionar un espacio de trabajo colaborativo donde diferentes equipos puedan desplegar sus propios servicios
- Reducir la complejidad del despliegue de microservicios mediante automatización

### 1.2 Usuarios Objetivo

- Desarrolladores que necesitan probar APIs rápidamente
- Equipos de desarrollo que trabajan con arquitecturas de microservicios
- Científicos de datos que desean exponer modelos como servicios web
- Analistas que requieren crear servicios de procesamiento de datos

---

## 2. Funcionalidades Principales

### 2.1 Gestión de Módulos de Servicio

#### 2.1.1 Carga de Módulos
Los usuarios pueden cargar módulos de servicio en el sistema de las siguientes formas:

**Carga mediante Interfaz Web:**
- El usuario accede a la interfaz web principal
- Puede seleccionar un archivo Python (.py) desde su sistema local
- Puede arrastrar y soltar el archivo en el área designada
- El sistema valida que el archivo sea de tipo Python
- Una vez cargado, el servicio queda inmediatamente disponible

**Organización Jerárquica:**
- Los módulos pueden organizarse en directorios y subdirectorios
- Los usuarios pueden crear carpetas para agrupar servicios relacionados
- La estructura de carpetas se refleja en las rutas de acceso a los endpoints

#### 2.1.2 Visualización de Módulos
Los usuarios pueden:
- Ver todos los módulos cargados en una vista de árbol jerárquica
- Expandir y colapsar carpetas para navegar por la estructura
- Identificar visualmente archivos y directorios mediante iconos
- Navegar entre diferentes niveles de la jerarquía mediante breadcrumbs

#### 2.1.3 Edición de Módulos
El sistema proporciona un editor integrado que permite:
- Seleccionar cualquier módulo existente para editar
- Visualizar el código con resaltado de sintaxis Python
- Realizar modificaciones al código directamente en el navegador
- Guardar los cambios realizados
- Los cambios se aplican automáticamente sin necesidad de reiniciar

Características del editor:
- Numeración de líneas
- Tema oscuro para reducir fatiga visual
- Resaltado de sintaxis Python
- Soporte para indentación y formato

#### 2.1.4 Eliminación de Módulos
Los usuarios pueden:
- Eliminar módulos individuales
- Confirmar la eliminación mediante un diálogo de confirmación
- El sistema limpia automáticamente directorios vacíos
- Los endpoints asociados dejan de estar disponibles inmediatamente

### 2.2 Sincronización con Repositorios Git

#### 2.2.1 Sincronización Manual
Los usuarios pueden sincronizar módulos desde un repositorio Git configurado:
- Presionar el botón de sincronización en la interfaz
- El sistema descarga todos los módulos desde el repositorio
- Se actualiza la lista de módulos disponibles
- Se muestra el estado de la sincronización (éxito/fallo)
- Se lista la cantidad de archivos sincronizados

#### 2.2.2 Sincronización Automática
El sistema puede configurarse para:
- Sincronizar automáticamente al iniciar
- Descargar módulos desde una rama específica
- Autenticarse con el repositorio de forma segura
- Crear respaldos antes de sobrescribir módulos existentes

#### 2.2.3 Gestión de Conflictos
Cuando se sincroniza con Git:
- Se crea un respaldo de los módulos existentes
- Los nuevos archivos reemplazan a los existentes
- Los módulos son recargados automáticamente
- Se notifica al usuario sobre el resultado de la operación

### 2.3 Sistema de Exposición de APIs

#### 2.3.1 Rutas Automáticas
Cuando un módulo es cargado:
- El sistema analiza el contenido del módulo
- Identifica los endpoints definidos en el módulo
- Expone los endpoints bajo una ruta basada en la ubicación del archivo
- Para archivos en la raíz: `/nombre_modulo/endpoint`
- Para archivos en subdirectorios: `/directorio/subdirectorio/nombre_modulo/endpoint`

#### 2.3.2 Recarga Dinámica
- Los módulos pueden ser modificados en tiempo de ejecución
- Los cambios se aplican sin necesidad de reiniciar el servidor
- Los endpoints existentes se actualizan con la nueva lógica
- Las conexiones activas no se interrumpen

#### 2.3.3 Documentación Automática
El sistema genera automáticamente:
- Documentación interactiva en formato OpenAPI (Swagger)
- Accesible desde la ruta `/docs`
- Lista de todos los endpoints disponibles
- Parámetros esperados para cada endpoint
- Esquemas de respuesta
- Posibilidad de probar endpoints directamente desde la documentación

### 2.4 Sistema de Monitoreo y Registros

#### 2.4.1 Visualización de Logs
Los usuarios tienen acceso a una interfaz de visualización de logs donde pueden:
- Ver registros en tiempo real de todos los módulos
- Observar mensajes informativos, advertencias y errores
- Identificar qué módulo generó cada mensaje
- Ver marcas de tiempo precisas de cada evento

#### 2.4.2 Filtrado de Logs
El sistema permite filtrar logs por:
- Nivel de severidad (DEBUG, INFO, WARNING, ERROR)
- Nombre del módulo
- Texto del mensaje
- Los filtros se aplican en tiempo real

#### 2.4.3 Modos de Visualización
Dos modos de acceso a los logs:
- **Modo Manual:** Refrescar manualmente para ver nuevos logs
- **Modo Stream:** Transmisión en vivo que actualiza automáticamente

#### 2.4.4 Gestión de Memoria
- El sistema mantiene un límite de entradas de log (1000)
- Las entradas más antiguas se eliminan automáticamente
- Previene problemas de consumo excesivo de memoria
- Los usuarios pueden limpiar la vista sin afectar el historial

### 2.5 Interfaz de Usuario Web

#### 2.5.1 Panel Principal
La interfaz principal proporciona:
- Instrucciones de uso claras
- Lista de bibliotecas disponibles en el entorno
- Área de carga de archivos (drag & drop y selección manual)
- Vista de árbol de todos los módulos
- Editor de código integrado
- Controles de sincronización Git

#### 2.5.2 Navegación
Los usuarios pueden:
- Navegar entre diferentes secciones
- Acceder a la documentación de la API
- Acceder a los logs del sistema
- Crear y navegar por estructuras de directorios

#### 2.5.3 Retroalimentación Visual
El sistema proporciona:
- Mensajes de estado para cada operación
- Confirmaciones de éxito/fallo
- Indicadores de carga durante operaciones largas
- Diálogos de confirmación para acciones destructivas

---

## 3. Bibliotecas y Capacidades Disponibles

Los módulos cargados por los usuarios tienen acceso a un conjunto extenso de bibliotecas Python que les permiten implementar diversas funcionalidades:

### 3.1 Desarrollo de APIs
- **FastAPI:** Framework para crear APIs REST modernas
- **Uvicorn:** Servidor ASGI para aplicaciones web
- **Python-multipart:** Manejo de carga de archivos

### 3.2 Análisis de Datos y Ciencia de Datos
- **Pandas:** Manipulación y análisis de datos tabulares
- **NumPy:** Computación científica y matrices
- **Matplotlib:** Generación de gráficos y visualizaciones

### 3.3 Finanzas Cuantitativas
- **QuantLib:** Modelado financiero y análisis cuantitativo
- **yfinance:** Descarga de datos de mercados financieros

### 3.4 Bases de Datos
- **PostgreSQL (psycopg2-binary):** Conexión a bases de datos PostgreSQL
- **MySQL (pymysql, mysql-connector-python):** Conexión a bases de datos MySQL
- **Oracle (cx_Oracle):** Conexión a bases de datos Oracle
- **SQLAlchemy:** ORM y toolkit SQL
- **Redis:** Base de datos en memoria y caché

### 3.5 Inteligencia Artificial
- **OpenAI:** Integración con modelos de IA de OpenAI
- **Qdrant:** Base de datos vectorial para búsqueda por similitud

### 3.6 Generación de Documentos
- **ReportLab:** Creación de documentos PDF

### 3.7 Utilidades
- **GitPython:** Operaciones con repositorios Git
- **xmltodict:** Conversión entre XML y diccionarios Python

---

## 4. Casos de Uso

### 4.1 Caso de Uso 1: Científico de Datos - Exposición de Modelo de ML
**Objetivo:** Exponer un modelo de machine learning como API REST

**Flujo:**
1. El científico desarrolla un modelo de predicción en Python
2. Crea un módulo con endpoints para predicción
3. Sube el módulo a través de la interfaz web
4. El modelo queda disponible como API REST
5. Otros sistemas pueden consumir predicciones mediante llamadas HTTP
6. Puede monitorear las solicitudes a través de los logs

### 4.2 Caso de Uso 2: Desarrollador - Prototipado Rápido de API
**Objetivo:** Crear y probar rápidamente un nuevo endpoint

**Flujo:**
1. El desarrollador escribe un nuevo servicio localmente
2. Sube el archivo a la plataforma
3. Prueba el endpoint usando la documentación interactiva en `/docs`
4. Identifica un problema en el código
5. Edita el servicio directamente en la interfaz web
6. Guarda los cambios y prueba nuevamente
7. El endpoint funciona correctamente sin necesidad de reiniciar

### 4.3 Caso de Uso 3: Analista Financiero - Servicio de Datos de Mercado
**Objetivo:** Crear un servicio que proporciona datos financieros en tiempo real

**Flujo:**
1. El analista crea un módulo que utiliza yfinance
2. Define endpoints para obtener cotizaciones, históricos, etc.
3. Sube el módulo y lo organiza en una carpeta "finanzas"
4. Comparte la URL del endpoint con su equipo
5. El equipo consume los datos desde sus aplicaciones
6. El analista puede actualizar la lógica editando el módulo

### 4.4 Caso de Uso 4: Equipo de Desarrollo - Gestión de Microservicios
**Objetivo:** Organizar múltiples microservicios de un proyecto

**Flujo:**
1. El equipo estructura sus servicios en carpetas por dominio
2. Suben módulos organizados: `/usuarios`, `/productos`, `/pedidos`
3. Cada módulo expone endpoints relacionados con su dominio
4. Configuran sincronización con Git para control de versiones
5. Los cambios en el repositorio se sincronizan automáticamente al iniciar
6. El equipo puede ver logs centralizados de todos los servicios

### 4.5 Caso de Uso 5: Desarrollador - Generación de Reportes PDF
**Objetivo:** Crear un servicio que genera reportes en PDF

**Flujo:**
1. El desarrollador crea un módulo usando ReportLab
2. Define un endpoint que recibe parámetros para el reporte
3. El servicio consulta datos de una base de datos (PostgreSQL/MySQL)
4. Genera un PDF con los datos formateados
5. Retorna el PDF al cliente
6. Monitorea errores de generación a través de los logs

---

## 5. Flujos de Trabajo

### 5.1 Flujo de Carga de Nuevo Módulo
```
Usuario → Accede a interfaz web
       → Selecciona archivo .py o arrastra y suelta
       → Sistema valida formato
       → Sistema guarda módulo
       → Sistema detecta endpoints en el módulo
       → Sistema expone endpoints automáticamente
       → Sistema actualiza lista de módulos
       → Usuario recibe confirmación
       → Usuario puede probar endpoint en /docs
```

### 5.2 Flujo de Edición de Módulo Existente
```
Usuario → Navega por árbol de módulos
       → Hace clic en módulo a editar
       → Sistema carga código en editor
       → Usuario modifica código
       → Usuario presiona "Guardar"
       → Sistema guarda cambios
       → Sistema recarga módulo automáticamente
       → Sistema actualiza endpoints
       → Usuario recibe confirmación
       → Cambios están activos inmediatamente
```

### 5.3 Flujo de Sincronización Git
```
Usuario → Presiona botón "Sync with Git Repository"
       → Sistema muestra "Sincronizando..."
       → Sistema crea respaldo de módulos actuales
       → Sistema clona repositorio configurado
       → Sistema copia archivos .py al directorio de módulos
       → Sistema excluye archivos de sistema (.git, __pycache__)
       → Sistema carga todos los módulos nuevos
       → Sistema muestra cantidad de archivos sincronizados
       → Sistema actualiza lista de módulos en interfaz
       → Usuario ve módulos actualizados
```

### 5.4 Flujo de Monitoreo de Logs
```
Usuario → Accede a /logs
       → Sistema muestra logs almacenados
       → Usuario aplica filtros (nivel, módulo)
       → Sistema filtra logs en tiempo real
       → Usuario activa modo "Live Stream"
       → Sistema transmite logs en tiempo real
       → Usuario observa actividad de módulos
       → Usuario identifica errores o comportamientos
       → Usuario puede desactivar stream o limpiar vista
```

### 5.5 Flujo de Organización de Módulos
```
Usuario → Navega a ubicación deseada
       → Ingresa nombre de nueva carpeta
       → Presiona "Create Folder"
       → Sistema crea estructura de directorio
       → Sistema actualiza vista de árbol
       → Usuario arrastra archivos a nueva ubicación o sube en carpeta
       → Las rutas de endpoints reflejan la estructura
```

---

## 6. Restricciones y Limitaciones

### 6.1 Restricciones de Formato
- Solo se aceptan archivos con extensión `.py`
- Los módulos deben contener una instancia de APIRouter para ser útiles
- Los nombres de archivos no deben contener caracteres especiales problemáticos

### 6.2 Restricciones de Seguridad
- Los módulos se ejecutan en el mismo contexto que la aplicación principal
- Los usuarios deben confiar en el código que suben
- No hay sandboxing entre módulos
- La sincronización Git requiere configuración de credenciales

### 6.3 Restricciones de Rendimiento
- Los logs se limitan a 1000 entradas para evitar consumo excesivo de memoria
- Las modificaciones de módulos requieren recarga, lo que puede tener un breve impacto
- El modo de stream de logs actualiza cada segundo

### 6.4 Restricciones de Entorno
- Las bibliotecas disponibles están limitadas a las pre-instaladas
- No se pueden instalar nuevas dependencias sin modificar el entorno base
- Los módulos comparten el mismo entorno Python

---

## 7. Escenarios de Error y Manejo

### 7.1 Error al Cargar Módulo
**Causa:** Archivo no es .py o contiene errores de sintaxis
**Comportamiento:** Sistema muestra mensaje de error, no se carga el módulo
**Recuperación:** Usuario corrige el archivo y vuelve a intentar

### 7.2 Error al Sincronizar con Git
**Causa:** Credenciales incorrectas, red no disponible, repositorio no existe
**Comportamiento:** Sistema muestra mensaje de error, mantiene módulos actuales
**Recuperación:** Usuario verifica configuración y vuelve a intentar

### 7.3 Error al Guardar Cambios
**Causa:** Permisos de archivo, código con errores de sintaxis
**Comportamiento:** Sistema muestra mensaje de error, no aplica cambios
**Recuperación:** Usuario corrige el problema y vuelve a guardar

### 7.4 Error en Ejecución de Módulo
**Causa:** Error en la lógica del módulo cargado
**Comportamiento:** El endpoint retorna error HTTP, se registra en logs
**Recuperación:** Usuario revisa logs, identifica error, edita módulo, guarda

### 7.5 Error al Eliminar Módulo
**Causa:** Permisos de sistema de archivos
**Comportamiento:** Sistema muestra mensaje de error, módulo no se elimina
**Recuperación:** Usuario verifica permisos o contacta administrador

---

## 8. Requisitos No Funcionales

### 8.1 Usabilidad
- La interfaz debe ser intuitiva y no requerir capacitación extensa
- Los mensajes de error deben ser claros y orientar al usuario
- Las operaciones comunes deben requerir pocos clics
- Debe funcionar en navegadores modernos sin plugins

### 8.2 Rendimiento
- La carga de módulos debe completarse en menos de 5 segundos
- La recarga de módulos editados debe ser inmediata (< 1 segundo)
- La interfaz web debe responder rápidamente a las interacciones
- Los logs deben transmitirse con latencia mínima

### 8.3 Confiabilidad
- El sistema debe manejar errores en módulos sin caer
- Los módulos defectuosos no deben afectar a otros módulos
- La sincronización fallida no debe eliminar módulos existentes
- Los respaldos deben crearse antes de operaciones destructivas

### 8.4 Mantenibilidad
- Los módulos deben poder actualizarse sin reiniciar el servidor
- La estructura de directorios debe ser clara y organizada
- Los logs deben proporcionar información suficiente para debugging

### 8.5 Escalabilidad
- El sistema debe manejar decenas de módulos simultáneos
- El sistema de logs debe prevenir consumo excesivo de memoria
- La interfaz debe manejar estructuras de directorios profundas

---

## 9. Definiciones y Terminología

- **Módulo:** Archivo Python que contiene código de servicio y define endpoints
- **Endpoint:** Punto de acceso API REST que responde a solicitudes HTTP
- **Router:** Componente que agrupa y organiza endpoints relacionados
- **Sincronización:** Proceso de descargar módulos desde un repositorio Git
- **Recarga:** Proceso de aplicar cambios a un módulo sin reiniciar el servidor
- **Log:** Registro de eventos, mensajes informativos, advertencias y errores
- **Stream:** Modo de transmisión continua de logs en tiempo real
- **Drag & Drop:** Funcionalidad de arrastrar y soltar archivos
- **Breadcrumb:** Navegación que muestra la ubicación actual en la jerarquía

---

## 10. Anexos

### 10.1 URLs del Sistema
- `/` - Interfaz principal de gestión
- `/docs` - Documentación interactiva OpenAPI
- `/logs` - Interfaz de visualización de logs
- `/upload` - Endpoint de carga de módulos (uso interno)
- `/files` - Endpoint de gestión de archivos (uso interno)
- `/git-sync` - Endpoint de sincronización Git (uso interno)
- `/api/logs` - Endpoint de acceso a logs (uso interno)
- `/api/logs/stream` - Endpoint de stream de logs (uso interno)

### 10.2 Estructura de Directorios del Usuario
```
modules/
├── servicio1.py
├── servicio2.py
├── finanzas/
│   ├── cotizaciones.py
│   └── analisis.py
├── datos/
│   ├── consultas.py
│   └── reportes/
│       └── pdf_generator.py
└── ml/
    ├── predicciones.py
    └── entrenamiento.py
```

### 10.3 Formato de Módulo Esperado
Un módulo válido debe:
1. Ser un archivo Python (.py)
2. Importar FastAPI's APIRouter
3. Crear una instancia de APIRouter
4. Definir endpoints usando decoradores (@router.get, @router.post, etc.)
5. La variable router debe ser accesible a nivel de módulo

### 10.4 Niveles de Log
- **DEBUG:** Información detallada para diagnóstico
- **INFO:** Confirmación de que las cosas funcionan como se espera
- **WARNING:** Indicación de algo inesperado o problema futuro
- **ERROR:** Error que impide que una función se complete

---

**Fin de la Especificación Funcional**
