#!/usr/bin/env python3
"""
To Much Rhythia Maps (TMRM)
============================
Bulk-downloads Rhythia maps (production.rhythia.com) matching a star
rating filter into a single folder.

Usage:
    python rhythia_downloader.py --min 3 --max 5
    python rhythia_downloader.py --min 4 --max 6 --status RANKED --out "D:/RhythiaMaps"
    python rhythia_downloader.py --min 0 --max 10 --status ALL --workers 8

    To download ONLY maps that award RP, filter by --status RANKED:
        python rhythia_downloader.py --min 3 --max 5 --status RANKED

    If you hit ConnectionResetError / WinError 10054 (usually a local proxy
    like Clash/zapret dropping many sequential connections):
        python rhythia_downloader.py --min 3 --max 5 --no-proxy
    or explicitly set a proxy:
        python rhythia_downloader.py --min 3 --max 5 --proxy http://127.0.0.1:7890

    To delete all downloaded maps from the output folder:
        python rhythia_downloader.py --clear
        python rhythia_downloader.py --clear --out "D:/RhythiaMaps"

    For the full option list:
        python rhythia_downloader.py --help

Requirements:
    pip install requests
"""

import argparse
import json
import os
import sys
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://production.rhythia.com/api/getBeatmaps"

BANNER = r"""
 /$$$$$$$$ /$$      /$$ /$$$$$$$  /$$      /$$
|__  $$__/| $$$    /$$$| $$__  $$| $$$    /$$$
   | $$   | $$$$  /$$$$| $$  \ $$| $$$$  /$$$$
   | $$   | $$ $$/$$ $$| $$$$$$$/| $$ $$/$$ $$
   | $$   | $$  $$$| $$| $$__  $$| $$  $$$| $$
   | $$   | $$\  $ | $$| $$  \ $$| $$\  $ | $$
   | $$   | $$ \/  | $$| $$  | $$| $$ \/  | $$
   |__/   |__/     |__/|__/  |__/|__/     |__/
"""

# Statuses actually supported by the API (based on the website frontend).
# "ALL" is our own sentinel value: the script will loop through every status.
KNOWN_STATUSES = ["RANKED", "UNRANKED", "QUALIFIED"]

# Map file extensions we recognize (used by --clear to know what to delete).
MAP_EXTENSIONS = (".sspm", ".rhm", ".ssmp", ".phxm")

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (RhythiaBulkDownloader/1.0)",
}


def get_version() -> str:
    """Reads the program version from version.txt next to this script."""
    version_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt")
    try:
        with open(version_path, "r", encoding="utf-8-sig") as f:
            content = f.read().strip()
            return content if content else "?.? (version.txt is empty)"
    except FileNotFoundError:
        return f"?.? (not found: {version_path})"
    except Exception as e:
        return f"?.? (read error: {e})"


def print_banner():
    version = get_version()
    print(BANNER)
    print(f"To Much Rhythia Maps  v{version}")
    print("-" * 48)


def make_session(proxy: str = None, no_proxy: bool = False) -> requests.Session:
    """Creates a requests session with retries on network drops and an optional proxy."""
    session = requests.Session()

    retry = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    if no_proxy:
        # Fully ignore system/environment proxy settings.
        session.trust_env = False
        session.proxies = {}
    elif proxy:
        session.proxies = {"http": proxy, "https": proxy}

    return session


def sanitize_filename(name: str) -> str:
    """Strips characters that are invalid in Windows/Linux/macOS filenames."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip(" .")
    return name[:150] if len(name) > 150 else name


def fetch_page(session_http: requests.Session, page: int, min_stars: float, max_stars: float, status: str, session_token: str = "") -> dict:
    """Makes a single request to the getBeatmaps API."""
    payload = {
        "page": page,
        "textFilter": "",
        "authorFilter": "",
        "tagsFilter": "",
        "minStars": min_stars,
        "maxStars": max_stars,
        "status": status,
        "sort": "newest",
        "sortDirection": "desc",
        "session": session_token,
    }
    resp = session_http.post(API_URL, json=payload, headers=DEFAULT_HEADERS, timeout=20)
    if not resp.ok:
        print(f"  !! Server returned {resp.status_code} for page {page} (status={status}).")
        print(f"  !! Response body: {resp.text[:1000]}")
    resp.raise_for_status()
    return resp.json()


def collect_all_beatmaps(session_http: requests.Session, min_stars: float, max_stars: float, status: str, delay: float = 0.2, session_token: str = "") -> list:
    """Walks through all API pages for a given status and collects the map list."""
    all_maps = []
    page = 1
    while True:
        data = fetch_page(session_http, page, min_stars, max_stars, status, session_token=session_token)
        beatmaps = data.get("beatmaps", [])
        total = data.get("total", 0)
        per_page = data.get("viewPerPage", 50) or 50

        if not beatmaps:
            break

        all_maps.extend(beatmaps)
        print(f"  [{status}] page {page} — got {len(beatmaps)} maps (collected {len(all_maps)} of {total} so far)")

        if len(all_maps) >= total or len(beatmaps) < per_page:
            break

        page += 1
        time.sleep(delay)

    return all_maps


def download_one(session: requests.Session, beatmap: dict, out_dir: str) -> tuple:
    """Downloads a single map file. Returns (success: bool, message: str)."""
    url = beatmap.get("beatmapFile")
    if not url:
        return False, f"Map {beatmap.get('title')} has no file URL"

    ext = os.path.splitext(url)[1] or ".sspm"
    title = sanitize_filename(beatmap.get("title", "unknown"))
    mapper = sanitize_filename(beatmap.get("ownerUsername", "unknown"))
    map_id = beatmap.get("id", "0")

    filename = f"{map_id} - {mapper} - {title}{ext}"
    filepath = os.path.join(out_dir, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return True, f"Skipped (already exists): {filename}"

    try:
        resp = session.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
        return True, f"Downloaded: {filename}"
    except Exception as e:
        return False, f"Failed to download {filename}: {e}"


def clear_folder(out_dir: str):
    """Deletes all map files (by extension) from the folder. Leaves the folder and unrelated files untouched."""
    if not os.path.isdir(out_dir):
        print(f"Folder not found: {out_dir} (nothing to delete)")
        return

    removed = 0
    skipped = 0
    for entry in os.listdir(out_dir):
        full_path = os.path.join(out_dir, entry)
        if not os.path.isfile(full_path):
            continue
        if entry.lower().endswith(MAP_EXTENSIONS):
            try:
                os.remove(full_path)
                removed += 1
            except OSError as e:
                print(f"  Could not delete {entry}: {e}")
        else:
            skipped += 1

    print(f"Clearing folder: {out_dir}")
    print(f"  Map files removed: {removed}")
    if skipped:
        print(f"  Skipped (doesn't look like a map file): {skipped}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rhythia_downloader.py",
        description="To Much Rhythia Maps (TMRM) — bulk-download Rhythia maps filtered by star rating.",
        epilog=(
            "Examples:\n"
            "  rhythia_downloader.py --min 3 --max 5\n"
            "  rhythia_downloader.py --min 3 --max 5 --status RANKED\n"
            "  rhythia_downloader.py --min 4 --max 6 --status RANKED --out \"D:/RhythiaMaps\"\n"
            "  rhythia_downloader.py --min 3 --max 5 --no-proxy\n"
            "  rhythia_downloader.py --clear --out \"D:/RhythiaMaps\"\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--min", type=float, default=None, help="Minimum star rating (e.g. 3)")
    parser.add_argument("--max", type=float, default=None, help="Maximum star rating (e.g. 5)")
    parser.add_argument(
        "--status",
        default="ALL",
        choices=KNOWN_STATUSES + ["ALL"],
        help="Map status: RANKED (awards RP), UNRANKED, QUALIFIED, or ALL (loop through every status). Default: ALL.",
    )
    parser.add_argument("--out", default="rhythia_maps", help="Folder to save maps into (default: ./rhythia_maps)")
    parser.add_argument("--workers", type=int, default=6, help="Number of parallel downloads (default: 6)")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between API page requests, in seconds (default: 0.2)")
    parser.add_argument("--no-proxy", action="store_true", help="Ignore the system proxy entirely (useful if you hit ConnectionResetError/10054)")
    parser.add_argument("--proxy", default=None, help="Explicitly set a proxy, e.g. http://127.0.0.1:7890")
    parser.add_argument(
        "--session",
        default="",
        help="Session token from DevTools (Payload of the getBeatmaps request), if anonymous requests get blocked (400/401)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete all map files from the --out folder (default ./rhythia_maps) and exit, without downloading anything.",
    )
    parser.add_argument(
        "--debug-fields",
        action="store_true",
        help="Print every field of the first found map (JSON) before filtering — for debugging.",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    print_banner()

    out_dir = os.path.abspath(args.out)

    if args.clear:
        clear_folder(out_dir)
        return

    if args.min is None or args.max is None:
        print("Error: --min and --max are required (or use --clear to wipe the folder).")
        sys.exit(1)

    if args.min > args.max:
        print("Error: --min cannot be greater than --max")
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)

    statuses = KNOWN_STATUSES if args.status == "ALL" else [args.status]

    session = make_session(proxy=args.proxy, no_proxy=args.no_proxy)

    print(f"Collecting maps: {args.min}-{args.max} stars, status(es): {', '.join(statuses)}")
    all_maps = []
    seen_ids = set()

    for status in statuses:
        maps = collect_all_beatmaps(session, args.min, args.max, status, delay=args.delay, session_token=args.session)
        for m in maps:
            if m["id"] not in seen_ids:
                seen_ids.add(m["id"])
                all_maps.append(m)

    print(f"Total unique maps found: {len(all_maps)}")

    if args.debug_fields and all_maps:
        print("\n--- DEBUG: first map's JSON ---")
        print(json.dumps(all_maps[0], indent=2, ensure_ascii=False))
        print("--- end DEBUG ---\n")

    if not all_maps:
        print("No maps found, nothing to download.")
        return

    print(f"Downloading into: {out_dir}\n")

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_one, session, m, out_dir): m for m in all_maps}
        for i, future in enumerate(as_completed(futures), 1):
            ok, msg = future.result()
            prefix = f"[{i}/{len(all_maps)}]"
            print(f"{prefix} {msg}")
            if ok:
                success_count += 1
            else:
                fail_count += 1

    print(f"\nDone. Succeeded: {success_count}, failed: {fail_count}")


if __name__ == "__main__":
    main()
