"""Vehicle gate camera: count vehicles crossing a line, read plates, send events.

    python -m smartgate.run_gate --source videos/gate.mp4 --line 100,500,1180,500 --save out.mp4
    python -m smartgate.run_gate --source rtsp://user:pass@camera/stream --gate main
    python -m smartgate.run_gate --source videos/gate.mp4 --line ... --dry-run --csv events.csv

--line x1,y1,x2,y2 is the virtual gate in pixels. Use --pick-line to click it
on the first frame instead. Crossing from one side to the other is IN; add
--flip if your camera sees it the other way round.
"""
from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime, timezone

import cv2

from . import config
from .api_client import ApiClient, jpeg_b64
from .detector import VehicleTracker
from .geometry import LineCounter
from .overlay import draw_line, draw_track
from .plates import PlateVoter, read_plate


def parse_line(text: str):
    x1, y1, x2, y2 = (float(v) for v in text.split(","))
    return (x1, y1), (x2, y2)


def pick_line(frame):
    pts = []

    def on_click(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 2:
            pts.append((x, y))

    cv2.namedWindow("pick line")
    cv2.setMouseCallback("pick line", on_click)
    while len(pts) < 2:
        view = frame.copy()
        for p in pts:
            cv2.circle(view, p, 6, (0, 215, 255), -1)
        cv2.putText(view, "click 2 points for the gate line", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 215, 255), 2)
        cv2.imshow("pick line", view)
        if cv2.waitKey(30) == 27:
            raise SystemExit("cancelled")
    cv2.destroyWindow("pick line")
    print(f"--line {pts[0][0]},{pts[0][1]},{pts[1][0]},{pts[1][1]}")
    return pts[0], pts[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="video file, RTSP url or webcam index")
    ap.add_argument("--line", help="x1,y1,x2,y2 of the gate line in pixels")
    ap.add_argument("--pick-line", action="store_true")
    ap.add_argument("--flip", action="store_true", help="swap IN and OUT")
    ap.add_argument("--gate", default="main")
    ap.add_argument("--plates", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--min-plate-height", type=int, default=120, help="only OCR vehicles at least this tall (px)")
    ap.add_argument("--plate-every", type=int, default=5, help="OCR a vehicle every N frames")
    ap.add_argument("--save", help="write the annotated video here")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--csv", help="also write events to this CSV")
    ap.add_argument("--dry-run", action="store_true", help="do not send events to the API")
    args = ap.parse_args()

    cap = cv2.VideoCapture(int(args.source) if args.source.isdigit() else args.source)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f"cannot read {args.source}")
    p1, p2 = pick_line(frame) if args.pick_line or not args.line else parse_line(args.line)

    tracker = VehicleTracker(config.YOLO_WEIGHTS)
    counter = LineCounter(p1, p2, in_is_positive=not args.flip)
    voter = PlateVoter()
    api = None if args.dry_run else ApiClient(config.API_URL, config.API_KEY)
    writer = None
    if args.save:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps, (frame.shape[1], frame.shape[0]))
    csv_file = open(args.csv, "w", newline="", encoding="utf-8") if args.csv else None
    csv_out = csv.writer(csv_file) if csv_file else None
    if csv_out:
        csv_out.writerow(["frame", "track_id", "vehicle_type", "direction", "plate", "plate_conf"])

    counts = {"IN": 0, "OUT": 0}
    plates_seen: dict[int, str] = {}
    n, t0 = 0, time.time()
    while ok:
        n += 1
        for tr in tracker.update(frame):
            x1, y1, x2, y2 = tr.box
            if (args.plates and tr.height >= args.min_plate_height and n % args.plate_every == 0
                    and voter.wants_more(tr.track_id)):
                plate, conf = read_plate(frame[max(0, y1):y2, max(0, x1):x2])
                voter.add(tr.track_id, plate, conf)
                if plate:
                    plates_seen[tr.track_id] = voter.best(tr.track_id)[0]
            crossing = counter.update(tr.track_id, tr.anchor)
            if crossing:
                counts[crossing.direction] += 1
                plate, plate_conf = voter.best(tr.track_id)
                event = {
                    "gateId": args.gate, "trackId": tr.track_id, "vehicleType": tr.label,
                    "direction": crossing.direction, "plate": plate, "plateConfidence": plate_conf,
                    "occurredAt": datetime.now(timezone.utc).isoformat(),
                    "snapshot": jpeg_b64(frame[max(0, y1):y2, max(0, x1):x2]),
                }
                print(f"[{n:6d}] {crossing.direction:3s} #{tr.track_id} {tr.label:10s} {plate or '-'}")
                if api:
                    api.vehicle_event(event)
                if csv_out:
                    csv_out.writerow([n, tr.track_id, tr.label, crossing.direction, plate or "", plate_conf])
            if writer or args.show:
                draw_track(frame, tr, plates_seen.get(tr.track_id))
        if writer or args.show:
            draw_line(frame, p1, p2, counts)
            if writer:
                writer.write(frame)
            if args.show:
                cv2.imshow("SmartGate", frame)
                if cv2.waitKey(1) == 27:
                    break
        ok, frame = cap.read()

    elapsed = time.time() - t0
    print(f"\nframes={n}  fps={n / elapsed:.1f}  IN={counts['IN']}  OUT={counts['OUT']}")
    for f in (writer, cap):
        if f:
            f.release()
    if csv_file:
        csv_file.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
