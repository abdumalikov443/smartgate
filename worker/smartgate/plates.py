"""Korean licence plate reading: locate the plate, OCR it, validate, vote.

1. The plate rectangle is found with colour + shape rules (yellow, white or
   green, aspect ratio 1.8-6.5) in the lower part of the vehicle crop.
2. That tight crop is upscaled and read by EasyOCR, restricted to the
   characters a Korean plate can contain.
3. A full plate (12가3456) is accepted only if it matches the Korean format.
   On low-resolution footage the Hangul letter is often unreadable while the
   digits are fine, so the last 4 digits are kept as a fallback key.
4. Reads from several frames of the same vehicle are combined by voting.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

REGIONS = "서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주"
# 12가3456 / 123가4567 / 서울12가3456
PLATE_RE = re.compile(rf"({REGIONS})?(\d{{2,3}})([가-힣])(\d{{4}})")
DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "D": "0", "I": "1", "l": "1", "|": "1", "Z": "2",
                             "S": "5", "B": "8", "G": "6", "T": "7"})


def normalize_plate(text: str) -> str | None:
    """Return a clean plate like '12가3456' or None if `text` is not a plate."""
    cleaned = re.sub(r"[\s\-·.]", "", text)
    # fix OCR letter/digit confusions only around the digit groups
    cleaned = "".join(ch.translate(DIGIT_FIXES) if not ("가" <= ch <= "힣") else ch for ch in cleaned)
    m = PLATE_RE.search(cleaned)
    if not m:
        return None
    region, first, letter, last = m.groups()
    return f"{region or ''}{first}{letter}{last}"


class PlateVoter:
    """Collects plate reads per track and returns the most confident plate (or last 4 digits)."""

    def __init__(self, max_reads: int = 6):
        self.max_reads = max_reads
        self._scores: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._digits: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._reads: dict[int, int] = defaultdict(int)

    def wants_more(self, track_id: int) -> bool:
        return self._reads[track_id] < self.max_reads

    def add(self, track_id: int, plate: str | None, conf: float, digits: str | None = None) -> None:
        self._reads[track_id] += 1
        if plate:
            self._scores[track_id][plate] += conf
            digits = digits or plate[-4:]
        if digits:
            self._digits[track_id][digits] += conf

    def best(self, track_id: int) -> tuple[str | None, float]:
        return self._top(self._scores.get(track_id))

    def best_digits(self, track_id: int) -> str | None:
        """Last 4 digits: from the best full plate if there is one, else from digit-only reads."""
        plate, _ = self.best(track_id)
        return plate[-4:] if plate else self._top(self._digits.get(track_id))[0]

    @staticmethod
    def _top(scores) -> tuple[str | None, float]:
        if not scores:
            return None, 0.0
        key, score = max(scores.items(), key=lambda kv: kv[1])
        total = sum(scores.values())
        return key, round(score / total, 3) if total else 0.0

    def forget(self, track_id: int) -> None:
        for d in (self._scores, self._digits, self._reads):
            d.pop(track_id, None)


PLATE_LETTERS = "가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주아바사자배하허호육공해국합"
# only characters that can appear on a Korean plate - stops OCR from "seeing" Latin letters
ALLOWLIST = "0123456789" + "".join(sorted(set(PLATE_LETTERS + REGIONS.replace("|", ""))))


@lru_cache(maxsize=1)
def _reader():
    import easyocr
    return easyocr.Reader(["ko"], gpu=False, verbose=False)


def plate_digits(text: str) -> str | None:
    """Last 4 digits when the text looks like a plate whose letter was misread (6-8 digits)."""
    digits = re.sub(r"\D", "", text.translate(DIGIT_FIXES))
    return digits[-4:] if 6 <= len(digits) <= 8 else None


def locate_plates(region: np.ndarray, max_boxes: int = 3) -> list[tuple[int, int, int, int]]:
    """Rectangles (x, y, w, h) that look like a Korean plate, best first."""
    import cv2
    h, w = region.shape[:2]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    masks = (cv2.inRange(hsv, (12, 70, 90), (40, 255, 255)),    # yellow: commercial vehicles
             cv2.inRange(hsv, (0, 0, 150), (180, 45, 255)),     # white: private cars
             cv2.inRange(hsv, (40, 60, 60), (90, 255, 255)))    # green: older plates
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    boxes = []
    for m in masks:
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
        for c in cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, bw, bh = cv2.boundingRect(c)
            area = bw * bh
            fill = cv2.contourArea(c) / max(area, 1)
            if 1.8 <= bw / max(bh, 1) <= 6.5 and area >= 0.003 * w * h and bh <= 0.4 * h and fill > 0.55:
                boxes.append((fill * area, (x, y, bw, bh)))
    return [b for _, b in sorted(boxes, reverse=True)][:max_boxes]


def tight_crop(region: np.ndarray, box, target_h: int = 96) -> np.ndarray:
    import cv2
    x, y, bw, bh = box
    px, py = int(bw * 0.06), int(bh * 0.15)
    crop = region[max(0, y - py):y + bh + py, max(0, x - px):x + bw + px]
    scale = target_h / max(crop.shape[0], 1)
    return cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def plate_candidates(results: list) -> list[tuple[str, float]]:
    """Build candidate strings from EasyOCR results [(box, text, conf), ...].

    Plates are often split into several boxes, and older Korean plates have
    two lines (서울 12 / 가 3456), so besides single boxes we try each text row
    joined left-to-right and all rows joined top-to-bottom.
    """
    if not results:
        return []
    def cx(r): return sum(p[0] for p in r[0]) / 4
    def cy(r): return sum(p[1] for p in r[0]) / 4
    def hgt(r): return max(p[1] for p in r[0]) - min(p[1] for p in r[0])
    cands = [(r[1], float(r[2])) for r in results]
    rows: list[list] = []
    tol = max(1.0, float(np.median([hgt(r) for r in results]))) * 0.6
    for r in sorted(results, key=cy):
        if rows and abs(cy(rows[-1][-1]) - cy(r)) <= tol:
            rows[-1].append(r)
        else:
            rows.append([r])
    joined_rows = []
    for row in rows:
        row = sorted(row, key=cx)
        # a joined string is only as reliable as its weakest part
        joined_rows.append(("".join(r[1] for r in row), float(min(r[2] for r in row))))
    seen = {c[0] for c in cands}
    cands += [jr for jr in joined_rows if jr[0] not in seen]
    if len(joined_rows) > 1:
        cands.append(("".join(t for t, _ in joined_rows), float(min(c for _, c in joined_rows))))
        for a, b in zip(joined_rows, joined_rows[1:]):           # neighbouring rows (two-line plates)
            cands.append((a[0] + b[0], min(a[1], b[1])))
    return cands


@dataclass
class PlateRead:
    plate: str | None = None       # full plate, e.g. 32배2641
    digits: str | None = None      # last 4 digits, e.g. 2641 (also set when only the digits were readable)
    conf: float = 0.0


def best_read(results: list) -> PlateRead:
    best = PlateRead()
    for text, conf in plate_candidates(results):
        plate = normalize_plate(text)
        if plate and conf > (best.conf if best.plate else 0):
            best = PlateRead(plate, plate[-4:], float(conf))
        elif not best.plate:
            digits = plate_digits(text)
            if digits and conf > best.conf:
                best = PlateRead(None, digits, float(conf))
    return best


def read_plate(vehicle_crop: np.ndarray, min_conf: float = 0.1, debug: list | None = None) -> PlateRead:
    """Find and read the plate in a vehicle crop (BGR).

    Pass a list as `debug` to receive the raw OCR texts (used by --plate-debug).
    """
    h = vehicle_crop.shape[0]
    region = vehicle_crop[int(h * 0.4):, :]
    if region.size == 0:
        return PlateRead()
    boxes = locate_plates(region)
    crops = [tight_crop(region, b) for b in boxes] or [region]     # fall back to the whole lower part
    best = PlateRead()
    for crop in crops:
        results = [r for r in _reader().readtext(crop, allowlist=ALLOWLIST) if r[2] >= min_conf]
        if debug is not None:
            debug.extend(f"{r[1]}({r[2]:.2f})" for r in results)
        read = best_read(results)
        if (read.plate and not best.plate) or (bool(read.plate) == bool(best.plate) and read.conf > best.conf):
            best = read
    return best
