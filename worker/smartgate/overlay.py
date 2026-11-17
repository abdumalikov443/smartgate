"""Drawing helpers for the annotated output video."""
import cv2

COLORS = {"car": (80, 200, 120), "truck": (40, 150, 255), "bus": (230, 160, 40), "motorcycle": (200, 90, 220)}


def draw_line(frame, p1, p2, counts: dict[str, int]):
    cv2.line(frame, tuple(map(int, p1)), tuple(map(int, p2)), (0, 215, 255), 3)
    text = f"IN {counts.get('IN', 0)}   OUT {counts.get('OUT', 0)}"
    cv2.rectangle(frame, (10, 10), (330, 56), (20, 20, 20), -1)
    cv2.putText(frame, text, (22, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)


def draw_track(frame, track, plate: str | None = None):
    x1, y1, x2, y2 = track.box
    color = COLORS.get(track.label, (200, 200, 200))
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    label = f"#{track.track_id} {track.label}" + (f" {plate}" if plate else "")
    # cv2 cannot draw Hangul; show the plate digits only on the video, the full plate goes to the API
    label = label.encode("ascii", "replace").decode().replace("?", "*")
    cv2.putText(frame, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)


def draw_face(frame, box, name: str | None, sim: float):
    x1, y1, x2, y2 = box
    color = (80, 200, 120) if name else (60, 60, 230)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"{name} {sim:.2f}" if name else f"UNKNOWN {sim:.2f}"
    cv2.putText(frame, text.encode("ascii", "replace").decode(), (x1, max(18, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
