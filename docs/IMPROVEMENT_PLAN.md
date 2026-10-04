# Plan de mejoras — Photo Cleaner

Plan surgido de la revisión del proyecto (2026-10-04). Se sigue fase a fase; marcar cada punto al terminarlo.

**Diagnóstico:** muchas funcionalidades y bastante documentación, pero hay huecos entre lo que se promete y lo que hace el código. Lo "no destructivo" no se cumplía (rotar/voltear reescribía el original y perdía EXIF), "50.000+ fotos" choca con que la galería carga 1.000, el agrupado de similares es O(n²) y el escaneo bloquea el servidor. Comparar no creaba grupos desde la UI. No hay tests.

---

## Fase 0 — Bugs críticos

- [x] **Rotar/voltear destruía el original** (recodificaba JPEG y perdía todo el EXIF). Ahora el original solo cambia la etiqueta EXIF `Orientation` (sin recodificar) y se transforman `thumbs/` y `web/`. Solo JPEG.
- [x] **`frontend/public/` estaba ignorado** por la regla `public` de Gatsby en `.gitignore`: un clon limpio no arrancaba.
- [x] **Comparar no creaba grupos**: `Compare.js` no llamaba a `similarAPI.group()`. Ahora agrupa si no hay grupos pendientes, muestra solo los no revisados y marca el grupo como revisado al borrar.
- [x] **404 convertidos en 500** por `except Exception` que capturaba `HTTPException`.
- [x] **Tarea de hashes con sesión de BD cerrada** (`similar/analyze`): ahora abre su propia sesión y corre en el threadpool.
- [x] **Grupos duplicados en cada agrupado**: se borran los grupos no revisados antes de reagrupar y se excluyen fotos ya revisadas.
- [x] **"Borrar los demás" con lógica de movimiento distinta**: usa la misma función que el resto (`utils/photo_files.py`) y valida que la foto pertenezca al grupo.
- [x] **Favoritos inconsistentes** (individual copiaba a `preferite/`, lote no): una sola función `set_favorite()`.
- [x] **API expuesta en la LAN** (`0.0.0.0`): por defecto `127.0.0.1`, configurable con `PHOTO_CLEANER_HOST`.

## Fase 1 — Escalabilidad real (50k fotos)

- [ ] No bloquear el event loop: endpoints `def` en vez de `async def` con trabajo síncrono; trabajo pesado (FFmpeg, PIL, hashes) en `ProcessPoolExecutor` dentro de la cola de tareas.
- [ ] Escaneo de carpeta como tarea en segundo plano con progreso (hoy calcula hashes/EXIF dentro de la petición HTTP).
- [ ] Comparar: `analyze` lanza los hashes en segundo plano y `group` se ejecuta enseguida, así que las fotos sin hash aún no entran en el agrupado. Esperar a que termine (tarea con estado) antes de agrupar.
- [ ] Agrupado de similares sin O(n²): ventanas por `date_taken`, BK-tree o numpy (`uint64` + XOR/popcount); union-find en vez del agrupado voraz.
- [ ] Galería: paginación / scroll virtual (`react-window`); hoy pide `limit: 1000` y nunca carga el resto.
- [ ] `_serialize_photo` sin tocar disco: guardar `web_width/web_height/web_size` en BD y confiar en `has_thumb/has_web`.
- [ ] Cerrar imágenes (`with Image.open(...)`): en Windows un handle abierto bloquea `shutil.move`.
- [ ] SQLite: WAL + `busy_timeout`; ruta absoluta de la BD (hoy `./photo_cleaner.db` depende del cwd).

## Fase 2 — Calidad de procesamiento de imagen

- [ ] Miniaturas: `scale=300:-1` fija el ancho, no el lado largo; aplicar orientación EXIF (o generarlas con Pillow + `ImageOps.exif_transpose`).
- [ ] Versiones web: no ampliar imágenes pequeñas (`min(iw,2048)`).
- [ ] Hashes con `exif_transpose` para detectar duplicados con distinta orientación.
- [ ] `extract_exif` falla (y lo registra como error) en fotos sin EXIF: `piexif.load(b'')` interpreta el vacío como nombre de archivo.
- [ ] Extraer `lens_model`; soporte HEIC/RAW (`pillow-heif`, `rawpy`).
- [ ] Rotar/voltear para formatos no JPEG sin perder datos.
- [ ] FFmpeg: `shutil.which` + variable de entorno en vez de ruta winget fija; `/api/health` debe usar `check_ffmpeg()`.
- [ ] Escaneo: evitar doble glob mayúsculas/minúsculas en Windows; opción recursiva; detectar fotos eliminadas del disco.

## Fase 3 — Deuda técnica

- [ ] Código muerto: `stats_cache`, `metadata_cache`, `QueryOptimizer` (importados sin uso), `cancel_task` (no cancela nada), `cleanup_old_tasks` (nunca se llama); endpoints `generate-*` síncronos duplicados.
- [ ] Acciones por lotes de la galería sin conectar: `handleBatchFavorite`, `handleBatchDelete` y `handleClearSelection` están definidos en `Gallery.js` pero no se usan (ESLint).
- [ ] Unificar `_get_web_file_details` (duplicado en `similar.py`, ignora `cancellate/`).
- [ ] Alembic para migraciones (antes de los cambios de esquema de la Fase 1).
- [ ] Configuración en `.env` (CORS, puertos, BD, FFmpeg); `start.bat` anuncia el puerto 3001 pero CRA usa 3000.
- [ ] Frontend: extraer `PhotoViewer`/`ThumbnailStrip` de `Gallery.js` (742 líneas), toasts en vez de `alert()`, ErrorBoundary, migrar CRA → Vite.
- [ ] Actualizar dependencias (FastAPI, Pydantic, SQLAlchemy); `lifespan` en lugar de `on_event("startup")`.
- [ ] Unificar idioma (README en italiano, código en inglés, carpetas `cancellate`/`preferite`).

## Fase 4 — Tests y CI

- [ ] pytest del ciclo de archivos (borrar, restaurar, favorito, rotar) en un directorio temporal, comprobando que el original nunca cambia de píxeles.
- [ ] Tests de escaneo y agrupado con imágenes sintéticas.
- [ ] Tests de endpoints con `TestClient`.
- [ ] GitHub Actions: ruff + pytest + build del frontend.

## Fase 5 — Funcionalidades

- [ ] Sugerir la mejor foto de cada grupo (nitidez por varianza del Laplaciano, resolución, tamaño).
- [ ] Detección de fotos borrosas.
- [ ] Vista de línea de tiempo (los endpoints `by-month` ya existen).
- [ ] Papelera con "vaciar definitivamente" y confirmación.
