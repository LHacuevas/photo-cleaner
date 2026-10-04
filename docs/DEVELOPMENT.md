# Guía de desarrollo

Cómo preparar el entorno, ejecutar los tests y añadir cambios sin romper las garantías de la aplicación. Los detalles internos (modelo de datos, API, pipeline de imagen) están en la [especificación técnica](TECHNICAL_SPECS.md).

## Entorno

Requisitos: Python 3.12, Node.js 20 o superior y FFmpeg.

```bat
REM Backend: entorno virtual en la raíz del repo
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

REM Frontend
cd frontend
npm install
```

`requirements-dev.txt` incluye `requirements.txt` más las herramientas de desarrollo: pytest, httpx2 (lo usa el `TestClient` de Starlette) y ruff.

## Ejecutar en desarrollo

```bat
REM Backend con recarga automática (http://127.0.0.1:8000, API en /docs)
cd backend
..\.venv\Scripts\python.exe main.py

REM Frontend con Vite (http://localhost:3000)
cd frontend
npm start
```

`start.bat` hace ambas cosas y además sincroniza las dependencias.

### Configuración

`backend/config.py` lee las variables de entorno o `backend/.env` (plantilla en `backend/.env.example`):

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `PHOTO_CLEANER_HOST` | `127.0.0.1` | Interfaz de escucha. `0.0.0.0` expone la API en la red local |
| `PHOTO_CLEANER_PORT` | `8000` | Puerto del backend |
| `PHOTO_CLEANER_DATABASE_URL` | `sqlite:///backend/photo_cleaner.db` | Base de datos (los tests usan una temporal) |
| `PHOTO_CLEANER_CORS_ORIGINS` | vacío = cualquier puerto de `localhost`/`127.0.0.1` | Orígenes del frontend permitidos |
| `PHOTO_CLEANER_FFMPEG` | búsqueda automática | Ruta explícita a `ffmpeg.exe` |

En el frontend, `VITE_API_URL` (en `frontend/.env.local`, por ejemplo) cambia la URL de la API. Por defecto es `http://localhost:8000/api`.

## Tests y lint

```bat
cd backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check --select F,E9 --exclude venv,migrations .

cd ..\frontend
npm run lint
npm run build
```

- **Aislamiento:** `tests/conftest.py` apunta `PHOTO_CLEANER_DATABASE_URL` a una BD temporal antes de importar la app, y cada test trabaja sobre una carpeta de fotos sintéticas en `tmp_path`. Nunca se toca `backend/photo_cleaner.db`.
- **FFmpeg:** los tests que lo necesitan se saltan solos si no está disponible.
- **Tareas en segundo plano:** el escaneo devuelve `analysis_task_id`; usa `wait_for_task(client, task_id)` antes de comprobar metadatos o hashes.
- **Garantía principal:** los originales nunca pierden datos. Cualquier cambio en borrar, restaurar, favoritas, rotar o voltear debe venir con un test que compruebe el hash o los píxeles del original (ver `tests/test_file_lifecycle.py` y `tests/test_orientation.py`).

## Migraciones de base de datos

El esquema se gestiona con Alembic (`backend/migrations/`). Al arrancar, `init_db()` aplica las migraciones pendientes. Las bases de datos antiguas, creadas con `create_all`, se marcan primero con la revisión `0001`.

Para cambiar el esquema:

```bat
cd backend
REM 1. Modifica los modelos en database.py
REM 2. Genera la migración y revísala a mano
..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe el cambio"
REM 3. Aplica (o simplemente arranca el backend)
..\.venv\Scripts\python.exe -m alembic upgrade head
REM 4. Comprueba que modelos y migraciones coinciden
..\.venv\Scripts\python.exe -m alembic check
```

SQLite solo admite `ALTER TABLE` limitado, así que las migraciones usan el modo batch (`render_as_batch=True`).

## Convenciones del backend

- **Endpoints síncronos:** usa `def`, no `async def`. FastAPI los ejecuta en su threadpool, y así el trabajo de disco, SQLAlchemy o PIL no bloquea el event loop.
- **Errores:** si capturas `Exception` en un endpoint, pon antes `except HTTPException: raise`. Si no, los 404 y 400 se convierten en 500.
- **Trabajo largo:** va a `utils.task_queue.task_queue.enqueue(nombre, funcion)`. La función es síncrona, abre su propia sesión (`SessionLocal()`) y, si acepta un parámetro `task`, puede informar del progreso con `task.set_progress(hechos, total)` y comprobar `task.is_cancelled`.
- **Paralelismo:** los objetos ORM no se tocan desde hilos de trabajo. Resuelve antes las rutas en el hilo principal, procesa los archivos en paralelo y escribe en la BD desde el hilo que llama (patrón de `utils/analysis.py` y `api/photos.py::_generate_variants`).
- **Rutas de archivos:** usa siempre `utils/photo_files.py` (`get_original_path`, `get_thumb_path`, `move_photo_variants`, `set_favorite`…). `Photo.filename` es la ruta relativa a la carpeta, así que puede contener subcarpetas.
- **Imágenes:** ábrelas con `with` o con `open_image()`. En Windows, un handle abierto impide mover el archivo.
- **Cambios en el análisis:** si cambia lo que se extrae o cómo se calcula el hash, los usuarios pueden actualizar su índice con `python reanalyze.py`.

## Convenciones del frontend

- **Notificaciones:** `const toast = useToast()` en lugar de `alert()`. Los mensajes de error de la API se obtienen con `apiErrorMessage(error, 'texto por defecto')`.
- **Listados grandes:** `/api/photos/list` devuelve solo resúmenes. Los detalles (EXIF, versión web) se piden con `/api/photos/get/{id}` para la foto visible.
- **Atajos de teclado:** registra el listener una sola vez y llama a los handlers a través de un `ref` (ver `Gallery.jsx`). Así se evitan listeners obsoletos y re-suscripciones en cada render.
- **Componentes:** van en `src/components/` con su CSS al lado. Las utilidades compartidas van en `src/utils/`.

## Estructura

```text
backend/
├── main.py              # App FastAPI (lifespan, CORS, routers, /api/health)
├── config.py            # Configuración desde entorno / .env
├── database.py          # Modelos SQLAlchemy, init_db() con Alembic
├── reanalyze.py         # Re-analizar fotos ya indexadas
├── api/                 # folders, photos, similar, metadata
├── utils/
│   ├── image_processing.py  # FFmpeg/Pillow, EXIF, hashes, rotación sin pérdida
│   ├── analysis.py          # Análisis en segundo plano (EXIF + hashes)
│   ├── photo_files.py       # Rutas y movimientos de archivos
│   └── task_queue.py        # Cola de tareas en hilos
├── migrations/          # Alembic
└── tests/               # pytest
frontend/
├── index.html, vite.config.js, eslint.config.js
└── src/
    ├── pages/           # Home, Gallery, Compare
    ├── components/      # PhotoViewer, ThumbnailStrip, BatchActionBar, Toast, ErrorBoundary...
    ├── hooks/           # useBackgroundTask
    ├── services/api.js  # Cliente axios
    └── utils/           # format
```

## Plan de trabajo

El estado de las mejoras pendientes está en [IMPROVEMENT_PLAN.md](IMPROVEMENT_PLAN.md).
