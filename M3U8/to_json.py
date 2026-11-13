#!/usr/bin/env python3
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

BASE_DIR = Path(__file__).parent
WIB = timezone(timedelta(hours=7))

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
)


def detect_category(tvg_id: str, group_title: str) -> str:
    tid = tvg_id.lower()
    if "soccer" in tid or "football" in tid:
        return "Football"
    if "tennis" in tid:
        return "Tennis"
    if "basketball" in tid or "nba" in tid:
        return "Basketball"
    if "baseball" in tid or "mlb" in tid:
        return "Baseball"
    if "hockey" in tid or "nhl" in tid:
        return "Hockey"
    if "mma" in tid or "ufc" in tid or "boxing" in tid:
        return "Fighting"
    if "motor" in tid or "f1" in tid or "formula" in tid or "motogp" in tid:
        return "Motorsport"
    return group_title or "Live Events"


def parse_m3u8_to_sports_array(m3u8_path: Path, json_path: Path) -> int:
    now_wib = datetime.now(WIB)
    start_time_str = now_wib.strftime("%d/%m/%Y %I:%M:%S %p")
    now_ts = int(now_wib.timestamp())

    if not m3u8_path.exists():
        print(f"[!] File tidak ditemukan: {m3u8_path}")
        return 0

    lines = m3u8_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    grouped_matches: dict[str, dict] = {}
    current_meta = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF:"):
            name_match = re.search(r'tvg-name="([^"]*)"', line)
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            group_match = re.search(r'group-title="([^"]*)"', line)
            id_match = re.search(r'tvg-id="([^"]*)"', line)

            fallback_title = (
                line.rsplit(",", 1)[-1].strip() if "," in line else "Unknown"
            )
            raw_title = (
                name_match.group(1).strip()
                if name_match and name_match.group(1).strip()
                else fallback_title
            )
            logo = logo_match.group(1).strip() if logo_match else ""
            group_title = (
                group_match.group(1).strip() if group_match else "Live Events"
            )
            tvg_id = id_match.group(1).strip() if id_match else ""

            # Ambil nama liga dari [Nama Liga]
            league = group_title
            clean_title = raw_title
            league_match = re.match(r"^\[([^\]]+)\]\s*(.+)$", clean_title)
            if league_match:
                league = league_match.group(1).strip()
                clean_title = league_match.group(2).strip()

            # Ambil nama sumber/channel dari (FAWA) atau | Disney+ (TVF90)
            source_tag = "DOMS9"
            source_match = re.search(r"\(([^()]+)\)\s*$", clean_title)
            if source_match:
                source_tag = source_match.group(1).strip()
                clean_title = re.sub(
                    r"\s*\([^()]+\)\s*$", "", clean_title
                ).strip()

            if "|" in clean_title:
                parts = clean_title.split("|", 1)
                clean_title = parts[0].strip()
                extra_ch = parts[1].strip()
                source_tag = f"{extra_ch} [{source_tag}]"

            # Bersihkan nomor urut stream di belakang judul (misal "Comoros vs Congo 2")
            base_match_title = re.sub(r"\s+\d+$", "", clean_title).strip()

            # Pisahkan Team A dan Team B dengan format "Team A Vs Team B"
            team_a = base_match_title
            team_b = ""
            event_display_name = base_match_title
            vs_split = re.split(
                r"\s+vs\.?\s+", base_match_title, maxsplit=1, flags=re.IGNORECASE
            )
            if len(vs_split) == 2:
                team_a = vs_split[0].strip()
                team_b = vs_split[1].strip()
                event_display_name = f"{team_a} Vs {team_b}"

            category = detect_category(tvg_id, group_title)

            current_meta = {
                "group_key": f"{category.lower()}::{event_display_name.lower()}",
                "status": "LIVE",
                "Category": category,
                "event_name": event_display_name,
                "eventInfo": {
                    "teamA": team_a,
                    "teamB": team_b,
                    "teamAFlag": logo,
                    "teamBFlag": "",
                    "eventName": league,
                    "event_logo": logo,
                    "startTime": start_time_str,
                },
                "timestamp": now_ts,
                "channel_name": source_tag,
                "referer": "",
                "user_agent": DEFAULT_UA,
            }

        elif line.startswith("#EXTVLCOPT:") and current_meta is not None:
            opt = line[11:].strip()
            if "=" in opt:
                key, val = opt.split("=", 1)
                key = key.lower().strip()
                val = unquote(val.strip())
                if key == "http-referrer":
                    current_meta["referer"] = val
                elif key == "http-user-agent":
                    current_meta["user_agent"] = val

        elif line.startswith(("http://", "https://")) and current_meta is not None:
            stream_url = line.split("|", 1)[0].strip()
            gkey = current_meta["group_key"]

            if gkey not in grouped_matches:
                grouped_matches[gkey] = {
                    "status": current_meta["status"],
                    "Category": current_meta["Category"],
                    "event_name": current_meta["event_name"],
                    "eventInfo": current_meta["eventInfo"],
                    "streams": [],
                    "timestamp": current_meta["timestamp"],
                }

            stream_idx = len(grouped_matches[gkey]["streams"]) + 1
            ch_label = current_meta["channel_name"]
            if stream_idx > 1:
                ch_label = f"{ch_label} {stream_idx}"

            grouped_matches[gkey]["streams"].append(
                {
                    "channel_name": ch_label,
                    "stream_url": stream_url,
                    "referer": current_meta["referer"],
                    "user_agent": current_meta["user_agent"],
                }
            )
            current_meta = None

    # Output langsung berupa Array [ ... ] persis seperti sports.json di Gist
    matches_array = list(grouped_matches.values())

    json_path.write_text(
        json.dumps(matches_array, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] {m3u8_path.name} -> {json_path.name} ({len(matches_array)} item)")
    return len(matches_array)


def main() -> None:
    targets = [
        (BASE_DIR / "events.m3u8", BASE_DIR / "events.json"),  # Live Sports
        (BASE_DIR / "base.m3u8", BASE_DIR / "tv.json"),        # TV Channels 24 Jam
        (BASE_DIR / "TV.m3u8", BASE_DIR / "all.json"),         # Gabungan TV + Live
    ]
    for src, dst in targets:
        parse_m3u8_to_sports_array(src, dst)


if __name__ == "__main__":
    main()
