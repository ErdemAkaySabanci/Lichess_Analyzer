"""Small A/B-test style statistics helpers for the dashboard's Experiments section.

Only the standard library and numpy (already pulled in by pandas) are used, so
the lean Streamlit Cloud environment needs no extra dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log, exp, sqrt

import numpy as np
from statistics import NormalDist

_N = NormalDist()


@dataclass
class ProportionTest:
    """Two-sample comparison of success rates, group A minus group B."""
    n_a: int
    n_b: int
    rate_a: float
    rate_b: float
    diff: float
    ci_low: float
    ci_high: float
    p_value: float
    odds_ratio: float
    or_ci_low: float
    or_ci_high: float


def two_proportion_test(x_a: int, n_a: int, x_b: int, n_b: int, alpha: float = 0.05) -> ProportionTest:
    """Two-sided two-proportion z-test with a Wald CI and a log-odds-ratio CI.

    The p-value uses the pooled standard error (the null says the rates are
    equal); the confidence interval uses the unpooled one (it describes the
    observed difference).
    """
    x_a, n_a, x_b, n_b = int(x_a), int(n_a), int(x_b), int(n_b)
    p_a, p_b = x_a / n_a, x_b / n_b
    diff = p_a - p_b
    z_crit = _N.inv_cdf(1 - alpha / 2)

    pooled = (x_a + x_b) / (n_a + n_b)
    se_null = sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = diff / se_null if se_null > 0 else 0.0
    p_value = 2 * _N.cdf(-abs(z))

    se = sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)

    # +0.5 on every cell (Haldane-Anscombe) keeps the odds ratio finite at 0 or n
    a, b, c, d = x_a + 0.5, n_a - x_a + 0.5, x_b + 0.5, n_b - x_b + 0.5
    log_or = log((a / b) / (c / d))
    se_log_or = sqrt(1 / a + 1 / b + 1 / c + 1 / d)

    return ProportionTest(
        n_a=n_a, n_b=n_b, rate_a=p_a, rate_b=p_b, diff=diff,
        ci_low=diff - z_crit * se, ci_high=diff + z_crit * se, p_value=p_value,
        odds_ratio=exp(log_or),
        or_ci_low=exp(log_or - z_crit * se_log_or), or_ci_high=exp(log_or + z_crit * se_log_or),
    )


def share_vs_half_pvalue(x: int, n: int) -> float:
    """Sample-ratio-mismatch check: is the share x/n consistent with a 50/50 split?"""
    z = (x - n / 2) / sqrt(n / 4)
    return 2 * _N.cdf(-abs(z))


def required_n_per_group(p_a: float, p_b: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Games needed in EACH group to detect p_a vs p_b with a two-sided z-test."""
    if p_a == p_b:
        return 0
    z_alpha, z_beta = _N.inv_cdf(1 - alpha / 2), _N.inv_cdf(power)
    p_bar = (p_a + p_b) / 2
    numerator = (z_alpha * sqrt(2 * p_bar * (1 - p_bar))
                 + z_beta * sqrt(p_a * (1 - p_a) + p_b * (1 - p_b))) ** 2
    return int(np.ceil(numerator / (p_a - p_b) ** 2))


def minimum_detectable_diff(n_per_group: int, base_rate: float, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest win-rate difference detectable with n games per group (approximate)."""
    z = _N.inv_cdf(1 - alpha / 2) + _N.inv_cdf(power)
    return z * sqrt(2 * base_rate * (1 - base_rate) / n_per_group)


def permutation_pvalue(wins_a: np.ndarray, wins_b: np.ndarray, n_perm: int = 5000, seed: int = 0) -> float:
    """Two-sided permutation test on the difference in win rates (no normality assumption)."""
    rng = np.random.default_rng(seed)
    pooled = np.concatenate([wins_a, wins_b]).astype(np.int8)
    n_a = len(wins_a)
    observed = abs(wins_a.mean() - wins_b.mean())
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        if abs(pooled[:n_a].mean() - pooled[n_a:].mean()) >= observed:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def aa_false_positive_rate(wins: np.ndarray, n_sims: int = 1000, alpha: float = 0.05, seed: int = 0) -> float:
    """A/A test: split the same games at random into two halves and count how often
    the z-test calls them different. A sound test should do so about alpha of the time."""
    rng = np.random.default_rng(seed)
    wins = wins.astype(np.float64)
    n = len(wins)
    half = n // 2
    z_crit = _N.inv_cdf(1 - alpha / 2)
    rejections = 0
    for _ in range(n_sims):
        shuffled = rng.permutation(wins)
        a, b = shuffled[:half], shuffled[half:2 * half]
        pooled = (a.sum() + b.sum()) / (2 * half)
        se = sqrt(pooled * (1 - pooled) * 2 / half)
        if se > 0 and abs(a.mean() - b.mean()) / se > z_crit:
            rejections += 1
    return rejections / n_sims


def stratified_diff(strata: list[tuple[int, int, int, int]], alpha: float = 0.05, min_n: int = 30):
    """Inverse-variance weighted win-rate difference (A minus B) across strata.

    Each stratum is (wins_a, n_a, wins_b, n_b), e.g. one opponent-rating band.
    Comparing within a band removes the effect of the groups facing different
    opposition. Strata with fewer than min_n games in either group are skipped.
    Returns (diff, ci_low, ci_high, p_value, n_strata_used) or None if none qualify.
    """
    weights, diffs = [], []
    for x_a, n_a, x_b, n_b in strata:
        if n_a < min_n or n_b < min_n:
            continue
        p_a, p_b = x_a / n_a, x_b / n_b
        # +0.5/+1 smoothing keeps the variance positive when a band is all wins or losses
        v_a, v_b = (x_a + 0.5) / (n_a + 1), (x_b + 0.5) / (n_b + 1)
        var = v_a * (1 - v_a) / n_a + v_b * (1 - v_b) / n_b
        weights.append(1 / var)
        diffs.append(p_a - p_b)
    if not weights:
        return None
    w = np.array(weights)
    diff = float(np.dot(w, diffs) / w.sum())
    se = float(1 / sqrt(w.sum()))
    z_crit = _N.inv_cdf(1 - alpha / 2)
    p_value = 2 * _N.cdf(-abs(diff / se))
    return diff, diff - z_crit * se, diff + z_crit * se, p_value, len(weights)


def wilson_ci(x: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a single proportion (behaves well at small n)."""
    z = _N.inv_cdf(1 - alpha / 2)
    p = x / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half
