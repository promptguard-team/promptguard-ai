"""Split a token sequence into overlapping windows the model can read."""


def split_windows(
    ids: list[int], size: int, overlap: int, max_windows: int
) -> list[list[int]]:
    """Return windows of exactly `size` ids (or one shorter window for short input).

    Consecutive windows share at least `overlap` ids, and the last window ends at the last
    id, so every token is read with some context. Past `max_windows`, the first
    ceil(max/2) and last floor(max/2) windows are kept: injected instructions are
    usually prepended or appended to otherwise harmless text.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if not 0 <= overlap < size:
        raise ValueError("overlap must be in [0, size)")
    if max_windows <= 0:
        raise ValueError("max_windows must be positive")

    if len(ids) <= size:
        return [list(ids)]

    step = size - overlap
    starts = list(range(0, len(ids) - size, step)) + [len(ids) - size]

    if len(starts) > max_windows:
        head = (max_windows + 1) // 2
        tail = max_windows // 2
        starts = starts[:head] + (starts[-tail:] if tail else [])
    return [list(ids[start : start + size]) for start in starts]
