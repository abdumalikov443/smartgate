import json

import numpy as np
import requests

from smartgate.api_client import ApiClient
from smartgate.detector import LabelVoter, Track
from smartgate.eval_count import accuracy, evaluate
from smartgate.faces import EventGate, FaceMatcher, average_embedding, l2norm

rng = np.random.default_rng(0)


def emb():
    return l2norm(rng.normal(size=512).astype(np.float32))


def test_matcher_recognises_enrolled_and_rejects_strangers():
    alice, bob = emb(), emb()
    m = FaceMatcher(threshold=0.45)
    m.load([{"id": "a", "name": "Alice", "embedding": alice.tolist()},
            {"id": "b", "name": "Bob", "embedding": bob.tolist()},
            {"id": "c", "name": "No face yet", "embedding": None}])
    noisy_alice = l2norm(alice + 0.03 * rng.normal(size=512))
    assert m.match(noisy_alice)[:2] == ("a", "Alice")
    assert m.match(emb())[0] is None                 # random face ~ 0 similarity
    assert m.ids == ["a", "b"]


def test_empty_matcher():
    assert FaceMatcher().match(emb()) == (None, None, 0.0)


def test_average_embedding_is_unit_length():
    avg = average_embedding([emb(), emb(), emb()])
    assert abs(np.linalg.norm(avg) - 1) < 1e-5


def test_event_gate_cooldown():
    t = [0.0]
    g = EventGate(cooldown_s=60, clock=lambda: t[0])
    assert g.allow("a") and not g.allow("a") and g.allow("b")
    t[0] = 61
    assert g.allow("a")


def test_label_voter_keeps_majority():
    v = LabelVoter()
    for label in ["car", "truck", "truck", "car", "truck"]:
        last = v.add(1, label, 0.5)
    assert last == "truck"


def test_track_anchor_is_bottom_centre():
    assert Track(1, "car", 0.9, (10, 20, 30, 100)).anchor == (20, 100.0)


class FakeSession:
    def __init__(self, fail):
        self.fail, self.sent = fail, []

    def post(self, url, json=None, headers=None, timeout=None):
        if self.fail:
            raise requests.ConnectionError("down")
        self.sent.append((url, json))
        return type("R", (), {"raise_for_status": lambda self: None})()


def test_offline_queue_resends_when_api_is_back(tmp_path):
    q = tmp_path / "q.jsonl"
    down = ApiClient("http://api", "k", queue_file=q, session=FakeSession(fail=True))
    assert down.vehicle_event({"n": 1}) is False and down.vehicle_event({"n": 2}) is False
    assert len(q.read_text().splitlines()) == 2
    up_session = FakeSession(fail=False)
    up = ApiClient("http://api", "k", queue_file=q, session=up_session)
    assert up.vehicle_event({"n": 3})
    assert [body["n"] for _, body in up_session.sent] == [3, 1, 2]
    assert not q.exists()


def test_eval_count(tmp_path):
    (tmp_path / "gate1.csv").write_text(
        "frame,track_id,vehicle_type,direction,plate,plate_conf\n"
        "1,1,car,IN,,0\n2,2,car,IN,,0\n3,3,truck,IN,,0\n4,4,car,OUT,,0\n", encoding="utf-8")
    truth = {"gate1.mp4": {"IN": {"car": 2, "truck": 2}, "OUT": {"car": 1}}}
    report = evaluate(truth, tmp_path)
    assert report["gate1.mp4"]["IN"]["accuracy"] == 0.75
    assert report["gate1.mp4"]["OUT"]["accuracy"] == 1.0
    assert report["overall_accuracy"] == 0.8
    assert accuracy(0, 0) == 1.0 and accuracy(3, 0) == 0.0
