"""Bringing the game window to the front: the waiting rules (no window is touched)."""

from oldschool.player import focus


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(find, front, wait=10.0, stable=1.0):
    clock, forced = Clock(), []
    ok = focus._loop(find, front, forced.append, wait, stable, clock=clock, sleep=clock.sleep)
    return ok, forced, clock.t


def test_waits_for_the_window_then_brings_it_once():
    clock_window = {"front": 1}
    t = {"n": 0}

    def find():
        t["n"] += 1
        return 7 if t["n"] > 4 else None  # the game opens its window after a second

    def front():
        return clock_window["front"]

    ok, forced, _ = run(find, front, stable=1.0)
    assert not ok and forced  # never came to the front: kept trying until the end
    clock_window["front"] = 7
    t["n"] = 0
    ok, forced, elapsed = run(find, front, stable=1.0)
    assert ok and forced == [] and elapsed < 3  # already in front: nothing to do, stops after 1 s


def test_stops_once_it_stays_in_front():
    state = {"front": 1}

    def force(hwnd):
        state["front"] = hwnd

    clock = Clock()
    ok = focus._loop(lambda: 9, lambda: state["front"], force, 10.0, 1.0, clock=clock, sleep=clock.sleep)
    assert ok and state["front"] == 9 and clock.t < 2


def test_no_game_window_gives_up():
    ok, forced, elapsed = run(lambda: None, lambda: 1, wait=5.0)
    assert not ok and forced == [] and elapsed >= 5.0
