#!/usr/bin/env python3
#
# SCRIPT DI PREPARAZIONE - Eseguito PRIMA del download
#
# Imposta il percorso corretto basato su TMDB prima che qBittorrent
# inizi a scaricare, evitando spostamenti e recheck aggiuntivi.
# Pulisce automaticamente le cartelle vuote lasciate da torrent cancellati.
#
# QBITTORRENT - "Run external program on torrent added":
#   python3 /percorso/tmdb_prepare.py --hash %I
#
# CONFIGURAZIONE:
#   1. Imposta QB_URL con l'indirizzo della tua Web UI qBittorrent
#   2. Imposta TMDB_TOKEN con il tuo Read Access Token da themoviedb.org/settings/api
#      oppure esportalo come variabile d'ambiente: export TMDB_TOKEN="eyJ..."
#   3. Imposta FILM_DIR e SERIE_DIR con i percorsi delle tue cartelle
#
import re, os, urllib.parse, urllib.request, json, sys, subprocess, time

def check_deps():
    missing = []
    for pkg, apt in [("requests","python3-requests"),("urllib3","python3-urllib3"),("chardet","python3-chardet")]:
        try: __import__(pkg)
        except ImportError: missing.append(apt)
    if missing:
        subprocess.run(["sudo","apt","install","-y"] + missing, check=True)
    try:
        import importlib.metadata as meta
        req_ver     = tuple(int(x) for x in meta.version('requests').split('.')[:2])
        chardet_ver = int(meta.version('chardet').split('.')[0])
        if chardet_ver >= 6 and req_ver < (2, 31):
            subprocess.run([sys.executable, "-m", "pip", "install",
                            "--upgrade", "requests", "--break-system-packages", "-q"], check=True)
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except:
        pass

check_deps()
import requests

# ── CONFIGURAZIONE ────────────────────────────────────────────────────────────
QB_URL     = "http://localhost:8080"
TMDB_TOKEN = os.environ.get("TMDB_TOKEN", "IL_TUO_TMDB_READ_ACCESS_TOKEN")
FILM_DIR   = "/percorso/alla/tua/cartella/FILM"
SERIE_DIR  = "/percorso/alla/tua/cartella/SERIE"
# ─────────────────────────────────────────────────────────────────────────────

if "--hash" not in sys.argv:
    print("❌ Uso: python3 tmdb_prepare.py --hash <hash>")
    sys.exit(1)

if TMDB_TOKEN == "IL_TUO_TMDB_READ_ACCESS_TOKEN":
    print("❌ TMDB_TOKEN non configurato.")
    print("   Ottieni il token su: https://www.themoviedb.org/settings/api")
    sys.exit(1)

idx  = sys.argv.index("--hash")
HASH = sys.argv[idx + 1].lower()

def safe_name(name):
    return re.sub(r'[<>:"/\\|?*]', ' -', name).strip()

def clean_title(filename, is_serie):
    name = re.sub(r'\.(mkv|avi|mp4)$', '', filename, flags=re.IGNORECASE)
    if is_serie:
        m = re.search(r'[Ss]\d+[Ee]\d+', name)
        if m: name = name[:m.start()]
    else:
        m = re.search(r'[\. ](19|20)\d{2}[\. ]', name)
        if m: name = name[:m.start()]
        name = re.sub(r'[\. ](2160p|1080p|720p|BluRay|WEB-DL|HDTV|UHDrip).*', '', name, flags=re.IGNORECASE)
    return name.replace('.', ' ').strip(' -_')

def search_tmdb(title, year=None, media='movie'):
    base = f"https://api.themoviedb.org/3/search/{media}"
    params = {'query': title, 'language': 'it-IT'}
    if year: params['year' if media == 'movie' else 'first_air_date_year'] = year
    url = base + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {TMDB_TOKEN}'})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.load(r)
        results = data.get('results', [])
        if results:
            res = results[0]
            name = res.get('title') or res.get('name')
            year_out = (res.get('release_date','') or res.get('first_air_date',''))[:4]
            return name, year_out
    except:
        pass
    return None, None

def cleanup_empty_folders():
    for base in [FILM_DIR, SERIE_DIR]:
        if not os.path.isdir(base):
            continue
        for folder in os.listdir(base):
            full = os.path.join(base, folder)
            if os.path.isdir(full) and not os.listdir(full):
                os.rmdir(full)
                print(f"🗑️  Cartella vuota rimossa: {folder}")

# Pulizia cartelle vuote lasciate da torrent cancellati
cleanup_empty_folders()

# Aspetta che qBittorrent registri il torrent
time.sleep(3)

s = requests.Session()
s.post(f"{QB_URL}/api/v2/auth/login", data={"username": "", "password": ""})

torrents = s.get(f"{QB_URL}/api/v2/torrents/info").json()
torrent  = next((t for t in torrents if t.get('hash','').lower() == HASH), None)

if not torrent:
    print(f"❌ Torrent {HASH} non trovato")
    sys.exit(1)

name      = torrent['name']
save_path = torrent['save_path'].rstrip('/')

is_film  = FILM_DIR  in save_path
is_serie = SERIE_DIR in save_path

if not is_film and not is_serie:
    print(f"⏭️  Ignorato (non in FILM/SERIE): {name}")
    sys.exit(0)

title_clean = clean_title(name, is_serie)
year_m      = re.search(r'(19|20)\d{2}', name)
year        = year_m.group() if year_m and is_film else None
media       = 'tv' if is_serie else 'movie'

tmdb_title, tmdb_year = search_tmdb(title_clean, year, media)

if tmdb_title:
    folder_name = safe_name(tmdb_title)
    if is_film and tmdb_year:
        folder_name = f"{folder_name} ({tmdb_year})"
    source = "TMDB"
else:
    folder_name = safe_name(title_clean)
    if is_film and year:
        folder_name = f"{folder_name} ({year})"
    source = "FALLBACK"

base_dir = FILM_DIR if is_film else SERIE_DIR
dst_dir  = os.path.join(base_dir, folder_name)

os.makedirs(dst_dir, exist_ok=True)
r = s.post(f"{QB_URL}/api/v2/torrents/setLocation",
           data={"hashes": HASH, "location": dst_dir})

if r.status_code == 200:
    print(f"✅ [{source}] {folder_name}")
    print(f"   Percorso impostato: {dst_dir}")
else:
    print(f"❌ setLocation fallito: {r.text}")
