# qBittorrent TMDB Organizer

> 🇮🇹 [Leggi in Italiano](README.it.md)

> **Tired of installing Sonarr, Radarr, Plex and a dozen other apps just to keep your library organized?**  
> Want movies and TV shows to automatically sort themselves into the right folders — with the official title, ready for Kodi — after every qBittorrent download, without touching anything?  
> **This project does exactly that. Nothing else.**

Two Python scripts that hook into qBittorrent and automatically organize your downloads into **MOVIES** and **TV SHOWS** folders, using the [TMDB](https://www.themoviedb.org/) API to fetch official titles.

---

## 📦 Available scripts

### ⭐ `tmdb_prepare.py` — Recommended

Runs **before** the download starts. Sets the correct folder in qBittorrent immediately, so the file is downloaded **directly to its final destination** with no subsequent moves.

**Advantages:**
- No file move after download
- No extra recheck — only qBittorrent's native one on completion
- Faster and more efficient, especially for large files (4K, UHD)
- Automatic cleanup of empty folders on every new torrent added

### `tmdb_organizer.py` — Migration / manual use

Runs **after** the download. Moves already-downloaded files into the correct folders based on TMDB.

**When to use it:**
- To organize torrents **already downloaded** in the past with wrong paths
- For a one-time migration of an existing library
- If you want to manually reorganize a batch of files

> **In short:** use `tmdb_prepare.py` for new downloads, use `tmdb_organizer.py` only if you have an existing library to reorganize.

---

## ✨ How `tmdb_prepare.py` works

```
1. Add torrent in qBittorrent selecting MOVIES/ or SERIES/
         ↓
2. qBittorrent fires "Run on torrent added" → launches tmdb_prepare.py
         ↓
3. Automatic cleanup of empty folders left by deleted torrents
         ↓
4. Script reads the torrent name and searches TMDB
         ↓
5. Creates the final folder (e.g. /MOVIES/Avatar - Fire and Ash (2025)/)
         ↓
6. Sets the path in qBittorrent before the download starts
         ↓
7. qBittorrent downloads directly into the correct folder
         ↓
8. Native completion recheck — just that, nothing else
```

### Resulting structure

```
<MOVIES_DIR>/
├── Movie Title (Year)/
│   └── Movie.Title.Year.quality.mkv
└── Another Movie (Year)/
    └── Another.Movie.Year.quality.mkv

<SERIES_DIR>/
├── Series Name/
│   ├── Series.Name.S01E01.mkv
│   └── Series.Name.S01E02.mkv
└── Another Series/
    ├── Another.Series.S02E01.mkv
    └── Another.Series.S02E02.mkv
```

Kodi will automatically read this structure and download posters, plots and metadata without any extra configuration.

---

## 🗑️ Automatic empty-folder cleanup

qBittorrent has no native "on torrent deleted" event, so when you delete a torrent with its files, the folder created by TMDB remains empty on disk.

`tmdb_prepare.py` solves this intelligently: **every time you add a new torrent**, before doing anything else, it scans the `MOVIES/` and `SERIES/` folders and automatically removes all empty folders left by previous deletions.

No extra service, no cron job, no additional configuration. The simple act of adding a new torrent keeps the library clean. 🧹

---

## 📋 Requirements

- Python 3.8+
- qBittorrent with Web UI enabled
- Free TMDB API Key → [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
- Packages: `python3-requests`, `python3-urllib3`, `python3-chardet` (auto-installed if missing)

---

## ⚙️ Configuration

Open **both scripts** and edit the **CONFIGURATION** section:

```python
QB_URL     = "http://localhost:8080"           # qBittorrent Web UI URL and port
TMDB_TOKEN = "YOUR_TMDB_READ_ACCESS_TOKEN"     # See below
MOVIES_DIR = "/path/to/your/MOVIES/folder"     # Folder where you save movies
SERIES_DIR = "/path/to/your/SERIES/folder"     # Folder where you save TV shows
```

### TMDB Token

1. Register at [themoviedb.org](https://www.themoviedb.org/signup)
2. Go to **Settings → API**
3. Copy the **Read Access Token** (the long one, not the API key)
4. Paste it into the file or export it as an environment variable (more secure):

```bash
export TMDB_TOKEN="eyJ..."
```

---

## ⚡ qBittorrent Integration

### ⭐ tmdb_prepare.py — Torrent added

1. Open **qBittorrent → Tools → Options → Downloads**
2. Enable **"Run external program on torrent added"**
3. Enter:

```
python3 /path/to/tmdb_prepare.py --hash %I
```

### tmdb_organizer.py — Manual use or migration

```bash
# Dry run — preview with no changes
python3 tmdb_organizer.py

# Real execution on all torrents
python3 tmdb_organizer.py --ok

# Single specific torrent
python3 tmdb_organizer.py --ok --hash XXXXXXXXXX
```

### Parameters summary — `tmdb_organizer.py`

| Parameter | Description |
|-----------|-------------|
| *(none)* | Dry run — preview only |
| `--ok` | Real execution |
| `--hash XXXX` | Only the torrent with that hash |
| `--ok --hash XXXX` | Real execution on a single torrent |

---

## 🛡️ Safety

Both scripts automatically ignore all torrents that are **not** located in `MOVIES_DIR` or `SERIES_DIR`. Software downloads, games, music or any other content are never touched.

---

## 🔄 Fallback

If TMDB can't find the title, the scripts use the **cleaned filename** as the folder name instead of crashing.

---

## 📦 Automatic dependencies

On startup, both scripts check that all required packages are installed. If any are missing, they are automatically installed via `apt`. If the version of `requests` is incompatible with `chardet`, it automatically updates via `pip`.

---

## 🖥️ Tested on

- Raspberry Pi OS (Debian Bookworm)
- qBittorrent-nox 4.x with Web UI
- Python 3.11

---

## ⚠️ Disclaimer

This project was born out of personal passion and for hobbyist use.

qBittorrent is a legitimate open-source tool used to download content distributed via the BitTorrent protocol: **public domain movies and shows, Creative Commons licensed releases, Linux distributions, open-source software, and any other content you have the rights to download.**

These scripts are a **simple file organizer**: they don't download anything, don't index trackers, and don't facilitate any illegal activity. They only rename and move files already present on your disk, consulting TMDB solely to retrieve the official title.

**Anyone using this software must do so exclusively with content they have the rights to, in compliance with copyright laws in force in their country.  
The author disclaims all liability for uses that do not comply with applicable law.**
