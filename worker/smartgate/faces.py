"""Face detection + recognition with InsightFace (RetinaFace + ArcFace).

Only 512-number embeddings are compared and stored - never face photos of
employees. A face is "known" when its cosine similarity to an enrolled
employee is above the threshold.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np


@dataclass
class Face:
    box: tuple[int, int, int, int]
    embedding: np.ndarray            # L2-normalised, shape (512,)
    det_score: float


def l2norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n == 0, 1, n)


class FaceEngine:
    def __init__(self, model: str = "buffalo_l", det_size: int = 640, min_face: int = 60):
        from insightface.app import FaceAnalysis        # downloads the model pack on first use
        self.app = FaceAnalysis(name=model, providers=["CPUExecutionProvider"])
        self.app.prepare(ctx_id=-1, det_size=(det_size, det_size))
        self.min_face = min_face

    def faces(self, frame: np.ndarray) -> list[Face]:
        out = []
        for f in self.app.get(frame):
            x1, y1, x2, y2 = (int(v) for v in f.bbox)
            if min(x2 - x1, y2 - y1) < self.min_face:
                continue                                  # too small to recognise reliably
            out.append(Face((x1, y1, x2, y2), l2norm(f.normed_embedding), float(f.det_score)))
        return out


class FaceMatcher:
    """Nearest enrolled employee by cosine similarity."""

    def __init__(self, threshold: float = 0.45):
        self.threshold = threshold
        self.ids: list[str] = []
        self.names: list[str] = []
        self.matrix = np.zeros((0, 512), dtype=np.float32)

    def load(self, employees: list[dict]) -> None:
        """`employees`: [{"id", "name", "embedding": [512 floats]}] from the API."""
        valid = [e for e in employees if e.get("embedding")]
        self.ids = [e["id"] for e in valid]
        self.names = [e["name"] for e in valid]
        self.matrix = l2norm(np.array([e["embedding"] for e in valid], dtype=np.float32)) if valid \
            else np.zeros((0, 512), dtype=np.float32)

    def match(self, embedding: np.ndarray) -> tuple[str | None, str | None, float]:
        if len(self.ids) == 0:
            return None, None, 0.0
        sims = self.matrix @ l2norm(embedding)
        i = int(np.argmax(sims))
        sim = float(sims[i])
        if sim < self.threshold:
            return None, None, sim
        return self.ids[i], self.names[i], sim


class EventGate:
    """Avoid sending the same face event every frame: one event per key per cooldown."""

    def __init__(self, cooldown_s: float = 60.0, clock=time.monotonic):
        self.cooldown_s, self.clock = cooldown_s, clock
        self._last: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = self.clock()
        if now - self._last.get(key, -1e18) < self.cooldown_s:
            return False
        self._last[key] = now
        return True


def average_embedding(embeddings: list[np.ndarray]) -> np.ndarray:
    """Enrolment: average several photos of one person into a single template."""
    return l2norm(np.mean(l2norm(np.stack(embeddings)), axis=0))
