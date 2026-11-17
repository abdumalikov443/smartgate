"""YOLO11 + ByteTrack wrapper that returns tracked vehicles for each frame."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np

# COCO class ids used by the pretrained YOLO models
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


@dataclass
class Track:
    track_id: int
    label: str
    conf: float
    box: tuple[int, int, int, int]         # x1, y1, x2, y2

    @property
    def anchor(self) -> tuple[float, float]:
        """Bottom-centre of the box: where the vehicle touches the ground."""
        x1, _, x2, y2 = self.box
        return (x1 + x2) / 2, float(y2)

    @property
    def height(self) -> int:
        return self.box[3] - self.box[1]


class LabelVoter:
    """The detector may call the same vehicle 'car' in one frame and 'truck' in the next;
    keep the majority label per track."""

    def __init__(self):
        self._votes: dict[int, Counter] = defaultdict(Counter)

    def add(self, track_id: int, label: str, conf: float) -> str:
        self._votes[track_id][label] += conf
        return self._votes[track_id].most_common(1)[0][0]

    def forget(self, track_id: int) -> None:
        self._votes.pop(track_id, None)


class VehicleTracker:
    def __init__(self, weights: str = "yolo11n.pt", conf: float = 0.35, imgsz: int = 640):
        from ultralytics import YOLO          # downloads the weights on first use
        self.model = YOLO(weights)
        self.conf, self.imgsz = conf, imgsz
        self.labels = LabelVoter()

    def update(self, frame: np.ndarray) -> list[Track]:
        result = self.model.track(frame, persist=True, tracker="bytetrack.yaml", conf=self.conf,
                                  imgsz=self.imgsz, classes=list(VEHICLE_CLASSES), verbose=False)[0]
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            return []
        tracks = []
        for xyxy, tid, cls, conf in zip(boxes.xyxy.cpu().numpy(), boxes.id.int().cpu().tolist(),
                                        boxes.cls.int().cpu().tolist(), boxes.conf.cpu().tolist()):
            label = self.labels.add(tid, VEHICLE_CLASSES.get(cls, "car"), conf)
            x1, y1, x2, y2 = (int(v) for v in xyxy)
            tracks.append(Track(tid, label, float(conf), (x1, y1, x2, y2)))
        return tracks
