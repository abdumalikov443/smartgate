"""Enrol an employee's face from 3-5 photos (the employee must have given consent).

    python -m smartgate.enroll --employee <id> --images photos/asadbek/

Photos are read locally; only the averaged 512-number embedding is sent to
the API. The photos themselves are never uploaded.
"""
import argparse
from pathlib import Path

import cv2

from . import config
from .api_client import ApiClient
from .faces import FaceEngine, average_embedding


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--employee", required=True, help="employee id from the API")
    ap.add_argument("--images", required=True, type=Path)
    args = ap.parse_args()

    engine = FaceEngine(min_face=40)
    embeddings = []
    for path in sorted(args.images.iterdir()):
        img = cv2.imread(str(path))
        if img is None:
            continue
        faces = engine.faces(img)
        if not faces:
            print(f"skip {path.name}: no face found")
            continue
        biggest = max(faces, key=lambda f: (f.box[2] - f.box[0]) * (f.box[3] - f.box[1]))
        embeddings.append(biggest.embedding)
        print(f"ok   {path.name}")
    if len(embeddings) < 2:
        raise SystemExit("need at least 2 photos with a clear face")
    ApiClient(config.API_URL, config.API_KEY).enroll(args.employee, average_embedding(embeddings).tolist())
    print(f"enrolled from {len(embeddings)} photos")


if __name__ == "__main__":
    main()
