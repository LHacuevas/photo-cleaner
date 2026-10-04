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

- [x] Miniaturas y versiones web escaladas por el **lado largo** y **sin ampliar** nunca (filtro `scale` con `min(iw,N)`; FFmpeg 8 aplica la orientación EXIF, comprobado).
- [x] Hashes, ancho y alto calculados sobre la imagen **tal como se ve** (`exif_transpose`): la misma foto guardada con otra orientación se detecta como duplicada. Rotar o voltear recalcula hash y dimensiones.
- [x] `extract_exif` ya no falla en fotos sin EXIF; se extrae `lens_model`.
- [x] **HEIC/HEIF** (`pillow-heif`) y **RAW** (CR2, CR3, NEF, ARW, DNG, ORF, RW2, RAF vía `rawpy`, usando la vista previa incrustada): se escanean, analizan, generan miniaturas y versiones web en JPEG, y se sirven como JPEG al navegador. RAW está probado con un `rawpy` simulado; falta probarlo con archivos reales.
- [x] Rotar/voltear **sin pérdida** también en PNG, BMP, TIFF, GIF y WebP lossless (píxeles exactos; se conservan ICC, EXIF, DPI y textos PNG). Se rechazan WebP con pérdida, imágenes animadas, HEIC y RAW.
- [x] FFmpeg: se busca en `PHOTO_CLEANER_FFMPEG`, luego en el PATH y luego en winget/Program Files, sin versión fija; `/api/health` lo comprueba de verdad (y también la BD).
- [x] Escaneo: extensiones sin distinguir mayúsculas; opción **recursiva** («Include subfolders»), donde `filename` es la ruta relativa y thumbs, web, cancellate y preferite replican las subcarpetas; al reescanear se **olvidan las fotos borradas del disco**.
- [x] `backend/reanalyze.py` sustituye a `update_metadata.py`: vuelve a analizar las fotos ya indexadas. Conviene ejecutarlo una vez sobre el índice existente para tener hashes según la orientación y el objetivo.

## Fase 3 — Deuda técnica

- [x] Cola de tareas: `cancel_task` cancela de verdad (`POST /api/photos/tasks/{id}/cancel`) y las tareas viejas se limpian solas.
- [x] Endpoints `generate-*` síncronos y asíncronos comparten una única implementación.
- [x] Código muerto eliminado: `utils/cache.py`, `utils/query_optimizer.py`, `update_metadata.py`, `compare_hashes`, modelos Pydantic sin uso, componentes `EXIFPanel`/`LoadingSpinner`, imports sobrantes (ruff y ESLint limpios) y 5 dependencias que no se usaban (aiosqlite, aiofiles, watchdog, exifread, python-multipart).
- [x] Acciones por lotes conectadas: Ctrl+clic en miniaturas + `BatchActionBar` (favorita / descartar / limpiar).
- [x] `get_web_file_details` unificado en `utils/photo_files.py` (la copia de `similar.py` ignoraba `cancellate/`).
- [x] **Alembic**: migración inicial `0001`; `init_db()` marca las BD antiguas creadas con `create_all` y aplica migraciones. Verificado sobre una copia de la BD real (849 fotos, `alembic check` sin diferencias).
- [x] Configuración en `backend/config.py` + `.env` (`.env.example`): host, puerto, BD, CORS (por defecto cualquier puerto de localhost) y FFmpeg. `start.bat` reescrito: puertos correctos, siempre sincroniza dependencias, CRLF/ASCII.
- [x] Frontend: `PhotoViewer` (con zoom/desplazamiento) y `ThumbnailStrip` extraídos de `Gallery`; **toasts** en vez de `alert()`; **ErrorBoundary**; **CRA → Vite 8** (build en <1 s); React Router 7; `npm audit`: 0 vulnerabilidades; ESLint 9 sin avisos (atajos de teclado registrados una vez vía `ref`).
- [x] Dependencias actualizadas y fijadas (FastAPI 0.142, Starlette 1.7, SQLAlchemy 2.1, Pydantic 2.13, Pillow 12.3); `lifespan` en lugar de `on_event`; sin `datetime.utcnow`; **0 avisos de deprecación** en los tests (antes 551).
- [x] Idioma: documentación en **español**; interfaz y código en inglés (se tradujeron los textos en italiano de la galería). Las carpetas `cancellate`/`preferite` se mantienen a propósito (compatibilidad con archivos existentes) y se documentan. `OVERVIEW.md` y `TODO.md` eliminados (obsoletos; el backlog de ideas está abajo).
- [x] Bug de paso: `H` abría la ayuda de atajos **y** volteaba la foto; la ayuda ahora solo se abre con `?` y lista los atajos reales.

### Revisión con agentes (al documentar) — corregido

Al escribir la guía de usuario y la especificación técnica, dos agentes leyeron todo el código y encontraron estos fallos, ya corregidos y con tests:

- [x] **Grave:** rotar un RAW con estructura TIFF (NEF, DNG…) podía sobrescribirlo con un TIFF pequeño. Ahora HEIC y RAW se rechazan siempre.
- [x] TIFF: miniaturas y versiones web en JPEG (los navegadores no muestran TIFF) y originales servidos como JPEG.
- [x] Las versiones web conservan el EXIF del original (FFmpeg lo perdía pese a `-map_metadata`); WebP salía con calidad ínfima (`-q:v` de libwebp es 0–100).
- [x] La home mostraba siempre «0 favorites / 0 deleted»; `has_thumbs` contaba fotos descartadas.
- [x] Undo oculto con el panel de información plegado; el zoom con rueda hacía scroll (listener pasivo); teclas activas con la ayuda abierta; `useBackgroundTask` sondeaba para siempre tras un error.
- [x] Escanear la carpeta padre de otra ya indexada daba 500; la misma carpeta con otras mayúsculas creaba un duplicado.
- [x] Grupos pendientes obsoletos tras escanear o `reanalyze.py`; agrupado no determinista (sin `ORDER BY`).
- [x] Estadísticas de metadatos >100 %, `date_to` excluía el último día, filtros numéricos a 0 ignorados, `GET /tasks?status=` no filtraba, altitud bajo el nivel del mar positiva, ISO en tupla, tarea cancelada marcada como fallida.

### Pendiente detectado en la revisión

- [ ] Vista de papelera: ver y restaurar lo que hay en `cancellate/` (la API ya admite `only_deleted`); quitar un proyecto de la lista.
- [ ] Comparar no usa `POST /similar/group/{id}/select/{photo_id}`, así que no guarda `selected_photo_id`.
- [x] Mapa de fotos y búsqueda por posición (2026-10-04): pantalla **Map** con *clusters* (Leaflet), selección de zona → galería filtrada, «Nearby photos» con radio, búsqueda de lugares (proxy a Nominatim) y filtros `min/max_lat/lon` y `near_lat/near_lon/radius_km` en `/api/photos/list` (función SQL `distance_km`).
- [x] Filtro «solo favoritas» en la galería (botón **Favorites**, `?favorites=1`, combinable con los filtros de posición).
- [x] Fechas de archivo conservadas: versiones web y copias favoritas heredan las del original (también la de creación en Windows) y rotar ya no las cambia (antes las ponía en el día de hoy).
- [ ] Endpoints de metadatos (búsqueda por cámara/fecha, por mes) y cancelación de tareas sin interfaz.
- [ ] Columnas `folders.favorites_count/deleted_count` sin uso (los recuentos se calculan al vuelo): eliminarlas con una migración.
- [ ] Fotos cuyo análisis falla se reintentan en cada análisis: marcarlas para no repetir.
- [ ] Cancelar un análisis permite lanzar otro de la misma carpeta antes de que el primero se detenga.

## Fase 4 — Tests y CI

- [x] pytest del ciclo de archivos (borrar, restaurar, favorito, rotar) comprobando que el original no cambia (hash/píxeles).
- [x] Tests de escaneo y agrupado con imágenes sintéticas (incluye equivalencia del agrupado vectorizado con el original).
- [x] Tests de endpoints con `TestClient` (157 tests; `cd backend && pytest`, dependencias en `requirements-dev.txt`).
- [ ] GitHub Actions: ruff + pytest + build del frontend.

## Fase 5 — Funcionalidades

- [ ] Sugerir la mejor foto de cada grupo (nitidez por varianza del Laplaciano, resolución, tamaño).
- [ ] Detección de fotos borrosas.
- [ ] Vista de línea de tiempo (los endpoints `by-month` ya existen).
- [ ] Papelera con "vaciar definitivamente" y confirmación.

## Ideas a más largo plazo (backlog del antiguo TODO.md)

- Reconocimiento facial y agrupación por persona; reconocimiento de objetos y escenas.
- Puntuación de calidad (enfoque, exposición) y selección automática de "lo mejor de".
- Soporte de vídeo (miniaturas, reproducción, metadatos).
- Sistema de plugins.
- Interfaz: tema claro/oscuro, atajos personalizables, varios idiomas, accesibilidad, uso en tablet/táctil.
- Distribución: empaquetado como aplicación de escritorio (Electron o similar) con instalador.
