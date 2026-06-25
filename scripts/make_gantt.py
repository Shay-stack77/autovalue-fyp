"""Generate a Gantt chart PNG for Appendix C of the FYP dissertation.

Six one-week sprints across the eight-week project window (23 Mar – 04 May 2026).
Output: docs/screenshots/gantt_chart.png
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots" / "gantt_chart.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

# (label, planned_start, planned_end, actual_start, actual_end)
tasks = [
    ("Sprint 1 — Proposal, ethics, EDA",            date(2026, 3, 23), date(2026, 3, 29), date(2026, 3, 23), date(2026, 3, 29)),
    ("Sprint 2 — Data preparation pipeline",         date(2026, 3, 30), date(2026, 4, 5),  date(2026, 3, 30), date(2026, 4, 5)),
    ("Sprint 3 — Three-model training & evaluation", date(2026, 4, 6),  date(2026, 4, 12), date(2026, 4, 6),  date(2026, 4, 12)),
    ("Sprint 4 — API, frontend, scraper",            date(2026, 4, 13), date(2026, 4, 19), date(2026, 4, 13), date(2026, 4, 20)),  # 1d overrun
    ("Sprint 5 — Testing & deployment",              date(2026, 4, 20), date(2026, 4, 26), date(2026, 4, 21), date(2026, 4, 26)),
    ("Sprint 6 — Dissertation write-up",             date(2026, 4, 27), date(2026, 5, 4),  date(2026, 4, 27), date(2026, 5, 4)),
    ("Sprint 7 — Scope extension (buying assistant)", date(2026, 6, 8),  date(2026, 6, 16), date(2026, 6, 8),  date(2026, 6, 16)),
    ("Final polish & submission",                    date(2026, 6, 17), date(2026, 6, 24), date(2026, 6, 17), date(2026, 6, 24)),
]

fig, ax = plt.subplots(figsize=(11, 5.5))

y_positions = list(range(len(tasks)))[::-1]  # top-down

for y, (label, p_start, p_end, a_start, a_end) in zip(y_positions, tasks):
    p_dur = (p_end - p_start).days + 1
    a_dur = (a_end - a_start).days + 1
    # planned (light bar, top)
    ax.barh(y + 0.18, p_dur, left=mdates.date2num(p_start), height=0.32,
            color="#9bb7d4", edgecolor="#4d6788", label="Planned" if y == y_positions[0] else "")
    # actual (dark bar, bottom)
    ax.barh(y - 0.18, a_dur, left=mdates.date2num(a_start), height=0.32,
            color="#1f4e79", edgecolor="#0d2c47", label="Actual" if y == y_positions[0] else "")

ax.set_yticks(y_positions)
ax.set_yticklabels([t[0] for t in tasks], fontsize=9)
ax.xaxis_date()
ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.set_xlim(mdates.date2num(date(2026, 3, 22)), mdates.date2num(date(2026, 6, 26)))

# milestone markers
milestones = [
    (date(2026, 3, 25), "Ethics approval (P17519)"),
    (date(2026, 4, 14), "Switch to Kaggle corpus"),
    (date(2026, 5, 4),  "First full draft"),
    (date(2026, 6, 8),  "Scope-extension feedback"),
    (date(2026, 6, 24), "Submission"),
]
for d, name in milestones:
    ax.axvline(mdates.date2num(d), color="#c0504d", linestyle=":", linewidth=1, alpha=0.7)
    ax.text(mdates.date2num(d), len(tasks) - 0.2, name, rotation=90, va="top", ha="right",
            fontsize=7.5, color="#7a2925")

ax.set_xlabel("Calendar date (2026)", fontsize=10)
ax.set_title("Figure C.1 — Project Gantt Chart (planned vs. actual)\nSyed Shayaan Ali Ali (STU195050) — FYP CMP6200",
             fontsize=11, pad=12)
ax.grid(axis="x", linestyle="--", alpha=0.4)
ax.legend(loc="lower right", fontsize=9)
plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

plt.tight_layout()
plt.savefig(OUT, dpi=160, bbox_inches="tight")
print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")
