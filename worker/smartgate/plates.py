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


def read_plate(vehicle_crop: np.ndarray, min_conf: float = 0.3) -> tuple[str | None, float]:
    """OCR the lower 60% of a vehicle crop (BGR) and return (plate, confidence)."""
    h = vehicle_crop.shape[0]
    region = vehicle_crop[int(h * 0.4):, :]
    if region.size == 0:
        return None, 0.0
    if region.shape[1] < 400:                       # small crops: upscale so characters are readable
        scale = 400 / region.shape[1]
        import cv2
        region = cv2.resize(region, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    results = [r for r in _reader().readtext(region) if r[2] >= min_conf]
    best: tuple[str | None, float] = (None, 0.0)
    # single boxes first, then the whole line joined left-to-right (plates are often split in two)
    candidates = [(r[1], r[2]) for r in results]
    if len(results) > 1:
        ordered = sorted(results, key=lambda r: r[0][0][0])
        candidates.append(("".join(r[1] for r in ordered), float(np.mean([r[2] for r in ordered]))))
    for text, conf in candidates:
        plate = normalize_plate(text)
        if plate and conf > best[1]:
            best = (plate, float(conf))
    return best
