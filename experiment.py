"""
Cross-frequency generalization experiment for SRH image classification.

Tests hypotheses H1-H9: how well does f_{3000} generalize to 6000 and 12200 MHz?

Usage:
    python experiment.py --seed 42 --n-samples 1000 --output results/
"""

import os
import sys
import json
import time
import argparse
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'materials'))
from ftp_client import FTPClient
from api_client import APIClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

FREQUENCIES = [3000, 6000, 12200]
SEED = 42
N_H1 = 100
N_MAIN = 1000
MAX_DIFF_SEC = 180
BOOTSTRAP_RESAMPLES = 1000
ALPHA = 0.05
ALPHA_BONF = 0.0125
RNG = random.Random(SEED)


def parse_args():
    parser = argparse.ArgumentParser(description='SRH cross-frequency experiment')
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--n-samples', type=int, default=N_MAIN)
    parser.add_argument('--output', type=str, default='results')
    parser.add_argument('--plots', type=str, default='experiment/plots')
    parser.add_argument('--max-diff-sec', type=int, default=MAX_DIFF_SEC)
    parser.add_argument('--skip-h1', action='store_true')
    return parser.parse_args()


def setup_dirs(args):
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(args.plots, exist_ok=True)
    os.makedirs('data/fits', exist_ok=True)
    os.makedirs('logs', exist_ok=True)


def save_log(records: List[dict], log_file: str):
    with open(log_file, 'w') as f:
        for rec in records:
            f.write(json.dumps(rec, default=str) + '\n')
    logger.info(f'Log saved: {log_file} ({len(records)} records)')


def load_log(log_file: str) -> List[dict]:
    records = []
    with open(log_file) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def agreement(preds_a: List[str], preds_b: List[str]) -> float:
    if len(preds_a) != len(preds_b) or len(preds_a) == 0:
        return 0.0
    return sum(1 for a, b in zip(preds_a, preds_b) if a == b) / len(preds_a)


def bootstrap_ci(preds_a: List[str], preds_b: List[str],
                 n_resamples: int = 1000, ci: float = 0.95) -> Tuple[float, float]:
    n = len(preds_a)
    agr = [a == b for a, b in zip(preds_a, preds_b)]
    boot_means = []
    for _ in range(n_resamples):
        idx = RNG.choices(range(n), k=n)
        boot_means.append(sum(agr[i] for i in idx) / n)
    lo = np.percentile(boot_means, (1 - ci) / 2 * 100)
    hi = np.percentile(boot_means, (1 + ci) / 2 * 100)
    return float(lo), float(hi)


# ─── H1: Self-consistency check ────────────────────────────────────

def collect_available_3000_files(ftp: FTPClient, year: int = 2025) -> List[Tuple[datetime, str]]:
    """
    Build a pool of all available 3000 MHz I-polarization files for the given year.
    """
    pool = []
    logger.info('Scanning FTP for 3000 MHz files...')
    for month in range(1, 13):
        for day in range(1, 32):
            try:
                dt = datetime(year, month, day)
                files = ftp.list_files(3000, dt)
                pool.extend(files)
            except (ValueError, requests.RequestException):
                continue
    logger.info(f'  Found {len(pool)} 3000 MHz files')
    return pool


def collect_available_triplets(ftp: FTPClient, max_diff_sec: int = 180,
                                max_triplets: int = 2000) -> List[tuple]:
    """
    Build a pool of valid triplets by scanning 3000 MHz files
    and finding matching 6000/12200 files across the full year.
    Scans all available months and collects up to max_triplets from each month.
    """
    triplet_pool = []
    logger.info('Building triplet pool (scanning full year)...')

    triplets_per_month = max(max_triplets // 12, 50)

    for month in range(1, 13):
        month_triplets = []
        for day in range(1, 32):
            try:
                dt = datetime(2025, month, day)
            except ValueError:
                continue

            files_3000 = ftp.list_files(3000, dt)
            if not files_3000:
                continue

            files_6000 = ftp.list_files(6000, dt)
            files_12200 = ftp.list_files(12200, dt)
            if not files_6000 or not files_12200:
                continue

            for dt_3000, url_3000 in files_3000:
                if len(month_triplets) >= triplets_per_month:
                    break

                dt_6000, url_6000 = None, None
                for dt_f, url_f in files_6000:
                    diff = abs((dt_f - dt_3000).total_seconds())
                    if diff <= max_diff_sec:
                        dt_6000, url_6000 = dt_f, url_f
                        break
                if dt_6000 is None:
                    continue

                dt_12200, url_12200 = None, None
                for dt_f, url_f in files_12200:
                    diff = abs((dt_f - dt_3000).total_seconds())
                    if diff <= max_diff_sec:
                        dt_12200, url_12200 = dt_f, url_f
                        break
                if dt_12200 is None:
                    continue

                max_dt = max(
                    abs((dt_3000 - dt_6000).total_seconds()),
                    abs((dt_3000 - dt_12200).total_seconds()),
                    abs((dt_6000 - dt_12200).total_seconds())
                )
                month_triplets.append((dt_3000, url_3000, dt_6000, url_6000,
                                       dt_12200, url_12200, max_dt))

        logger.info(f'  Month {month:02d}: {len(month_triplets)} triplets')
        triplet_pool.extend(month_triplets)

    logger.info(f'  Total triplets in pool: {len(triplet_pool)}')
    return triplet_pool


def run_h1_from_pool(ftp: FTPClient, api: APIClient,
                      triplet_pool: List[tuple], args) -> float:
    logger.info('=' * 60)
    logger.info('H1: Self-consistency check (S_{3000,3000} >= 0.95)')
    logger.info('=' * 60)

    sample = RNG.sample(triplet_pool, min(N_H1, len(triplet_pool)))

    records = []
    for trial, entry in enumerate(sample):
        url_3000 = entry[1]
        result1 = api.predict_from_url(url_3000)
        if result1 is None:
            continue
        time.sleep(1)

        result2 = api.predict_from_url(url_3000)
        if result2 is None:
            continue
        time.sleep(1)

        records.append({
            'trial': trial, 'phase': 'h1', 'frequency': 3000, 'url': url_3000,
            'dt': str(entry[0]), 'label_1': result1['label'],
            'prob_1': result1['probability'], 'label_2': result2['label'],
            'prob_2': result2['probability']
        })

        if trial % 25 == 0:
            logger.info(f'  H1: {trial}/{N_H1} collected')

    save_log(records, f'logs/h1_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl')

    labels_1 = [r['label_1'] for r in records]
    labels_2 = [r['label_2'] for r in records]
    s = agreement(labels_1, labels_2)
    lo, hi = bootstrap_ci(labels_1, labels_2)

    logger.info(f'  H1 result: S = {s:.4f} [{lo:.4f}, {hi:.4f}]')
    return s


def collect_triplets_from_pool(api: APIClient, triplet_pool: List[tuple],
                                 n_samples: int) -> List[dict]:
    logger.info('=' * 60)
    logger.info(f'Main collection: {n_samples} triplets')
    logger.info('=' * 60)

    sample = RNG.sample(triplet_pool, min(n_samples, len(triplet_pool)))
    records = []

    for trial, entry in enumerate(sample):
        dt_3000, url_3000, dt_6000, url_6000, dt_12200, url_12200, max_dt = entry

        trial_ok = True
        trial_records = []
        for freq, dt_f, url_f in [(3000, dt_3000, url_3000),
                                   (6000, dt_6000, url_6000),
                                   (12200, dt_12200, url_12200)]:
            result = api.predict_from_url(url_f)
            if result is None:
                trial_ok = False
                break

            trial_records.append({
                'trial': trial, 'phase': 'main', 'frequency': freq,
                'url': url_f, 'dt': str(dt_f),
                'label': result['label'], 'probability': result['probability'],
                'max_dt_sec': max_dt
            })
            time.sleep(1)

        if not trial_ok:
            continue

        records.extend(trial_records)

        if trial % 50 == 0:
            logger.info(f'  Main: {trial}/{n_samples} triplets collected')

    log_file = f'logs/main_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl'
    save_log(records, log_file)

    logger.info(f'  Collected {len(records) // 3} triplets')
    return records


# ─── Analysis ──────────────────────────────────────────────────────

def analyze(records: List[dict], args) -> dict:
    df = pd.DataFrame(records)

    results = {}

    preds = {}
    probs = {}
    months = {}
    for freq in FREQUENCIES:
        mask = df['frequency'] == freq
        preds[freq] = df.loc[mask, 'label'].tolist()
        probs[freq] = df.loc[mask, 'probability'].tolist()
        months[freq] = pd.to_datetime(df.loc[mask, 'dt']).dt.month.tolist()

    n_triplets = len(preds[3000])
    logger.info(f'Analysis on {n_triplets} triplets')

    # H2: symmetry
    s_6 = agreement(preds[3000], preds[6000])
    s_12 = agreement(preds[3000], preds[12200])
    ci_6 = bootstrap_ci(preds[3000], preds[6000])
    ci_12 = bootstrap_ci(preds[3000], preds[12200])

    n_6 = len(preds[3000])
    n_12 = len(preds[3000])
    agree_6 = sum(1 for a, b in zip(preds[3000], preds[6000]) if a == b)
    agree_12 = sum(1 for a, b in zip(preds[3000], preds[12200]) if a == b)

    # chi-squared for H2
    cont = [[agree_6, n_6 - agree_6], [agree_12, n_12 - agree_12]]
    if all(c > 0 for row in cont for c in row):
        chi2, p_h2 = sp_stats.chi2_contingency(cont, correction=False)[:2]
    else:
        chi2, p_h2 = None, 1.0

    results['h2'] = {
        'S_3000_6000': s_6, 'CI_3000_6000': ci_6,
        'S_3000_12200': s_12, 'CI_3000_12200': ci_12,
        'chi2': chi2, 'p_value': p_h2
    }

    # H3: threshold test
    z_6 = (s_6 - 0.90) / np.sqrt(0.90 * 0.10 / n_6)
    z_12 = (s_12 - 0.85) / np.sqrt(0.85 * 0.15 / n_12)
    p_h3_6 = 1 - sp_stats.norm.cdf(z_6)
    p_h3_12 = 1 - sp_stats.norm.cdf(z_12)

    results['h3'] = {
        'threshold_6000_passed': s_6 >= 0.90,
        'threshold_12200_passed': s_12 >= 0.85,
        'z_6000': z_6, 'p_6000': p_h3_6,
        'z_12200': z_12, 'p_12200': p_h3_12
    }

    # Detect actual label names from data
    all_labels = set(p for ps in preds.values() for p in ps)
    good_label = 'Ok' if 'Ok' in all_labels else 'GOOD'
    bad_label = 'Bad' if 'Bad' in all_labels else 'BAD'

    # H7: marginal distribution homogeneity
    good_counts = {}
    for freq in FREQUENCIES:
        good_counts[freq] = sum(1 for p in preds[freq] if p == good_label)
    cont_h7 = [[good_counts[f], n_triplets - good_counts[f]] for f in FREQUENCIES]
    if all(c > 0 for row in cont_h7 for c in row):
        chi2_h7, p_h7 = sp_stats.chi2_contingency(cont_h7, correction=False)[:2]
    else:
        chi2_h7, p_h7 = None, 1.0

    results['h7'] = {
        f'{good_label}_rate_3000': good_counts[3000] / n_triplets,
        f'{good_label}_rate_6000': good_counts[6000] / n_triplets,
        f'{good_label}_rate_12200': good_counts[12200] / n_triplets,
        'chi2': chi2_h7, 'p_value': p_h7
    }

    # H4: class-stratified agreement
    s_6_good = agreement(
        [p for p, ref in zip(preds[6000], preds[3000]) if ref == good_label],
        [ref for ref in preds[3000] if ref == good_label]
    ) if any(p == good_label for p in preds[3000]) else 0.0
    s_6_bad = agreement(
        [p for p, ref in zip(preds[6000], preds[3000]) if ref == bad_label],
        [ref for ref in preds[3000] if ref == bad_label]
    ) if any(p == bad_label for p in preds[3000]) else 0.0
    s_12_good = agreement(
        [p for p, ref in zip(preds[12200], preds[3000]) if ref == good_label],
        [ref for ref in preds[3000] if ref == good_label]
    ) if any(p == good_label for p in preds[3000]) else 0.0
    s_12_bad = agreement(
        [p for p, ref in zip(preds[12200], preds[3000]) if ref == bad_label],
        [ref for ref in preds[3000] if ref == bad_label]
    ) if any(p == bad_label for p in preds[3000]) else 0.0

    results['h4'] = {
        f'S_6_{good_label}': s_6_good, f'S_6_{bad_label}': s_6_bad,
        f'S_12_{good_label}': s_12_good, f'S_12_{bad_label}': s_12_bad
    }

    # H5: confidence degradation
    mean_prob = {f: np.mean(probs[f]) for f in FREQUENCIES}
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
        't_3000_vs_12200': t_12, 'p_3000_vs_12200': p_h5_12
    }

    # H6: correlation with delta_t
    dt_per_trial = []
    agree_6_per_trial = []
    agree_12_per_trial = []
    for t in range(n_triplets):
        row = df[df['trial'] == t]
        dt_vals = row['max_dt_sec'].dropna().unique()
        if len(dt_vals) > 0:
            dt_val = dt_vals[0]
        else:
            dt_val = 0
        dt_per_trial.append(dt_val)
        labels_3000 = row[row['frequency'] == 3000]['label'].values
        labels_6000 = row[row['frequency'] == 6000]['label'].values
        labels_12200 = row[row['frequency'] == 12200]['label'].values
        if len(labels_3000) > 0 and len(labels_6000) > 0:
            agree_6_per_trial.append(1 if labels_3000[0] == labels_6000[0] else 0)
        if len(labels_3000) > 0 and len(labels_12200) > 0:
            agree_12_per_trial.append(1 if labels_3000[0] == labels_12200[0] else 0)

    r_6, p_h6_6 = sp_stats.spearmanr(dt_per_trial[:len(agree_6_per_trial)], agree_6_per_trial)
    r_12, p_h6_12 = sp_stats.spearmanr(dt_per_trial[:len(agree_12_per_trial)], agree_12_per_trial)

    results['h6'] = {
        'spearman_6000': r_6, 'p_6000': p_h6_6,
        'spearman_12200': r_12, 'p_12200': p_h6_12
    }

    # H8: seasonal stability
    months_series = pd.to_datetime(df[df['frequency'] == 3000]['dt']).dt.month
    agree_by_month = {m: [] for m in range(1, 13)}
    for t in range(n_triplets):
        m = months_series.iloc[t]
        agree_by_month[m].append(agree_6_per_trial[t] if t < len(agree_6_per_trial) else 0)

    month_means = {m: np.mean(agree_by_month[m]) if agree_by_month[m] else 0
                   for m in range(1, 13)}
    groups = [agree_by_month[m] for m in range(1, 13) if len(agree_by_month[m]) > 1]
    if len(groups) >= 2:
        h_stat, p_h8 = sp_stats.kruskal(*groups)
    else:
        h_stat, p_h8 = None, 1.0

    results['h8'] = {
        'monthly_agreement': month_means,
        'kruskal_h': h_stat, 'p_value': p_h8
    }

    # H9: baseline comparison
    majority_class_3000 = max(set(preds[3000]), key=preds[3000].count)
    baseline_6 = sum(1 for p in preds[6000] if p == majority_class_3000) / len(preds[6000])
    baseline_12 = sum(1 for p in preds[12200] if p == majority_class_3000) / len(preds[12200])

    z_b6 = (s_6 - baseline_6) / np.sqrt(baseline_6 * (1 - baseline_6) / n_6)
    z_b12 = (s_12 - baseline_12) / np.sqrt(baseline_12 * (1 - baseline_12) / n_12)
    p_h9_6 = 1 - sp_stats.norm.cdf(z_b6)
    p_h9_12 = 1 - sp_stats.norm.cdf(z_b12)

    results['h9'] = {
        'majority_class': majority_class_3000,
        'baseline_S_6000': baseline_6,
        'baseline_S_12200': baseline_12,
        'model_S_6000': s_6, 'model_S_12200': s_12,
        'z_6000': z_b6, 'p_6000': p_h9_6,
        'z_12200': z_b12, 'p_12200': p_h9_12
    }

    return results


# ─── Plots ─────────────────────────────────────────────────────────

def make_plots(df: pd.DataFrame, results: dict, args):
    logger.info('Generating plots...')

    n_triplets = len(df[df['frequency'] == 3000])

    all_labels = set(df['label'].tolist())
    good_label = 'Ok' if 'Ok' in all_labels else 'GOOD'
    bad_label = 'Bad' if 'Bad' in all_labels else 'BAD'

    # 1. agreement_bar.png
    fig, ax = plt.subplots(figsize=(7, 5))
    labels = ['3000↔6000', '3000↔12200']
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
    fig.savefig(os.path.join(args.plots, 'agreement_bar.png'), dpi=150)
    plt.close(fig)

    # 2. distribution_by_channel.png
    fig, ax = plt.subplots(figsize=(7, 5))
    freqs_labels = ['3000 MHz', '6000 MHz', '12200 MHz']
    h7 = results['h7']
    good_keys = [k for k in h7 if '_rate_3000' in k]
    good_label_plot = good_keys[0].replace('_rate_3000', '') if good_keys else 'Good'
    good_counts = [
        h7.get(f'{good_label_plot}_rate_3000', 0) * n_triplets,
        h7.get(f'{good_label_plot}_rate_6000', 0) * n_triplets,
        h7.get(f'{good_label_plot}_rate_12200', 0) * n_triplets
    ]
    bad_counts = [n_triplets - g for g in good_counts]
    x = np.arange(len(freqs_labels))
    ax.bar(x, good_counts, label=good_label_plot, color='green', alpha=0.7)
    ax.bar(x, bad_counts, bottom=good_counts, label=f'not {good_label_plot}', color='red', alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(freqs_labels)
    ax.set_ylabel('Count')
    ax.set_title('Distribution of predicted classes by channel')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(args.plots, 'distribution_by_channel.png'), dpi=150)
    plt.close(fig)

    # 3. confidence_boxplot.png
    fig, ax = plt.subplots(figsize=(7, 5))
    data = [df[df['frequency'] == f]['probability'].dropna().values
            for f in FREQUENCIES]
    ax.boxplot(data, labels=freqs_labels)
    ax.set_ylabel('Confidence (probability)')
    ax.set_title('Prediction confidence by channel')
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(os.path.join(args.plots, 'confidence_boxplot.png'), dpi=150)
    plt.close(fig)

    # 4. agreement_by_class.png
    fig, ax = plt.subplots(figsize=(7, 5))
    h4 = results['h4']
    h4_keys = list(h4.keys())
    s6_keys = [k for k in h4_keys if k.startswith('S_6_')]
    good_key = [k for k in s6_keys if bad_label not in k][0] if s6_keys else 'S_6_Ok'
    bad_key = f'S_6_{bad_label}' if bad_label and any(bad_label in k for k in s6_keys) else 'S_6_Bad'
    good_label_plot2 = good_key.replace('S_6_', '') if good_key else 'Ok'
    class_labels = [good_label_plot2, bad_label]
    s_6_by_class = [h4.get(good_key, 0), h4.get(bad_key, 0)]
    s_12_by_class = [h4.get(good_key.replace('S_6_', 'S_12_'), 0), h4.get(bad_key.replace('S_6_', 'S_12_'), 0)]
    x = np.arange(len(class_labels))
    w = 0.35
    ax.bar(x - w/2, s_6_by_class, w, label='3000↔6000', color='steelblue')
    ax.bar(x + w/2, s_12_by_class, w, label='3000↔12200', color='coral')
    ax.set_xticks(x)
    ax.set_xticklabels(class_labels)
    ax.set_ylabel('Agreement S')
    ax.set_ylim(0, 1)
    ax.set_title('Agreement stratified by class')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(args.plots, 'agreement_by_class.png'), dpi=150)
    plt.close(fig)

    # 5. agreement_vs_deltat.png
    fig, ax = plt.subplots(figsize=(7, 5))
    dt_per_trial = []
    agree_6_per_trial = []
    agree_12_per_trial = []
    for t in range(n_triplets):
        row = df[df['trial'] == t]
        dt_vals = row['max_dt_sec'].dropna().unique()
        dt_val = dt_vals[0] if len(dt_vals) > 0 else 0
        dt_per_trial.append(dt_val)
        l3 = row[row['frequency'] == 3000]['label'].values
        l6 = row[row['frequency'] == 6000]['label'].values
        l12 = row[row['frequency'] == 12200]['label'].values
        if len(l3) > 0 and len(l6) > 0:
            agree_6_per_trial.append(1 if l3[0] == l6[0] else 0)
        if len(l3) > 0 and len(l12) > 0:
            agree_12_per_trial.append(1 if l3[0] == l12[0] else 0)

    ax.scatter(dt_per_trial[:len(agree_6_per_trial)], agree_6_per_trial,
               alpha=0.3, label='3000↔6000', c='steelblue', s=10)
    ax.scatter(dt_per_trial[:len(agree_12_per_trial)], agree_12_per_trial,
               alpha=0.3, label='3000↔12200', c='coral', s=10)

    # moving average
    dt_arr = np.array(dt_per_trial[:max(len(agree_6_per_trial), len(agree_12_per_trial))])
    bins = np.linspace(0, args.max_diff_sec, 10)
    for agree_vals, color, label in [
        (agree_6_per_trial, 'steelblue', '6000 MA'),
        (agree_12_per_trial, 'coral', '12200 MA')
    ]:
        bin_means = []
        bin_centers = []
        for i in range(len(bins) - 1):
            mask = (dt_arr[:len(agree_vals)] >= bins[i]) & (dt_arr[:len(agree_vals)] < bins[i+1])
            if mask.sum() > 0:
                bin_means.append(np.mean(np.array(agree_vals)[mask]))
                bin_centers.append((bins[i] + bins[i+1]) / 2)
        if bin_means:
            ax.plot(bin_centers, bin_means, color=color, lw=2, ls='--', label=label)

    ax.set_xlabel('Δt (seconds)')
    ax.set_ylabel('Agreement')
    ax.set_title('Agreement vs temporal offset')
    ax.legend()
    ax.set_ylim(-0.05, 1.05)
    fig.tight_layout()
    fig.savefig(os.path.join(args.plots, 'agreement_vs_deltat.png'), dpi=150)
    plt.close(fig)

    # 6. agreement_by_month.png
    fig, ax = plt.subplots(figsize=(9, 5))
    month_means = results['h8']['monthly_agreement']
    months = list(range(1, 13))
    means = [month_means[m] for m in months]
    ax.bar(months, means, color='steelblue', alpha=0.7)
    ax.axhline(results['h2']['S_3000_6000'], color='gray', ls='--',
               label=f'Overall S (3000↔6000) = {results["h2"]["S_3000_6000"]:.3f}')
    ax.set_xlabel('Month')
    ax.set_ylabel('Agreement S')
    ax.set_xticks(months)
    ax.set_title('Agreement by month (3000↔6000)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(args.plots, 'agreement_by_month.png'), dpi=150)
    plt.close(fig)

    logger.info(f'Plots saved to {args.plots}/')


def save_results(results: dict, args):
    rows = []
    for key, data in results.items():
        row = {'hypothesis': key}
        for k, v in data.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    row[f'{k}_{kk}'] = vv
            else:
                row[k] = v
        rows.append(row)

    df = pd.DataFrame(rows)
    csv_path = os.path.join(args.output, 'agreement_table.csv')
    df.to_csv(csv_path, index=False)
    logger.info(f'Results saved: {csv_path}')
    return df


def print_summary(results: dict):
    logger.info('=' * 60)
    logger.info('EXPERIMENT SUMMARY')
    logger.info('=' * 60)

    h2 = results['h2']
    logger.info(f'H2: S(3000,6000)={h2["S_3000_6000"]:.4f} '
                f'S(3000,12200)={h2["S_3000_12200"]:.4f} '
                f'p={h2["p_value"]:.4f}')

    h3 = results['h3']
    logger.info(f'H3: 6000>0.90: {h3["threshold_6000_passed"]} '
                f'12200>0.85: {h3["threshold_12200_passed"]}')

    h7 = results['h7']
    good_keys = [k for k in h7 if k.endswith('_rate_3000')]
    good_label_plot = good_keys[0].replace('_rate_3000', '') if good_keys else 'Good'
    logger.info(f'H7: {good_label_plot} rate 3000={h7.get(f"{good_label_plot}_rate_3000", 0):.3f} '
                f'6000={h7.get(f"{good_label_plot}_rate_6000", 0):.3f} '
                f'12200={h7.get(f"{good_label_plot}_rate_12200", 0):.3f} '
                f'p={h7["p_value"]:.4f}')

    h9 = results['h9']
    logger.info(f'H9: majority="{h9["majority_class"]}" '
                f'baseline_6={h9["baseline_S_6000"]:.3f} '
                f'model_6={h9["model_S_6000"]:.3f} '
                f'p={h9["p_6000"]:.4f}')


# ─── Main ──────────────────────────────────────────────────────────

def main():
    args = parse_args()
    setup_dirs(args)

    global RNG
    RNG = random.Random(args.seed)
    np.random.seed(args.seed)

    ftp = FTPClient(cache_dir='data/fits')
    api = APIClient()

    # Build triplet pool first (directory scanning, no API calls)
    max_pool = max(1200, N_H1, args.n_samples)
    triplet_pool = collect_available_triplets(ftp, args.max_diff_sec, max_pool)

    if len(triplet_pool) == 0:
        logger.error('No triplets available. Check FTP connectivity.')
        return 1

    if len(triplet_pool) < args.n_samples:
        logger.warning(f'Only {len(triplet_pool)} triplets available '
                       f'(target: {args.n_samples})')

    # H1: self-consistency
    if not args.skip_h1:
        s_h1 = run_h1_from_pool(ftp, api, triplet_pool, args)
        if s_h1 < 0.95:
            logger.error(f'H1 FAILED: S={s_h1:.4f} < 0.95. '
                         'API or model is not deterministic. Stopping.')
            return 1
        logger.info(f'H1 PASSED: S={s_h1:.4f} >= 0.95')
    else:
        logger.info('Skipping H1')

    # Main collection
    records = collect_triplets_from_pool(api, triplet_pool, args.n_samples)

    if len(records) < 3 * args.n_samples:
        logger.warning(f'Only {len(records) // 3} triplets collected '
                       f'(target: {args.n_samples})')

    df = pd.DataFrame(records)

    # Analysis
    results = analyze(records, args)

    # Save results
    save_results(results, args)
    print_summary(results)

    # Plots
    make_plots(df, results, args)

    logger.info('Experiment complete.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
