# Technical Specification: Cross-Frequency Generalization Experiment

## Objective
Evaluate whether the SRH image quality classifier trained at 3000 MHz generalizes to 6000 MHz and 12200 MHz.

## Data
- **Source:** Pre-computed logs in `logs/`
  - `h1_*.jsonl` — 100 self-consistency trials
  - `main_*.jsonl` — 3000 predictions (1000 triplets × 3 channels)
- **Schema per record:** trial, phase, frequency, url, dt, label, probability, max_dt_sec
- **Constraint:** $\Delta t \leq 3$ min within triplet

## Tools
All analysis via MCP server (`tools/experiment_mcp.py`):
1. `explore_data()` — data structure, channels, class balance
2. `explore_temporal()` — monthly distribution
3. `compute_metrics()` — H1–H9 metrics
4. `generate_plots(output_dir)` — 6 plots → `experiment/plots/`
5. `get_h1_summary()` — H1 self-consistency

## Analysis Plan

### Step 1: Data exploration
- Call `explore_data()` and `explore_temporal()`
- Document: channels, n_triplets, class distribution, time range, monthly distribution

### Step 2: Self-consistency check (H1)
- Call `get_h1_summary()`
- Verify $S_{3000,3000} \geq 0.95$

### Step 3: Main metrics (H2–H9)
- Call `compute_metrics()`
- Extract all 9 hypothesis results with CIs, p-values, test statistics

### Step 4: Visualization
- Call `generate_plots(output_dir='experiment/plots')`
- Generate 6 PNG files

### Step 5: Interpretation
- Summarize results for author
- Highlight key findings and practical recommendations

## Deliverables
- [ ] `experiment/plots/agreement_bar.png`
- [ ] `experiment/plots/distribution_by_channel.png`
- [ ] `experiment/plots/confidence_boxplot.png`
- [ ] `experiment/plots/agreement_by_class.png`
- [ ] `experiment/plots/agreement_vs_deltat.png`
- [ ] `experiment/plots/agreement_by_month.png`
- [ ] `statement/diary.md` with all metrics
- [ ] `notes/paper/ai4math_ysda2026_template/example_paper.tex`
