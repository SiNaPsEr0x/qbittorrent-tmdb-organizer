# qBittorrent TMDB Organizer

> **Sei stanco di installare Sonarr, Radarr, Plex e mille altre app solo per tenere organizzata la tua libreria?**  
> Vuoi che dopo ogni download da qBittorrent, film e serie si sistemino da soli nelle cartelle giuste — con il titolo ufficiale, pronti per Kodi — senza toccare niente?  
> **Questo progetto fa esattamente questo. Nient'altro.**

Due script Python che si agganciano a qBittorrent e organizzano automaticamente i tuoi download in cartelle **FILM** e **SERIE TV**, usando l'API di [TMDB](https://www.themoviedb.org/) per ottenere i titoli ufficiali in italiano.

---

## 📦 Script disponibili

### ⭐ `tmdb_prepare.py` — Consigliato

Viene eseguito **prima** che il download inizi. Imposta subito la cartella corretta in qBittorrent, quindi il file viene scaricato **direttamente nella destinazione finale** senza spostamenti successivi.

**Vantaggi:**
- Nessuno spostamento file dopo il download
- Nessun recheck aggiuntivo — solo quello nativo di qBittorrent al completamento
- Più veloce ed efficiente, soprattutto per file grandi (4K, UHD)
- Pulizia automatica delle cartelle vuote ad ogni nuovo torrent aggiunto

### `tmdb_organizer.py` — Migrazione/uso manuale

Viene eseguito **dopo** il download. Sposta i file già scaricati nelle cartelle corrette basandosi su TMDB.

**Quando usarlo:**
- Per organizzare torrent **già scaricati** in passato con percorsi errati
- Per una migrazione una-tantum della libreria esistente
- Se vuoi riorganizzare manualmente un gruppo di file

> **In sintesi:** usa `tmdb_prepare.py` per i nuovi download, usa `tmdb_organizer.py` solo se hai già una libreria da riorganizzare.

---

## ✨ Come funziona `tmdb_prepare.py`

```
1. Aggiungi il torrent in qBittorrent selezionando FILM/ o SERIE/
         ↓
2. qBittorrent scatta "Run on torrent added" → lancia tmdb_prepare.py
         ↓
3. Pulizia automatica delle cartelle vuote lasciate da torrent cancellati
         ↓
4. Lo script legge il nome del torrent e cerca su TMDB
         ↓
5. Crea la cartella finale (es. /FILM/Avatar - Fuoco e Cenere (2025)/)
         ↓
6. Imposta il percorso in qBittorrent prima che inizi il download
         ↓
7. qBittorrent scarica direttamente nella cartella giusta
         ↓
8. Recheck nativo di completamento — solo quello, nient'altro
```

### Struttura risultante

```
<FILM_DIR>/
├── Titolo Film (Anno)/
│   └── Titolo.Film.Anno.qualita.mkv
└── Altro Film (Anno)/
    └── Altro.Film.Anno.qualita.mkv

<SERIE_DIR>/
├── Nome Serie TV/
│   ├── Nome.Serie.S01E01.mkv
│   └── Nome.Serie.S01E02.mkv
└── Altra Serie TV/
    ├── Altra.Serie.S02E01.mkv
    └── Altra.Serie.S02E02.mkv
```

Kodi leggerà automaticamente questa struttura e scaricherà locandine, trame e metadati senza configurazione aggiuntiva.

---

## 🗑️ Pulizia automatica cartelle vuote

qBittorrent non ha un evento nativo "on torrent deleted", quindi quando cancelli un torrent con i suoi file, la cartella creata da TMDB rimane vuota sul disco.

`tmdb_prepare.py` risolve questo problema in modo intelligente: **ogni volta che aggiungi un nuovo torrent**, prima di fare qualsiasi altra cosa, scansiona le cartelle `FILM/` e `SERIE/` e rimuove automaticamente tutte le cartelle vuote lasciate da cancellazioni precedenti.

Nessun servizio extra, nessun cron job, nessuna configurazione aggiuntiva. Il semplice atto di aggiungere un nuovo torrent mantiene la libreria pulita. 🧹

---

## 📋 Requisiti

- Python 3.8+
- qBittorrent con Web UI abilitata
- API Key TMDB gratuita → [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
- Pacchetti: `python3-requests`, `python3-urllib3`, `python3-chardet` (installati automaticamente se mancanti)

---

## ⚙️ Configurazione

Apri **entrambi gli script** e modifica la sezione **CONFIGURAZIONE**:

```python
QB_URL     = "http://localhost:8080"          # URL e porta della Web UI qBittorrent
TMDB_TOKEN = "IL_TUO_TMDB_READ_ACCESS_TOKEN"  # Vedi sotto
FILM_DIR   = "/percorso/alla/tua/cartella/FILM"   # Cartella dove salvi i film
SERIE_DIR  = "/percorso/alla/tua/cartella/SERIE"  # Cartella dove salvi le serie
```

### Token TMDB

1. Registrati su [themoviedb.org](https://www.themoviedb.org/signup)
2. Vai in **Impostazioni → API**
3. Copia il **Read Access Token** (quello lungo, non la API key)
4. Incollalo nel file oppure esportalo come variabile d'ambiente (più sicuro):

```bash
export TMDB_TOKEN="eyJ..."
```

---

## ⚡ Integrazione qBittorrent

### ⭐ tmdb_prepare.py — Torrent aggiunto

1. Apri **qBittorrent → Strumenti → Opzioni → Download**
2. Abilita **"Run external program on torrent added"**
3. Inserisci:

```
python3 /percorso/tmdb_prepare.py --hash %I
```

### tmdb_organizer.py — Uso manuale o migrazione

```bash
# Dry run — anteprima senza modifiche
python3 tmdb_organizer.py

# Esecuzione reale su tutti i torrent
python3 tmdb_organizer.py --ok

# Solo un torrent specifico
python3 tmdb_organizer.py --ok --hash XXXXXXXXXX
```

### Riepilogo parametri `tmdb_organizer.py`

| Parametro | Descrizione |
|-----------|-------------|
| *(nessuno)* | Dry run — solo anteprima |
| `--ok` | Esecuzione reale |
| `--hash XXXX` | Solo il torrent con quell'hash |
| `--ok --hash XXXX` | Esecuzione reale su singolo torrent |

---

## 🛡️ Sicurezza

Entrambi gli script ignorano automaticamente tutti i torrent che **non** si trovano in `FILM_DIR` o `SERIE_DIR`. Download di software, giochi, musica o qualsiasi altro contenuto non vengono mai toccati.

---

## 🔄 Fallback

Se TMDB non trova il titolo, gli script usano il **nome pulito del file** come nome cartella invece di crashare.

---

## 📦 Dipendenze automatiche

Allo startup, entrambi gli script verificano che tutti i pacchetti necessari siano installati. Se mancano, li installano automaticamente via `apt`. Se la versione di `requests` è incompatibile con `chardet`, aggiornano automaticamente via `pip`.

---

## 🖥️ Testato su

- Raspberry Pi OS (Debian Bookworm)
- qBittorrent-nox 4.x con Web UI
- Python 3.11

---

## ⚠️ Disclaimer

Questo progetto è nato per passione personale e per uso hobbistico.

qBittorrent è uno strumento legittimo e open source utilizzato per scaricare contenuti distribuiti tramite il protocollo BitTorrent: **film e serie in pubblico dominio, rilasci sotto licenza Creative Commons, distribuzioni Linux, software open source, e qualsiasi altro contenuto per cui si dispone dei diritti necessari al download.**

Questo script è un **semplice organizzatore di file**: non scarica nulla, non indicizza tracker, non facilita alcuna attività illegale. Si limita a rinominare e spostare file già presenti sul proprio disco, consultando TMDB solo per ottenere il titolo ufficiale.

**Chiunque utilizzi questo software è tenuto a farlo esclusivamente con contenuti per cui dispone dei diritti necessari, nel rispetto delle leggi sul diritto d'autore vigenti nel proprio paese.  
L'autore declina ogni responsabilità per utilizzi non conformi alla normativa applicabile.**
