import pytest

from app.windows import split_windows


def test_empty_input_is_one_empty_window():
    assert split_windows([], size=4, overlap=1, max_windows=8) == [[]]


@pytest.mark.parametrize("ids", [[1, 2, 3], [1, 2, 3, 4]])
def test_input_that_fits_is_one_window(ids):
    assert split_windows(ids, size=4, overlap=1, max_windows=8) == [ids]


def test_long_input_gets_full_overlapping_windows_ending_at_the_last_token():
    ids = list(range(10))

    windows = split_windows(ids, size=4, overlap=1, max_windows=8)

    assert windows == [[0, 1, 2, 3], [3, 4, 5, 6], [6, 7, 8, 9]]


def test_last_window_is_aligned_to_the_end_rather_than_short():
    windows = split_windows(list(range(11)), size=4, overlap=1, max_windows=8)

    assert windows[-1] == [7, 8, 9, 10]
    assert all(len(w) == 4 for w in windows)


def test_every_token_is_covered():
    ids = list(range(57))

    windows = split_windows(ids, size=10, overlap=3, max_windows=100)

    assert set().union(*map(set, windows)) == set(ids)


def test_over_the_cap_keeps_head_and_tail_windows():
    windows = split_windows(list(range(100)), size=10, overlap=0, max_windows=4)

    assert [w[0] for w in windows] == [0, 10, 80, 90]


def test_an_odd_cap_favours_the_head():
    windows = split_windows(list(range(100)), size=10, overlap=0, max_windows=3)

    assert [w[0] for w in windows] == [0, 10, 90]


def test_a_cap_of_one_keeps_the_first_window():
    assert split_windows(list(range(100)), size=10, overlap=0, max_windows=1) == [
        list(range(10))
    ]


@pytest.mark.parametrize(
    ("size", "overlap", "max_windows"),
    [(0, 0, 1), (4, 4, 1), (4, -1, 1), (4, 1, 0)],
)
def test_invalid_parameters_are_rejected(size, overlap, max_windows):
    with pytest.raises(ValueError):
        split_windows([1, 2, 3], size=size, overlap=overlap, max_windows=max_windows)


def test_cap_with_overlap_keeps_head_and_tail_windows():
    windows = split_windows(list(range(100)), size=10, overlap=2, max_windows=4)

    assert [w[0] for w in windows] == [0, 8, 88, 90]


@pytest.mark.parametrize("size", range(2, 12))
@pytest.mark.parametrize("overlap_pct", [0, 25, 50, 90])
@pytest.mark.parametrize("length", [1, 7, 33, 100])
def test_consecutive_windows_share_at_least_the_overlap(size, overlap_pct, length):
    overlap = size * overlap_pct // 100
    windows = split_windows(list(range(length)), size, overlap, max_windows=1000)

    for left, right in zip(windows, windows[1:]):
        assert len(set(left) & set(right)) >= overlap
