import pytest

from smartgate.plates import PlateVoter, normalize_plate


@pytest.mark.parametrize("raw,plate", [
    ("12가 3456", "12가3456"),
    ("123나4567", "123나4567"),
    ("서울 12 가 3456", "서울12가3456"),
    ("l2가34S6", "12가3456"),            # OCR confusions l->1, S->5
    ("[ 67허 1234 ]", "67허1234"),
])
def test_valid_plates(raw, plate):
    assert normalize_plate(raw) == plate


@pytest.mark.parametrize("raw", ["SAMSUNG", "1234", "가나다", "12가34", ""])
def test_invalid_text_is_rejected(raw):
    assert normalize_plate(raw) is None


def test_voter_picks_the_most_confident_plate():
    v = PlateVoter(max_reads=5)
    for plate, conf in [("12가3456", 0.6), ("12가3458", 0.4), ("12가3456", 0.7), (None, 0.0)]:
        v.add(1, plate, conf)
    plate, share = v.best(1)
    assert plate == "12가3456" and 0.7 < share < 0.8
    assert v.wants_more(1)
    v.add(1, None, 0)
    assert not v.wants_more(1)


def test_voter_without_reads():
    assert PlateVoter().best(99) == (None, 0.0)


def box(x, y, w=60, h=30):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def best_plate(results):
    from smartgate.plates import normalize_plate, plate_candidates
    found = [(normalize_plate(t), c) for t, c in plate_candidates(results)]
    found = [f for f in found if f[0]]
    return max(found, key=lambda f: f[1])[0] if found else None


def test_plate_split_into_two_boxes_on_one_line():
    results = [(box(200, 50), "3456", 0.9), (box(100, 52), "12가", 0.6)]       # right part read first
    assert best_plate(results) == "12가3456"


def test_two_line_old_style_plate():
    results = [(box(100, 10), "서울12", 0.7), (box(100, 60), "가3456", 0.8)]
    assert best_plate(results) == "서울12가3456"


def test_noise_text_around_the_plate_is_ignored():
    results = [(box(10, 5), "HYUNDAI", 0.9), (box(100, 60), "123나", 0.5), (box(170, 61), "4567", 0.8),
               (box(300, 120), "SONATA", 0.9)]
    assert best_plate(results) == "123나4567"


def test_no_text_gives_no_candidates():
    from smartgate.plates import plate_candidates
    assert plate_candidates([]) == []
