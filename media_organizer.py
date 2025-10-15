import os
import re
import time
import shutil
import logging
import requests
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === CONFIG ===
load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
INPUT_FOLDER = os.getenv("INPUT_FOLDER")
OUTPUT_SERIES = os.getenv("OUTPUT_SERIES")
OUTPUT_MOVIES = os.getenv("OUTPUT_MOVIES")
LOG_FILE = os.getenv("LOG_FILE", "media_organizer.log")

VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv')

# === LOGGING ===
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

# === TMDB API ===
def search_tmdb(query, is_movie):
    """Caută filmul sau serialul pe TMDB."""
    base_url = "https://api.themoviedb.org/3/search/"
    search_type = "movie" if is_movie else "tv"
    params = {"api_key": TMDB_API_KEY, "query": query}
    r = requests.get(base_url + search_type, params=params)
    if r.status_code != 200:
        logging.warning(f"TMDB search failed for {query}: {r.status_code}")
        return None
    results = r.json().get("results", [])
    return results[0] if results else None

def get_episode_info(tmdb_id, season, episode):
    """Ia numele episodului din TMDB."""
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season}/episode/{episode}"
    params = {"api_key": TMDB_API_KEY}
    r = requests.get(url, params=params)
    return r.json() if r.status_code == 200 else None

# === FILE PARSING ===
def detect_type(filename):
    # curăță numele
    clean_name = re.sub(r'\[.*?\]', '', filename) 
    # verifică dacă are tipar SxxEyy
    if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}', clean_name):
        return 'episode'
    # detectează tipar comun în anime: " - 02" sau "-02"
    if re.search(r'[-_ ]\d{1,3}(\s|$)', clean_name):
        return 'episode'
    # dacă nu se potrivește nimic, tratăm ca film
    return 'movie'

def parse_filename(filename):
    """Determină dacă fișierul e serial sau film, pe baza numelui."""
    name, _ = os.path.splitext(filename)
    show_match = re.search(r"(.+)[. _-][Ss](\d{1,2})[Ee](\d{1,2})", name)
    if show_match:
        title = re.sub(r'[._]', ' ', show_match.group(1)).strip()
        season = int(show_match.group(2))
        episode = int(show_match.group(3))
        return {"type": "tv", "title": title, "season": season, "episode": episode}
    else:
        title = re.sub(r'[._]', ' ', name).strip()
        return {"type": "movie", "title": title}

# === PROCESSING ===
def rename_and_move(filepath):
    filename = os.path.basename(filepath)
    info = parse_filename(filename)
    logging.info(f"Procesare fișier: {filename}")

    # retry dacă fișierul încă se copiază
    for _ in range(5):
        try:
            if os.path.getsize(filepath) > 0:
                break
        except FileNotFoundError:
            time.sleep(2)

    if info["type"] == "tv":
        data = search_tmdb(info["title"], is_movie=False)
        if not data:
            logging.warning(f"Serialul nu a fost găsit pentru {info['title']}")
            return
        tmdb_id = data["id"]
        show_name = data["name"]
        episode_info = get_episode_info(tmdb_id, info["season"], info["episode"])
        episode_title = episode_info.get("name", f"Ep{info['episode']}") if episode_info else f"Ep{info['episode']}"
        new_name = f"{show_name} - S{info['season']:02d}E{info['episode']:02d} - {episode_title}{os.path.splitext(filename)[1]}"
        dest_dir = os.path.join(OUTPUT_SERIES, f"{show_name} [tmdbid-{tmdb_id}]", f"Season {info['season']}")
    else:
        data = search_tmdb(info["title"], is_movie=True)
        if not data:
            logging.warning(f"Filmul nu a fost găsit pentru {info['title']}")
            return
        tmdb_id = data["id"]
        movie_name = data["title"]
        year = data.get("release_date", "0000")[:4]
        new_name = f"{movie_name} ({year}) - [tmdbid-{tmdb_id}]{os.path.splitext(filename)[1]}"
        dest_dir = os.path.join(OUTPUT_MOVIES, f"{movie_name} ({year}) - [tmdbid-{tmdb_id}]")

    os.makedirs(dest_dir, exist_ok=True)
    new_path = os.path.join(dest_dir, new_name)

    try:
        shutil.move(filepath, new_path)
        logging.info(f"✅ Mutat: {new_path}")
    except Exception as e:
        logging.error(f"Eroare la mutare {filename}: {e}")

# === WATCHDOG HANDLER ===
class MediaHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(VIDEO_EXTENSIONS):
            time.sleep(3)  # așteaptă finalizarea copierii
            rename_and_move(event.src_path)

# === INITIAL SCAN ===
def initial_scan():
    logging.info("🔍 Scanare inițială a folderului...")
    for filename in os.listdir(INPUT_FOLDER):
        filepath = os.path.join(INPUT_FOLDER, filename)
        if os.path.isfile(filepath) and filepath.endswith(VIDEO_EXTENSIONS):
            rename_and_move(filepath)
    logging.info("✅ Scanare inițială terminată.")

# === MAIN LOOP ===
if __name__ == "__main__":
    logging.info(f"👀 Pornit media_organizer – monitorizează: {INPUT_FOLDER}")
    initial_scan()
    event_handler = MediaHandler()
    observer = Observer()
    observer.schedule(event_handler, INPUT_FOLDER, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
