# qBittorrent TMDB Organizer

> 🇮🇹 [Leggi in Italiano](README.it.md)

> **Tired of installing Sonarr, Radarr, Plex and a dozen other apps just to keep your library organized?**  
> Want movies and TV shows to automatically sort themselves into the right folders — with the official title, ready for Kodi — after every qBittorrent download, without touching anything?  
> **This script does exactly that. Nothing else.**

A lightweight Python script that hooks into qBittorrent and automatically organizes your downloads into **MOVIES** and **TV SHOWS** folders, using the [TMDB](https://www.themoviedb.org/) API to fetch official titles.

---

## ✨ What it does

1. Connects to qBittorrent via local API
2. For each torrent in `MOVIES/` or `SERIES/`, cleans the filename by removing encoding tags (2160p, WEB-DL, HEVC, etc.)
3. Searches for the official title on TMDB
4. Creates a folder with the clean name and moves the file
5. Updates qBittorrent with the new path
6. Deletes the old folder if left empty

> **Note:** the script does not perform a manual recheck — qBittorrent already runs its native recheck on download completion; running it again would just be wasted time on large files.

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

## 📋 Requirements

- Python 3.8+
- qBittorrent with Web UI enabled
- Free TMDB API Key → [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
- Packages: `python3-requests`, `python3-urllib3`, `python3-chardet` (auto-installed if missing)

---

## ⚙️ Configuration

Open `tmdb_organizer.py` and edit the **CONFIGURATION** section:

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

## 🚀 Manual usage

### Available commands

```bash
# Shows what it would do without touching anything (RECOMMENDED for first run)
python3 tmdb_organizer.py
```
> Runs a **dry run**: analyzes all torrents and shows where each file would be moved,  
> but doesn't move anything and doesn't modify qBittorrent. Always use this before running for the first time.

---

```bash
# Performs the actual move on all torrents
python3 tmdb_organizer.py --ok
```
> Adds the `--ok` flag to confirm real execution.  
> The script physically moves files, updates paths in qBittorrent, and cleans up empty folders.

---

```bash
# Runs only on a specific torrent by hash
python3 tmdb_organizer.py --ok --hash XXXXXXXXXX
```
> `--hash` followed by the torrent hash limits execution to that single torrent.  
> Useful to manually reprocess a specific torrent without touching the others.

---

### Parameters summary

| Parameter | Description |
|-----------|-------------|
| *(none)* | Dry run — preview only, no changes |
| `--ok` | Real execution |
| `--hash XXXX` | Process only the torrent with that hash |
| `--ok --hash XXXX` | Real execution on a single torrent |

---

## ⚡ qBittorrent Integration (automatic on download completion)

This is the most useful part: the script runs automatically every time qBittorrent completes a download, **without you having to do anything**.

### Where to configure it

1. Open **qBittorrent**
2. Go to **Tools → Options** (or `Alt+O`)
3. Click the **Downloads** tab
4. Scroll down to the **"Run external program"** section
5. Check **"Run external program on torrent finished"**
6. In the **Command** field, enter:

```
python3 /full/path/to/tmdb_organizer.py --ok --hash %I
```

> Replace `/full/path/to/` with the actual path where you saved the script,  
> e.g. `/home/user/tmdb_organizer.py` or `/mnt/Download/tmdb_organizer.py`

7. Click **OK** to save

### Visual overview

```
Tools → Options → Downloads
┌──────────────────────────────────────────────────────────────────────┐
│ Run external program                                                 │
│ [✓] Run external program on torrent finished                         │
│ Command: python3 /path/to/tmdb_organizer.py --ok --hash %I           │
└──────────────────────────────────────────────────────────────────────┘
```

### Why `--hash %I`?

`%I` is a special qBittorrent parameter that gets automatically replaced with the **unique hash** of the just-completed torrent. Passing it to the script with `--hash` processes only that torrent instead of rescanning the entire library — faster and more precise.

> **Do not use `--hash %I` when launching the script manually** — `%I` is a qBittorrent placeholder, not a real value.

---

## 🛡️ Safety

The script automatically ignores all torrents that are **not** located in `MOVIES_DIR` or `SERIES_DIR`. Software downloads, games, music or any other content are never touched.

---

## 🔄 Fallback

If TMDB can't find the title, the script uses the **cleaned filename** as the folder name instead of crashing.

---

## 📦 Automatic dependencies

On startup, the script checks that all required packages are installed. If any are missing, they are automatically installed via `apt`. If the version of `requests` is incompatible with `chardet`, it automatically updates via `pip`.

---

## 🖥️ Tested on

- Raspberry Pi OS (Debian Bookworm)
- qBittorrent-nox 4.x with Web UI
- Python 3.11

---

## ⚠️ Disclaimer

This project was born out of personal passion and for hobbyist use.

qBittorrent is a legitimate open-source tool used to download content distributed via the BitTorrent protocol: **public domain movies and shows, Creative Commons licensed releases, Linux distributions, open-source software, and any other content you have the rights to download.**

This script is a **simple file organizer**: it doesn't download anything, doesn't index trackers, and doesn't facilitate any illegal activity. It only renames and moves files already present on your disk, consulting TMDB solely to retrieve the official title.

**Anyone using this software must do so exclusively with content they have the rights to, in compliance with copyright laws in force in their country.  
The author disclaims all liability for uses that do not comply with applicable law.**
