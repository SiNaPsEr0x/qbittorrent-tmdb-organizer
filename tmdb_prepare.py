#!/usr/bin/env python3
#
# SCRIPT DI PREPARAZIONE - Eseguito PRIMA del download
#
# Imposta il percorso corretto basato su TMDB prima che qBittorrent inizi a
# scaricare. Se il torrent entra in INBOX_DIR, riconosce automaticamente film
# e serie; FILM_DIR e SERIE_DIR restano selezionabili manualmente.
#
# QBITTORRENT - "Run external program on torrent added":
#   python3 /percorso/tmdb_prepare.py --hash %I
#
# CONSIGLIATO: abilita "Non avviare automaticamente i download" in qBittorrent.
# Lo script avvia il torrent solo dopo aver impostato la destinazione finale.
#
# Richiede solo Python 3.8+ - nessun pacchetto esterno.
#
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


# == CONFIGURAZIONE ==========================================================
QB_URL = os.environ.get("QB_URL", "http://localhost:8080").rstrip("/")
QB_USER = os.environ.get("QB_USER", "")
QB_PASS = os.environ.get("QB_PASS", "")
TMDB_TOKEN = os.environ.get("TMDB_TOKEN", "IL_TUO_TMDB_READ_ACCESS_TOKEN")
INBOX_DIR = os.environ.get("INBOX_DIR", "/percorso/alla/tua/cartella")
FILM_DIR = os.environ.get("FILM_DIR", "/percorso/alla/tua/cartella/FILM")
SERIE_DIR = os.environ.get("SERIE_DIR", "/percorso/alla/tua/cartella/SERIE")
CLEANUP_MIN_AGE = 300
START_AFTER_SET = True
# ============================================================================


_SERIES_MARKER_RE = re.compile(
    r"""(?ix)
    (?<![a-z0-9])(?:
        s\d{1,2}(?:e\d{1,3}(?:e\d{1,3})*)?
        | \d{1,2}x\d{1,3}
        | (?:season|stagione)[._ -]*\d{1,2}
        | complete[._ -]+series
        | serie[._ -]+completa
    )(?![a-z0-9])
    """
)


@dataclass(frozen=True)
class Classification:
    media: str
    folder_name: str
    source: str


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*]', ' -', name).strip()


def strip_release_group(name):
    name = re.sub(
        r'^\s*[\[\(](?=[^\]\)]*[A-Za-z])[^\]\)]{1,40}[\]\)]\s*[-_. ]*',
        '', name)
    return re.sub(r'\[[^\]]{1,40}\]', ' ', name)


def series_marker_match(name):
    return _SERIES_MARKER_RE.search(name)


def has_series_marker(name):
    return series_marker_match(name) is not None


def clean_title(filename, is_serie):
    name = re.sub(r'\.(mkv|avi|mp4)$', '', filename, flags=re.IGNORECASE)
    name = strip_release_group(name)
    if is_serie:
        marker = series_marker_match(name)
        if marker:
            name = name[:marker.start()]
    else:
        years = list(re.finditer(
            r'(?<=[\. \(])(19|20)\d{2}(?=[\. \)\-]|$)', name))
        if years:
            name = name[:years[-1].start()]
    name = re.sub(
        r'[\. ](2160p|1080p|720p|BluRay|WEB-DL|WEBRip|HDTV|UHDrip|x26[45]|HEVC|REMUX).*',
        '', name, flags=re.IGNORECASE)
    name = re.sub(r'[\s.\-_\(\[]+$', '', name)
    if '.' in name:
        name = re.sub(r'-[A-Za-z0-9]{2,20}$', '', name)
    return re.sub(r'\s{2,}', ' ', name.replace('.', ' ')).strip(' -_')


def extract_year(name):
    years = re.findall(r'(?:19|20)\d{2}', name)
    return years[-1] if years else None


def same_path(path, base):
    return os.path.normpath(path) == os.path.normpath(base)


def is_within(path, base):
    path, base = os.path.normpath(path), os.path.normpath(base)
    return path == base or path.startswith(base + os.sep)


def route_for_path(save_path):
    if is_within(save_path, FILM_DIR):
        return 'movie'
    if is_within(save_path, SERIE_DIR):
        return 'tv'
    if same_path(save_path, INBOX_DIR):
        return 'auto'
    return 'skip'


def _tmdb_get(path, params):
    url = "https://api.themoviedb.org/3" + path
    url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={'Authorization': f'Bearer {TMDB_TOKEN}'})
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.load(response)


def search_tmdb(title, year=None, media='movie', retries=2):
    params = {'query': title, 'language': 'it-IT'}
    if year:
        params['year' if media == 'movie' else 'first_air_date_year'] = year
    for attempt in range(retries):
        try:
            results = _tmdb_get(f"/search/{media}", params).get('results', [])
            if not results:
                return None, None
            result = results[0]
            title_out = result.get('title') or result.get('name')
            year_out = (
                result.get('release_date', '')
                or result.get('first_air_date', '')
            )[:4]
            return title_out, year_out
        except Exception as error:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"ATTENZIONE Ricerca TMDB fallita ({error})")
    return None, None


def select_tmdb_multi_result(results, year=None):
    candidates = [
        result for result in results
        if result.get('media_type') in ('movie', 'tv')
        and (result.get('title') or result.get('name'))
    ]
    if year:
        matching_year = []
        for result in candidates:
            result_year = (
                result.get('release_date', '')
                or result.get('first_air_date', '')
            )[:4]
            if result_year == year:
                matching_year.append(result)
        if matching_year:
            candidates = matching_year
    return candidates[0] if candidates else None


def search_tmdb_multi(title, year=None, retries=2):
    params = {
        'query': title,
        'language': 'it-IT',
        'include_adult': 'false',
    }
    for attempt in range(retries):
        try:
            results = _tmdb_get('/search/multi', params).get('results', [])
            result = select_tmdb_multi_result(results, year)
            if not result:
                return None, None, None
            media = result['media_type']
            title_out = result.get('title') or result.get('name')
            year_out = (
                result.get('release_date', '')
                or result.get('first_air_date', '')
            )[:4]
            return media, title_out, year_out
        except Exception as error:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"ATTENZIONE Ricerca TMDB combinata fallita ({error})")
    return None, None, None


def _folder_name(media, title, year):
    folder = safe_name(title)
    if media == 'movie' and year:
        folder = f"{folder} ({year})"
    return folder


def classify_torrent(name, route, specific_search=None, multi_search=None):
    specific_search = specific_search or search_tmdb
    multi_search = multi_search or search_tmdb_multi
    year = extract_year(name)

    if route == 'auto' and not has_series_marker(name):
        title_clean = clean_title(name, False)
        media, tmdb_title, tmdb_year = multi_search(title_clean, year)
        if not media or not tmdb_title:
            return None
        return Classification(
            media,
            _folder_name(media, tmdb_title, tmdb_year),
            'TMDB-AUTO')

    media = 'tv' if route == 'tv' or route == 'auto' else 'movie'
    title_clean = clean_title(name, media == 'tv')
    tmdb_title, tmdb_year = specific_search(title_clean, year, media)
    if tmdb_title:
        return Classification(
            media,
            _folder_name(media, tmdb_title, tmdb_year),
            'TMDB')

    return Classification(
        media,
        _folder_name(media, title_clean, year),
        'FALLBACK')


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
                pass


_cookie_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_cookie_jar))


def build_qb_request(path, data=None):
    headers = {'Referer': QB_URL}
    encoded = None
    if data is not None:
        encoded = urllib.parse.urlencode(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    return urllib.request.Request(QB_URL + path, data=encoded, headers=headers)


def qb_post(path, data):
    with _opener.open(build_qb_request(path, data), timeout=10) as response:
        return response.read().decode()


def qb_get_text(path):
    with _opener.open(build_qb_request(path), timeout=10) as response:
        return response.read().decode()


def qb_get_json(path):
    with _opener.open(build_qb_request(path), timeout=10) as response:
        return json.load(response)


def qb_login():
    body = qb_post(
        "/api/v2/auth/login",
        {"username": QB_USER, "password": QB_PASS})
    if body.strip() == "Ok." or any(c.name == 'SID' for c in _cookie_jar):
        return
    try:
        qb_get_json("/api/v2/torrents/info?limit=1")
        return
    except Exception as error:
        raise RuntimeError(
            "Login Web UI fallito: controlla QB_USER/QB_PASS o il bypass localhost"
        ) from error


def qb_versions():
    return (
        qb_get_text("/api/v2/app/version").strip(),
        qb_get_text("/api/v2/app/webapiVersion").strip(),
    )


def qb_major_version(version):
    match = re.search(r'\d+', version)
    if not match:
        raise ValueError(f"Versione qBittorrent non riconosciuta: {version!r}")
    return int(match.group())


def qb_pause(hash_, app_version):
    method = 'stop' if qb_major_version(app_version) >= 5 else 'pause'
    qb_post(f"/api/v2/torrents/{method}", {"hashes": hash_})


def qb_start(hash_, app_version):
    method = 'start' if qb_major_version(app_version) >= 5 else 'resume'
    qb_post(f"/api/v2/torrents/{method}", {"hashes": hash_})


def get_torrent_by_hash(hash_, attempts=10):
    query = urllib.parse.urlencode({'hashes': hash_})
    path = "/api/v2/torrents/info?" + query
    for attempt in range(attempts):
        torrents = qb_get_json(path)
        torrent = next(
            (item for item in torrents
             if item.get('hash', '').lower() == hash_.lower()),
            None)
        if torrent:
            return torrent
        if attempt < attempts - 1:
            time.sleep(1)
    return None


def _http_error_detail(error):
    labels = {
        400: "percorso di destinazione vuoto",
        403: "qBittorrent non puo' scrivere nella destinazione",
        409: "qBittorrent non riesce a creare o usare la destinazione",
    }
    try:
        body = error.read().decode(errors='replace').strip()
    except Exception:
        body = ''
    detail = labels.get(error.code, str(error.reason))
    return f"HTTP {error.code}: {detail}" + (f" ({body})" if body else '')


def relocate_torrent(hash_, dst_dir, app_version, start_after_set=True):
    try:
        os.makedirs(dst_dir, exist_ok=True)
        if not os.path.isdir(dst_dir) or not os.access(dst_dir, os.W_OK):
            raise OSError("la destinazione non e' una cartella scrivibile")
    except OSError as error:
        print(f"ERRORE Creazione destinazione fallita: {error}")
        return False

    try:
        qb_post(
            "/api/v2/torrents/setLocation",
            {"hashes": hash_, "location": dst_dir})
    except urllib.error.HTTPError as error:
        print(f"ERRORE setLocation fallito: {_http_error_detail(error)}")
        return False
    except (urllib.error.URLError, OSError) as error:
        print(f"ERRORE setLocation fallito: {error}")
        return False

    if start_after_set:
        try:
            qb_start(hash_, app_version)
        except (urllib.error.URLError, OSError, ValueError) as error:
            print(f"ERRORE Avvio torrent fallito: {error}")
            return False
    return True


def parse_hash(argv):
    if "--hash" not in argv:
        raise ValueError("Uso: python3 tmdb_prepare.py --hash <hash>")
    index = argv.index("--hash")
    if index + 1 >= len(argv) or not argv[index + 1].strip():
        raise ValueError("Uso: python3 tmdb_prepare.py --hash <hash>")
    return argv[index + 1].lower()


def validate_config():
    if TMDB_TOKEN == "IL_TUO_TMDB_READ_ACCESS_TOKEN":
        raise ValueError("TMDB_TOKEN non configurato")
    if re.fullmatch(r'[0-9a-fA-F]{32}', TMDB_TOKEN):
        raise ValueError(
            "TMDB_TOKEN e' una API Key v3; serve l'API Read Access Token")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        hash_ = parse_hash(argv)
        validate_config()
    except ValueError as error:
        print(f"ERRORE {error}")
        return 1

    try:
        qb_login()
        app_version, webapi_version = qb_versions()
        torrent = get_torrent_by_hash(hash_)
    except (urllib.error.URLError, OSError, RuntimeError, ValueError) as error:
        print(f"ERRORE qBittorrent non raggiungibile su {QB_URL}: {error}")
        return 1

    if not torrent:
        print(f"ERRORE Torrent {hash_} non trovato")
        return 1

    name = torrent['name']
    save_path = torrent['save_path'].rstrip('/')
    route = route_for_path(save_path)

    if route != 'skip':
        try:
            qb_pause(hash_, app_version)
        except (urllib.error.URLError, OSError, ValueError) as error:
            print(f"ERRORE Impossibile mettere in pausa il torrent: {error}")
            return 1

    cleanup_empty_folders()

    if route == 'skip':
        print(f"SKIP Ignorato (fuori da INBOX/FILM/SERIE): {name}")
        return 0

    classification = classify_torrent(name, route)
    if not classification:
        print(f"IN ATTESA Tipo non riconosciuto da TMDB: {name}")
        print(f"   Torrent lasciato in pausa: {save_path}")
        return 0

    base_dir = FILM_DIR if classification.media == 'movie' else SERIE_DIR
    dst_dir = os.path.join(base_dir, classification.folder_name)
    if not relocate_torrent(
            hash_, dst_dir, app_version, start_after_set=START_AFTER_SET):
        print("   Torrent lasciato in pausa per evitare il download nel percorso errato")
        return 1

    print(
        f"OK [{classification.source}] "
        f"{'FILM' if classification.media == 'movie' else 'SERIE'}: "
        f"{classification.folder_name}")
    print(f"   Percorso impostato: {dst_dir}")
    print(f"   qBittorrent {app_version} / WebAPI {webapi_version}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
