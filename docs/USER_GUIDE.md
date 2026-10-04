# Photo Cleaner: guía de usuario

Photo Cleaner sirve para revisar y limpiar archivos de fotos grandes guardados en tu ordenador: ver las fotos una a una, marcar favoritas, descartar las que sobran, girarlas y encontrar duplicados. Todo funciona en local, en tu navegador, sin subir nada a internet.

La interfaz está en inglés. En esta guía los textos de botones y mensajes aparecen tal como se ven en pantalla (por ejemplo **Scan Folder**), con su explicación en castellano.

> **Lo más importante:** la aplicación nunca borra una foto de forma definitiva. «Borrar» mueve la foto a la subcarpeta `cancellate/`, de donde se puede recuperar. Vaciar esa carpeta lo haces tú, a mano, cuando quieras.

---

## 1. Requisitos y arranque

### Qué necesitas instalar (una sola vez)

| Programa | Para qué | Cómo |
| --- | --- | --- |
| Python 3.12 | El servidor de la aplicación (backend) | <https://www.python.org/downloads/>, marcando «Add Python to PATH» |
| Node.js 20 o superior | La interfaz web (frontend) | <https://nodejs.org/> |
| FFmpeg | Generar miniaturas y versiones web | `winget install Gyan.FFmpeg` |

La aplicación busca FFmpeg en el PATH, en la carpeta de paquetes de winget y en `C:\Program Files\FFmpeg\bin`. Si lo tienes en otro sitio, copia `backend/.env.example` como `backend/.env` y descomenta esta línea con tu ruta:

```ini
PHOTO_CLEANER_FFMPEG=C:/ffmpeg/bin/ffmpeg.exe
```

### Arrancar

Haz doble clic en **`start.bat`**, en la carpeta principal del proyecto. El script:

1. Crea el entorno de Python `.venv` si no existe.
2. Instala o actualiza las dependencias (la primera vez tarda unos minutos).
3. Abre dos ventanas: **Photo Cleaner Backend** (servidor en <http://localhost:8000>) y **Photo Cleaner Frontend** (interfaz en <http://localhost:3000>).

El navegador se abre solo en <http://localhost:3000>. Si no, ábrelo tú.

Para comprobar que todo va bien, abre <http://localhost:8000/api/health>. Debe responder `"database": "connected"` y `"ffmpeg": "available"`.

Para **cerrar** la aplicación, cierra las dos ventanas de consola (backend y frontend).

---

## 2. Primeros pasos

### Escanear una carpeta

En la pantalla de inicio, en el recuadro **Start New Project**:

1. Escribe la ruta de la carpeta de fotos, por ejemplo `C:\Fotos\Vacaciones2024`.
2. Marca **Include subfolders** si quieres incluir también las fotos de sus subcarpetas (a cualquier profundidad).
3. Pulsa **Scan Folder** (o `Intro`).

El escaneo solo registra los archivos, así que termina enseguida y te lleva a la galería. Un aviso arriba a la derecha resume el resultado: fotos totales (**Photos**), nuevas (**New**) y, si las hay, las que ya no están en el disco (**No longer on disk (removed)**). La fecha, la cámara, la resolución y los datos para detectar duplicados se calculan después, **en segundo plano**, usando todos los núcleos del procesador.

Cada carpeta escaneada aparece en **Recent Projects** en la pantalla de inicio. Haz clic en su tarjeta para volver a abrirla.

### Volver a escanear

Puedes escanear la misma carpeta tantas veces como quieras:

- Las fotos nuevas se añaden.
- Las fotos que ya no existen en el disco (porque las has movido o borrado tú) se olvidan.
- Tus favoritas y descartes se mantienen.

La misma carpeta escrita con otras mayúsculas o con una barra final se reconoce como el mismo proyecto. Si escaneas una carpeta que contiene otra ya escaneada (con **Include subfolders**), las fotos que ya estaban en el proyecto de la subcarpeta se omiten: cada foto pertenece a un solo proyecto.

### Subcarpetas que crea la aplicación

Al escanear, Photo Cleaner crea cuatro subcarpetas dentro de la carpeta de fotos. Sus nombres están en italiano a propósito, para mantener la compatibilidad con archivos ya organizados así:

| Carpeta | Significado | Contenido |
| --- | --- | --- |
| `thumbs/` | miniaturas | Miniaturas de 300 px por el lado largo |
| `web/` | versiones web | Copias reducidas a 2048 px por el lado largo |
| `cancellate/` | **borradas** | Papelera: las fotos descartadas, con sus miniaturas, versiones web y copias de favoritas |
| `preferite/` | **favoritas** | Una **copia** de cada foto marcada como favorita (el original no se mueve) |

Las fotos de subcarpetas conservan su ruta relativa dentro de estas carpetas. Ejemplo:

```text
Vacaciones2024/
├── IMG_001.jpg               # original
├── playa/IMG_050.jpg         # original en una subcarpeta
├── thumbs/
│   ├── IMG_001.jpg
│   └── playa/IMG_050.jpg
├── web/
│   └── IMG_001.jpg
├── preferite/
│   └── playa/IMG_050.jpg     # copia de una favorita
└── cancellate/               # papelera
    ├── IMG_007.jpg           # foto descartada
    ├── thumbs/IMG_007.jpg
    ├── web/IMG_007.jpg
    └── preferite/            # (si la descartada era favorita)
```

Al escanear con **Include subfolders**, cualquier carpeta llamada `thumbs`, `web`, `cancellate` o `preferite` se ignora, esté donde esté. No uses esos nombres para tus propias carpetas de fotos.

---

## 3. La galería

La galería muestra una foto grande, una tira de miniaturas abajo y una barra de botones arriba. Las fotos se ordenan por nombre de archivo (incluida la subcarpeta) y la navegación da la vuelta: después de la última viene la primera.

### Botones de la barra superior

| Botón | Qué hace |
| --- | --- |
| **Back** | Vuelve a la pantalla de inicio |
| **Generate Thumbnails** | Genera las miniaturas que falten (solo aparece mientras a alguna foto le falte la miniatura) |
| **Find Duplicates** | Abre la revisión de duplicados (ver sección 4) |
| Estrella (**Favorite (F)**) | Marca o desmarca la foto como favorita |
| Flecha circular (**Rotate 90 deg (R)**) | Gira la foto 90° en el sentido de las agujas del reloj |
| Espejo (**Flip Horizontal (H)**) | Voltea la foto horizontalmente |
| Monitor (**Generate Web Version**) | Genera las versiones web que falten de toda la carpeta |
| Imagen (**Generate Thumbnails**) | Igual que el botón de texto anterior, siempre visible |
| **Web** / **Original** | Cambia entre la versión web y el original (solo si existe versión web) |
| Papelera (**Delete (D or Del)**) | Descarta la foto (la mueve a `cancellate/`) |

Debajo del nombre de la carpeta, una barra muestra tu posición (`125 / 3400`). Mientras se generan miniaturas o versiones web aparece también el estado de la tarea y su porcentaje (por ejemplo `Task running (45%)`); al terminar, la galería se actualiza sola.

### Ver la foto

- **Rueda del ratón** sobre la foto: zoom (hasta 8×).
- **Arrastrar** con el ratón cuando hay zoom: mover la imagen.
- El zoom se reinicia al cambiar de foto.
- Las flechas laterales grandes, o `←` y `→`, pasan a la foto anterior o siguiente.

Si la foto tiene versión web, la galería muestra **la versión web por defecto**, porque carga mucho más rápido. Pulsa `V` o el botón **Web** / **Original** para ver el original.

### Panel de información

A la izquierda de la foto hay un panel con:

- Nombre del archivo y qué estás viendo (**Showing: Web version** u **Original**).
- **Resolution** (resolución) y **Size** (tamaño en disco) de la versión mostrada.
- **Camera** (modelo de cámara), **Lens** (objetivo) y **Date** (fecha de la toma), si la foto los tiene.
- **Location** (coordenadas GPS) y un mapa de OpenStreetMap, con el enlace **Open map** para abrirlo en una pestaña nueva. Solo aparece si la foto tiene GPS.

El botón **Hide** pliega el panel y **Info** lo vuelve a desplegar.

Si justo después de escanear ves `Resolution: ? x ?` y falta la fecha o la cámara, es que el análisis en segundo plano aún no ha llegado a esa foto. Pasa a otra foto y vuelve en unos segundos.

### Favoritas

Pulsa `F` o la estrella. La foto se marca y se copia a `preferite/`. Si la desmarcas, se borra esa copia (el original no se toca). En la tira de miniaturas, las favoritas llevan una estrella.

### Descartar (borrar) y deshacer

Pulsa `D`, `Supr` o la papelera. La foto se mueve a `cancellate/` junto con su miniatura, su versión web y su copia en `preferite/`, si las tiene. **No se pide confirmación.**

En el panel de información aparece el aviso «*nombre* moved to cancellate.» con el botón **Undo** (deshacer), que devuelve la foto a su sitio. El aviso se ve aunque el panel esté plegado. Solo se puede deshacer **el último** descarte.

Para recuperar una foto descartada antes, consulta [Preguntas frecuentes](#9-preguntas-frecuentes-y-problemas).

### Rotar y voltear

`R` gira 90° a la derecha y `H` voltea en horizontal. Para girar a la izquierda, pulsa `R` tres veces. Estas operaciones **no pierden calidad**:

- **JPEG:** no se tocan los píxeles. Solo se cambia la etiqueta EXIF de orientación; la fecha, el GPS y los datos de la cámara se conservan.
- **PNG, BMP, TIFF, GIF (no animado) y WebP sin pérdida:** se vuelve a guardar el archivo con exactamente los mismos píxeles, conservando el perfil de color y los metadatos.
- **WebP con pérdida, imágenes animadas, TIFF con compresión JPEG, HEIC y RAW:** no se pueden girar. Aparece un mensaje de error y el archivo no se toca.

Si la foto es favorita, su copia en `preferite/` se gira igual. La miniatura y la versión web se regeneran girados.

### Selección múltiple y acciones por lotes

En la tira de miniaturas, **Ctrl+clic** marca o desmarca una foto (aparece «OK» sobre ella). Con al menos una seleccionada, aparece una barra con el número de fotos seleccionadas (por ejemplo `12 of 3400 selected`) y tres botones:

- **Favorite:** marca todas como favoritas.
- **Delete:** las descarta todas. Pide confirmación («Move N photos to cancellate?»).
- **Clear:** quita la selección.

La tira solo dibuja unas 60 miniaturas a cada lado de la foto actual. Para seleccionar fotos lejanas, avanza hasta ellas.

### Avisos

Los mensajes (resultados, errores) aparecen como avisos en la **esquina superior derecha**. Desaparecen solos (los de error duran más) o se cierran con la ✕.

---

## 4. Buscar duplicados

Pulsa **Find Duplicates** en la galería. Photo Cleaner busca fotos casi idénticas: copias exactas, la misma foto a otro tamaño o con otra compresión, y ráfagas muy parecidas. Usa una «huella» visual de cada foto, así que reconoce la misma foto aunque esté guardada con otra orientación.

### Cómo funciona

1. Si el análisis de la carpeta aún no ha terminado, verás **Analyzing photos for similarities...** con un porcentaje. Espera a que termine.
2. Las fotos se agrupan por parecido. Solo se muestran los grupos **sin revisar**.
3. Si no hay ninguno, verás **No Similar Photos Found**.

### Revisar cada grupo

Cada grupo muestra sus fotos en tarjetas numeradas, con nombre, resolución y tamaño. Cada tarjeta tiene su propio botón **Web** / **Original** si existe versión web.

Para seleccionar fotos, haz clic en la tarjeta o en su casilla, o pulsa su número (`1` a `9`). Después elige:

| Botón / tecla | Qué hace |
| --- | --- |
| **Delete Selected (N)** | Descarta las fotos seleccionadas y da el grupo por revisado |
| **Delete Others** | Descarta las **no** seleccionadas (te quedas con las seleccionadas) y da el grupo por revisado |
| **Skip Group (S)** / `S` | Da el grupo por revisado **sin borrar nada** |
| **Previous** / **Next**, `←` / `→` | Cambia de grupo sin marcarlo como revisado |

Ambos botones de borrar piden confirmación y mueven las fotos a `cancellate/`, como en la galería. Aquí no hay **Undo**.

Cuando pasas del último grupo, aparece «All groups reviewed!» y vuelves a la galería.

### Qué conviene saber

- **«Skip» es definitivo:** las fotos de un grupo revisado (por borrado o por **Skip**) no se vuelven a proponer como duplicados. Si quieres dejar un grupo para más tarde, usa **Next** o `→`.
- Los grupos que dejas sin revisar se guardan y se muestran la próxima vez, salvo que entre medias vuelvas a escanear y la carpeta tenga fotos nuevas o eliminadas: en ese caso los grupos pendientes se descartan y se recalculan con todas las fotos actuales. Los grupos ya revisados no se ven afectados.
- Las teclas `1`–`9` solo llegan a las nueve primeras fotos del grupo. Para las demás, haz clic.

---

## 5. Atajos de teclado

Pulsa `?` en cualquier momento para ver la ayuda de atajos (`Esc` la cierra).

| Dónde | Tecla | Acción |
| --- | --- | --- |
| Inicio | `Intro` | Escanear la ruta escrita (**Scan Folder**) |
| Galería | `←` / `→` | Foto anterior / siguiente |
| Galería | `F` | Marcar o desmarcar favorita |
| Galería | `D` o `Supr` | Descartar la foto (sin confirmación) |
| Galería | `R` | Girar 90° a la derecha |
| Galería | `H` | Voltear en horizontal |
| Galería | `V` | Cambiar entre versión web y original |
| Galería | `Ctrl+clic` en una miniatura | Seleccionar o deseleccionar para acciones por lotes |
| Galería | Rueda / arrastrar | Zoom / mover la imagen ampliada |
| Duplicados | `1`–`9` | Seleccionar o deseleccionar la foto con ese número |
| Duplicados | `←` / `→` | Grupo anterior / siguiente |
| Duplicados | `S` | Saltar el grupo (queda como revisado) |
| General | `?` / `Esc` | Abrir / cerrar la ayuda de atajos |

---

## 6. Formatos compatibles

| Formato | Extensiones | Se ve en la galería | Miniaturas y web | Girar / voltear | Duplicados y metadatos |
| --- | --- | --- | --- | --- | --- |
| JPEG | `.jpg`, `.jpeg` | Sí | Sí (FFmpeg) | Sí, sin tocar píxeles | Sí |
| PNG | `.png` | Sí | Sí (FFmpeg) | Sí, sin pérdida | Sí |
| GIF | `.gif` | Sí | Sí (FFmpeg) | Solo no animados | Sí (primer fotograma) |
| BMP | `.bmp` | Sí | Sí (FFmpeg) | Sí, sin pérdida | Sí |
| TIFF | `.tif`, `.tiff` | Sí, como vista previa JPEG | Sí, en JPEG (sin FFmpeg) | Sí, sin pérdida, salvo TIFF con compresión JPEG | Sí |
| WebP | `.webp` | Sí | Sí (FFmpeg) | Solo WebP sin pérdida | Sí |
| HEIC / HEIF | `.heic`, `.heif` | Sí, como vista previa JPEG | Sí, en JPEG (sin FFmpeg) | No | Sí |
| RAW | `.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`, `.orf`, `.rw2`, `.raf` | Sí, con la vista previa JPEG incrustada en el archivo | Sí, en JPEG (sin FFmpeg) | No | Sí (sobre la vista previa) |

Notas:

- **TIFF, HEIC y RAW:** el navegador no sabe mostrarlos, así que la aplicación genera al vuelo una vista previa JPEG de hasta 2048 px. En RAW se usa la vista previa que guarda la cámara dentro del archivo, que puede tener menos resolución que el sensor. Con estos formatos, **Original** también muestra esa vista previa, no el archivo real. Sus miniaturas y versiones web son JPEG, aunque conserven el nombre original (por ejemplo `thumbs/IMG_001.HEIC`).
- **Los demás formatos conservan su formato** en miniaturas y versiones web (un PNG da una miniatura PNG).

---

## 7. Consejos para archivos grandes

- **Primero las miniaturas.** Sin miniaturas, la tira de abajo carga los originales completos, lo que es lento con fotos grandes y muy lento con TIFF, HEIC o RAW. Pulsa **Generate Thumbnails** nada más escanear.
- **Después, las versiones web.** Con originales de muchos megapíxeles, el botón del monitor (**Generate Web Version**) crea copias de 2048 px por el lado largo (nunca se amplía una foto más pequeña). La galería las usa por defecto y la navegación es mucho más fluida. En la interfaz solo existe este tamaño: no hay selector de calidad ni de tamaño.
- **Las tareas se pueden interrumpir.** Si cierras la aplicación a mitad de una generación, al volver a pulsar el botón solo se procesan las que falten. Lo mismo pasa con el análisis: se reanuda al volver a escanear la carpeta o al abrir **Find Duplicates**.
- **Espacio en disco.** Las versiones web y las copias de `preferite/` ocupan espacio extra. Las miniaturas ocupan poco.
- **Metadatos en las versiones web.** Las versiones web en JPEG conservan los datos EXIF del original (fecha, cámara y **ubicación GPS**). Tenlo en cuenta antes de compartirlas.
- **Proyectos por carpeta.** Cada ruta escaneada es un proyecto. Si mueves o renombras la carpeta principal, escanea la nueva ruta: se creará un proyecto nuevo (el antiguo seguirá en la lista).
- **Repetir el análisis tras actualizar la aplicación.** Las versiones nuevas pueden analizar mejor (por ejemplo, la detección de duplicados que tiene en cuenta la orientación o la lectura del objetivo). Para volver a analizar fotos ya indexadas, abre una consola en la carpeta `backend` y ejecuta:

  ```bat
  ..\.venv\Scripts\python.exe reanalyze.py
  REM o solo algunos proyectos, por número:
  ..\.venv\Scripts\python.exe reanalyze.py 3 7
  ```

  El número de proyecto aparece en la dirección de la galería (`/gallery/3`). Es mejor hacerlo con la aplicación cerrada. El script descarta los grupos de duplicados pendientes (no revisados), así que el siguiente **Find Duplicates** reagrupa con los datos nuevos. Los grupos ya revisados no se vuelven a proponer.

---

## 8. Privacidad

- Todo se hace en tu ordenador: las fotos, la base de datos (`backend/photo_cleaner.db`) y las miniaturas no salen de él.
- El servidor solo escucha en `127.0.0.1`, así que solo tu propio ordenador puede conectarse.
- Puedes abrirlo a tu red local con `PHOTO_CLEANER_HOST=0.0.0.0` en `backend/.env`. **Cuidado:** cualquiera en tu red podría ver fotos de tu disco. No lo hagas en redes que no controlas.
- La única conexión a internet es el **mapa** del panel de información: cuando una foto tiene GPS, se cargan los mapas de OpenStreetMap con esas coordenadas.

---

## 9. Preguntas frecuentes y problemas

**¿Cómo vacío la papelera?**
La aplicación no borra nada de forma definitiva. Cuando estés seguro, borra a mano el contenido de `cancellate/` desde el Explorador de Windows y vuelve a escanear la carpeta para que la aplicación olvide esas fotos.

**¿Cómo recupero una foto descartada hace tiempo?**
**Undo** solo sirve para el último descarte de la galería, y la aplicación no tiene una vista de la papelera desde la que restaurar. Para las demás, muévela a mano desde `cancellate/` a su ubicación original (respetando la subcarpeta) y vuelve a escanear. Aparecerá como foto nueva: si era favorita, tendrás que volver a marcarla. Su miniatura y su versión web se quedan en `cancellate/thumbs/` y `cancellate/web/`; puedes moverlas también o generarlas de nuevo.

**He movido, renombrado o borrado fotos con el Explorador.**
Vuelve a escanear la carpeta. Las que ya no existen se olvidan y las nuevas o renombradas se añaden.

**`/api/health` dice `"ffmpeg": "missing"` o no se generan miniaturas.**
FFmpeg no está instalado o no se encuentra. Instálalo (`winget install Gyan.FFmpeg`) o indica su ruta en `PHOTO_CLEANER_FFMPEG` dentro de `backend/.env`, y **reinicia el backend** (cierra su ventana y vuelve a ejecutar `start.bat`). Sin FFmpeg, la galería sigue funcionando con los originales, y las miniaturas de TIFF, HEIC y RAW se generan igualmente.

**Las fotos no tienen fecha, cámara ni resolución, o no aparecen duplicados.**
El análisis se hace en segundo plano después del escaneo y, con decenas de miles de fotos, tarda un rato. Pasa a otra foto y vuelve. Si cerraste la aplicación antes de que terminara, vuelve a escanear la carpeta o abre **Find Duplicates** para que continúe. Las fotos sin datos EXIF (capturas de pantalla, imágenes de WhatsApp...) no tienen fecha ni cámara. Si un archivo está dañado y no se puede analizar, se vuelve a intentar cada vez que se escanea la carpeta o se abre **Find Duplicates**; no afecta al resto, pero esa foto no entrará en la búsqueda de duplicados.

**Las fotos TIFF, HEIC o RAW van lentas.**
Sin miniaturas ni versión web, cada vista previa se genera al vuelo. Genera las miniaturas y las versiones web: a partir de entonces se usan esos JPEG.

**Al girar una foto sale un error.**
El formato no admite giro sin pérdida (WebP con pérdida, GIF animado, HEIC, RAW...). Consulta la tabla de formatos. El archivo no se ha modificado.

**El puerto 8000 o 3000 está ocupado.**

- Puerto 3000 (frontend): Vite usa automáticamente el siguiente puerto libre (3001...) y abre el navegador en él. No tienes que hacer nada.
- Puerto 8000 (backend): pon otro puerto en `backend/.env`, por ejemplo `PHOTO_CLEANER_PORT=8001`. Como la interfaz busca el backend en el 8000, crea también el archivo `frontend/.env` con `VITE_API_URL=http://localhost:8001/api`, y vuelve a arrancar con `start.bat`.

**¿Cómo quito un proyecto de «Recent Projects»?**
Desde la interfaz no se puede. La lista es solo un acceso rápido; no afecta a tus fotos.

**Aparece «Something went wrong» o un error inesperado.**
Pulsa **Reload** (recargar) o **Back to Home** (volver al inicio), o recarga la página con `F5`. Si el problema sigue, mira la ventana **Photo Cleaner Backend**: ahí aparecen los errores del servidor.
