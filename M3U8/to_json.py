#!/usr/bin/env python3
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
)


def parse_m3u8_to_json(m3u8_path: Path, json_path: Path) -> int:
    if not m3u8_path.exists():
        print(f"[!] File tidak ditemukan: {m3u8_path}")
        return 0

    lines = m3u8_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    items = []
    current = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF:"):
            # Ambil atribut dari tag #EXTINF
            name_match = re.search(r'tvg-name="([^"]*)"', line)
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            group_match = re.search(r'group-title="([^"]*)"', line)
            id_match = re.search(r'tvg-id="([^"]*)"', line)

            # Judul setelah koma terakhir
            fallback_title = line.rsplit(",", 1)[-1].strip() if "," in line else "Unknown"
            raw_title = name_match.group(1).strip() if name_match and name_match.group(1).strip() else fallback_title

            # Ekstrak [Liga] dan (Sumber) jika formatnya seperti "[Africa Cup of Nations] Comoros vs Congo (FAWA)"
            league = ""
            source_tag = ""
            clean_title = raw_title

            league_match = re.match(r"^\[([^\]]+)\]\s*(.+)$", clean_title)
            if league_match:
                league = league_match.group(1).strip()
                clean_title = league_match.group(2).strip()

            source_match = re.search(r"\(([^()]+)\)\s*$", clean_title)
            if source_match:
                source_tag = source_match.group(1).strip()
                clean_title = re.sub(r"\s*\([^()]+\)\s*$", "", clean_title).strip()

            current = {
                "id": len(items) + 1,
                "title": clean_title,
                "raw_title": raw_title,
                "league": league,
                "source_tag": source_tag,
                "category": group_match.group(1).strip() if group_match else "General",
                "tvg_id": id_match.group(1).strip() if id_match else "",
                "logo": logo_match.group(1).strip() if logo_match else "",
                "url": "",
                "headers": {
                    "User-Agent": DEFAULT_UA
                },
            }

        elif line.startswith("#EXTVLCOPT:") and current is not None:
            opt = line[11:].strip()
            if "=" in opt:
                key, val = opt.split("=", 1)
                key = key.lower().strip()
                val = val.strip()
                if key == "http-referrer":
                    current["headers"]["Referer"] = val
                elif key == "http-user-agent":
                    current["headers"]["User-Agent"] = val
                elif key == "http-origin":
                    current["headers"]["Origin"] = val

        elif line.startswith(("http://", "https://")) and current is not None:
            # Bersihkan jika ada format Kodi "|Referer=..."
            stream_url = line.split("|", 1)[0].strip()
            current["url"] = stream_url
            items.append(current)
            current = None

    json_path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] {m3u8_path.name} -> {json_path.name} ({len(items)} item)")
    return len(items)


def main() -> None:
    targets = [
        (BASE_DIR / "events.m3u8", BASE_DIR / "events.json"),  # Khusus Live Sports
        (BASE_DIR / "base.m3u8", BASE_DIR / "tv.json"),        # Khusus Channel TV 24 Jam
        (BASE_DIR / "TV.m3u8", BASE_DIR / "all.json"),         # Gabungan TV + Live Sports
    ]
    for src, dst in targets:
        parse_m3u8_to_json(src, dst)


if __name__ == "__main__":
    main()
