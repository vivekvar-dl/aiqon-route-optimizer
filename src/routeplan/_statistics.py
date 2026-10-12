"""Finite-sample uncertainty under the assumed simulator, not model uncertainty."""

from __future__ import annotations

import math


def wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    """Two-sided 95% Wilson interval for a simulated Bernoulli frequency."""
    if trials < 1 or not 0 <= successes <= trials:
        raise ValueError("need positive trials and successes from 0 to trials")
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0.0, center - half), min(1.0, center + half)
