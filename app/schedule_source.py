import re
import datetime as dt
from typing import Dict, List, Tuple, Optional
import aiohttp
from bs4 import BeautifulSoup
from .config import RIVNE_SCHEDULE_URL

TIME_RANGE_RE = re.compile(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})")
SUBQUEUE_RE = re.compile(r"^[1-6]\.[1-2]$")

SubqueueSchedule = Dict[str, List[Tuple[dt.time, dt.time]]]

async def _fetch_html() -> str:
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(RIVNE_SCHEDULE_URL) as r:
            r.raise_for_status()
            return await r.text()

def _parse_time_ranges(text: str) -> List[Tuple[dt.time, dt.time]]:
    out: List[Tuple[dt.time, dt.time]] = []
    for a, b in TIME_RANGE_RE.findall(text):
        h1, m1 = a.split(":")
        h2, m2 = b.split(":")
        out.append((dt.time(int(h1), int(m1)), dt.time(int(h2), int(m2))))
    return out

def _clean_cell(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()

def _find_updated_text(full_text: str) -> Optional[str]:
    m = re.search(r"(Оновлено\s*:\s*\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})", full_text, re.IGNORECASE)
    return m.group(1) if m else None

def _date_matches(cell_text: str, target: dt.date) -> bool:
    return target.strftime("%d.%m.%Y") in cell_text

async def get_schedule_for_date(target_date: dt.date) -> tuple[Optional[str], SubqueueSchedule]:
    html = await _fetch_html()
    soup = BeautifulSoup(html, "lxml")

    full_text = _clean_cell(soup.get_text(" ", strip=True))
    updated_text = _find_updated_text(full_text)

    tables = soup.find_all("table")
    if not tables:
        return updated_text, {}

    chosen = None
    for t in tables:
        t_text = _clean_cell(t.get_text(" ", strip=True))
        if "Підчерга" in t_text and "1.1" in t_text:
            chosen = t
            break
    if chosen is None:
        return updated_text, {}

    grid: List[List[str]] = []
    for tr in chosen.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        row = [_clean_cell(c.get_text(" ", strip=True)) for c in cells]
        if row:
            grid.append(row)

    header_row_idx = None
    for i, row in enumerate(grid):
        if any(SUBQUEUE_RE.match(x) for x in row):
            header_row_idx = i
            break
    if header_row_idx is None:
        return updated_text, {}

    header_row = grid[header_row_idx]
    col_to_sq: Dict[int, str] = {idx: cell for idx, cell in enumerate(header_row) if SUBQUEUE_RE.match(cell)}
    if not col_to_sq:
        return updated_text, {}

    target_row = None
    for row in grid[header_row_idx+1:]:
        if row and _date_matches(" ".join(row[:2]), target_date):
            target_row = row
            break
    if target_row is None:
        return updated_text, {}

    schedule: SubqueueSchedule = {}
    for col, sq in col_to_sq.items():
        cell = target_row[col] if col < len(target_row) else ""
        if not cell or "Очікується" in cell:
            schedule[sq] = []
        else:
            schedule[sq] = _parse_time_ranges(cell)

    return updated_text, schedule
