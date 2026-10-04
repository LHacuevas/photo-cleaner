# Photo Cleaner — Especificación técnica

Documento de referencia para quien mantenga el código. Describe lo que hay en `backend/` y `frontend/` en este momento; si algo de aquí no coincide con el código, manda el código y hay que corregir este documento. El entorno de desarrollo, los tests y las convenciones están en [DEVELOPMENT.md](DEVELOPMENT.md); el plan de trabajo, en [IMPROVEMENT_PLAN.md](IMPROVEMENT_PLAN.md).

## 1. Arquitectura

| Capa | Tecnología |
| --- | --- |
| Frontend | React 18, Vite (servidor de desarrollo en el puerto 3000), React Router 7, axios, lucide-react, Leaflet + react-leaflet 4 + leaflet.markercluster (cargados solo en la pantalla del mapa) |
| Backend | FastAPI + uvicorn (Python 3.12 en el `.venv` del proyecto) |
| Persistencia | SQLite mediante SQLAlchemy 2.1; migraciones con Alembic |
| Imagen | FFmpeg (subproceso), Pillow, pillow-heif (HEIC), rawpy/LibRaw (RAW), piexif, imagehash, numpy |
| Dependencias | `backend/requirements.txt` (versiones fijadas: FastAPI 0.142.2, SQLAlchemy 2.1.3, Alembic 1.20.0…); `backend/requirements-dev.txt` añade pytest, httpx2 (para `TestClient`) y ruff |
| Tests | `cd backend && pytest`: 135 tests en `backend/tests/` |

```text
Navegador ── http://localhost:3000 ──► Vite + React (SPA)
                                          │ axios → VITE_API_URL (por defecto http://localhost:8000/api)
                                          ▼
                              FastAPI / uvicorn (127.0.0.1:8000)
                              endpoints `def` → threadpool de FastAPI
              ┌───────────────────────┼─────────────────────────────┐
              ▼                       ▼                             ▼
     SQLite (WAL, busy_timeout)   task_queue (3 hilos, en memoria)   Sistema de archivos
     backend/photo_cleaner.db     ├─ analyze_folder                  <carpeta>/  originales
                                  │    └─ ThreadPoolExecutor(cpu_count)  thumbs/ web/
                                  │         Pillow · piexif · imagehash  preferite/ cancellate/
                                  └─ _generate_variants
                                       └─ ThreadPoolExecutor(max(2, cpu/2))
                                            FFmpeg (subproceso) · Pillow para TIFF/HEIC/RAW
```

Principios que el código mantiene:

- **Nunca se bloquea el event loop.** Todos los endpoints son funciones `def`, que FastAPI ejecuta en su threadpool. El trabajo pesado va a la cola de tareas, que también usa hilos. Se usan hilos y no procesos porque FFmpeg ya es un proceso externo y Pillow libera el GIL al decodificar.
- **El ORM solo se toca desde el hilo que abrió la sesión.** Los workers reciben rutas (`Path`) resueltas de antemano y devuelven diccionarios; el hilo que llama aplica los resultados y hace commit por lotes.
- **No destructivo.** Borrar mueve archivos a `cancellate/`, los favoritos son copias, rotar y voltear no recodifican el original (sección 5.5).

### 1.1 Cola de tareas (`backend/utils/task_queue.py`)

- `BackgroundTaskQueue(max_workers=3, keep_last_n=100)`, instancia global `task_queue`. Usa un `ThreadPoolExecutor` y guarda el estado **en memoria**: si se reinicia el backend, se pierden las tareas.
- `enqueue(name, func, args, kwargs)` devuelve un UUID. Si `func` tiene un parámetro llamado `task`, recibe su `Task` para informar del progreso (`task.set_progress(done, total)`) y comprobar `task.is_cancelled`.
- Estados (`TaskStatus`): `pending`, `running`, `completed`, `failed` y `cancelled`. `to_dict()` expone `id`, `name`, `status`, `progress` (0–100), `result`, `error`, `created_at`, `started_at` y `completed_at` (ISO, UTC).
- **Cancelación cooperativa**: `cancel_task` solo marca la tarea como `CANCELLED`. Una tarea pendiente no llega a arrancar; una en marcha se detiene en su siguiente comprobación de `is_cancelled`, cancelando con `pool.shutdown(cancel_futures=True)` los trabajos que aún no habían empezado. Si la función lanza una excepción después de cancelarse, se guarda `error` pero el estado sigue siendo `cancelled`. Una tarea ya terminada no se puede cancelar (`False`).
- **Limpieza automática**: en cada `enqueue` se olvidan las tareas terminadas más antiguas a partir de la número 100.

### 1.2 Análisis en segundo plano (`backend/utils/analysis.py`)

- `enqueue_folder_analysis(folder_id)` lanza el análisis de las fotos no borradas sin `phash`. Con un diccionario `folder_id → task_id`, protegido por un lock, garantiza **un solo análisis activo por carpeta**: si ya hay uno pendiente o en marcha, devuelve su `task_id`. Devuelve `None` si no queda nada pendiente.
- `analyze_folder(folder_id, task=None)` abre su propia `SessionLocal`, resuelve las rutas con `get_original_path` y reparte `_analyze_file` (que llama a `get_image_info`, `extract_exif` y `compute_hashes`) en un `ThreadPoolExecutor(max_workers=os.cpu_count())`. Aplica los resultados en el hilo que llama, hace commit cada 100 fotos e informa del progreso. Devuelve `{total, analyzed, errors}`; `errors` son las fotos que siguen sin `phash`.
- La llaman `POST /api/folders/scan` (al final del escaneo), `POST /api/similar/analyze/{id}` y el script `backend/reanalyze.py`. Este último pone a `NULL` los hashes de las carpetas indicadas (o de todas), las vuelve a analizar de forma síncrona y descarta sus grupos pendientes con `clear_pending_groups`: `python reanalyze.py [folder_id ...]`.

### 1.3 Generación de derivados (`backend/api/photos.py::_generate_variants`)

- `_get_missing_generated_photos` recorre las fotos no borradas de la carpeta, sincroniza `has_thumb` y `has_web` con el disco (hace commit si algo cambió) y devuelve las que no tienen el derivado pedido.
- Los trabajos `(photo, origen, destino)` se resuelven antes de empezar y se reparten en un `ThreadPoolExecutor(max_workers=max(2, cpu_count // 2))`. Cada worker lanza FFmpeg (o Pillow para TIFF/HEIC/RAW). El hilo que llama actualiza los indicadores, hace commit cada 50 fotos y atiende la cancelación.
- Los endpoints síncronos (`generate-thumbs`, `generate-web`) y los asíncronos (`*-async`) usan esta misma función. La versión asíncrona la ejecuta dentro de una tarea con su propia sesión de BD.

## 2. Configuración

`backend/config.py` lee las variables de entorno y `backend/.env` con python-dotenv. Las variables reales tienen prioridad sobre las de `.env`. Para empezar, se copia `backend/.env.example` como `backend/.env`.

| Variable | Valor por defecto | Uso |
| --- | --- | --- |
| `PHOTO_CLEANER_HOST` | `127.0.0.1` | Interfaz de escucha. `0.0.0.0` expone en la LAN una API que lee cualquier carpeta del disco. |
| `PHOTO_CLEANER_PORT` | `8000` | Puerto de uvicorn. |
| `PHOTO_CLEANER_DATABASE_URL` | `sqlite:///<backend>/photo_cleaner.db` (ruta absoluta) | URL de SQLAlchemy; la usan también las migraciones. |
| `PHOTO_CLEANER_CORS_ORIGINS` | vacío | Orígenes permitidos, separados por comas. Si está vacío, se acepta cualquier puerto de `localhost` o `127.0.0.1` (regex `http://(localhost\|127\.0\.0\.1)(:\d+)?`). |
| `PHOTO_CLEANER_FFMPEG` | sin definir | Ruta explícita a FFmpeg (ver 5.2). |

En el frontend, `VITE_API_URL` (variable de Vite) define la URL base de la API; por defecto es `http://localhost:8000/api`.

`python main.py` arranca uvicorn con `reload=True`. El `lifespan` de la aplicación llama a `init_db()` antes de atender peticiones.

## 3. Modelo de datos (`backend/database.py`)

Las fechas se guardan como `datetime` UTC *naive* (`utcnow()`).

### 3.1 `folders`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | Integer PK | índice |
| `path` | String, único, no nulo | Ruta tal como llegó a `/scan` la primera vez (`str(Path(...))`). Al escanear, las carpetas se comparan con `os.path.normcase(os.path.abspath(...))`, así que `C:\Fotos`, `c:\fotos\` y `C:/Fotos` son la misma. |
| `name` | String, no nulo | Último componente de la ruta. |
| `total_photos` | Integer | Fotos no borradas, recalculado en cada escaneo. Los endpoints (`/list`, `/stats`) no lo leen: cuentan al vuelo. |
| `favorites_count`, `deleted_count` | Integer | Existen en el esquema, pero no se usan: los recuentos se calculan al vuelo. |
| `created_at` | DateTime | |
| `last_scanned` | DateTime | Se actualiza en cada escaneo. |

### 3.2 `photos`

| Grupo | Columnas |
| --- | --- |
| Identidad | `id` PK; `filename` (no nulo, índice): **ruta relativa a la carpeta** con `/` (p. ej. `2024/img.jpg`); `filepath` (único, no nulo): ruta absoluta actual del original (cambia al borrar y al restaurar); `folder_id` FK → `folders.id` |
| Archivo | `size` (bytes), `width`, `height` (tal como se muestra, con la orientación aplicada), `format` (`JPEG`, `PNG`, `HEIF`… o la extensión en mayúsculas para RAW) |
| Estado | `is_favorite`, `is_deleted` (ambos con índice, por defecto `False`) |
| Hashes | `phash`, `dhash`: 16 caracteres hexadecimales (64 bits), con índice. `phash IS NULL` significa «pendiente de análisis». |
| EXIF | `date_taken` (índice), `camera_make`, `camera_model`, `lens_model`, `iso`, `aperture`, `shutter_speed` (texto `n/d`), `focal_length` |
| GPS | `gps_latitude`, `gps_longitude`, `gps_altitude` |
| Derivados | `has_thumb`, `has_web`: caché de la existencia de los archivos, que se resincroniza con el disco |
| Tiempos | `created_at`, `updated_at` (`onupdate`) |

### 3.3 `similar_groups` y `photo_similar_groups`

- `similar_groups`: `id`, `folder_id` FK, `similarity_score` (distancia de Hamming media entre los miembros), `group_type` (`duplicate` / `burst` / `similar`), `is_reviewed` (por defecto `False`), `selected_photo_id` (sin FK) y `created_at`.
- `photo_similar_groups`: tabla N:M con PK compuesta `(photo_id, group_id)`, cada una FK a su tabla. No hay cascadas: el código borra explícitamente las filas de asociación (`clear_pending_groups` y al olvidar fotos que ya no existen en disco).

### 3.4 Motor, pragmas y sesiones

- `create_engine(DATABASE_URL, connect_args={"check_same_thread": False})`. En cada conexión se ejecutan `PRAGMA journal_mode=WAL`, para que la galería lea mientras las tareas escriben, y `PRAGMA busy_timeout=5000`, para esperar hasta 5 s en lugar de fallar con un bloqueo.
- `SessionLocal = sessionmaker(autoflush=False)`. Los endpoints usan la dependencia `get_db()`; las tareas en segundo plano abren su propia sesión.
- En cada conexión se registra la función SQL `distance_km(lat1, lon1, lat2, lon2)` (haversine, radio terrestre 6371 km; `NULL` si falta algún valor). La misma función está disponible en Python como `database.distance_km`.

### 3.5 Migraciones (Alembic)

- `backend/alembic.ini` (`script_location = migrations`). `migrations/env.py` toma `Base.metadata` y el `engine` de la aplicación, y configura `render_as_batch=True` porque SQLite solo puede hacer `ALTER` recreando la tabla. El logging de `alembic.ini` solo se aplica cuando se usa la CLI.
- Revisión única por ahora: `0001_initial_schema.py` (`revision = "0001"`), que crea las cuatro tablas y sus índices.
- `init_db()` se ejecuta al arrancar el backend y en `reanalyze.py`, dentro de una única transacción:
  1. Si existe `photos` pero no `alembic_version`, la BD se creó con el antiguo `create_all()`: se marca como `0001` (`command.stamp`, `BASELINE_REVISION`) sin tocar los datos.
  2. `command.upgrade(config, "head")`.
- Cambio de esquema: modificar los modelos, ejecutar `alembic revision --autogenerate -m "..."` desde `backend/`, revisar el script y aplicarlo con `alembic upgrade head` o arrancando el backend.

## 4. Estructura en disco y reglas de rutas (`backend/utils/photo_files.py`)

`POST /api/folders/scan` crea en la raíz de la carpeta `thumbs/`, `web/`, `cancellate/` y `preferite/`. Las rutas se derivan siempre de `folder.path`, `photo.filename` y `photo.is_deleted`:

```text
<carpeta>/                      ← raíz (Folder.path)
├── 2024/img.jpg                ← original (filename = "2024/img.jpg")
├── thumbs/2024/img.jpg         ← miniatura
├── web/2024/img.jpg            ← versión web
├── preferite/2024/img.jpg      ← copia del favorito
└── cancellate/                 ← misma estructura completa para las fotos borradas
    ├── 2024/img.jpg
    ├── thumbs/2024/img.jpg
    ├── web/2024/img.jpg
    └── preferite/2024/img.jpg
```

- `get_original_path`, `get_thumb_path`, `get_web_path` y `get_favorite_path` aceptan `deleted=None`, que usa el estado actual, o un booleano explícito. La raíz es `folder.path` y, si falta, se deduce de `filepath`.
- Al escanear con `recursive=true`, `_find_images` recorre las subcarpetas con `os.walk` y salta, **a cualquier profundidad**, las que se llaman `thumbs`, `web`, `cancellate` o `preferite`. Como `filename` incluye la subcarpeta, los derivados reproducen la misma estructura.
- Extensiones reconocidas (sin distinguir mayúsculas): `.jpg .jpeg .png .gif .bmp .tif .tiff .webp`, `.heic .heif` y `.cr2 .cr3 .nef .arw .dng .orf .rw2 .raf`.
- El escaneo también **olvida** las fotos cuyo original ya no existe (ni en la raíz ni en `cancellate/`) y borra sus asociaciones con grupos. Solo registra los archivos que no están ya en la BD **en ninguna carpeta** (comparando `filepath` con `os.path.normcase`), de modo que escanear una carpeta padre en modo recursivo no duplica las fotos de una carpeta hija ya registrada: siguen perteneciendo a la hija. Si hubo fotos nuevas u olvidadas, borra los grupos pendientes de la carpeta (`clear_pending_groups`), actualiza `last_scanned` y deja el análisis en segundo plano.
- **Borrar o restaurar** (`move_photo_variants`): mueve con `shutil.move` el original, la miniatura, la versión web y la copia de `preferite/` entre la raíz y `cancellate/`, crea las carpetas que falten, actualiza `is_deleted` y recalcula `filepath`, `has_thumb` y `has_web` (`refresh_photo_file_state`). La aplicación nunca borra archivos de forma definitiva.
- **Favoritos** (`set_favorite`): al marcar, copia el original a `preferite/` con `shutil.copy2` y le aplica sus fechas con `copy_file_times` (en Windows `copy2` no conserva la de creación); al desmarcar, borra esa copia. La usan tanto el endpoint individual como el de lotes.
- **Fechas de archivo** (`utils/file_times.py`): `apply_file_times(path, stat)` restaura acceso y modificación con `os.utime(ns=…)` y, en Windows, la creación (`st_birthtime_ns`) con `SetFileTime` vía `ctypes`, que `os.utime` no puede cambiar. Nunca lanza excepciones: si falla, deja un aviso en el log. Se usa en las versiones web (heredan las fechas del original), en las copias favoritas y al rotar o voltear (el original reescrito con `os.replace` conserva sus fechas). Las miniaturas mantienen su propia fecha de generación.
- `get_web_file_details` devuelve `web_size`, `web_width` y `web_height` de la versión web, o `None` si no existe.

## 5. Procesado de imagen (`backend/utils/image_processing.py`)

### 5.1 Apertura de formatos

- `pillow_heif.register_heif_opener()` se ejecuta al importar el módulo: a partir de ahí, Pillow abre HEIC/HEIF directamente.
- `open_image(path)` es un context manager que cierra siempre la imagen. Para RAW usa `_open_raw_preview`: con `rawpy.imread` extrae la vista previa incrustada (JPEG o bitmap). Si no hay vista previa, revela el archivo completo con `postprocess(use_camera_wb=True)`, que ya aplica la orientación. Si la vista previa no lleva su propia etiqueta Orientation, la endereza según `raw.sizes.flip` de LibRaw (3 → 180°, 5 → 90° antihorario, 6 → 90° horario).
- `needs_jpeg_preview(path)` es verdadero para las extensiones de `JPEG_PREVIEW_EXTENSIONS` = `{.tif, .tiff}` ∪ HEIF ∪ RAW: formatos que los navegadores no muestran. Sus derivados se hacen con Pillow en JPEG y sus originales se sirven como vista previa JPEG (5.3).

### 5.2 FFmpeg

`find_ffmpeg()` se cachea con `lru_cache`, así que tras instalar FFmpeg hay que reiniciar el backend. Busca el ejecutable en este orden:

1. `PHOTO_CLEANER_FFMPEG`;
2. `shutil.which("ffmpeg")` (PATH);
3. solo en Windows, `%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffmpeg.exe`, empezando por la carpeta de versión más reciente;
4. solo en Windows, `%ProgramFiles%\FFmpeg\bin\ffmpeg.exe`.

Si no lo encuentra, se intenta ejecutar `ffmpeg` sin ruta. `check_ffmpeg()` ejecuta `ffmpeg -version` con un timeout de 5 s y es lo que consulta `/api/health`.

El filtro de escalado (`_fit_long_side`) fija el **lado largo** y nunca amplía la imagen:

```text
scale=w='if(gt(iw,ih),min(iw,S),-2)':h='if(gt(iw,ih),-2,min(ih,S))'
```

FFmpeg aplica por sí mismo la orientación EXIF (comprobado con FFmpeg 8).

### 5.3 Derivados

| Derivado | Lado largo | FFmpeg `-q:v` (qscale) | Pillow (TIFF/HEIC/RAW, calidad JPEG) |
| --- | --- | --- | --- |
| Miniatura | 300 px | 5 | 80 |
| Web `web` (por defecto) | 2048 px | 3 | 87 |
| Web `archive` | 1600 px | 5 | 81 |
| Web `ultra` | 1200 px | 7 | 75 |

- Un `mode` desconocido se trata como `web`.
- **Vía FFmpeg** (`_run_ffmpeg(input, output, size, qscale)`): el derivado conserva el nombre y el formato del original (un PNG genera miniaturas PNG). Si la salida es `.webp`, el qscale se convierte a la escala 0–100 de libwebp con `_qscale_to_quality` (`max(10, 96 − 3·qscale)`); para el resto se pasa tal cual.
- **Vía Pillow** (`_resize_with_pillow`: `exif_transpose`, `thumbnail` y `RGB`), para `needs_jpeg_preview`: el derivado es **siempre JPEG, pero conserva el nombre original** (`thumbs/foto.heic` o `web/scan.tif` contienen un JPEG). La calidad web sale del mismo `_qscale_to_quality`. Por eso `GET /file` sirve estos derivados con `media_type="image/jpeg"`.
- **EXIF de las versiones web** (las miniaturas no lo llevan): `_upright_exif` copia el EXIF del original (fecha, cámara, GPS…) con `Orientation = 1`, porque los píxeles ya están derechos, y sin la miniatura incrustada (IFD `1st`). Por la vía Pillow se pasa con `exif=`; por la vía FFmpeg, que no escribe EXIF, se inserta después con `piexif.insert`, solo si la salida es `.jpg`/`.jpeg`. Si el original no tiene EXIF o no se puede leer, la versión web se genera sin él.

`render_jpeg(path, size=2048)` genera al vuelo una vista JPEG derecha (calidad 88) de los originales TIFF/HEIC/RAW que aún no tienen versión web, porque los navegadores no muestran esos formatos. No se guarda en caché.

### 5.4 Metadatos, dimensiones y hashes

- `extract_exif` carga el diccionario de piexif. En los RAW intenta primero leer el propio archivo (casi todos son contenedores TIFF) y, si falla, usa el EXIF de la vista previa. En el resto lee `img.info["exif"]`. Si no hay EXIF, devuelve `{}`. Campos:

| Campo | Origen EXIF |
| --- | --- |
| `camera_make`, `camera_model` | `0th` Make / Model |
| `lens_model` | `Exif` LensModel (sin `\x00` ni espacios finales) |
| `iso` | ISOSpeedRatings (si viene como tupla, el primer valor) |
| `aperture`, `focal_length` | FNumber, FocalLength (racional → float) |
| `shutter_speed` | ExposureTime como `"n/d"` |
| `date_taken` | DateTimeOriginal (`%Y:%m:%d %H:%M:%S`); si no es válida, `None` |
| `gps_latitude`, `gps_longitude` | GPSLatitude/Longitude en grados, minutos y segundos → decimal, negativo si la referencia no es N/E |
| `gps_altitude` | GPSAltitude; negativa si GPSAltitudeRef = 1 (bajo el nivel del mar) |

- `get_image_info` devuelve `width`, `height`, `format` y `size`. Las dimensiones son **las de la imagen tal como se muestra**: se intercambian si la orientación EXIF es 5–8 o, en RAW, si `sizes.flip` es 5 o 6.
- `compute_hashes` calcula `phash` y `dhash` (`hash_size=8`, 64 bits) **sobre la imagen ya enderezada** (`exif_transpose`), para que una misma foto guardada con distinta orientación EXIF dé el mismo hash. Si falla, devuelve `None` en ambos.

### 5.5 Rotar y voltear sin pérdida

Operaciones de usuario: `ROTATIONS` (`90`, `-90`, `180` y `270` grados en sentido horario, convertidos a `Image.Transpose`) y `FLIPS` (`horizontal`, `vertical`). `_transform_photo` en `api/photos.py` elige la estrategia según el original:

1. **JPEG** (extensión `.jpg`/`.jpeg`): `transform_original` solo reescribe la etiqueta EXIF `Orientation` con piexif. Los píxeles, la fecha, el GPS y la cámara no cambian. La orientación nueva sale de `_compose_orientation(actual, op)`, que aplica la orientación actual y la operación a una imagen de prueba asimétrica de 3×2 y busca cuál de las 8 orientaciones EXIF produce el mismo resultado (una orientación desconocida se trata como 1).
2. **Formatos sin pérdida** (`can_transform_losslessly`): primero descarta por extensión HEIC/HEIF y RAW, porque Pillow abre algunos RAW (basados en TIFF) y volver a guardarlos sustituiría los datos de la cámara por la imagen decodificada. Después admite PNG, BMP, TIFF, GIF y WebP, siempre con **un solo fotograma**, sin TIFF con compresión JPEG y, en WebP, solo sin pérdida (`_webp_is_lossless_still` recorre los chunks RIFF buscando `VP8L`; un chunk `VP8` con pérdida o `ANIM` lo descartan). `transform_lossless` integra la orientación EXIF en los píxeles, aplica la operación y vuelve a guardar en el mismo formato con `icc_profile`, `dpi`, `transparency`, EXIF (ya sin orientación), los chunks de texto PNG, la compresión TIFF y, en WebP, `lossless=True, exact=True`.
3. **Todo lo demás** se rechaza con **400**: HEIC/HEIF, RAW, GIF/WebP animados, WebP con pérdida, TIFF-JPEG y otros formatos.

En los dos primeros casos se escribe primero en `<archivo>.tmp` y después se hace `os.replace`, para que un fallo nunca deje el original truncado. Además: la copia de `preferite/`, si existe, recibe la misma transformación; la miniatura y la versión web se recodifican (`transform_derivative`, calidad 90) en el **formato real** del archivo, no en el que sugiere su extensión (el derivado de un TIFF sigue siendo JPEG), y, si eso falla, se borran para regenerarlas después; por último se recalculan `width`, `height`, `phash` y `dhash`.

## 6. Detección de duplicados (`backend/api/similar.py`)

1. **Candidatas**: fotos de la carpeta no borradas, con un `phash` hexadecimal válido y que no estén en ningún grupo ya revisado (`is_reviewed = True`), ordenadas por `filename, id`. Como el agrupado voraz depende del orden, así el resultado es determinista. Si quedan menos de 2, la respuesta es `{"message": "Not enough photos to compare"}`.
2. **Reagrupar sustituye**: `clear_pending_groups(db, folder_id)` borra los grupos **pendientes** de la carpeta y sus asociaciones; los revisados se conservan. La llaman `POST /group` antes de agrupar, el escaneo (si hubo fotos nuevas u olvidadas) y `reanalyze.py`, para que no queden grupos obsoletos. Compare vuelve a agrupar cuando no hay ninguno pendiente.
3. **Agrupado voraz vectorizado** (`_find_groups`): los hashes se pasan a un array `uint64`. Cada foto que aún no tiene grupo reúne a todas las posteriores sin grupo cuya distancia de Hamming con ella sea `<= threshold` (por defecto 5). Cada fila se calcula como `np.bitwise_count(hashes[i+1:] ^ hashes[i])`, que requiere numpy ≥ 2.0. Es el mismo algoritmo que el bucle original por pares (los tests de `tests/test_similar.py` comprueban la equivalencia), pero la comparación ocurre en C: **50.000 hashes en ~1,2 s** (medido). La complejidad sigue siendo O(n²).
4. **Clasificación** por la distancia media entre todos los pares del grupo (`_average_distance`), que se guarda en `similarity_score`:

| Distancia media | `group_type` |
| --- | --- |
| ≤ 3 | `duplicate` |
| ≤ 5 | `burst` |
| > 5 | `similar` |

Como los miembros solo se comparan con la foto semilla, la distancia media puede superar el umbral (hasta 2·`threshold` entre dos miembros).

**Revisión**: `select` marca el grupo como revisado y guarda `selected_photo_id`; con `delete_others=true` mueve las demás fotos a `cancellate/` con `move_photo_variants`. `skip` solo lo marca como revisado.

## 7. API REST

Base `http://localhost:8000`. Todas las respuestas son JSON salvo `GET /api/photos/file`. Errores:

- `HTTPException`: `{"detail": "..."}` con su código. Casi todos los endpoints convierten las excepciones inesperadas en **500** con `detail=str(e)`, pero dejan pasar las `HTTPException`, así que un 404 sigue siendo 404.
- Validación de parámetros: **422** `{"error": true, "code": "VALIDATION_ERROR", "message", "details": {"errors": [{field, message, type}]}}`.
- Excepción no capturada: **500** `{"error": true, "code": "INTERNAL_SERVER_ERROR", "message", "details": {"path"}}`.
- `LoggingMiddleware` registra en el log el método y la ruta de cada petición HTTP.

### 7.1 General (`main.py`)

| Método | Ruta | Respuesta |
| --- | --- | --- |
| GET | `/` | `{status: "running", app, version}` |
| GET | `/api/health` | `{status: "healthy"\|"degraded", database: "connected"\|"unavailable", ffmpeg: "available"\|"missing"}` (ejecuta `SELECT 1` y `ffmpeg -version`) |

### 7.2 Carpetas (`/api/folders`)

| Método | Ruta | Parámetros / cuerpo | Respuesta | Códigos |
| --- | --- | --- | --- | --- |
| POST | `/scan` | `{path: str, recursive: bool = false}` | `{folder_id, name, path, total_photos, new_photos, removed_photos, subfolders_created, analysis_task_id}` (`analysis_task_id` es `null` si no hay nada que analizar) | 400 si la carpeta no existe |
| GET | `/stats/{folder_id}` | — | `{id, name, path, total_photos, favorites_count, deleted_count, thumbs_count, web_count, has_thumbs, has_web}`, contado al vuelo sobre las fotos **no borradas** (salvo `deleted_count`); `has_thumbs = thumbs_count == total_photos` | 404 |
| GET | `/list` | — | `[{id, name, path, total_photos, favorites_count, deleted_count, created_at, last_scanned}]`, con recuentos al vuelo (`total_photos` y `favorites_count` sobre fotos no borradas) | — |

### 7.3 Fotos (`/api/photos`)

| Método | Ruta | Parámetros / cuerpo | Respuesta | Códigos |
| --- | --- | --- | --- | --- |
| GET | `/list/{folder_id}` | `skip ≥ 0` (0), `limit` 1–5000 (100), `only_favorites`, `only_deleted`; filtro de **zona** `min_lat`, `max_lat`, `min_lon`, `max_lon` (los cuatro; `min_lon > max_lon` = cruza el antimeridiano) o de **radio** `near_lat`, `near_lon`, `radius_km` (0 < r ≤ 20000, con `distance_km`) | `{total, skip, limit, photos: [{id, filename, is_favorite, is_deleted, has_thumb, has_web}]}`, ordenadas por `filename, id`. Solo lee la BD; `total` respeta los filtros. | 422 si un parámetro está fuera de rango; 400 si un filtro de posición está incompleto o `min_lat > max_lat` |
| GET | `/get/{photo_id}` | — | Detalle completo: columnas de archivo, estado, EXIF y GPS (sin altitud), más `web_size/web_width/web_height`. Sincroniza `has_thumb/has_web` con el disco y lo guarda (commit). | 404 |
| GET | `/file/{photo_id}` | `thumb` (false), `prefer_web` (false) | Archivo. `thumb=true`: la miniatura. Si no: la versión web si existe y (`prefer_web` o TIFF/HEIC/RAW); si no, el original; TIFF/HEIC/RAW sin versión web → `render_jpeg`. Los derivados de TIFF/HEIC/RAW se sirven como `image/jpeg` | 404 si falta la miniatura o el original |
| POST | `/favorite/{photo_id}` | — | `{id, is_favorite}` (alterna) | 404 |
| POST | `/delete/{photo_id}` | — | `{id, is_deleted}` | 404 |
| POST | `/restore/{photo_id}` | — | `{id, is_deleted}` o `{message: "Photo is not deleted"}` | 404 |
| POST | `/batch-operation` | `{operation: "favorite"\|"unfavorite"\|"delete"\|"restore", photo_ids: [int]}` | `{operation, total, success, errors, failed_ids, message}` (commit cada 25) | 400 si la lista está vacía o la operación es desconocida |
| POST | `/generate-thumbs/{folder_id}` | — | Síncrono: `{total, success, errors, message}` | — |
| POST | `/generate-web/{folder_id}` | `mode` = `web`\|`archive`\|`ultra` | Síncrono: igual que el anterior, más `mode` | — |
| POST | `/generate-thumbs-async/{folder_id}` | — | `{task_id, message, status_url}` o `{task_id: null, message, status: "already_exists"}` | — |
| POST | `/generate-web-async/{folder_id}` | `mode` | Igual que el anterior | — |
| GET | `/tasks/{task_id}` | — | `Task.to_dict()` | 404 |
| POST | `/tasks/{task_id}/cancel` | — | `{id, cancelled: bool}` | 404 |
| GET | `/tasks` | `status` opcional (`TaskStatus`: `pending`, `running`, `completed`, `failed`, `cancelled`) | `{total, tasks: [...]}`, filtradas por estado si se indica | 422 si el estado no es válido |
| POST | `/rotate/{photo_id}` | `degrees` ∈ {90, -90, 180, 270} (90) | `{id, filename, rotation, message}` | 400 si el ángulo o el formato no son válidos; 404; 500 si falla |
| POST | `/flip/{photo_id}` | `direction` ∈ {horizontal, vertical} | `{id, filename, direction, message}` | Igual que el anterior |

### 7.4 Similares (`/api/similar`)

| Método | Ruta | Parámetros | Respuesta | Códigos |
| --- | --- | --- | --- | --- |
| POST | `/analyze/{folder_id}` | — | `{status: "started", task_id, status_url, message}` o `{task_id: null, message}` (reutiliza un análisis en curso) | — |
| POST | `/group/{folder_id}` | `threshold` (5) | `{groups_found, photos_grouped, groups: [{id, photo_count, similarity_score, group_type}]}` | — |
| GET | `/groups/{folder_id}` | `only_unreviewed` (false) | `{total_groups, groups: [{id, photo_count, similarity_score, group_type, is_reviewed, selected_photo_id, photo_ids}]}` | — |
| GET | `/group/{group_id}` | — | `{id, similarity_score, group_type, is_reviewed, selected_photo_id, photos: [{id, filename, filepath, width, height, size, has_web, date_taken, is_favorite, is_deleted, web_size, web_width, web_height}]}` | 404 |
| POST | `/group/{group_id}/select/{photo_id}` | `delete_others` (false) | `{group_id, selected_photo_id, deleted_count}` | 404 si el grupo no existe; 400 si la foto no pertenece al grupo |
| POST | `/group/{group_id}/skip` | — | `{group_id, is_reviewed: true}` | 404 |

Ojo: `POST /group/{folder_id}` y `GET /group/{group_id}` comparten patrón de ruta, pero el identificador es distinto.

### 7.5 Metadatos (`/api/metadata`)

El frontend actual no usa estos endpoints. Salvo `/cameras` y `/search` con `only_deleted`, todos trabajan solo con fotos no borradas.

| Método | Ruta | Parámetros / cuerpo | Respuesta |
| --- | --- | --- | --- |
| POST | `/search` | `{folder_id, date_from?, date_to?, camera_make?, camera_model?, min_iso?, max_iso?, min_aperture?, max_aperture?, has_gps?, only_favorites=false, only_deleted=false}`. Fechas ISO, que se parsean con `datetime.fromisoformat` (una fecha inválida da 500); un `date_to` de solo fecha (`YYYY-MM-DD`) incluye el día entero. `camera_*` con `LIKE %…%`. Los filtros numéricos se aplican si no son `null` (0 incluido). | `{total, photos: [{id, filename, filepath, date_taken, camera_model, iso, aperture, is_favorite, has_gps}]}` (sin paginar) |
| GET | `/cameras/{folder_id}` | — | `{total, cameras: [{make, model, display_name}]}` (incluye las fotos borradas) |
| GET | `/date-range/{folder_id}` | — | `{min_date, max_date, photos_with_dates}` o `{min_date: null, max_date: null}` |
| GET | `/stats/{folder_id}` | — | `{total_photos, photos_with_exif, photos_with_gps, unique_cameras, exif_coverage, gps_coverage}` (todo sobre el mismo conjunto, así que la cobertura no pasa del 100 %) |
| GET | `/by-month/{folder_id}` | — | `{total_months, months: [{year, month, month_name, photo_count, photos (10 primeras)}]}`, de más reciente a más antiguo |
| GET | `/gps-map/{folder_id}` | — | `{total, locations: [{id, filename, latitude, longitude, altitude, date_taken, has_thumb}]}` (solo fotos no borradas con GPS) |

### 7.6 Geo (`/api/geo`, `backend/api/geo.py`)

| Método | Ruta | Parámetros | Respuesta | Errores |
| --- | --- | --- | --- | --- |
| GET | `/search` | `q` (2–200 caracteres) | `{total, places: [{name, latitude, longitude, bbox: {south, north, west, east}}]}` (máx. 5) | 422; **502** si Nominatim no responde |

Es el único endpoint que sale a internet: hace de proxy a `https://nominatim.openstreetmap.org/search` con un `User-Agent` propio (`PhotoCleaner/1.0`), como pide la política de uso de Nominatim, y cachea los resultados en memoria por texto buscado (`lru_cache`, 256 entradas). Solo envía el texto buscado. Los tests simulan `urllib.request.urlopen`.

## 8. Frontend (`frontend/src`)

Scripts de `package.json`: `npm run dev` (o `npm start`) arranca Vite en el puerto 3000 y abre el navegador; también hay `build`, `preview` y `lint` (ESLint 9, `eslint.config.js`). El punto de entrada es `index.html` → `src/index.jsx` (`React.StrictMode`) → `App.jsx`.

```text
src/
├── App.jsx              BrowserRouter > ToastProvider > KeyboardShortcuts + ErrorBoundary > Routes
├── pages/
│   ├── Home.jsx         /                     escanear carpeta (con opción recursiva) y lista de proyectos
│   ├── Gallery.jsx      /gallery/:folderId    visor, tira de miniaturas, acciones y lotes
│   └── Compare.jsx      /compare/:folderId    revisión de grupos de similares
├── components/          PhotoViewer, ThumbnailStrip, BatchActionBar, Toast, ErrorBoundary,
│                        KeyboardShortcuts, ProgressBar
├── hooks/useBackgroundTask.js   sondea GET /photos/tasks/{id} cada 1 s hasta que la tarea termina o la consulta falla
├── services/api.js      cliente axios + foldersAPI, photosAPI, similarAPI, metadataAPI, geoAPI, apiErrorMessage
└── utils/format.js      formatFileSize
```

- **`services/api.js`**: la base es `import.meta.env.VITE_API_URL || 'http://localhost:8000/api'`. `photosAPI.getFile` no hace ninguna petición: devuelve la URL para un `<img>`. `apiErrorMessage(error, fallback)` extrae `detail` o `message` de la respuesta del backend.
- **Gallery**:
  - Filtros de posición por URL (`utils/geo.js::readPositionFilter`): los parámetros de zona o radio se pasan tal cual a `/photos/list`, se muestra una barra con el filtro (con selector de radio para «Nearby photos») y `?photo=ID` sitúa la galería en esa foto en cuanto se carga. «View on map» (tecla `M`) abre `/map/:id?focus=ID`; «Nearby photos» abre la galería con `near_lat/near_lon/radius_km=1`.
  - **Carga paginada**: pide `/photos/list` de 2.000 en 2.000 (`PAGE_SIZE`; el backend admite hasta 5.000) hasta llegar a `total`. En la primera carga muestra cada página en cuanto llega (`progressive`); en las recargas solo sustituye la lista cuando está completa, para no perder la posición. Un contador de peticiones descarta las cargas que ya no son las más recientes.
  - **Detalle bajo demanda**: la lista solo contiene resúmenes. Para la foto actual se pide `/photos/get/{id}`, que se vuelve a pedir cuando cambia `imageRevision` tras rotar o voltear, y se combina con el resumen. La imagen principal usa `getFile(id, false, preferWeb)&rev=N` para evitar la caché del navegador.
  - Generación de miniaturas y versiones web con los endpoints `*-async` y `useBackgroundTask`; al terminar recarga la lista y las estadísticas. Si la consulta del estado falla (p. ej. 404 porque el backend se reinició y la tarea ya no existe), el hook deja de sondear y la galería muestra el error.
  - Atajos: ←/→, `F` favorito, `D`/`Supr` borrar (con aviso para deshacer, que llama a `restore`), `R` rotar 90°, `H` voltear en horizontal, `V` alternar entre original y versión web. Se ignoran cuando el foco está en un `input` o un `textarea` y mientras está abierta la ayuda de atajos (`.keyboard-shortcuts-overlay`).
- **PhotoViewer**: imagen con zoom por rueda (1–8×, en pasos de 0,15) y desplazamiento arrastrando. El zoom usa un listener nativo `wheel` con `{ passive: false }`, porque el `onWheel` de React es pasivo y no puede cancelar el scroll. Panel de información plegable (resolución y tamaño de la versión que se muestra, cámara, objetivo, fecha y GPS con un mapa de OpenStreetMap en `iframe`). El aviso para deshacer el borrado queda fuera de la parte plegable, así que se ve aunque el panel esté plegado.
- **ThumbnailStrip**: solo pinta las miniaturas en una **ventana de ±60** alrededor de la foto actual (`STRIP_WINDOW`, como mucho 121 nodos), con `loading="lazy"`, y centra la miniatura activa. Ctrl/Cmd+clic alterna la selección. Si una foto no tiene miniatura, carga el archivo completo.
- **BatchActionBar**: aparece cuando hay selección; las acciones son favorito, borrar (con confirmación) y limpiar la selección, y van a `/photos/batch-operation`.
- **Compare**: pide los grupos pendientes y el detalle de cada uno, descartando las fotos ya borradas y los grupos que se quedan con menos de 2. Si no queda ninguno, lanza `similar/analyze`, espera a que termine mostrando el progreso, agrupa (`threshold` 5) y vuelve a pedirlos. «Delete Selected» y «Delete Others» borran con `/photos/delete` y después marcan el grupo como revisado con `skip`; no usan `select`, así que `selected_photo_id` no se guarda desde la UI. Atajos (desactivados mientras está abierta la ayuda): `1`–`9` seleccionan, ←/→ cambian de grupo, `S` salta el grupo.
- **MapView** (`pages/MapView.jsx`, ruta `/map/:folderId`, cargada con `React.lazy`): pide `/metadata/gps-map` y pinta un `L.circleMarker` por foto dentro de un `L.markerClusterGroup` con `chunkedLoading`. El encuadre inicial (o el popup de `?focus=ID`) se hace en `chunkProgress` cuando se han procesado todos los marcadores, en el tick siguiente, porque markercluster avisa antes de terminar de montar el árbol. El popup (miniatura, nombre, fecha y «Open in gallery» → `/gallery/:id?photo=ID`) se construye bajo demanda. «Select area» desactiva el arrastre del mapa y dibuja un `Rectangle` con mousedown/move/up; «Use visible area» usa `map.getBounds()`. La zona se convierte con `utils/geo.js::boundsToArea`, que normaliza las copias del mundo y el antimeridiano. El recuento se hace en el cliente con la misma regla que el backend (`isInArea`), y «Open in gallery» navega a `/gallery/:id?min_lat=…`. El buscador llama a `geoAPI.searchPlaces` y hace `flyToBounds` a la `bbox` elegida.
- **Toast**: `ToastProvider` + `useToast()` con los tipos `info`/`success` (4 s) y `error` (7 s); sustituye a `alert()`.
- **ErrorBoundary**: si un error de render escapa de una página, muestra una pantalla de recuperación con «Reload» y «Back to Home».
- **KeyboardShortcuts**: modal de ayuda global que se abre con `?` y se cierra con `Esc` o con un clic fuera.

## 9. Rendimiento y limitaciones

### 9.1 Mediciones (300 fotos de 3000×2000 con el servidor real, salvo que se indique otra cosa)

| Operación | Resultado |
| --- | --- |
| `POST /folders/scan` (solo registra los archivos) | 0,13 s |
| Análisis en segundo plano (EXIF, dimensiones, hashes) | ~4,5 s |
| `/api/health` mientras se generan 300 miniaturas | 3–50 ms |
| Agrupado de similares, 50.000 hashes | ~1,2 s |

Otros valores relevantes: miniaturas de 300 px de lado largo; la galería no vuelve a tocar el disco al listar; la tira de miniaturas mantiene como mucho 121 nodos; hay 3 tareas en paralelo como máximo, y dentro de cada una `cpu_count` workers de análisis o `cpu_count/2` de FFmpeg.

### 9.2 Limitaciones conocidas

- **RAW sin probar con archivos reales**: en los tests, `rawpy` está simulado. No se han validado la orientación por `sizes.flip`, el EXIF leído con piexif ni las dimensiones con cámaras reales.
- **El agrupado sigue siendo O(n²)**, aunque en C. Si 1,2 s/50k se queda corto, las alternativas previstas son ventanas por `date_taken` o un BK-tree. El agrupado voraz en estrella es determinista (orden `filename, id`), pero el resultado depende de ese orden, y las fotos de grupos ya revisados no se vuelven a proponer aunque aparezcan duplicados nuevos.
- **Los archivos que fallan al analizarse** se quedan con `phash = NULL` y se reintentan en cada escaneo y cada vez que se abre Comparar.
- **Cancelar un análisis puede solaparlo con otro nuevo**: una tarea cancelada cuenta como terminada en cuanto se marca, así que `enqueue_folder_analysis` puede lanzar otro análisis de la misma carpeta mientras el anterior aún no ha llegado a su siguiente comprobación de `is_cancelled`.
- Si un archivo cambia en disco después de analizarse, no se reanaliza solo: hay que ejecutar `reanalyze.py`.
- **La cola de tareas vive en memoria**: un reinicio pierde las tareas y su progreso. Las tareas ya terminadas se olvidan pasado el límite de 100.
- Cambiar el modo de la versión web no regenera las versiones que ya existen; solo se generan las que faltan.
- TIFF/HEIC/RAW sin versión web se convierten al vuelo en cada petición (`render_jpeg`, sin caché).
- Rotar y voltear no están disponibles para HEIC/HEIF, RAW, formatos animados ni WebP con pérdida.
- Con carpetas solapadas, cada foto pertenece a la primera carpeta que la registró: al escanear la carpeta padre de forma recursiva no aparecen las fotos que ya están en una carpeta hija registrada, y al revés.
- Funciones del backend sin interfaz: la UI no usa `select` de similares (no guarda `selected_photo_id`), los endpoints de `/api/metadata`, la cancelación de tareas (`POST /tasks/{id}/cancel`) ni los `generate-*` síncronos.
- Las columnas `folders.favorites_count` y `deleted_count` siguen en el esquema pero no se usan: los recuentos se calculan al vuelo.
- Hay restos ignorados por git que no pertenecen al proyecto actual: `backend/models/` (vacía) y `frontend/build/` (compilación antigua de CRA).
- En el escaneo recursivo se ignora cualquier subcarpeta del usuario que se llame `thumbs`, `web`, `cancellate` o `preferite`.
- No hay autenticación. La API solo escucha en `127.0.0.1` por defecto y puede leer cualquier ruta a la que tenga acceso el proceso. El mapa del visor carga `openstreetmap.org` con las coordenadas de la foto.
- SQLite admite un único escritor; WAL y `busy_timeout` evitan los errores de bloqueo, pero no paralelizan las escrituras.
