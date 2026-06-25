"""Render a clean layered system-architecture diagram (Figure 5.1) to replace
the ASCII-art version. Output: docs/screenshots/architecture.png
"""
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots" / "architecture.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

# (title, subtitle, fill, edge)
BRAND = "#1E40AF"
layers = [
    ("PRESENTATION LAYER", "frontend/index.html · script.js · style.css\nTailwind CSS (CDN) · vanilla JS · no framework", "#DBEAFE", BRAND),
    ("APPLICATION LAYER", "src/api/app.py\nFlask 3.0 + flask-cors    /health · /vocab · /predict", "#DBEAFE", BRAND),
    ("ENGINE LAYER", "src/models/insights.py — ValuationEngine\ninterval · market adj. · deal rating · attribution · depreciation · comparables", "#BFDBFE", BRAND),
    ("MODEL LAYER", "best_model.pkl (XGBoost + ColumnTransformer) · quantile_models.pkl\ncorpus.pkl · calibration.json · vocab.json", "#E0E7FF", "#4338CA"),
    ("DATA-PREPARATION LAYER", "src/pipeline/preprocess.py · feature_engineering.py\nsrc/models/train.py · evaluate.py", "#EEF2FF", "#4338CA"),
    ("DATA LAYER", "data/raw/*.csv (Kaggle) · data/cleaned/listings.csv\nsrc/scraper/autotrader_scraper.py", "#F1F5F9", "#475569"),
]
# arrow labels between layers (top->bottom)
arrows = ["HTTP / JSON", "ValuationEngine", "joblib.load", "fit() at training time", "reads"]

fig, ax = plt.subplots(figsize=(9.5, 10))
ax.set_xlim(0, 10); ax.set_ylim(0, 12.4); ax.axis("off")

box_h, gap, w, x = 1.5, 0.42, 9.0, 0.5
y = 12.4 - 0.3 - box_h
centers = []
for (title, sub, fill, edge) in layers:
    box = FancyBboxPatch((x, y), w, box_h, boxstyle="round,pad=0.02,rounding_size=0.12",
                         linewidth=1.6, edgecolor=edge, facecolor=fill)
    ax.add_patch(box)
    ax.text(x + 0.3, y + box_h - 0.42, title, fontsize=12, fontweight="bold", color=edge, va="center")
    ax.text(x + 0.3, y + 0.46, sub, fontsize=8.3, color="#334155", va="center", linespacing=1.4)
    centers.append((x + w / 2, y, y + box_h))
    y -= (box_h + gap)

# downward arrows + labels
for i, lbl in enumerate(arrows):
    cx, _, top_lower = centers[i]
    bottom_upper = centers[i][1]
    a = FancyArrowPatch((cx, bottom_upper), (cx, centers[i + 1][2]),
                        arrowstyle="-|>", mutation_scale=16, linewidth=1.6, color="#64748B")
    ax.add_patch(a)
    ax.text(cx + 0.18, (bottom_upper + centers[i + 1][2]) / 2, lbl, fontsize=8,
            color="#64748B", style="italic", va="center", ha="left")

ax.text(5.0, 12.15, "AutoValue — layered system architecture", fontsize=13,
        fontweight="bold", ha="center", color="#0F172A")

plt.tight_layout()
plt.savefig(OUT, dpi=160, bbox_inches="tight", facecolor="white")
print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")
