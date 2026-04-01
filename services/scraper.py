"""Schedule scraping utilities."""

from __future__ import annotations

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import SCHEDULE_URL
from database.db import clear_schedule_for, save_schedule

DATE_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")
TIME_RANGE_RE = re.compile(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})")


def _normalize_queue_code(raw: str) -> str:
    # Supports: 2.1 / 2,1 / "2 . 1" -> 2.1
    cleaned = raw.replace(" ", "").replace(",", ".")
    match = re.search(r"(\d+)\.(\d+)", cleaned)
    if not match:
        return ""
    return f"{match.group(1)}.{match.group(2)}"


def _extract_intervals(cell_text: str) -> list[tuple[str, str]]:
    return TIME_RANGE_RE.findall(cell_text)


def scrape_and_store() -> dict[str, dict[str, list[tuple[str, str]]]]:
    """Parse schedule page and store data to DB."""
    response = requests.get(SCHEDULE_URL, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    all_data: dict[str, dict[str, list[tuple[str, str]]]] = {}

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 4:
            continue

        date_cell = rows[1].find("td")
        if not date_cell:
            continue

        date_match = DATE_RE.search(date_cell.get_text(" ", strip=True))
        if not date_match:
            continue

        date = datetime.strptime(date_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")

        header_cells = rows[2].find_all("td")[1:]
        queue_codes = [_normalize_queue_code(c.get_text(strip=True)) for c in header_cells]

        daily_data = all_data.setdefault(date, {})

        for row in rows[3:]:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue

            for idx, col in enumerate(cols[1:]):
                if idx >= len(queue_codes):
                    break

                queue_code = queue_codes[idx]
                if not queue_code:
                    continue

                intervals = _extract_intervals(col.get_text("\n", strip=True))
                if not intervals:
                    continue

                daily_data.setdefault(queue_code, []).extend(intervals)

    for date, queues in all_data.items():
        clear_schedule_for(date)
        for queue_code, intervals in queues.items():
            unique_intervals = sorted(set(intervals))
            for off_time, on_time in unique_intervals:
                save_schedule(date, queue_code, off_time, on_time)

    return all_data
