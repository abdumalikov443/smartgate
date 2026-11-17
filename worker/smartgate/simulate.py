"""Send realistic demo events to the API so the dashboard can be tried without cameras.

    python -m smartgate.simulate --vehicles 120 --face-events 40

Vehicle plates are random but valid Korean formats; every vehicle that goes
IN later comes OUT (some stay inside), so dwell times and "inside now" work.
Face events use the employees already registered in the API.
"""
import argparse
import random
from datetime import datetime, timedelta, timezone

import requests

from . import config

KST = timezone(timedelta(hours=9))
LETTERS = "가나다라마거너더러머고노도로모구누두루무바사아자배하허호"


def random_plate():
    return f"{random.randint(10, 399)}{random.choice(LETTERS)}{random.randint(1000, 9999)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vehicles", type=int, default=120)
    ap.add_argument("--face-events", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    random.seed(args.seed)
    headers = {"x-api-key": config.API_KEY}
    post = lambda path, body: requests.post(config.API_URL + path, json=body, headers=headers, timeout=5).raise_for_status()

    today = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    now = datetime.now(KST)
    events = []
    for i in range(args.vehicles):
        kind = random.choices(["car", "truck", "bus", "motorcycle"], weights=[60, 28, 5, 7])[0]
        hour = random.choices(range(6, 21), weights=[2, 6, 9, 8, 6, 5, 6, 7, 6, 5, 6, 7, 5, 3, 2])[0]
        t_in = today + timedelta(hours=hour, minutes=random.randint(0, 59))
        if t_in > now:
            continue
        plate = random_plate() if random.random() < 0.85 else None   # some plates are unreadable
        events.append((t_in, kind, "IN", plate))
        stay = timedelta(minutes=random.randint(15, 240) if kind == "truck" else random.randint(10, 480))
        if t_in + stay < now and random.random() < 0.9:
            events.append((t_in + stay, kind, "OUT", plate))
    for i, (t, kind, direction, plate) in enumerate(sorted(events)):
        post("/api/vehicle-events", {"gateId": "main", "trackId": i, "vehicleType": kind, "direction": direction,
                                     "plate": plate, "plateConfidence": round(random.uniform(0.6, 0.98), 2) if plate else 0,
                                     "occurredAt": t.astimezone(timezone.utc).isoformat()})
    print(f"sent {len(events)} vehicle events")

    employees = requests.get(config.API_URL + "/api/employees", timeout=5).json()
    sent = 0
    for e in employees:
        start = today + timedelta(hours=8, minutes=random.randint(30, 75))
        for k in range(max(2, args.face_events // max(len(employees), 1))):
            t = start + timedelta(minutes=k * random.randint(40, 90))
            if t > now:
                break
            post("/api/face-events", {"cameraId": "entrance", "employeeId": e["id"],
                                      "similarity": round(random.uniform(0.5, 0.8), 3),
                                      "occurredAt": t.astimezone(timezone.utc).isoformat()})
            sent += 1
    for _ in range(3):
        t = today + timedelta(hours=random.randint(9, 18), minutes=random.randint(0, 59))
        if t < now:
            post("/api/face-events", {"cameraId": "entrance", "employeeId": None, "similarity": 0.21,
                                      "occurredAt": t.astimezone(timezone.utc).isoformat()})
            sent += 1
    print(f"sent {sent} face events for {len(employees)} employees")


if __name__ == "__main__":
    main()
