import re 
import subprocess
import sys 
import os
import logging
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(BASE_DIR, "queue.txt")
PROCESSED_FILE = os.path.join(BASE_DIR, "processed.txt")
FAILED_FILE = os.path.join(BASE_DIR, "failed.txt")
LOCK_FILE = os.path.join(BASE_DIR, "downloader.lock")
LOG_FILE = os.path.join(BASE_DIR, "logs", "downloader.log")

MEDIA_ROOT = os.environ.get("MEDIA_ROOT", os.path.join(BASE_DIR, "output"))

PLATFORM_DIRS = {
    "twitter": os.path.join(MEDIA_ROOT, "twitter"),
    "instagram": os.path.join(MEDIA_ROOT, "instagram"),
}

OUTPUT_TEMPLATE = "%(uploader)s_%(upload_date)s_%(is)s.%(ext)s"

def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )

def detect_platform(url):
    if re.search(r"(twitter\.com|x\.com)", url):
        return "twitter"
    if re.search(r"instagram\.com", url):
        return "instagram"
    return None

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE) as f:
            old_pid = f.read().strip()
        if old_pid and is_pid_running (int(old_pid)):
            logging.info(f"Another run is active (pid {old_pid}), skipping.")
            return False 
        logging.warning(f"Found stale lock (pid {old_pid} not running), removing.")
        os.remove(LOCK_FILE)

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True 

def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def is_pid_running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False 
    return True

def read_queue():
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE) as f:
        lines = [line.strip() for line in f]
    return [ line for line in lines if line and not line.startswith("#")]

def remove_from_queue(url):
    remaining = [u for u in read_queue() if u != url]
    with open(QUEUE_FILE, "w") as f:
        for u in remaining:
            f.write(u + "\n")

def record_outcome(url, target_file, note=None):
    line = url if not note else f"{url} # {note}"
    with open(target_file, "a") as f:
        f.write(line + "\n")

def download(url, platform):
    output_dir = PLATFORM_DIRS[platform]
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "yt-dlp",
        "-o", os.path.join(output_dir, OUTPUT_TEMPLATE),
        url,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return True, None
    error_msg = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
    return False, error_msg

def main():
    setup_logging()

    if not acquire_lock():
        return

    try:
        urls = read_queue()
        if not urls:
            logging.info("Queue is empty, nothing to do.")
            return

        for url in urls:
            platform = detect_platform(url)

            if platform is None:
                logging.warning(f"Unrecognizable platform, skipping: {url}")
                record_outcome(url, FAILED_FILE, "no platform match")
                remove_from_queue(url)
                continue

            logging.info(f"Downloading ({platform}): {url}")
            success, error = download(url, platform)

            if success: 
                logging.info(f"Done: {url}")
                record_outcome(url, PROCESSED_FILE)
            else: 
                logging.error(f"Failed: {url} - {error}")
                record_outcome(url, FAILED_FILE, error)

            remove_from_queue(url)
    finally:
        release_lock()

if __name__ == "__main__":
    main()
