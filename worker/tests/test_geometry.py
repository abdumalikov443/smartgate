from smartgate.geometry import LineCounter, side_of_line, within_segment


def walk(counter, track_id, points):
    return [c for p in points if (c := counter.update(track_id, p))]


def test_crossing_down_is_in_and_up_is_out():
    c = LineCounter((0, 100), (200, 100))           # horizontal gate at y=100
    down = walk(c, 1, [(100, 60), (100, 90), (100, 120), (100, 140)])
    up = walk(c, 2, [(100, 140), (100, 110), (100, 80)])
    assert [x.direction for x in down] == ["IN"]
    assert [x.direction for x in up] == ["OUT"]


def test_flip_swaps_directions():
    c = LineCounter((0, 100), (200, 100), in_is_positive=False)
    assert walk(c, 1, [(100, 60), (100, 140)])[0].direction == "OUT"


def test_jitter_inside_dead_zone_is_ignored():
    c = LineCounter((0, 100), (200, 100), margin=12)
    assert walk(c, 1, [(100, 80), (100, 95), (100, 106), (100, 92), (100, 110)]) == []


def test_each_track_is_counted_only_once():
    # a box wobbling back over the line right after crossing must not add an OUT
    c = LineCounter((0, 100), (200, 100))
    events = walk(c, 7, [(100, 60), (100, 140), (100, 60), (100, 140)])
    assert [e.direction for e in events] == ["IN"]
    assert [e.direction for e in walk(c, 8, [(100, 140), (100, 60)])] == ["OUT"]


def test_crossing_outside_the_segment_is_ignored():
    c = LineCounter((0, 100), (200, 100))
    assert walk(c, 1, [(400, 60), (400, 140)]) == []


def test_helpers():
    assert side_of_line((0, 0), (10, 0), (5, 5)) > 0 > side_of_line((0, 0), (10, 0), (5, -5))
    assert within_segment((0, 0), (10, 0), (5, 3)) and not within_segment((0, 0), (10, 0), (20, 0))


def test_in_arrow_points_the_way_that_counts_as_in():
    from smartgate.geometry import in_direction
    for p1, p2 in [((0, 100), (200, 100)), ((200, 100), (0, 100)), ((50, 0), (60, 300))]:
        for positive in (True, False):
            c = LineCounter(p1, p2, in_is_positive=positive)
            dx, dy = in_direction(p1, p2, positive)
            mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
            start = (mid[0] - dx * 50, mid[1] - dy * 50)
            end = (mid[0] + dx * 50, mid[1] + dy * 50)
            assert walk(c, 1, [start, end])[0].direction == "IN"
