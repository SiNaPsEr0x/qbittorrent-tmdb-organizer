#!/usr/bin/env python3
#
# USO MANUALE:
#   python3 tmdb_organizer.py        → dry run (solo anteprima)
#   python3 tmdb_organizer.py --ok   → esecuzione reale su tutti i torrent
#
# QBITTORRENT - Esecuzione automatica a fine download:
#   Strumenti → Opzioni → Download → "Run external program on torrent finished"
#   Inserire: python3 /percorso/tmdb_organizer.py --ok --hash %I
#   NOTA: --hash %I va inserito SOLO qui, non usarlo manualmente.
#         qBittorrent sostituisce %I con l'hash del torrent appena completato
#         così lo script processa solo quello invece di tutti.
#
# CONFIGURAZIONE:
#   1. Imposta QB_URL con l'indirizzo della tua Web UI qBittorrent
#   2. Imposta TMDB_TOKEN con il tuo Read Access Token da themoviedb.org/settings/api
#      oppure esportalo come variabile d'ambiente: export TMDB_TOKEN="eyJ..."
#   3. Imposta FILM_DIR e SERIE_DIR con i percorsi delle tue cartelle
#
# STRUTTURA RISULTANTE:
#   <FILM_DIR>/Titolo Film (Anno)/file.mkv
#   <SERIE_DIR>/Nome Serie/episodio.mkv
#
import re, os, shutil, urllib.parse, urllib.request, json, sys, subprocess

def check_deps():
    missing = []
    for pkg, apt in [("requests","python3-requests"),("urllib3","python3-urllib3"),("chardet","python3-chardet")]:
        try: __import__(pkg)
        except ImportError: missing.append(apt)
    if missing:
        print(f"📦 Installo: {missing}")
        subprocess.run(["sudo","apt","install","-y"] + missing, check=True)
    try:
        import importlib.metadata as meta
        req_ver     = tuple(int(x) for x in meta.version('requests').split('.')[:2])
        chardet_ver = int(meta.version('chardet').split('.')[0])
        if chardet_ver >= 6 and req_ver < (2, 31):
            print("🔧 Aggiorno requests...")
            subprocess.run([sys.executable, "-m", "pip", "install",
                            "--upgrade", "requests", "--break-system-packages", "-q"], check=True)
            print("✅ Aggiornato — riavvio...\n")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except:
        pass

check_deps()
import requests

# ── CONFIGURAZIONE ────────────────────────────────────────────────────────────
QB_URL     = "http://localhost:8080"          # URL Web UI qBittorrent
TMDB_TOKEN = os.environ.get("TMDB_TOKEN", "IL_TUO_TMDB_READ_ACCESS_TOKEN")
FILM_DIR   = "/percorso/alla/tua/cartella/FILM"   # es. /mnt/Download/FILM
SERIE_DIR  = "/percorso/alla/tua/cartella/SERIE"  # es. /mnt/Download/SERIE
# ─────────────────────────────────────────────────────────────────────────────

DRY_RUN   = "--ok" not in sys.argv
HASH_FILTER = None
if "--hash" in sys.argv:
    idx = sys.argv.index("--hash")
    if idx + 1 < len(sys.argv):
        HASH_FILTER = sys.argv[idx + 1].lower()

if TMDB_TOKEN == "IL_TUO_TMDB_READ_ACCESS_TOKEN":
    print("❌ TMDB_TOKEN non configurato.")
    print("   Ottieni il token su: https://www.themoviedb.org/settings/api")
    print("   Poi impostalo nel file o con: export TMDB_TOKEN=\"eyJ...\"")
    sys.exit(1)

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

def get_files(content):
    if os.path.isfile(content) and content.endswith('.mkv'):
        return [content], os.path.dirname(content)
    if os.path.isdir(content):
        files = [os.path.join(content, f) for f in os.listdir(content) if f.endswith('.mkv')]
        return sorted(files), content
    return [], None

s = requests.Session()
s.post(f"{QB_URL}/api/v2/auth/login", data={"username": "", "password": ""})
torrents = s.get(f"{QB_URL}/api/v2/torrents/info").json()

if HASH_FILTER:
    torrents = [t for t in torrents if t.get('hash','').lower() == HASH_FILTER]
    if not torrents:
        print(f"❌ Nessun torrent trovato con hash {HASH_FILTER}")
        sys.exit(1)

mode  = '[DRY RUN - aggiungi --ok per eseguire]' if DRY_RUN else '[ESECUZIONE REALE]'
scope = f'solo hash {HASH_FILTER}' if HASH_FILTER else 'tutti i torrent'
print(f"{mode} — {scope}\n")

moved = 0
for t in torrents:
    content   = t.get('content_path', '').rstrip('/')
    hash_     = t['hash']
    save_path = t['save_path'].rstrip('/')
    if not content: continue

    is_film  = FILM_DIR  in save_path or FILM_DIR  in content
    is_serie = SERIE_DIR in save_path or SERIE_DIR in content
    if not is_film and not is_serie: continue

    src_files, src_dir = get_files(content)
    if not src_files: continue

    first       = os.path.basename(src_files[0])
    title_clean = clean_title(first, is_serie)
    year_m      = re.search(r'(19|20)\d{2}', first)
    year        = year_m.group() if year_m and not is_serie else None
    media       = 'tv' if is_serie else 'movie'

    tmdb_title, tmdb_year = search_tmdb(title_clean, year, media)

    if tmdb_title:
        folder_name = safe_name(tmdb_title)
        if not is_serie and tmdb_year:
            folder_name = f"{folder_name} ({tmdb_year})"
        source = "TMDB"
    else:
        folder_name = safe_name(title_clean)
        if not is_serie and year:
            folder_name = f"{folder_name} ({year})"
        source = "FALLBACK"

    base_dir = FILM_DIR if is_film else SERIE_DIR
    dst_dir  = os.path.join(base_dir, folder_name)

    if all(os.path.dirname(f) == dst_dir for f in src_files):
        print(f"⏭️  già OK: {folder_name}")
        continue

    print(f"{'🎬' if is_film else '📺'} [{source}] {folder_name}")
    for f in src_files:
        print(f"   DA: {f}")
        print(f"   A:  {dst_dir}/{os.path.basename(f)}")
    print()

    if not DRY_RUN:
        os.makedirs(dst_dir, exist_ok=True)
        for f in src_files:
            shutil.move(f, os.path.join(dst_dir, os.path.basename(f)))
        s.post(f"{QB_URL}/api/v2/torrents/setLocation", data={"hashes": hash_, "location": dst_dir})
        if src_dir and os.path.isdir(src_dir) and not os.listdir(src_dir):
            os.rmdir(src_dir)
    moved += 1

print(f"✅ {moved} torrent {'da spostare' if DRY_RUN else 'spostati'}")
