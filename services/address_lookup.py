"""Address lookup in city/region PDF tables."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PyPDF2 import PdfReader

from config import CITY_PDF_PATH, REGION_PDF_PATH

PODCHERGA_AT_END_RE = re.compile(r"([1-6])[\.,]([12])\s*$")
ONLY_NUMBER_RE = re.compile(r"\d+")
RANGE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")
NUMBER_RE = re.compile(r"\b\d+\b")


class AddressLookup:
    def __init__(self) -> None:
        self.city_rows: list[dict[str, object]] = []
        self.region_rows: list[dict[str, object]] = []

    def load(self) -> None:
        self.city_rows = self._load_pdf(CITY_PDF_PATH)
        self.region_rows = self._load_pdf(REGION_PDF_PATH)

    def _load_pdf(self, path: Path) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []

        try:
            reader = PdfReader(str(path))
        except Exception:
            return rows

        lines: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if not text:
                continue
            lines.extend(line.strip() for line in text.splitlines() if line.strip())

        buffer = ""
        for line in lines:
            match = PODCHERGA_AT_END_RE.search(line)
            if match:
                podcherga = f"{match.group(1)},{match.group(2)}"
                addr_part = line[: match.start()].strip()

                if not addr_part and buffer:
                    addr_text = buffer.strip()
                else:
                    addr_text = f"{buffer} {addr_part}".strip()

                buffer = ""
                if addr_text:
                    numbers, ranges = self._extract_numbers_and_ranges(addr_text)
                    rows.append(
                        {
                            "text": addr_text,
                            "podcherga": podcherga,
                            "norm_text": self._normalize(addr_text),
                            "numbers": numbers,
                            "ranges": ranges,
                        }
                    )
                continue

            if ONLY_NUMBER_RE.fullmatch(line):
                continue

            buffer = f"{buffer} {line}".strip() if buffer else line

        return rows

    @staticmethod
    def _normalize(text: str) -> str:
        s = text.lower()
        for rm in [
            "вул.",
            "вул",
            "вулиця",
            "пр.",
            "проспект",
            "пров.",
            "провулок",
            "с.",
        ]:
            s = s.replace(rm, " ")
        for ch in [",", ".", ";", ":", "(", ")", '"', "'"]:
            s = s.replace(ch, " ")
        return " ".join(s.split())

    @staticmethod
    def _extract_numbers_and_ranges(text: str) -> tuple[set[int], list[tuple[int, int]]]:
        ranges: list[tuple[int, int]] = []
        for a, b in RANGE_RE.findall(text):
            a_i, b_i = int(a), int(b)
            if a_i > b_i:
                a_i, b_i = b_i, a_i
            ranges.append((a_i, b_i))

        numbers = {int(n) for n in NUMBER_RE.findall(text)}
        for a_i, b_i in ranges:
            numbers.discard(a_i)
            numbers.discard(b_i)

        return numbers, ranges

    def _extract_local_numbers_and_ranges(
        self, text: str, street_norm: str
    ) -> tuple[set[int], list[tuple[int, int]]]:
        token = (street_norm or "").strip().split()
        if not token:
            return self._extract_numbers_and_ranges(text)

        key = token[0]
        lower = text.lower()
        numbers: set[int] = set()
        ranges: list[tuple[int, int]] = []

        for match in re.finditer(re.escape(key), lower):
            start = max(0, match.start() - 24)
            end = min(len(text), match.end() + 160)
            local = text[start:end]
            local_numbers, local_ranges = self._extract_numbers_and_ranges(local)
            numbers.update(local_numbers)
            ranges.extend(local_ranges)

        if not numbers and not ranges:
            return self._extract_numbers_and_ranges(text)
        return numbers, ranges

    @staticmethod
    def _parse_podcherga(code: str) -> tuple[str, str]:
        normalized = code.replace(".", ",")
        queue, sub = normalized.split(",")
        return queue.strip(), sub.strip()

    def find_queue(self, street: str, house: str) -> tuple[Optional[tuple[str, str, str]], Optional[str]]:
        street_norm = self._normalize(street)
        house_match = NUMBER_RE.search(house or "")
        house_num: Optional[int] = int(house_match.group()) if house_match else None

        if not street_norm:
            return None, "EMPTY_STREET"

        result = self._find_in_rows(self.city_rows, street_norm, house_num)
        if result is not None:
            queue, sub = result
            return (queue, sub, "city"), None

        result = self._find_in_rows(self.region_rows, street_norm, house_num)
        if result is not None:
            queue, sub = result
            return (queue, sub, "region"), None

        return None, "NOT_FOUND"

    def _find_in_rows(
        self,
        rows: list[dict[str, object]],
        street_norm: str,
        house_num: Optional[int],
    ) -> Optional[tuple[str, str]]:
        best: tuple[int, tuple[str, str]] | None = None
        query_token = street_norm.split()[0] if street_norm.split() else ""

        for row in rows:
            row_text = str(row["text"])
            row_norm = row.get("norm_text") or self._normalize(row_text)
            if street_norm not in row_norm:
                continue

            numbers, ranges = self._extract_local_numbers_and_ranges(row_text, street_norm)

            has_number_match = False
            if house_num is not None:
                if house_num in numbers:
                    has_number_match = True
                else:
                    has_number_match = any(start <= house_num <= end for start, end in ranges)

            score = 0
            row_lower = row_text.lower()
            has_explicit_street_marker = False
            if query_token and re.search(
                rf"\b(вул|вулиця|м|смт|с)\.?\s*{re.escape(query_token)}\b",
                row_lower,
            ):
                score += 120
                has_explicit_street_marker = True
            elif query_token and query_token in row_lower:
                score += 40

            is_partial_area = "частк" in row_lower or "район" in row_lower

            # Row has explicit house list/ranges but requested house is absent.
            # Keep "partial area" rows, because these records may describe feeder zones
            # without strict building-number coverage.
            if (
                house_num is not None
                and (numbers or ranges)
                and not has_number_match
                and not (is_partial_area and has_explicit_street_marker)
            ):
                continue

            if house_num is None:
                score += 20
            elif has_number_match:
                score += 80
            elif not numbers and not ranges:
                score += 30
            elif is_partial_area and has_explicit_street_marker:
                score += 60

            # Penalize noisy merged rows from PDF extraction.
            text_len = len(row_text)
            if text_len > 800:
                score -= 50
            elif text_len > 500:
                score -= 25

            street_mentions = row_lower.count("вул")
            if street_mentions <= 2:
                score += 20
            elif street_mentions > 6:
                score -= 20

            parsed = self._parse_podcherga(str(row["podcherga"]))
            if best is None or score > best[0]:
                best = (score, parsed)

        return best[1] if best is not None else None
