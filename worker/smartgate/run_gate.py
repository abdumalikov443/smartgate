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
from pathlib import Path

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


SCREEN_W, SCREEN_H = 1280, 720          # largest window we open on screen


def limit_width(frame, max_width: int):
    """Shrink big videos (4K, 1440p) before processing; 0 keeps the original size."""
    h, w = frame.shape[:2]
    if not max_width or w <= max_width:
        return frame
    scale = max_width / w
    return cv2.resize(frame, (max_width, round(h * scale)), interpolation=cv2.INTER_AREA)


def fit_to_screen(frame):
    """Return (view, scale) so the window fits on a laptop screen."""
    h, w = frame.shape[:2]
    scale = min(1.0, SCREEN_W / w, SCREEN_H / h)
    view = frame if scale == 1.0 else cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return view, scale


def pick_line(frame):
    """Click two points on a screen-sized preview; returns them in frame pixels."""
    view0, scale = fit_to_screen(frame)
    pts = []

    def on_click(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 2:
            pts.append((x, y))

    cv2.namedWindow("pick line")
    cv2.setMouseCallback("pick line", on_click)
    while len(pts) < 2:
        view = view0.copy()
        for p in pts:
            cv2.circle(view, p, 6, (0, 215, 255), -1)
        cv2.putText(view, "click 2 points for the gate line (Esc = cancel)", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 215, 255), 2)
        cv2.imshow("pick line", view)
        if cv2.waitKey(30) == 27:
            raise SystemExit("cancelled")
    cv2.destroyWindow("pick line")
    (ax, ay), (bx, by) = [(round(x / scale), round(y / scale)) for x, y in pts]
    print(f"--line {ax},{ay},{bx},{by}")
    return (ax, ay), (bx, by)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="video file, RTSP url or webcam index")
    ap.add_argument("--line", help="x1,y1,x2,y2 of the gate line in pixels")
    ap.add_argument("--pick-line", action="store_true")
    ap.add_argument("--flip", action="store_true", help="swap IN and OUT")
    ap.add_argument("--margin", type=float, default=12, help="dead zone around the line in pixels (bigger = less double counting)")
    ap.add_argument("--stride", type=int, default=1, help="process every N-th frame (2 = about twice as fast)")
    ap.add_argument("--max-width", type=int, default=1280,
                    help="shrink wider videos to this width before processing (0 = keep original; "
                         "use 0 or 1920 when plates are small). --line is in these pixels.")
    ap.add_argument("--gate", default="main")
    ap.add_argument("--plates", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--min-plate-height", type=int, default=120, help="only OCR vehicles at least this tall (px)")
    ap.add_argument("--plate-every", type=int, default=5, help="OCR a vehicle every N frames")
    ap.add_argument("--plate-debug", help="save the OCR crops and raw OCR text to this folder")
    ap.add_argument("--save", help="write the annotated video here")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--csv", help="also write events to this CSV")
    ap.add_argument("--dry-run", action="store_true", help="do not send events to the API")
    args = ap.parse_args()

    cap = cv2.VideoCapture(int(args.source) if args.source.isdigit() else args.source)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f"cannot read {args.source}")
    orig_h, orig_w = frame.shape[:2]
    preview = limit_width(frame, args.max_width)        # `frame` itself stays full size for plate crops
    if preview.shape[1] != orig_w:
        print(f"video {orig_w}x{orig_h} -> processing at {preview.shape[1]}x{preview.shape[0]} (--max-width)")
    p1, p2 = pick_line(preview) if args.pick_line or not args.line else parse_line(args.line)

    tracker = VehicleTracker(config.YOLO_WEIGHTS)
    counter = LineCounter(p1, p2, margin=args.margin, in_is_positive=not args.flip)
    voter = PlateVoter()
    api = None if args.dry_run else ApiClient(config.API_URL, config.API_KEY)
    writer = None
    if args.save:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps, (preview.shape[1], preview.shape[0]))
    csv_file = open(args.csv, "w", newline="", encoding="utf-8") if args.csv else None
    csv_out = csv.writer(csv_file) if csv_file else None
    if csv_out:
        csv_out.writerow(["frame", "track_id", "vehicle_type", "direction", "plate", "plate_digits", "plate_conf"])

    debug_dir = Path(args.plate_debug) if args.plate_debug else None
    debug_log = None
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)
        debug_log = (debug_dir / "ocr.tsv").open("w", encoding="utf-8")
        debug_log.write("crop\tplate\tdigits\traw_ocr\n")

    counts = {"IN": 0, "OUT": 0}
    plates_seen: dict[int, str] = {}
    n, processed, t0 = 0, 0, time.time()
    t_detect = t_ocr = 0.0
    while ok:
        n += 1
        if (n - 1) % args.stride:
            ok, frame = cap.read()
            continue
        processed += 1
        full = frame                                   # original resolution, used for plate crops
        frame = limit_width(full, args.max_width)
        scale = full.shape[1] / frame.shape[1]
        t = time.time()
        tracks = tracker.update(frame)
        t_detect += time.time() - t
        for tr in tracks:
            x1, y1, x2, y2 = tr.box
            if (args.plates and tr.height >= args.min_plate_height and processed % args.plate_every == 0
                    and voter.wants_more(tr.track_id)):
                t = time.time()
                # detection runs on the small frame; the plate is read from the full-resolution frame
                crop = full[max(0, int(y1 * scale)):int(y2 * scale), max(0, int(x1 * scale)):int(x2 * scale)]
                raw: list[str] = []
                read = read_plate(crop, debug=raw)
                t_ocr += time.time() - t
                if debug_dir:
                    name = f"t{tr.track_id:04d}_f{n:05d}.jpg"
                    cv2.imwrite(str(debug_dir / name), crop[int(crop.shape[0] * 0.4):])
                    debug_log.write(f"{name}\t{read.plate or '-'}\t{read.digits or '-'}\t{' | '.join(raw)}\n")
                    debug_log.flush()
                voter.add(tr.track_id, read.plate, read.conf, read.digits)
                if read.plate or read.digits:
                    best_plate = voter.best(tr.track_id)[0]
                    plates_seen[tr.track_id] = best_plate or f"..{voter.best_digits(tr.track_id)}"
            crossing = counter.update(tr.track_id, tr.anchor)
            if crossing:
                counts[crossing.direction] += 1
                plate, plate_conf = voter.best(tr.track_id)
                digits = voter.best_digits(tr.track_id)
                event = {
                    "gateId": args.gate, "trackId": tr.track_id, "vehicleType": tr.label,
                    "direction": crossing.direction, "plate": plate, "plateDigits": digits,
                    "plateConfidence": plate_conf,
                    "occurredAt": datetime.now(timezone.utc).isoformat(),
                    "snapshot": jpeg_b64(frame[max(0, y1):y2, max(0, x1):x2]),
                }
                print(f"[{n:6d}] {crossing.direction:3s} #{tr.track_id} {tr.label:10s} "
                      f"{plate or (f'..{digits}' if digits else '-')}")
                if api:
                    api.vehicle_event(event)
                if csv_out:
                    csv_out.writerow([n, tr.track_id, tr.label, crossing.direction, plate or "", digits or "", plate_conf])
            if writer or args.show:
                draw_track(frame, tr, plates_seen.get(tr.track_id))
        if writer or args.show:
            draw_line(frame, p1, p2, counts, in_is_positive=not args.flip)
            if writer:
                writer.write(frame)
            if args.show:
                cv2.imshow("SmartGate", fit_to_screen(frame)[0])
                if cv2.waitKey(1) == 27:
                    break
        ok, frame = cap.read()

    elapsed = time.time() - t0
    print(f"\nframes={n}  processed={processed}  fps={processed / elapsed:.1f}  IN={counts['IN']}  OUT={counts['OUT']}")
    print(f"time: detection+tracking {t_detect:.0f}s · plate OCR {t_ocr:.0f}s · other {elapsed - t_detect - t_ocr:.0f}s")
    for f in (writer, cap):
        if f:
            f.release()
    if csv_file:
        csv_file.close()
    if debug_log:
        debug_log.close()
        print(f"plate debug: crops and raw OCR text in {debug_dir}")
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
