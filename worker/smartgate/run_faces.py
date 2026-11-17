"""Entrance camera: recognise employees for attendance and alert on unknown people.

    python -m smartgate.run_faces --source 0            # laptop webcam
    python -m smartgate.run_faces --source rtsp://...   # IP camera
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

import cv2

from . import config
from .api_client import ApiClient, jpeg_b64
from .faces import EventGate, FaceEngine, FaceMatcher
from .overlay import draw_face


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="0")
    ap.add_argument("--camera", default="entrance")
    ap.add_argument("--every", type=int, default=3, help="analyse every N-th frame")
    ap.add_argument("--unknown-frames", type=int, default=5,
                    help="a face must stay unknown this many analysed frames before an alert")
    ap.add_argument("--reload", type=float, default=60, help="reload enrolled employees every N seconds")
    ap.add_argument("--no-show", action="store_true")
    args = ap.parse_args()

    api = ApiClient(config.API_URL, config.API_KEY)
    engine = FaceEngine()
    matcher = FaceMatcher(config.FACE_THRESHOLD)
    known_gate, unknown_gate = EventGate(cooldown_s=60), EventGate(cooldown_s=30)
    unknown_streak, last_reload, n = 0, 0.0, 0

    cap = cv2.VideoCapture(int(args.source) if args.source.isdigit() else args.source)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        if time.time() - last_reload > args.reload:
            matcher.load(api.employee_embeddings())
            last_reload = time.time()
            print(f"loaded {len(matcher.ids)} enrolled employees")
        if n % args.every:
            continue
        faces = engine.faces(frame)
        any_unknown = False
        for face in faces:
            emp_id, name, sim = matcher.match(face.embedding)
            x1, y1, x2, y2 = face.box
            now = datetime.now(timezone.utc).isoformat()
            if emp_id:
                if known_gate.allow(emp_id):
                    api.face_event({"cameraId": args.camera, "employeeId": emp_id, "similarity": round(sim, 3),
                                    "occurredAt": now})
                    print(f"{now}  {name}  sim={sim:.2f}")
            else:
                any_unknown = True
                if unknown_streak >= args.unknown_frames and unknown_gate.allow("unknown"):
                    api.face_event({"cameraId": args.camera, "employeeId": None, "similarity": round(sim, 3),
                                    "occurredAt": now, "snapshot": jpeg_b64(frame[max(0, y1):y2, max(0, x1):x2])})
                    print(f"{now}  UNKNOWN person alert")
            if not args.no_show:
                draw_face(frame, face.box, name, sim)
        unknown_streak = unknown_streak + 1 if any_unknown else 0
        if not args.no_show:
            cv2.imshow("SmartGate faces", frame)
            if cv2.waitKey(1) == 27:
                break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
