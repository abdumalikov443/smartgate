"""Virtual gate line: decide when a tracked object crosses it and in which direction."""
from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float]


@dataclass
class Crossing:
    track_id: int
    direction: str          # "IN" or "OUT"
    point: Point


def side_of_line(p1: Point, p2: Point, p: Point) -> float:
    """Signed distance-like value: > 0 on one side of the line p1->p2, < 0 on the other."""
    (x1, y1), (x2, y2), (x, y) = p1, p2, p
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1.0
    return ((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) / length


def within_segment(p1: Point, p2: Point, p: Point, slack: float = 0.05) -> bool:
    """True if the projection of p falls between p1 and p2 (with a little slack at the ends)."""
    (x1, y1), (x2, y2), (x, y) = p1, p2, p
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy or 1.0
    t = ((x - x1) * dx + (y - y1) * dy) / denom
    return -slack <= t <= 1 + slack


@dataclass
class LineCounter:
    """Counts objects crossing the segment p1->p2.

    Crossing from the negative side to the positive side is "IN" (flip with
    `in_is_positive=False`). A dead zone of `margin` pixels around the line
    ignores jitter, and each track is counted only once: a vehicle passes a
    gate once, so a box wobbling back over the line must not add an OUT
    right after its IN.
    """
    p1: Point
    p2: Point
    margin: float = 12.0
    in_is_positive: bool = True
    _last_side: dict[int, int] = field(default_factory=dict)
    _counted: set[int] = field(default_factory=set)

    def update(self, track_id: int, point: Point) -> Crossing | None:
        if track_id in self._counted:
            return None
        d = side_of_line(self.p1, self.p2, point)
        if abs(d) < self.margin:
            return None                       # inside the dead zone: keep the previous side
        side = 1 if d > 0 else -1
        prev = self._last_side.get(track_id)
        self._last_side[track_id] = side
        if prev is None or prev == side or not within_segment(self.p1, self.p2, point):
            return None
        direction = "IN" if (side > 0) == self.in_is_positive else "OUT"
        self._counted.add(track_id)
        return Crossing(track_id, direction, point)

    def forget(self, track_id: int) -> None:
        self._last_side.pop(track_id, None)
