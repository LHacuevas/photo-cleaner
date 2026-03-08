# 📸 Photo Cleaner

**Gestione locale di archivi fotografici enormi - fino a 50.000+ foto**

Sistema completo per organizzare, pulire e ottimizzare archivi fotografici mantenendo tutto locale e non distruttivo.

## ✨ Caratteristiche Principali

- 🚀 **Prestazioni Estreme**: gestisce 50.000+ foto con navigazione fluida
- 🔍 **Rilevamento Foto Simili**: trova automaticamente duplicati e raffiche
- ⭐ **Sistema Preferiti**: marca e organizza le migliori foto
- 🗑️ **Eliminazione Non Distruttiva**: niente viene mai cancellato definitivamente
- 🌐 **Versioni Ottimizzate**: genera automaticamente thumbs e versioni web
- 📊 **Ricerca Metadati**: filtra per data, GPS, camera, ISO, etc.
- 💾 **Completamente Locale**: zero cloud, massima privacy

## 🏗️ Architettura

```
photo-cleaner/
├── backend/          # Python FastAPI + elaborazione immagini
├── frontend/         # React UI
└── docs/            # Documentazione
```

## 📁 Struttura Cartelle Foto

```
cartella_foto/
├── IMG_001.jpg           # Originali (intoccate)
├── IMG_002.jpg
├── IMG_003.jpg
│
├── thumbs/               # Miniature 300px (10-30 KB)
├── web/                  # Versioni web 2048px (500-900 KB)
├── cancellate/           # Foto scartate (reversibile)
└── preferite/            # Foto marcate con stella
```

## 🎮 Comandi Principali

### Navigazione
- `→` / `←` - Foto successiva/precedente
- `Spazio` - Modalità confronto (foto simili)
- `Esc` - Torna alla vista normale

### Azioni
- `F` - Aggiungi ai preferiti ⭐
- `D` - Sposta in cancellate 🗑️
- `1-4` - Seleziona foto migliore (in modalità confronto)
- `S` - Salta gruppo (in modalità confronto)

## 🚀 Quick Start

### 1. Installazione

```bash
# Clona il repository
git clone https://github.com/tuonome/photo-cleaner.git
cd photo-cleaner

# Installa dipendenze backend
cd backend
pip install -r requirements.txt

# Installa dipendenze frontend
cd ../frontend
npm install
```

### 2. Avvio

```bash
# Terminale 1 - Backend
cd backend
python main.py

# Terminale 2 - Frontend
cd frontend
npm start
```

### 3. Utilizzo

1. Apri browser: `http://localhost:3000`
2. Seleziona cartella con le foto
3. Clicca "Genera Miniature"
4. Inizia a pulire!

## 📊 Funzionalità Dettagliate

### Generazione Miniature
- **Thumbs**: 300px lato lungo, 10-30 KB
- **Formato**: JPEG ottimizzato
- **Preserva**: Tutti i metadati EXIF

### Versioni Web (3 modalità)

| Modalità | Dimensione | Qualità | Peso |
|----------|-----------|---------|------|
| Web (consigliata) | 2048px | Alta | 500-900 KB |
| Archivio leggero | 1600px | Media | 300-600 KB |
| Ultra leggero | 1200px | Media-bassa | 150-400 KB |

### Rilevamento Foto Simili
- **Algoritmo**: Perceptual hashing (pHash)
- **Velocità**: Analizza 1000+ foto/minuto
- **Accuratezza**: Trova duplicati e variazioni minime
- **Grouping**: Raggruppa automaticamente le raffiche

### Ricerca e Filtri
- Per data (range, mese, anno)
- Per posizione GPS
- Per camera/modello
- Per parametri (ISO, apertura, tempo)
- Solo preferite
- Solo JPG/RAW

## 💡 Flusso di Lavoro Consigliato

1. **Importa** foto nella cartella
2. **Avvia** Photo Cleaner e seleziona la cartella
3. **Genera** miniature (una volta sola)
4. **Analizza** foto simili automaticamente
5. **Pulisci** raffiche e duplicati (modalità confronto)
6. **Marca** ⭐ le migliori
7. **Genera** versioni web ottimizzate
8. **Risultato**: archivio pulito e organizzato!

## 📈 Risultati Tipici

| Fase | Dimensione |
|------|-----------|
| Archivio originale | 25 GB |
| + Thumbs | +200 MB |
| Archivio web | ~3 GB |
| **Risparmio** | **88% rispetto all'originale** |

## 🛠️ Requisiti di Sistema

- **OS**: Windows 10/11 (compatibile anche macOS/Linux)
- **RAM**: 4 GB minimo, 8 GB consigliato
- **Disco**: Spazio per thumbs (~1% originali) + web (~12% originali)
- **Software**: FFmpeg (incluso nel package)

## 🔒 Privacy

- ✅ Tutto locale, zero cloud
- ✅ Nessun dato inviato online
- ✅ Database SQLite locale
- ✅ Controllo completo sui tuoi dati

## 📝 Licenza

MIT License - Usa liberamente!

## 🤝 Contributi

Contributi benvenuti! Apri una issue o pull request.

## 📧 Supporto

Per domande o problemi, apri una issue su GitHub.

---

**Made with ❤️ for photographers who love local control**
