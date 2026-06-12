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
# CONSIGLIATO: abilita "Non avviare automaticamente i download" in qBittorrent
# (Opzioni -> Download -> "Do not start automatically"). Lo script avviera' il
# torrent da solo DOPO aver impostato il percorso, eliminando ogni race.
#
# CONFIGURAZIONE:
#   1. Imposta QB_URL con l'indirizzo della tua Web UI qBittorrent
#      Se la Web UI richiede credenziali: export QB_USER="utente" QB_PASS="password"
#   2. Imposta TMDB_TOKEN con il tuo Read Access Token da themoviedb.org/settings/api
#      oppure esportalo come variabile d'ambiente: export TMDB_TOKEN="eyJ..."
#   3. Imposta FILM_DIR e SERIE_DIR con i percorsi delle tue cartelle
#
# Richiede solo Python 3.8+ - nessun pacchetto esterno.
#
import re, os, urllib.parse, urllib.request, urllib.error, http.cookiejar, json, sys, time

# == CONFIGURAZIONE ==========================================================
QB_URL     = "http://localhost:8080"          # URL Web UI qBittorrent
QB_USER    = os.environ.get("QB_USER", "")    # vuoto se la Web UI non richiede login
QB_PASS    = os.environ.get("QB_PASS", "")
TMDB_TOKEN = os.environ.get("TMDB_TOKEN", "IL_TUO_TMDB_READ_ACCESS_TOKEN")
FILM_DIR   = "/percorso/alla/tua/cartella/FILM"
SERIE_DIR  = "/percorso/alla/tua/cartella/SERIE"
CLEANUP_MIN_AGE = 3600   # secondi: elimina solo cartelle vuote piu' vecchie di 1h
START_AFTER_SET = True   # avvia il torrent dopo setLocation (usa con add-paused)
# ============================================================================

if "--hash" not in sys.argv:
    print("ERRORE Uso: python3 tmdb_prepare.py --hash <hash>")
    sys.exit(1)

if TMDB_TOKEN == "IL_TUO_TMDB_READ_ACCESS_TOKEN":
    print("ERRORE TMDB_TOKEN non configurato.")
    print("   Ottieni il token su: https://www.themoviedb.org/settings/api")
    sys.exit(1)

idx = sys.argv.index("--hash")
if idx + 1 >= len(sys.argv):
    print("ERRORE Uso: python3 tmdb_prepare.py --hash <hash>")
    sys.exit(1)
HASH = sys.argv[idx + 1].lower()

def safe_name(name):
    return re.sub(r'[<>:"/\\|?*]', ' -', name).strip()

def strip_release_group(name):
    # [Group] o (Group) all'inizio del nome; deve contenere almeno una lettera
    # per non mangiare titoli come "(500).Days.of.Summer"
    name = re.sub(r'^\s*[\[\(](?=[^\]\)]*[A-Za-z])[^\]\)]{1,40}[\]\)]\s*[-_. ]*', '', name)
    # blocchi tra parentesi quadre ovunque nel nome (es. [ITA], [x265-Grp])
    name = re.sub(r'\[[^\]]{1,40}\]', ' ', name)
    return name

def clean_title(filename, is_serie):
    name = re.sub(r'\.(mkv|avi|mp4)$', '', filename, flags=re.IGNORECASE)
    name = strip_release_group(name)
    if is_serie:
        m = re.search(r'[Ss]\d+[Ee]\d+', name)
        if m: name = name[:m.start()]
    else:
        # Usa l'ULTIMO anno trovato: gestisce titoli che contengono un anno
        # (es. "Blade.Runner.2049.2017..." -> tronca a "Blade Runner 2049").
        # Lookaround: i delimitatori non vengono consumati, cosi' anni adiacenti
        # (".2049.2017.") vengono trovati entrambi. Il '-' copre "Titolo.2024-GRP".
        years = list(re.finditer(r'(?<=[\. \(])(19|20)\d{2}(?=[\. \)\-]|$)', name))
        if years:
            name = name[:years[-1].start()]
    # tag di qualita': utili anche per le serie senza SxxExx nel nome
    name = re.sub(r'[\. ](2160p|1080p|720p|BluRay|WEB-DL|WEBRip|HDTV|UHDrip|x26[45]|HEVC|REMUX).*',
                  '', name, flags=re.IGNORECASE)
    # suffisso "-GROUP" tipico delle release (es. Titolo.2024-RARBG); solo su
    # nomi scene-style con punti, per non troncare titoli come "Spider-Man"
    if '.' in name:
        name = re.sub(r'-[A-Za-z0-9]{2,20}$', '', name)
    return re.sub(r'\s{2,}', ' ', name.replace('.', ' ')).strip(' -_')

def extract_year(name):
    # Ultimo anno nel nome = anno di uscita (il primo puo' far parte del titolo)
    years = re.findall(r'(?:19|20)\d{2}', name)
    return years[-1] if years else None

def is_within(path, base):
    path, base = os.path.normpath(path), os.path.normpath(base)
    return path == base or path.startswith(base + os.sep)

def search_tmdb(title, year=None, media='movie', retries=2):
    base = f"https://api.themoviedb.org/3/search/{media}"
    params = {'query': title, 'language': 'it-IT'}
    if year: params['year' if media == 'movie' else 'first_air_date_year'] = year
    url = base + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {TMDB_TOKEN}'})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.load(r)
            results = data.get('results', [])
            if results:
                res = results[0]
                name = res.get('title') or res.get('name')
                year_out = (res.get('release_date','') or res.get('first_air_date',''))[:4]
                return name, year_out
            return None, None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"ATTENZIONE Ricerca TMDB fallita ({e}) - uso il nome torrent come fallback")
    return None, None

def cleanup_empty_folders():
    now = time.time()
    for base in [FILM_DIR, SERIE_DIR]:
        if not os.path.isdir(base):
            continue
        for folder in os.listdir(base):
            full = os.path.join(base, folder)
            try:
                if (os.path.isdir(full) and not os.listdir(full)
                        and now - os.path.getmtime(full) > CLEANUP_MIN_AGE):
                    os.rmdir(full)
                    print(f"PULIZIA Cartella vuota rimossa: {folder}")
            except OSError:
                pass  # creata/scritta da un altro processo nel frattempo

# == API qBittorrent (urllib con cookie di sessione) =========================
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def qb_post(path, data, fatal=True):
    req = urllib.request.Request(QB_URL + path,
                                 data=urllib.parse.urlencode(data).encode())
    try:
        with _opener.open(req, timeout=10) as r:
            return r.read().decode()
    except urllib.error.HTTPError:
        if fatal:
            raise
        return None

def qb_get_json(path):
    with _opener.open(QB_URL + path, timeout=10) as r:
        return json.load(r)

def qb_login():
    try:
        body = qb_post("/api/v2/auth/login", {"username": QB_USER, "password": QB_PASS})
    except (urllib.error.URLError, OSError) as e:
        print(f"ERRORE qBittorrent non raggiungibile su {QB_URL}: {e}")
        sys.exit(1)
    if body.strip() != "Ok.":
        print("ERRORE Login Web UI fallito: controlla QB_USER/QB_PASS o le impostazioni della Web UI")
        sys.exit(1)

def qb_pause(h):
    # qBittorrent 5.x usa /stop, 4.x usa /pause: prova entrambi
    if qb_post("/api/v2/torrents/stop", {"hashes": h}, fatal=False) is None:
        qb_post("/api/v2/torrents/pause", {"hashes": h}, fatal=False)

def qb_start(h):
    if qb_post("/api/v2/torrents/start", {"hashes": h}, fatal=False) is None:
        qb_post("/api/v2/torrents/resume", {"hashes": h}, fatal=False)

qb_login()

# Aspetta che qBittorrent registri il torrent appena aggiunto
torrent = None
for attempt in range(10):
    torrents = qb_get_json("/api/v2/torrents/info")
    torrent  = next((t for t in torrents if t.get('hash','').lower() == HASH), None)
    if torrent:
        break
    time.sleep(1)

if not torrent:
    print(f"ERRORE Torrent {HASH} non trovato")
    sys.exit(1)

name      = torrent['name']
save_path = torrent['save_path'].rstrip('/')

is_film  = is_within(save_path, FILM_DIR)
is_serie = is_within(save_path, SERIE_DIR)

if not is_film and not is_serie:
    print(f"SKIP Ignorato (non in FILM/SERIE): {name}")
    sys.exit(0)

# Metti in pausa SUBITO: evita che qBittorrent scriva nel path sbagliato
# mentre interroghiamo TMDB (elimina la race su setLocation)
qb_pause(HASH)

# Cleanup DOPO aver identificato il torrent, con guardia sull'eta' delle cartelle
cleanup_empty_folders()

title_clean = clean_title(name, is_serie)
year        = extract_year(name) if is_film else None
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
try:
    qb_post("/api/v2/torrents/setLocation", {"hashes": HASH, "location": dst_dir})
except (urllib.error.URLError, OSError) as e:
    detail = e.read().decode(errors='replace') if isinstance(e, urllib.error.HTTPError) else str(e)
    print(f"ERRORE setLocation fallito: {detail}")
    qb_start(HASH)  # non lasciare il torrent fermo per sempre
    sys.exit(1)

if START_AFTER_SET:
    qb_start(HASH)

print(f"OK [{source}] {folder_name}")
print(f"   Percorso impostato: {dst_dir}")
