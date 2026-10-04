# 🚀 Inicio rápido

## 1. Requisitos (una sola vez)

1. **Python 3.12:** <https://www.python.org/downloads/> (marca «Add Python to PATH»)
2. **Node.js 20 o superior:** <https://nodejs.org/>
3. **FFmpeg:**

   ```bat
   winget install Gyan.FFmpeg
   ```

   El backend lo encuentra solo, ya esté en el PATH o instalado con winget o en Program Files. Si lo tienes en otra ruta, indícala en `backend/.env` con `PHOTO_CLEANER_FFMPEG=...`.

## 2. Arrancar

Doble clic en **`start.bat`** (o ejecútalo desde una consola en la raíz del proyecto).

La primera vez tarda unos minutos porque instala las dependencias. Se abren dos ventanas, backend y frontend, y el navegador en <http://localhost:3000>.

Para comprobar que todo está bien, abre <http://localhost:8000/api/health>. Debe responder `"database": "connected"` y `"ffmpeg": "available"`.

## 3. Primer uso

1. Escribe la ruta de una carpeta de fotos, por ejemplo `C:\Fotos\Vacaciones2024`.
2. Marca **Include subfolders** si quieres incluir sus subcarpetas.
3. Pulsa **Scan Folder**. Las fotos aparecen enseguida; la fecha, la cámara y la detección de duplicados se calculan en segundo plano.
4. En la galería, pulsa **Generate Thumbnails**. Con archivos grandes, conviene generar también las versiones web (botón del monitor) para navegar con fluidez.
5. Revisa con el teclado: `→` siguiente, `F` favorita, `D` descartar, `R` rotar. Pulsa `?` para ver todos los atajos.
6. Pulsa **Find Duplicates** para revisar duplicados y ráfagas grupo a grupo.

Nada se borra de verdad: lo descartado está en la subcarpeta `cancellate/` y se puede restaurar.

## Arranque manual (sin `start.bat`)

```bat
REM Backend
cd backend
..\.venv\Scripts\python.exe main.py

REM Frontend (en otra consola)
cd frontend
npm install
npm start
```

## Problemas frecuentes

| Problema | Solución |
| --- | --- |
| `/api/health` dice `"ffmpeg": "missing"` | Instala FFmpeg o configura `PHOTO_CLEANER_FFMPEG` en `backend/.env` |
| No aparecen fechas ni cámara tras escanear | El análisis sigue en segundo plano; vuelve a abrir la foto en unos segundos |
| Puerto 8000 ocupado | Cambia `PHOTO_CLEANER_PORT` en `backend/.env` **y** crea `frontend/.env.local` con `VITE_API_URL=http://localhost:<puerto>/api` para que el frontend lo encuentre |
| Puerto 3000 ocupado | Vite elige automáticamente otro puerto libre; mira la ventana del frontend |
| Has borrado fotos a mano en el explorador | Vuelve a escanear la carpeta: las fotos que ya no existen desaparecen del índice |

Más detalle en la [guía de usuario](docs/USER_GUIDE.md).
