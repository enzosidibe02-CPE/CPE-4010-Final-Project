"""Regenerate results/ from the timing model. Run: python tools/make_figures.py"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import game_model as g

OUT = Path(__file__).resolve().parents[1] / "results"
OUT.mkdir(exist_ok=True)
RED, GREEN, NAVY = "#c0392b", "#2e8b57", "#14213d"


def main():
    sim = g.simulate(game_s=200)
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 3.9), gridspec_kw={"width_ratios": [1.2, 1]})
    for state, start, end in sim["phases"]:
        if start / 1000 > 20:
            break
        a.barh(0, (end - start) / 1000, left=start / 1000, color=RED if state == "RED" else GREEN, edgecolor="white", height=0.6)
    a.set_xlim(0, 20); a.set_yticks([]); a.set_xlabel("Time since button press (s)")
    a.set_title("Light schedule from the code's timing (red 3 s, green 2 s)")
    xs = [0] + [t for t, _ in sim["ticks"]]
    ys = [g.P.countdown_s] + [v for _, v in sim["ticks"]]
    b.step(xs, ys, where="post", color=NAVY, label="displayed countdown (model)")
    b.plot([0, g.P.countdown_s], [g.P.countdown_s, 0], "--", color="#888", label="ideal 1 s per count")
    b.set_xlabel("Real time (s)"); b.set_ylabel("LCD value"); b.legend(frameon=False, fontsize=8)
    b.set_title(f"Countdown reaches 0 at about {sim['countdown_real_s']:.0f} s")
    for ax in (a, b):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.suptitle("Timing model of the final sketch (analysis of the code, not a hardware measurement)", fontsize=10)
    fig.tight_layout(); fig.savefig(OUT / "timing_model.png", dpi=150); plt.close(fig)

    red = [e - s for st, s, e in sim["phases"][:-1] if st == "RED"]
    grn = [e - s for st, s, e in sim["phases"][:-1] if st == "GREEN"]
    summary = dict(
        red_phase_ms=round(sum(red) / len(red)), green_phase_ms=round(sum(grn) / len(grn)),
        red_pass_ms=sim["red_pass_ms"], green_pass_ms=sim["green_pass_ms"],
        countdown_60_real_seconds=round(sim["countdown_real_s"], 1),
        min_detectable_speed_cm_per_s=round(g.min_detectable_speed_cm_s(), 1),
        note="Model of the code's timing with 3 ms per distance read; not a hardware measurement.",
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
