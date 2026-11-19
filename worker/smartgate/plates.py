"""Korean licence plate reading: OCR on the vehicle crop + format validation + voting.

No separate plate-detector model is needed: EasyOCR finds text regions in the
lower part of the vehicle crop, and only strings that match a Korean plate
format are accepted. Reads from several frames of the same vehicle are
combined by confidence-weighted voting.
"""
from __future__ import annotations

import re
from collections import defaultdict
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
    """Collects plate reads per track and returns the most confident plate."""

    def __init__(self, max_reads: int = 6):
        self.max_reads = max_reads
        self._scores: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._reads: dict[int, int] = defaultdict(int)

    def wants_more(self, track_id: int) -> bool:
        return self._reads[track_id] < self.max_reads

    def add(self, track_id: int, plate: str | None, conf: float) -> None:
        self._reads[track_id] += 1
        if plate:
            self._scores[track_id][plate] += conf

    def best(self, track_id: int) -> tuple[str | None, float]:
        scores = self._scores.get(track_id)
        if not scores:
            return None, 0.0
        plate, score = max(scores.items(), key=lambda kv: kv[1])
        total = sum(scores.values())
        return plate, round(score / total, 3) if total else 0.0

    def forget(self, track_id: int) -> None:
        self._scores.pop(track_id, None)
        self._reads.pop(track_id, None)


@lru_cache(maxsize=1)
def _reader():
    import easyocr
    return easyocr.Reader(["ko", "en"], gpu=False)


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
        joined_rows.append(("".join(r[1] for r in row), float(np.mean([r[2] for r in row]))))
    seen = {c[0] for c in cands}
    cands += [jr for jr in joined_rows if jr[0] not in seen]
    if len(joined_rows) > 1:
        cands.append(("".join(t for t, _ in joined_rows), float(np.mean([c for _, c in joined_rows]))))
        for a, b in zip(joined_rows, joined_rows[1:]):           # neighbouring rows (two-line plates)
            cands.append((a[0] + b[0], (a[1] + b[1]) / 2))
    return cands


def read_plate(vehicle_crop: np.ndarray, min_conf: float = 0.1, debug: list | None = None) -> tuple[str | None, float]:
    """OCR the lower 60% of a vehicle crop (BGR) and return (plate, confidence).

    Pass a list as `debug` to receive the raw OCR texts (used by --plate-debug).
    """
    h = vehicle_crop.shape[0]
    region = vehicle_crop[int(h * 0.4):, :]
    if region.size == 0:
        return None, 0.0
    if region.shape[1] < 400:                       # small crops: upscale so characters are readable
        scale = 400 / region.shape[1]
        import cv2
        region = cv2.resize(region, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    results = [r for r in _reader().readtext(region) if r[2] >= min_conf]
    if debug is not None:
        debug.extend(f"{r[1]}({r[2]:.2f})" for r in results)
    best: tuple[str | None, float] = (None, 0.0)
    for text, conf in plate_candidates(results):
        plate = normalize_plate(text)
        if plate and conf > best[1]:
            best = (plate, float(conf))
    return best
