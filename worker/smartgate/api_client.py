"""HTTP client for the SmartGate NestJS API, with an offline queue.

If the API is down, events are appended to a local JSONL file and re-sent
the next time a request succeeds, so no gate event is lost.
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)


def jpeg_b64(image, max_side: int = 360) -> str | None:
    """Encode a BGR crop as a small base64 JPEG for the event snapshot."""
    if image is None or getattr(image, "size", 0) == 0:
        return None
    import cv2
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1:
        image = cv2.resize(image, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf.tobytes()).decode() if ok else None


class ApiClient:
    def __init__(self, base_url: str, api_key: str, queue_file: str | Path = "pending_events.jsonl",
                 session=None, timeout: float = 5.0):
        self.base = base_url.rstrip("/")
        self.headers = {"x-api-key": api_key}
        self.queue = Path(queue_file)
        self.http = session or requests.Session()
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> bool:
        try:
            r = self.http.post(self.base + path, json=payload, headers=self.headers, timeout=self.timeout)
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            log.warning("API %s failed (%s) - queued", path, e)
            return False

    def send(self, path: str, payload: dict) -> bool:
        if self._post(path, payload):
            self.flush()
            return True
        with self.queue.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"path": path, "payload": payload}, ensure_ascii=False) + "\n")
        return False

    def flush(self) -> int:
        """Re-send queued events; keep the ones that still fail."""
        if not self.queue.exists():
            return 0
        lines = [json.loads(l) for l in self.queue.read_text(encoding="utf-8").splitlines() if l.strip()]
        left = [item for item in lines if not self._post(item["path"], item["payload"])]
        if left:
            self.queue.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in left), encoding="utf-8")
        else:
            self.queue.unlink()
        return len(lines) - len(left)

    def vehicle_event(self, event: dict) -> bool:
        return self.send("/api/vehicle-events", event)

    def face_event(self, event: dict) -> bool:
        return self.send("/api/face-events", event)

    def enroll(self, employee_id: str, embedding: list[float]) -> None:
        r = self.http.post(f"{self.base}/api/employees/{employee_id}/face", json={"embedding": embedding},
                           headers=self.headers, timeout=self.timeout)
        r.raise_for_status()

    def employee_embeddings(self) -> list[dict]:
        r = self.http.get(f"{self.base}/api/employees/embeddings", headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()
