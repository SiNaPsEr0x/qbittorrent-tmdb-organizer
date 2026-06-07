# qBittorrent TMDB Organizer

> 🇬🇧 [Read in English](README.md)

> **Sei stanco di installare Sonarr, Radarr, Plex e mille altre app solo per tenere organizzata la tua libreria?**  
> Vuoi che dopo ogni download da qBittorrent, film e serie si sistemino da soli nelle cartelle giuste — con il titolo ufficiale, pronti per Kodi — senza toccare niente?  
> **Questo script fa esattamente questo. Nient'altro.**

Uno script Python leggero che si aggancia a qBittorrent e organizza automaticamente i tuoi download in cartelle **FILM** e **SERIE TV**, usando l'API di [TMDB](https://www.themoviedb.org/) per ottenere i titoli ufficiali in italiano.

---

## ✨ Cosa fa

1. Si connette a qBittorrent via API locale
2. Per ogni torrent in `FILM/` o `SERIE/`, pulisce il nome del file rimuovendo sigle di encoding (2160p, WEB-DL, HEVC, ecc.)
3. Cerca il titolo ufficiale su TMDB in italiano
4. Crea la cartella con il nome pulito e sposta il file
5. Aggiorna qBittorrent con il nuovo percorso
6. Elimina la vecchia cartella se rimasta vuota

> **Nota:** lo script non esegue il recheck manuale — qBittorrent esegue già il suo recheck nativo al completamento del download, eseguirlo di nuovo sarebbe solo tempo perso su file grandi.

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

## 📋 Requisiti

- Python 3.8+
- qBittorrent con Web UI abilitata
- API Key TMDB gratuita → [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
- Pacchetti: `python3-requests`, `python3-urllib3`, `python3-chardet` (installati automaticamente se mancanti)

---

## ⚙️ Configurazione

Apri `tmdb_organizer.py` e modifica la sezione **CONFIGURAZIONE**:

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

## 🚀 Uso manuale

### Comandi disponibili

```bash
# Mostra cosa farebbe senza toccare niente (CONSIGLIATO la prima volta)
python3 tmdb_organizer.py
```
> Esegue un **dry run**: analizza tutti i torrent e mostra dove sposterebbe ogni file,  
> ma non sposta nulla e non modifica qBittorrent. Usalo sempre prima di eseguire per la prima volta.

---

```bash
# Esegue lo spostamento reale su tutti i torrent
python3 tmdb_organizer.py --ok
```
> Aggiunge il flag `--ok` per confermare l'esecuzione reale.  
> Lo script sposta fisicamente i file, aggiorna i percorsi in qBittorrent e pulisce le cartelle vuote.

---

```bash
# Esegue solo su un torrent specifico tramite hash
python3 tmdb_organizer.py --ok --hash XXXXXXXXXX
```
> `--hash` seguito dall'hash del torrent limita l'esecuzione a quel singolo torrent.  
> Utile se vuoi riprocessare manualmente un torrent specifico senza toccare gli altri.

---

### Riepilogo parametri

| Parametro | Descrizione |
|-----------|-------------|
| *(nessuno)* | Dry run — solo anteprima, nessuna modifica |
| `--ok` | Esecuzione reale |
| `--hash XXXX` | Processa solo il torrent con quell'hash |
| `--ok --hash XXXX` | Esecuzione reale su un singolo torrent |

---

## ⚡ Integrazione qBittorrent (automatico a fine download)

Questa è la parte più utile: lo script si esegue da solo ogni volta che qBittorrent completa un download, **senza che tu debba fare niente**.

### Dove si configura

1. Apri **qBittorrent**
2. Vai in **Strumenti → Opzioni** (o `Alt+O`)
3. Clicca sulla scheda **Download**
4. Scorri in basso fino alla sezione **"Run external program"**
5. Metti la spunta su **"Run external program on torrent finished"**
6. Nel campo **Command** inserisci:

```
python3 /percorso/completo/tmdb_organizer.py --ok --hash %I
```

> Sostituisci `/percorso/completo/` con il percorso reale dove hai salvato lo script,  
> ad esempio `/home/utente/tmdb_organizer.py` o `/mnt/Download/tmdb_organizer.py`

7. Clicca **OK** per salvare

### Schema visivo

```
Strumenti → Opzioni → Download
┌──────────────────────────────────────────────────────────────────────┐
│ Run external program                                                 │
│ [✓] Run external program on torrent finished                         │
│ Command: python3 /percorso/tmdb_organizer.py --ok --hash %I          │
└──────────────────────────────────────────────────────────────────────┘
```

### Perché `--hash %I`?

`%I` è un parametro speciale di qBittorrent che viene sostituito automaticamente con l'**hash univoco** del torrent appena completato. Passandolo allo script con `--hash`, si processa solo quel torrent invece di riscansionare tutta la libreria — più veloce e preciso.

> **Non usare `--hash %I` quando lanci lo script manualmente** — `%I` è un placeholder di qBittorrent, non un valore reale.

---

## 🛡️ Sicurezza

Lo script ignora automaticamente tutti i torrent che **non** si trovano in `FILM_DIR` o `SERIE_DIR`. Download di software, giochi, musica o qualsiasi altro contenuto non vengono mai toccati.

---

## 🔄 Fallback

Se TMDB non trova il titolo, lo script usa il **nome pulito del file** come nome cartella invece di crashare.

---

## 📦 Dipendenze automatiche

Allo startup, lo script verifica che tutti i pacchetti necessari siano installati. Se mancano, li installa automaticamente via `apt`. Se la versione di `requests` è incompatibile con `chardet`, aggiorna automaticamente via `pip`.

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
