# 📸 Photo Cleaner

**Organiza y limpia archivos fotográficos enormes (50.000+ fotos) en local, sin perder nada.**

Photo Cleaner indexa una carpeta de fotos, genera miniaturas y versiones web, detecta duplicados y ráfagas, y te deja marcar favoritas o descartar fotos. Todo ocurre en tu equipo y ninguna acción destruye datos: «borrar» mueve la foto a una subcarpeta de la que se puede restaurar.

## Características

- 🚀 **Pensado para archivos grandes:** el escaneo registra los archivos al instante y analiza EXIF y hashes en segundo plano, en paralelo. La galería carga por páginas y el agrupado de similares procesa 50.000 fotos en ~1 s.
- 🔍 **Duplicados y ráfagas:** agrupa por hash perceptual, teniendo en cuenta la orientación de la foto.
- ⭐ **Favoritas:** se copian a `preferite/`.
- 🗑️ **Borrado no destructivo:** el original y sus versiones se mueven a `cancellate/`, y se pueden deshacer.
- 🔄 **Rotar y voltear sin pérdida:** en JPEG solo cambia la etiqueta EXIF de orientación; en PNG, BMP, TIFF, GIF y WebP sin pérdida se conservan los píxeles exactos.
- 🖼️ **Formatos:** JPG, PNG, GIF, BMP, TIFF, WebP, HEIC/HEIF y RAW (CR2, CR3, NEF, ARW, DNG, ORF, RW2, RAF).
- 📊 **Metadatos:** fecha, cámara, objetivo, ajustes de exposición y GPS, con mapa.
- 💾 **100 % local:** el backend solo escucha en `127.0.0.1` por defecto.

## Requisitos

- Windows (el script `start.bat`; el código también funciona en otros sistemas)
- Python 3.12
- Node.js 20 o superior
- FFmpeg, por ejemplo con `winget install Gyan.FFmpeg`

## Inicio rápido

```bat
start.bat
```

El script crea el entorno virtual `.venv`, sincroniza las dependencias y abre:

- Backend: <http://localhost:8000> (documentación de la API en `/docs`)
- Frontend: <http://localhost:3000>

Después, escribe la ruta de una carpeta de fotos, pulsa **Scan Folder** y empieza a revisar. Tienes más detalle en [QUICKSTART.md](QUICKSTART.md) y en la [guía de usuario](docs/USER_GUIDE.md).

## Estructura de una carpeta de fotos

```text
mis_fotos/
├── IMG_001.jpg        # Originales (nunca se modifican sus píxeles)
├── viaje/IMG_050.jpg  # Subcarpetas, si se escanea con «Include subfolders»
├── thumbs/            # Miniaturas, 300 px de lado largo
├── web/               # Versiones web, 2048 px de lado largo (nunca se amplían)
├── cancellate/        # Fotos descartadas, con sus thumbs/web: reversible
└── preferite/         # Copias de las favoritas
```

Los nombres `cancellate` (descartadas) y `preferite` (favoritas) se mantienen en italiano por compatibilidad con los archivos ya organizados.

## Atajos de teclado

| Tecla | Acción |
| --- | --- |
| `←` / `→` | Foto anterior / siguiente |
| `F` | Marcar o desmarcar favorita |
| `D` / `Supr` | Descartar (mover a `cancellate/`) |
| `R` / `H` | Rotar 90° / voltear horizontalmente |
| `V` | Alternar original / versión web |
| `Ctrl+clic` | Seleccionar miniaturas para acciones por lotes |
| `?` | Ayuda de atajos |

En **Comparar**: `1`–`9` seleccionan foto, `←`/`→` cambian de grupo y `S` salta el grupo.

## Arquitectura

```text
photo-cleaner/
├── backend/           # FastAPI + SQLite (SQLAlchemy, Alembic) + Pillow/FFmpeg
│   ├── api/           # Endpoints: folders, photos, similar, metadata
│   ├── utils/         # Procesado de imagen, análisis, tareas en segundo plano
│   ├── migrations/    # Migraciones de la base de datos
│   └── tests/         # pytest
├── frontend/          # React + Vite
└── docs/              # Guía de usuario, desarrollo, especificación técnica y plan
```

## Configuración

Copia `backend/.env.example` como `backend/.env` para cambiar el puerto, la ruta de la base de datos, los orígenes CORS o la ruta de FFmpeg. Las variables de entorno reales tienen prioridad.

## Documentación

- [Inicio rápido](QUICKSTART.md)
- [Guía de usuario](docs/USER_GUIDE.md)
- [Guía de desarrollo](docs/DEVELOPMENT.md)
- [Especificación técnica](docs/TECHNICAL_SPECS.md)
- [Plan de mejoras](docs/IMPROVEMENT_PLAN.md)
