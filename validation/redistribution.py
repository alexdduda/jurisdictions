"""Validation: does provincial redistribution follow provincial inequality?

The model sets a region's redistribution from income inequality alone (the
median earner's preferred rate). That predicts, across provinces, a positive
link from market-income inequality to (a) wanting redistribution and (b)
spending on it. Neither input was used to calibrate the model.

    python3 validation/redistribution.py

Result (2015-2024, ten provinces): inequality predicts wanting redistribution
(+0.58) but not spending on it (-0.19). Provinces' fiscal capacity and federal
programs, both absent from the model, are the likely gap. n = 10, so treat the
signs as evidence, not proof.
"""

import json
import random
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tiebout.canada import PROVINCES, TOP_LEVEL, YEARS, rows, spending, value  # noqa: E402


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0] * len(xs)
    for k, i in enumerate(order):
        r[i] = k
    return r


def spearman(a, b):
    ra, rb, n = ranks(a), ranks(b), len(a)
    return 1 - 6 * sum((x - y) ** 2 for x, y in zip(ra, rb)) / (n * (n * n - 1))


def permutation_p(a, b, n=20000, seed=1):
    rng, obs, hits = random.Random(seed), abs(spearman(a, b)), 0
    for _ in range(n):
        bb = b[:]
        rng.shuffle(bb)
        hits += abs(spearman(a, bb)) >= obs
    return hits / n


def main():
    gini: dict[str, list[float]] = {}
    for r in rows("11100134.csv"):
        if r["GEO"] in PROVINCES and r["REF_DATE"] in YEARS and r["Income concept"] == "Adjusted market income":
            v = value(r)
            if v is not None:
                gini.setdefault(r["GEO"], []).append(v)
    spend = spending()
    share = {
        p: mean(spend[(p, y, "Social protection [710]")] / sum(spend[(p, y, t)] for t in TOP_LEVEL)
                for y in YEARS if (p, y, "Social protection [710]") in spend)
        for p in PROVINCES
    }
    survey = json.loads((ROOT / "data" / "ces_disagreement.json").read_text())["redistribution"]["province_means"]

    g = [mean(gini[p]) for p in PROVINCES]
    sh = [share[p] for p in PROVINCES]
    sv = [survey[p] for p in PROVINCES]
    result = {
        "inequality_to_wanting": {"spearman": round(spearman(g, sv), 3), "p": permutation_p(g, sv), "model_predicts": "positive"},
        "inequality_to_spending": {"spearman": round(spearman(g, sh), 3), "p": permutation_p(g, sh), "model_predicts": "positive"},
        "wanting_to_spending": {"spearman": round(spearman(sv, sh), 3), "p": permutation_p(sv, sh)},
    }
    (ROOT / "validation" / "redistribution.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
