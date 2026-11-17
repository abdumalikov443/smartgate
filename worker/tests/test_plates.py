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
