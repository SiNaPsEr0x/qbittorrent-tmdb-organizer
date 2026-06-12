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
#      Se la Web UI richiede credenziali: export QB_USER="utente" QB_PASS="password"
#   2. Imposta TMDB_TOKEN con il tuo "API Read Access Token" da
#      themoviedb.org/settings/api: e' quello LUNGO che inizia con "eyJ".
#      NON usare la "API Key" corta (32 caratteri): non funziona.
#      In alternativa esportalo come variabile d'ambiente: export TMDB_TOKEN="eyJ..."
#   3. Imposta FILM_DIR e SERIE_DIR con i percorsi delle tue cartelle
#
# STRUTTURA RISULTANTE:
#   <FILM_DIR>/Titolo Film (Anno)/file.mkv
#   <SERIE_DIR>/Nome Serie/episodio.mkv
#
# Richiede solo Python 3.8+ — nessun pacchetto esterno.
#
import re, os, shutil, urllib.parse, urllib.request, urllib.error, http.cookiejar, json, sys, time

# ── CONFIGURAZIONE ────────────────────────────────────────────────────────────
QB_URL     = "http://localhost:8080"          # URL Web UI qBittorrent
QB_USER    = os.environ.get("QB_USER", "")    # vuoto se la Web UI non richiede login
QB_PASS    = os.environ.get("QB_PASS", "")
TMDB_TOKEN = os.environ.get("TMDB_TOKEN", "IL_TUO_TMDB_READ_ACCESS_TOKEN")
FILM_DIR   = "/percorso/alla/tua/cartella/FILM"   # es. /mnt/Download/FILM
SERIE_DIR  = "/percorso/alla/tua/cartella/SERIE"  # es. /mnt/Download/SERIE
# ─────────────────────────────────────────────────────────────────────────────

VIDEO_EXTS = ('.mkv', '.mp4', '.avi')

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

if re.fullmatch(r'[0-9a-fA-F]{32}', TMDB_TOKEN):
    print("❌ TMDB_TOKEN e' una 'API Key' (v3): TMDB risponderebbe 401 a ogni ricerca.")
    print("   Serve l'API Read Access Token (quello LUNGO che inizia con 'eyJ').")
    print("   Lo trovi su: https://www.themoviedb.org/settings/api → 'API Read Access Token'")
    sys.exit(1)

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
        years = list(re.finditer(r'(?<=[\. \(])(19|20)\d{2}(?=[\. \)\-]|$)', name))
        if years:
            name = name[:years[-1].start()]
    # tag di qualita': utili anche per le serie senza SxxExx nel nome
    name = re.sub(r'[\. ](2160p|1080p|720p|BluRay|WEB-DL|WEBRip|HDTV|UHDrip|x26[45]|HEVC|REMUX).*',
                  '', name, flags=re.IGNORECASE)
    # residui a fine nome dopo il troncamento (es. "Nuremberg.(" da "Nuremberg.(2025)")
    name = re.sub(r'[\s.\-_\(\[]+$', '', name)
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
            print(f"⚠️  Ricerca TMDB fallita ({e}) — uso il nome file come fallback")
    return None, None

def get_files(content):
    if os.path.isfile(content) and content.lower().endswith(VIDEO_EXTS):
        return [content], os.path.dirname(content)
    if os.path.isdir(content):
        files = [os.path.join(content, f) for f in os.listdir(content)
                 if f.lower().endswith(VIDEO_EXTS)]
        return sorted(files), content
    return [], None

# ── API qBittorrent (urllib con cookie di sessione) ──────────────────────────
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def qb_post(path, data):
    req = urllib.request.Request(QB_URL + path,
                                 data=urllib.parse.urlencode(data).encode())
    with _opener.open(req, timeout=10) as r:
        return r.read().decode()

def qb_get_json(path):
    with _opener.open(QB_URL + path, timeout=10) as r:
        return json.load(r)

def qb_login():
    try:
        body = qb_post("/api/v2/auth/login", {"username": QB_USER, "password": QB_PASS})
    except (urllib.error.URLError, OSError) as e:
        print(f"❌ qBittorrent non raggiungibile su {QB_URL}: {e}")
        sys.exit(1)
    if body.strip() != "Ok.":
        print("❌ Login Web UI fallito: controlla QB_USER/QB_PASS o le impostazioni della Web UI")
        sys.exit(1)

qb_login()
torrents = qb_get_json("/api/v2/torrents/info")

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

    is_film  = is_within(save_path, FILM_DIR)  or is_within(content, FILM_DIR)
    is_serie = is_within(save_path, SERIE_DIR) or is_within(content, SERIE_DIR)
    if not is_film and not is_serie: continue

    src_files, src_dir = get_files(content)
    if not src_files: continue

    first       = os.path.basename(src_files[0])
    title_clean = clean_title(first, is_serie)
    year        = extract_year(first) if not is_serie else None
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
            dst = os.path.join(dst_dir, os.path.basename(f))
            if os.path.exists(dst):
                print(f"⚠️  Esiste già, salto: {dst}")
                continue
            shutil.move(f, dst)
        qb_post("/api/v2/torrents/setLocation", {"hashes": hash_, "location": dst_dir})
        if src_dir and os.path.isdir(src_dir) and not os.listdir(src_dir):
            os.rmdir(src_dir)
    moved += 1

print(f"✅ {moved} torrent {'da spostare' if DRY_RUN else 'spostati'}")
