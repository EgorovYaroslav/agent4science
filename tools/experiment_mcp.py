#!/usr/bin/env python3
"""
MCP server for SRH cross-frequency experiment.
Reads pre-computed logs and provides exploration, metrics, and plots.
"""

import asyncio
import json
import os
import sys
from glob import glob
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from mcp.types import ServerCapabilities

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREQUENCIES = [3000, 6000, 12200]
RNG = np.random.RandomState(42)

server = Server("srh-experiment")


# ─── Data loading ────────────────────────────────────────────────────

def _find_h1_log():
    files = sorted(glob(os.path.join(PROJECT_ROOT, 'logs', 'h1_*.jsonl')))
    if not files:
        raise FileNotFoundError("No h1_*.jsonl log found in logs/")
    return files[-1]


def _find_main_log():
    files = sorted(glob(os.path.join(PROJECT_ROOT, 'logs', 'main_*.jsonl')))
    if not files:
        raise FileNotFoundError("No main_*.jsonl log found in logs/")
    return files[-1]


def _load_jsonl(path: str) -> pd.DataFrame:
    records = []
    with open(path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return pd.DataFrame(records)


def load_h1() -> pd.DataFrame:
    return _load_jsonl(_find_h1_log())


def load_main() -> pd.DataFrame:
    return _load_jsonl(_find_main_log())


# ─── Metrics ─────────────────────────────────────────────────────────

def _agreement(preds_a: list, preds_b: list) -> float:
    if len(preds_a) != len(preds_b) or len(preds_a) == 0:
        return 0.0
    return sum(1 for a, b in zip(preds_a, preds_b) if a == b) / len(preds_a)


def _bootstrap_ci(preds_a: list, preds_b: list,
                  n_resamples: int = 1000, ci: float = 0.95):
    n = len(preds_a)
    agr = [a == b for a, b in zip(preds_a, preds_b)]
    boot = []
    for _ in range(n_resamples):
        idx = RNG.randint(0, n, n)
        boot.append(sum(agr[i] for i in idx) / n)
    lo = float(np.percentile(boot, (1 - ci) / 2 * 100))
    hi = float(np.percentile(boot, (1 + ci) / 2 * 100))
    return lo, hi


def compute_metrics(df: pd.DataFrame) -> dict:
    n_triplets = len(df[df['frequency'] == 3000])
    preds, probs, months = {}, {}, {}
    for f in FREQUENCIES:
        mask = df['frequency'] == f
        preds[f] = df.loc[mask, 'label'].tolist()
        probs[f] = df.loc[mask, 'probability'].tolist()
        months[f] = pd.to_datetime(df.loc[mask, 'dt']).dt.month.tolist()

    s_6 = _agreement(preds[3000], preds[6000])
    s_12 = _agreement(preds[3000], preds[12200])
    ci_6 = _bootstrap_ci(preds[3000], preds[6000])
    ci_12 = _bootstrap_ci(preds[3000], preds[12200])
    n_6 = len(preds[3000])
    n_12 = len(preds[3000])
    agree_6 = sum(1 for a, b in zip(preds[3000], preds[6000]) if a == b)
    agree_12 = sum(1 for a, b in zip(preds[3000], preds[12200]) if a == b)

    cont = [[agree_6, n_6 - agree_6], [agree_12, n_12 - agree_12]]
    if all(c > 0 for row in cont for c in row):
        chi2_h2, p_h2 = sp_stats.chi2_contingency(cont, correction=False)[:2]
    else:
        chi2_h2, p_h2 = None, 1.0

    results = {
        'n_triplets': n_triplets,
        'h2': {
            'S_3000_6000': s_6, 'CI_3000_6000': list(ci_6),
            'S_3000_12200': s_12, 'CI_3000_12200': list(ci_12),
            'chi2': chi2_h2, 'p_value': p_h2,
        },
        'h3': {
            'threshold_6000_passed': s_6 >= 0.90,
            'threshold_12200_passed': s_12 >= 0.85,
            'z_6000': (s_6 - 0.90) / np.sqrt(0.90 * 0.10 / n_6),
            'z_12200': (s_12 - 0.85) / np.sqrt(0.85 * 0.15 / n_12),
        },
    }

    good_label = 'Ok' if 'Ok' in set(df['label']) else 'GOOD'
    bad_label = 'Bad' if 'Bad' in set(df['label']) else 'BAD'

    good_counts = {f: sum(1 for p in preds[f] if p == good_label) for f in FREQUENCIES}
    cont_h7 = [[good_counts[f], n_triplets - good_counts[f]] for f in FREQUENCIES]
    if all(c > 0 for row in cont_h7 for c in row):
        chi2_h7, p_h7 = sp_stats.chi2_contingency(cont_h7, correction=False)[:2]
    else:
        chi2_h7, p_h7 = None, 1.0

    results['h7'] = {
        f'{good_label}_rate_3000': good_counts[3000] / n_triplets,
        f'{good_label}_rate_6000': good_counts[6000] / n_triplets,
        f'{good_label}_rate_12200': good_counts[12200] / n_triplets,
        'chi2': chi2_h7, 'p_value': p_h7,
    }

    s_6_good = _agreement(
        [p for p, r in zip(preds[6000], preds[3000]) if r == good_label],
        [r for r in preds[3000] if r == good_label]
    ) if any(p == good_label for p in preds[3000]) else 0.0
    s_6_bad = _agreement(
        [p for p, r in zip(preds[6000], preds[3000]) if r == bad_label],
        [r for r in preds[3000] if r == bad_label]
    ) if any(p == bad_label for p in preds[3000]) else 0.0
    s_12_good = _agreement(
        [p for p, r in zip(preds[12200], preds[3000]) if r == good_label],
        [r for r in preds[3000] if r == good_label]
    ) if any(p == good_label for p in preds[3000]) else 0.0
    s_12_bad = _agreement(
        [p for p, r in zip(preds[12200], preds[3000]) if r == bad_label],
        [r for r in preds[3000] if r == bad_label]
    ) if any(p == bad_label for p in preds[3000]) else 0.0

    results['h4'] = {
        f'S_6_{good_label}': s_6_good, f'S_6_{bad_label}': s_6_bad,
        f'S_12_{good_label}': s_12_good, f'S_12_{bad_label}': s_12_bad,
    }

    mean_prob = {f: float(np.mean(probs[f])) for f in FREQUENCIES}
    if len(set(probs[3000])) > 1 and len(set(probs[6000])) > 1:
        t_6, p_h5_6 = sp_stats.ttest_rel(probs[3000], probs[6000])
    else:
        t_6, p_h5_6 = None, 1.0
    if len(set(probs[3000])) > 1 and len(set(probs[12200])) > 1:
        t_12, p_h5_12 = sp_stats.ttest_rel(probs[3000], probs[12200])
    else:
        t_12, p_h5_12 = None, 1.0

    results['h5'] = {
        'mean_prob_3000': mean_prob[3000],
        'mean_prob_6000': mean_prob[6000],
        'mean_prob_12200': mean_prob[12200],
        't_3000_vs_6000': t_6, 'p_3000_vs_6000': p_h5_6,
        't_3000_vs_12200': t_12, 'p_3000_vs_12200': p_h5_12,
    }

    dt_per_trial = []
    agree_6_pt = []
    agree_12_pt = []
    for t in range(n_triplets):
        row = df[df['trial'] == t]
        dt_vals = row['max_dt_sec'].dropna().unique()
        dt_val = float(dt_vals[0]) if len(dt_vals) > 0 else 0.0
        dt_per_trial.append(dt_val)
        l3 = row[row['frequency'] == 3000]['label'].values
        l6 = row[row['frequency'] == 6000]['label'].values
        l12 = row[row['frequency'] == 12200]['label'].values
        if len(l3) > 0 and len(l6) > 0:
            agree_6_pt.append(1 if l3[0] == l6[0] else 0)
        if len(l3) > 0 and len(l12) > 0:
            agree_12_pt.append(1 if l3[0] == l12[0] else 0)

    r_6, p_h6_6 = sp_stats.spearmanr(dt_per_trial[:len(agree_6_pt)], agree_6_pt)
    r_12, p_h6_12 = sp_stats.spearmanr(dt_per_trial[:len(agree_12_pt)], agree_12_pt)

    results['h6'] = {
        'spearman_6000': float(r_6) if r_6 else None,
        'p_6000': float(p_h6_6) if p_h6_6 else 1.0,
        'spearman_12200': float(r_12) if r_12 else None,
        'p_12200': float(p_h6_12) if p_h6_12 else 1.0,
    }

    month_series = pd.to_datetime(df[df['frequency'] == 3000]['dt']).dt.month
    agree_by_month = {m: [] for m in range(1, 13)}
    for t in range(n_triplets):
        m = month_series.iloc[t]
        if t < len(agree_6_pt):
            agree_by_month[m].append(agree_6_pt[t])

    month_means = {m: float(np.mean(agree_by_month[m])) if agree_by_month[m] else 0.0
                   for m in range(1, 13)}
    groups = [agree_by_month[m] for m in range(1, 13) if len(agree_by_month[m]) > 1]
    if len(groups) >= 2:
        h_stat, p_h8 = sp_stats.kruskal(*groups)
    else:
        h_stat, p_h8 = None, 1.0

    results['h8'] = {
        'monthly_agreement': month_means,
        'kruskal_h': float(h_stat) if h_stat else None,
        'p_value': float(p_h8),
    }

    majority_class = max(set(preds[3000]), key=preds[3000].count)
    baseline_6 = sum(1 for p in preds[6000] if p == majority_class) / len(preds[6000])
    baseline_12 = sum(1 for p in preds[12200] if p == majority_class) / len(preds[12200])

    z_b6 = (s_6 - baseline_6) / np.sqrt(baseline_6 * (1 - baseline_6) / n_6) if baseline_6 * (1 - baseline_6) > 0 else 0
    z_b12 = (s_12 - baseline_12) / np.sqrt(baseline_12 * (1 - baseline_12) / n_12) if baseline_12 * (1 - baseline_12) > 0 else 0
    p_h9_6 = float(1 - sp_stats.norm.cdf(z_b6))
    p_h9_12 = float(1 - sp_stats.norm.cdf(z_b12))

    results['h9'] = {
        'majority_class': majority_class,
        'baseline_S_6000': baseline_6,
        'baseline_S_12200': baseline_12,
        'model_S_6000': s_6, 'model_S_12200': s_12,
        'z_6000': float(z_b6), 'p_6000': p_h9_6,
        'z_12200': float(z_b12), 'p_12200': p_h9_12,
    }

    return results


# ─── Plots ───────────────────────────────────────────────────────────

def generate_plots(df: pd.DataFrame, results: dict, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    n_triplets = len(df[df['frequency'] == 3000])
    good_label = 'Ok' if 'Ok' in set(df['label']) else 'GOOD'
    bad_label = 'Bad' if 'Bad' in set(df['label']) else 'BAD'

    fig, ax = plt.subplots(figsize=(7, 5))
    labels = ['3000\u21946000', '3000\u219412200']
    s_vals = [results['h2']['S_3000_6000'], results['h2']['S_3000_12200']]
    ci_vals = [results['h2']['CI_3000_6000'], results['h2']['CI_3000_12200']]
    err_lo = [s - ci[0] for s, ci in zip(s_vals, ci_vals)]
    err_hi = [ci[1] - s for s, ci in zip(s_vals, ci_vals)]
    ax.bar(labels, s_vals, yerr=[err_lo, err_hi], capsize=5,
           color=['steelblue', 'coral'], alpha=0.8)
    ax.axhline(0.90, color='gray', ls='--', label='0.90 threshold')
    ax.axhline(0.85, color='gray', ls=':', label='0.85 threshold')
    ax.set_ylabel('Agreement S')
    ax.set_ylim(0, 1)
    ax.set_title('Cross-frequency agreement')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'agreement_bar.png'), dpi=150)
    plt.close(fig)

    h7 = results['h7']
    good_rate_keys = [k for k in h7 if k.endswith('_rate_3000')]
    good_label_p = good_rate_keys[0].replace('_rate_3000', '') if good_rate_keys else 'Ok'
    good_counts_p = [
        int(h7.get(f'{good_label_p}_rate_3000', 0) * n_triplets),
        int(h7.get(f'{good_label_p}_rate_6000', 0) * n_triplets),
        int(h7.get(f'{good_label_p}_rate_12200', 0) * n_triplets),
    ]
    bad_counts_p = [n_triplets - g for g in good_counts_p]
    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(3)
    ax.bar(x, good_counts_p, label=good_label_p, color='green', alpha=0.7)
    ax.bar(x, bad_counts_p, bottom=good_counts_p,
           label=f'not {good_label_p}', color='red', alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(['3000 MHz', '6000 MHz', '12200 MHz'])
    ax.set_ylabel('Count')
    ax.set_title('Distribution of predicted classes by channel')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'distribution_by_channel.png'), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    data = [df[df['frequency'] == f]['probability'].dropna().values for f in FREQUENCIES]
    ax.boxplot(data, tick_labels=['3000 MHz', '6000 MHz', '12200 MHz'])
    ax.set_ylabel('Confidence (probability)')
    ax.set_title('Prediction confidence by channel')
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'confidence_boxplot.png'), dpi=150)
    plt.close(fig)

    h4 = results['h4']
    s6_k = [k for k in h4 if k.startswith('S_6_')]
    good_k = [k for k in s6_k if bad_label not in k]
    bad_k = f'S_6_{bad_label}'
    good_k = good_k[0] if good_k else 'S_6_Ok'
    gl2 = good_k.replace('S_6_', '')
    class_l = [gl2, bad_label]
    s6_bc = [h4.get(good_k, 0), h4.get(bad_k, 0)]
    s12_bc = [h4.get(good_k.replace('S_6_', 'S_12_'), 0),
              h4.get(bad_k.replace('S_6_', 'S_12_'), 0)]
    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(2)
    w = 0.35
    ax.bar(x - w / 2, s6_bc, w, label='3000\u21946000', color='steelblue')
    ax.bar(x + w / 2, s12_bc, w, label='3000\u219412200', color='coral')
    ax.set_xticks(x)
    ax.set_xticklabels(class_l)
    ax.set_ylabel('Agreement S')
    ax.set_ylim(0, 1)
    ax.set_title('Agreement stratified by class')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'agreement_by_class.png'), dpi=150)
    plt.close(fig)

    dt_per_trial = []
    agree_6_pt = []
    agree_12_pt = []
    for t in range(n_triplets):
        row = df[df['trial'] == t]
        dt_vals = row['max_dt_sec'].dropna().unique()
        dt_val = float(dt_vals[0]) if len(dt_vals) > 0 else 0.0
        dt_per_trial.append(dt_val)
        l3 = row[row['frequency'] == 3000]['label'].values
        l6 = row[row['frequency'] == 6000]['label'].values
        l12 = row[row['frequency'] == 12200]['label'].values
        if len(l3) > 0 and len(l6) > 0:
            agree_6_pt.append(1 if l3[0] == l6[0] else 0)
        if len(l3) > 0 and len(l12) > 0:
            agree_12_pt.append(1 if l3[0] == l12[0] else 0)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(dt_per_trial[:len(agree_6_pt)], agree_6_pt,
               alpha=0.3, label='3000\u21946000', c='steelblue', s=10)
    ax.scatter(dt_per_trial[:len(agree_12_pt)], agree_12_pt,
               alpha=0.3, label='3000\u219412200', c='coral', s=10)
    ax.set_xlabel('\u0394t (seconds)')
    ax.set_ylabel('Agreement')
    ax.set_title('Agreement vs temporal offset')
    ax.legend()
    ax.set_ylim(-0.05, 1.05)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'agreement_vs_deltat.png'), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    month_means = results['h8']['monthly_agreement']
    months_x = list(range(1, 13))
    means = [month_means[m] for m in months_x]
    ax.bar(months_x, means, color='steelblue', alpha=0.7)
    ax.axhline(results['h2']['S_3000_6000'], color='gray', ls='--',
               label=f'Overall S (3000\u21946000) = {results["h2"]["S_3000_6000"]:.3f}')
    ax.set_xlabel('Month')
    ax.set_ylabel('Agreement S')
    ax.set_xticks(months_x)
    ax.set_title('Agreement by month (3000\u21946000)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'agreement_by_month.png'), dpi=150)
    plt.close(fig)

    return [f for f in os.listdir(output_dir) if f.endswith('.png')]


# ─── H1 metrics ─────────────────────────────────────────────────────

def compute_h1_metrics(h1_df: pd.DataFrame) -> dict:
    labels_1 = h1_df['label_1'].tolist()
    labels_2 = h1_df['label_2'].tolist()
    s = _agreement(labels_1, labels_2)
    ci = _bootstrap_ci(labels_1, labels_2)
    return {
        'n_trials': len(h1_df),
        'S_self': s,
        'CI_self': list(ci),
        'all_identical': s == 1.0,
    }


# ─── MCP tools ──────────────────────────────────────────────────────

def _make_text(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="explore_data",
            description="Explore experiment data: channels, trial count, class balance, time range, schema",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="explore_temporal",
            description="Temporal distribution of trials across months",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="compute_metrics",
            description="Compute all H1-H9 metrics from the experiment logs",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="generate_plots",
            description="Generate all 6 experiment plots from logs",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Directory to save plots (default: experiment/plots)",
                    }
                },
            },
        ),
        types.Tool(
            name="get_h1_summary",
            description="H1 self-consistency check summary",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "explore_data":
        h1 = load_h1()
        main = load_main()
        channels = sorted(main['frequency'].unique().tolist())
        n_triplets = len(main[main['frequency'] == 3000])
        class_dist = main.groupby('frequency')['label'].value_counts().to_dict()
        class_dist = {str(k[0]): {str(k[1]): int(v)} for k, v in class_dist.items()}
        times = pd.to_datetime(main['dt'])
        return _make_text({
            'channels': channels,
            'n_triplets': n_triplets,
            'n_h1_trials': len(h1),
            'time_range': {'min': str(times.min()), 'max': str(times.max())},
            'class_distribution_by_channel': class_dist,
            'h1_schema': list(h1.columns),
            'main_schema': list(main.columns),
        })

    elif name == "explore_temporal":
        main = load_main()
        df_3000 = main[main['frequency'] == 3000].copy()
        df_3000['month'] = pd.to_datetime(df_3000['dt']).dt.month
        counts = df_3000['month'].value_counts().sort_index()
        return _make_text({
            'trials_per_month': {int(m): int(c) for m, c in counts.items()},
            'total_trials': int(counts.sum()),
            'months_covered': sorted(int(m) for m in counts.index),
        })

    elif name == "compute_metrics":
        h1_df = load_h1()
        main_df = load_main()
        h1_metrics = compute_h1_metrics(h1_df)
        main_metrics = compute_metrics(main_df)
        return _make_text({'h1': h1_metrics, **main_metrics})

    elif name == "generate_plots":
        output_dir = arguments.get('output_dir',
                                   os.path.join(PROJECT_ROOT, 'experiment', 'plots'))
        main_df = load_main()
        results = compute_metrics(main_df)
        files = generate_plots(main_df, results, output_dir)
        return _make_text({
            'message': f'Generated {len(files)} plots',
            'output_dir': output_dir,
            'files': files,
        })

    elif name == "get_h1_summary":
        h1_df = load_h1()
        m = compute_h1_metrics(h1_df)
        return _make_text(m)

    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="srh-experiment",
                server_version="0.1.0",
                capabilities=ServerCapabilities(),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
