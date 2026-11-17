import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

API_URL = os.getenv("SMARTGATE_API_URL", "http://localhost:3000")
API_KEY = os.getenv("SMARTGATE_API_KEY", "change-me")
YOLO_WEIGHTS = os.getenv("SMARTGATE_YOLO", "yolo11n.pt")
FACE_THRESHOLD = float(os.getenv("SMARTGATE_FACE_THRESHOLD", "0.45"))
