import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import game_model as g  # noqa: E402

P = g.P


def test_constants_parsed_from_the_final_sketch():
    assert (P.red_ms, P.green_ms, P.countdown_s) == (3000, 2000, 60)
    assert (P.move_cm, P.win_cm) == (2.5, 5)
    assert (P.mine_level, P.mine_ratio) == (600, 1.10)
    assert (P.top_delay_ms, P.red_delay_ms, P.us_per_cm) == (400, 200, 58.0)


def test_echo_conversion():
    assert g.echo_to_cm(1160) == pytest.approx(20.0)
    assert g.echo_to_cm(0) == 0.0


@pytest.mark.parametrize("a,b,expected", [(50, 50, False), (50, 47.6, False), (50, 47.5, True), (50, 52.4, False), (50, 52.5, True)])
def test_movement_threshold_is_plus_or_minus_2_5_cm(a, b, expected):
    assert g.moved_during_red(a, b) is expected


def test_finish_threshold():
    assert g.reached_finish(5.0) and not g.reached_finish(5.1)


@pytest.mark.parametrize("first,later,expected", [(500, 560, True), (500, 549, False), (601, 900, False), (300, 330, True), (300, 320, False)])
def test_landmine_needs_low_then_10_percent_brighter(first, later, expected):
    assert g.landmine_triggered(first, later) is expected


def test_no_echo_reads_as_a_win_documented_limitation():
    """pulseIn() returns 0 on timeout, so 'no object in front of the sensor' gives 0 cm,
    which satisfies distance <= 5. This follows from the code; it matches the report's note
    about ultrasonic sensitivity but was not observed on hardware."""
    assert g.reached_finish(g.echo_to_cm(0))


def test_light_phases_alternate_and_never_end_early():
    sim = g.simulate()
    states = [s for s, _, _ in sim["phases"]]
    assert states[0] == "RED" and all(a != b for a, b in zip(states, states[1:]))
    for state, start, end in sim["phases"][:-1]:
        nominal = P.red_ms if state == "RED" else P.green_ms
        assert end - start >= nominal


def test_phase_lateness_is_bounded_by_one_loop_pass():
    sim = g.simulate()
    for state, start, end in sim["phases"][:-1]:
        nominal = P.red_ms if state == "RED" else P.green_ms
        pass_ms = sim["red_pass_ms"] if state == "RED" else sim["green_pass_ms"]
        assert end - start - nominal < pass_ms + 1e-6


def test_countdown_runs_slower_than_wall_clock():
    """lastSecond is reset to the current time, not advanced by 1000, and checks happen once per
    pass (~0.4 to 0.6 s), so each displayed second lasts more than one real second."""
    sim = g.simulate(game_s=200)
    assert sim["countdown_real_s"] > 60 * 1.1
    gaps = [b[0] - a[0] for a, b in zip(sim["ticks"], sim["ticks"][1:])]
    assert min(gaps) >= 1.0


def test_minimum_detectable_speed():
    assert g.min_detectable_speed_cm_s() == pytest.approx(2.5 / 0.403, rel=1e-3)
