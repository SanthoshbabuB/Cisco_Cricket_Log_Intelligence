import json
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_FILE = PROJECT_ROOT / "data" / "raw" / "cricket_log.txt"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "cricket_events.json"

LOG_PATTERN = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s+"
    r"Match:(?P<match>.*?)\s+"
    r"Team:(?P<team>.*?)\s+"
    r"Player:(?P<player>.*?)\s+"
    r"Event:(?P<event>.*?)\s+"
    r"Runs:(?P<runs>-?\d+)\s+"
    r"Over:(?P<over>\d+)\s+"
    r"Status:(?P<status>.*?)\s+"
    r"Commentary:(?P<commentary>.*)$"
)


def parse_log_line(line: str):
    """Convert one raw cricket log line into a structured dictionary."""
    match = LOG_PATTERN.match(line.strip())

    if not match:
        return None

    record = match.groupdict()

    try:
        timestamp = datetime.strptime(
            record["timestamp"], "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        return None

    return {
        "timestamp": timestamp.isoformat(),
        "match_id": record["match"].strip(),
        "team": record["team"].strip(),
        "player": record["player"].strip(),
        "event": record["event"].strip(),
        "runs": int(record["runs"]),
        "over": int(record["over"]),
        "status": record["status"].strip(),
        "commentary": record["commentary"].strip(),
    }


def main():
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Raw log file not found: {RAW_FILE}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    valid_records = []
    invalid_records = []

    with RAW_FILE.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            record = parse_log_line(line)

            if record is None:
                invalid_records.append({
                    "line_number": line_number,
                    "raw_line": line.rstrip("\n"),
                })
            else:
                valid_records.append(record)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(valid_records, file, indent=2, ensure_ascii=False)

    print(f"Total valid records: {len(valid_records)}")
    print(f"Total invalid records: {len(invalid_records)}")
    print(f"Output saved to: {OUTPUT_FILE}")

    if invalid_records:
        print("\nFirst 3 invalid records:")
        for record in invalid_records[:3]:
            print(record)


if __name__ == "__main__":
    main()