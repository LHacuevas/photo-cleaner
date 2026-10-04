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

- [x] **No bloquear el event loop**: todos los endpoints son `def` (FastAPI los ejecuta en su threadpool); la cola de tareas usa hilos en vez de `asyncio.create_task`. Se usan hilos y no `ProcessPoolExecutor`: FFmpeg ya es un proceso externo y PIL libera el GIL al decodificar. Medido: `/api/health` responde en 3–50 ms mientras se generan 300 miniaturas.
- [x] **Escaneo en segundo plano**: la petición solo registra archivos (0,13 s para 300 fotos) y devuelve `analysis_task_id`; EXIF, dimensiones y hashes se calculan en paralelo en `utils/analysis.py`.
- [x] **Comparar espera al análisis** antes de agrupar (con progreso); un análisis en curso de la misma carpeta se reutiliza en vez de duplicarse.
- [x] **Agrupado vectorizado**: mismo algoritmo voraz (verificado contra la versión original con tests), pero cada fila es un XOR + popcount en numpy. 50.000 hashes en 1,2 s. Sigue siendo O(n²) en C; si hiciera falta más, ventanas por `date_taken` o BK-tree.
- [x] **Galería**: carga todas las páginas (2.000 por petición, la primera se muestra al llegar); la tira de miniaturas solo pinta ±60 alrededor de la foto actual.
- [x] **`/list` sin tocar disco**: devuelve resúmenes desde la BD; los detalles (EXIF, versión web) se piden con `/get` solo para la foto actual. No hizo falta cambiar el esquema.
- [x] Cerrar imágenes (`with Image.open(...)`).
- [x] SQLite: WAL + `busy_timeout`; ruta absoluta de la BD, configurable con `PHOTO_CLEANER_DATABASE_URL`.
- [ ] Opcional: agrupado sub-cuadrático (BK-tree / ventanas por fecha) y union-find, solo si 1,2 s/50k se queda corto.

## Fase 2 — Calidad de procesamiento de imagen

- [ ] Miniaturas: `scale=300:-1` fija el ancho, no el lado largo (FFmpeg 8 sí aplica la orientación EXIF, comprobado).
- [ ] Versiones web: no ampliar imágenes pequeñas (`min(iw,2048)`).
- [ ] Hashes con `exif_transpose` para detectar duplicados con distinta orientación.
- [x] `extract_exif` ya no falla en fotos sin EXIF.
- [ ] Extraer `lens_model`; soporte HEIC/RAW (`pillow-heif`, `rawpy`).
- [ ] Rotar/voltear para formatos no JPEG sin perder datos.
- [ ] FFmpeg: `shutil.which` + variable de entorno en vez de ruta winget fija; `/api/health` debe usar `check_ffmpeg()`.
- [x] Escaneo: extensiones sin distinguir mayúsculas y sin doble glob en Windows.
- [ ] Escaneo: opción recursiva; detectar fotos eliminadas del disco.

## Fase 3 — Deuda técnica

- [x] Cola de tareas: `cancel_task` cancela de verdad (nuevo `POST /api/photos/tasks/{id}/cancel`) y las tareas viejas se limpian solas.
- [x] Endpoints `generate-*` síncronos y asíncronos comparten una única implementación.
- [ ] Código muerto: `stats_cache`, `metadata_cache`, `QueryOptimizer` (importados o definidos sin uso); `update_metadata.py` duplica `utils/analysis.py`.
- [ ] Acciones por lotes de la galería sin conectar: `handleBatchFavorite`, `handleBatchDelete` y `handleClearSelection` están definidos en `Gallery.js` pero no se usan (ESLint).
- [ ] Unificar `_get_web_file_details` (duplicado en `similar.py`, ignora `cancellate/`).
- [ ] Alembic para migraciones (antes de cualquier cambio de esquema).
- [ ] Configuración en `.env` (CORS, puertos, FFmpeg); `start.bat` anuncia el puerto 3001 pero CRA usa 3000.
- [ ] Frontend: extraer `PhotoViewer`/`ThumbnailStrip` de `Gallery.js`, toasts en vez de `alert()`, ErrorBoundary, migrar CRA → Vite.
- [ ] Actualizar dependencias (FastAPI, Pydantic, SQLAlchemy, httpx); `lifespan` en lugar de `on_event("startup")`; `datetime.utcnow` deprecado.
- [ ] Unificar idioma (README en italiano, código en inglés, carpetas `cancellate`/`preferite`).

## Fase 4 — Tests y CI

- [x] pytest del ciclo de archivos (borrar, restaurar, favorito, rotar) comprobando que el original no cambia (hash/píxeles).
- [x] Tests de escaneo y agrupado con imágenes sintéticas (incluye equivalencia del agrupado vectorizado con el original).
- [x] Tests de endpoints con `TestClient` (98 tests; `cd backend && pytest`, dependencias en `requirements-dev.txt`).
- [ ] GitHub Actions: ruff + pytest + build del frontend.

## Fase 5 — Funcionalidades

- [ ] Sugerir la mejor foto de cada grupo (nitidez por varianza del Laplaciano, resolución, tamaño).
- [ ] Detección de fotos borrosas.
- [ ] Vista de línea de tiempo (los endpoints `by-month` ya existen).
- [ ] Papelera con "vaciar definitivamente" y confirmación.
