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


def test_plate_digits_fallback_when_the_letter_is_misread():
    from smartgate.plates import plate_digits
    assert plate_digits("3242641") == "2641"        # 배 read as 4
    assert plate_digits("'2u2641") is None          # only 5 digits: too unsure
    assert plate_digits("2261") is None
    assert plate_digits("12345678901") is None      # too long to be a plate


def test_best_read_prefers_a_full_plate_over_digits():
    from smartgate.plates import best_read
    r = best_read([(box(0, 0), "3242641", 0.94), (box(0, 40), "32배2641", 0.5)])
    assert (r.plate, r.digits) == ("32배2641", "2641")
    r = best_read([(box(0, 0), "3242641", 0.94)])
    assert (r.plate, r.digits) == (None, "2641")


def test_voter_keeps_digits_when_no_full_plate():
    v = PlateVoter()
    v.add(1, None, 0.9, "2641")
    v.add(1, None, 0.3, "2647")
    assert v.best(1) == (None, 0.0) and v.best_digits(1) == "2641"
    v.add(2, "12가3456", 0.8)
    assert v.best_digits(2) == "3456"


def test_locate_plates_finds_a_yellow_plate():
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    from smartgate.plates import locate_plates
    img = np.full((300, 700, 3), 90, np.uint8)                       # grey car body
    cv2.rectangle(img, (420, 150), (560, 185), (40, 200, 230), -1)    # yellow plate (BGR), ratio 4:1
    cv2.putText(img, "32 2641", (430, 178), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    boxes = locate_plates(img)
    assert boxes and abs(boxes[0][0] - 420) < 10 and abs(boxes[0][2] - 140) < 15
