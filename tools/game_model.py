"""Host-side model of the Red Light - Green Light sketch.

Constants are parsed from firmware/red_light_green_light/red_light_green_light.ino so the
model cannot silently drift from the code. The model reproduces the decision rules and the
loop timing (blocking delays, millis() checks). It is an analysis of the code, not a
measurement of the hardware.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SKETCH = Path(__file__).resolve().parents[1] / "firmware/red_light_green_light/red_light_green_light.ino"


def _num(pattern: str, src: str) -> float:
    m = re.search(pattern, src)
    if not m:
        raise ValueError(f"pattern not found in sketch: {pattern}")
    return float(m.group(1))


@dataclass(frozen=True)
class Params:
    red_ms: float          # interval used after GREEN -> RED (and initial interval)
    green_ms: float        # interval used after RED -> GREEN
    countdown_s: float     # initial timer value
    move_cm: float         # distance change that counts as movement
    win_cm: float          # distance at or below which the player "wins"
    mine_level: float      # photoresistor reading must be at or below this to arm
    mine_ratio: float      # later reading must be at least this multiple of the first
    top_delay_ms: float    # delay() at the top of every loop() pass
    red_delay_ms: float    # delay() inside the red-light movement check
    us_per_cm: float       # round-trip echo microseconds per centimetre


def load_params(path: Path = SKETCH) -> Params:
    src = path.read_text()
    return Params(
        red_ms=_num(r"unsigned long interval = (\d+);", src),
        green_ms=_num(r"RED -> GREEN\s*canMove = true;\s*interval = (\d+);", src),
        countdown_s=_num(r"int timer = (\d+);", src),
        move_cm=_num(r"cur_distance \+ ([0-9.]+)\)", src),
        win_cm=_num(r"distance <= (\d+)\)", src),
        mine_level=_num(r"landmineSensor1 <= (\d+)", src),
        mine_ratio=_num(r"futState1 >= ([0-9.]+)\*curState1", src),
        top_delay_ms=_num(r"Serial\.println\(landmineSensor2\);\s*delay\((\d+)\);", src),
        red_delay_ms=_num(r"float fut_distance = readSensorData\(\);\s*delay\((\d+)\);", src),
        us_per_cm=_num(r"pulseIn\(echoPin, HIGH\)/([0-9.]+)", src),
    )


P = load_params()


# ---- decision rules (mirror the sketch) -------------------------------------------------
def echo_to_cm(echo_us: float) -> float:
    """readSensorData(): pulseIn() microseconds divided by 58. pulseIn returns 0 on timeout."""
    return echo_us / P.us_per_cm


def moved_during_red(first_cm: float, second_cm: float) -> bool:
    return second_cm <= first_cm - P.move_cm or second_cm >= first_cm + P.move_cm


def reached_finish(distance_cm: float) -> bool:
    return distance_cm <= P.win_cm


def landmine_triggered(first_reading: int, later_reading: int) -> bool:
    """Photoresistor: armed when the first reading is low, fires when light returns."""
    return first_reading <= P.mine_level and later_reading >= P.mine_ratio * first_reading


# ---- timing model -----------------------------------------------------------------------
def simulate(game_s: float = 90.0, sensor_ms: float = 3.0, min_speed_unit: float = 1.0):
    """Simulate the light schedule and the countdown from the moment the button is read.

    One loop() pass: read distance (sensor_ms), delay(top_delay), then the millis() checks
    (second tick, light interval), then, while red, a second distance read and delay(red_delay).
    Returns a dict with the observed phases, countdown ticks and derived timings.
    """
    t_check = 0.0                      # time of the first millis() checks (button branch)
    prev = last_second = 0.0
    can_move = False                   # starts RED
    interval = P.red_ms
    timer = int(P.countdown_s)
    phases = [["RED", 0.0, None]]
    ticks = []                         # (real_time_s, displayed_value)
    red_extra = sensor_ms + P.red_delay_ms
    while timer > 0 and t_check / 1000 < game_s:
        # second tick
        if t_check - last_second >= 1000:
            last_second = t_check
            timer -= 1
            ticks.append((t_check / 1000, timer))
            if timer <= 0:
                break
        # light interval
        if t_check - prev >= interval:
            prev = t_check
            phases[-1][2] = t_check
            if can_move:
                can_move, interval = False, P.red_ms
                phases.append(["RED", t_check, None])
            else:
                can_move, interval = True, P.green_ms
                phases.append(["GREEN", t_check, None])
        # remainder of the pass, then the next pass up to its millis() checks
        pass_tail = red_extra if not can_move else 0.0
        t_check += pass_tail + sensor_ms + P.top_delay_ms
    if phases[-1][2] is None:
        phases[-1][2] = t_check
    return dict(phases=[tuple(p) for p in phases], ticks=ticks, countdown_real_s=ticks[-1][0] if ticks else None,
                red_pass_ms=red_extra + sensor_ms + P.top_delay_ms, green_pass_ms=sensor_ms + P.top_delay_ms)


def min_detectable_speed_cm_s(sensor_ms: float = 3.0) -> float:
    """Movement is judged between the distance read at the top of a pass and the one after
    delay(top_delay), so the effective sampling interval is about top_delay_ms."""
    return P.move_cm / ((P.top_delay_ms + sensor_ms) / 1000)
