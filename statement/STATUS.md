# STATUS.md

## Current Stage
All 7 stages complete. Paper ready for review.

## What was done in the last session
- [x] Stage 1: Literature review — read PDF (2507.04211v1), wrote `statement/LIT.md` with IEEE citations (5 sources)
- [x] Stage 2: Math decomposition — notations (M.0), assumptions (M.1), questions (M.2), methods (M.3), limitations (M.4) in `statement/diary.md`
- [x] Stage 3: Hypotheses — formalized H1–H9 in `statement/HYPOTHESIS.md`
- [x] Stage 4: Technical specification — wrote `statement/TZ.md` with experiment plan
- [x] Stage 5: MCP analysis — ran all 5 tools:
  - `explore_data` — 3 channels, 1000 triplets, 12-month coverage
  - `explore_temporal` — all months covered (79–89 trials/month)
  - `compute_metrics` — H1–H9 all computed (see summary below)
  - `generate_plots` — 6 PNGs in `experiment/plots/`, copied to `figures/`
  - `get_h1_summary` — S_self = 1.000 [1.000, 1.000]
- [x] Stage 6: Interpretation — notes for author in diary.md (M.5)
- [x] Stage 7: Rewrote `notes/paper/ai4math_ysda2026_template/example_paper.tex` with actual computed metrics

## Key results
| Hypothesis | Result |
|------------|--------|
| H1 (self-consistency) | S = 1.000 ✓ |
| H2 (symmetry) | S_6=0.671, S_12=0.542, χ² p=3.5e-9 ✗ |
| H3 (thresholds) | Both FAIL ✗ |
| H4 (class asymmetry) | Bad: 79.8–91.9%, Ok: 22.6–56.4% |
| H5 (confidence) | p drops: 0.932→0.922→0.893 (p=7.4e-12) |
| H6 (Δt correlation) | ρ ≈ 0, no effect ✓ |
| H7 (distribution shift) | Ok rate: 54.4%→39.9%→16.0% (χ² p≈0) |
| H8 (seasonal) | H=157.9, p=3.6e-28, range 36.7–100% |
| H9 (baseline) | Model > baseline for both (p≈0) ✓ |

## Files created/modified
- `statement/LIT.md` — new
- `statement/HYPOTHESIS.md` — new
- `statement/TZ.md` — new
- `statement/STATUS.md` — updated
- `statement/diary.md` — updated
- `experiment/plots/*.png` — 6 new plots
- `notes/paper/ai4math_ysda2026_template/example_paper.tex` — rewritten
- `notes/paper/ai4math_ysda2026_template/figures/*.png` — 6 new figures

## Problems/blockers
- LaTeX compilation requires `texlive-latex-recommended` (not installed on this system)

## Last updated
2026-06-23 00:03
