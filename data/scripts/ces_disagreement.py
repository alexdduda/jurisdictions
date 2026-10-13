"""Between- vs within-province disagreement from the 2019 Canadian Election Study.

Needs pandas and pyreadstat (data prep only; the simulation itself stays stdlib).

    python data/scripts/ces_disagreement.py data/raw/ces/ces2019_web.dta

Each answer (spend less / about the same / more) is read as a latent desired
level, normal within a province with sd 1, cut at two thresholds shared by all
provinces. A province's mean on that latent scale follows from its answer
shares: mu = -(Phi^-1(p_less) + Phi^-1(1 - p_more)) / 2, up to a constant.
The spread of provincial means, with sampling noise removed by bootstrap, is
then measured in units of within-province disagreement: rho = sd_between / sd_within.
"""

import json
import sys
from statistics import NormalDist

import numpy as np
import pyreadstat

PROVINCES = ["Newfoundland and Labrador", "Prince Edward Island", "Nova Scotia", "New Brunswick", "Quebec",
             "Ontario", "Manitoba", "Saskatchewan", "Alberta", "British Columbia"]
ITEMS = {
    "schools": ("cps19_spend_educ", "cps19_weight_general_all", {1: "low", 2: "mid", 3: "high"}),
    "environment": ("cps19_spend_env", "cps19_weight_general_all", {1: "low", 2: "mid", 3: "high"}),
    # "How much should be done to reduce the gap between the rich and the poor?"
    # 1 much more ... 5 much less; collapsed to more / same / less.
    "redistribution": ("pes19_gap", "pes19_weight_general_all", {1: "high", 2: "high", 3: "mid", 4: "low", 5: "low"}),
    # "To help reduce greenhouse gas emissions, the federal government should
    # continue the carbon tax." 1 strongly disagree ... 5 strongly agree.
    "climate": ("cps19_pos_carbon", "cps19_weight_general_all", {1: "low", 2: "low", 3: "mid", 4: "high", 5: "high"}),
}
inv = NormalDist().inv_cdf


def province_means(prov, ans, w, coding):
    mus = []
    for p in PROVINCES:
        m = prov == p
        tot = {k: w[m & (ans == code)].sum() for code, k in coding.items() for _ in [0]}
        low = sum(w[m & (ans == c)].sum() for c, k in coding.items() if k == "low")
        high = sum(w[m & (ans == c)].sum() for c, k in coding.items() if k == "high")
        n = sum(w[m & (ans == c)].sum() for c in coding)
        pl, ph = np.clip(low / n, 0.005, 0.995), np.clip(high / n, 0.005, 0.995)
        mus.append(-(inv(pl) + inv(1 - ph)) / 2)
    return np.array(mus)


def main(path):
    out = {}
    rng = np.random.default_rng(2019)
    for key, (var, wvar, coding) in ITEMS.items():
        df, meta = pyreadstat.read_dta(path, usecols=["cps19_province", var, wvar], encoding="latin1",
                                       apply_value_formats=False)
        labels = meta.variable_value_labels["cps19_province"]
        df["prov"] = df["cps19_province"].map(labels)
        df = df[df["prov"].isin(PROVINCES) & df[var].isin(list(coding)) & df[wvar].notna()]
        prov, ans, w = df["prov"].to_numpy(), df[var].to_numpy(), df[wvar].to_numpy()
        mus = province_means(prov, ans, w, coding)
        observed = mus.std()
        # Sampling noise: resample respondents within each province, recompute the spread.
        boots = []
        idx_by = {p: np.flatnonzero(prov == p) for p in PROVINCES}
        for _ in range(200):
            take = np.concatenate([rng.choice(ix, size=len(ix)) for ix in idx_by.values()])
            boots.append(province_means(prov[take], ans[take], w[take], coding))
        noise_var = np.mean([np.var(b - mus) for b in boots])
        rho = float(np.sqrt(max(observed ** 2 - noise_var, 0.0)))
        out[key] = {
            "question": var,
            "respondents": int(len(df)),
            "province_means": {p: round(float(m), 3) for p, m in zip(PROVINCES, mus)},
            "rho_raw": round(float(observed), 4),
            "rho": round(rho, 4),
        }
        print(f"{key}: n={len(df)} rho_raw={observed:.3f} rho_noise_corrected={rho:.3f}")
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    res = main(sys.argv[1])
    json.dump(res, open(sys.argv[2] if len(sys.argv) > 2 else "data/ces_disagreement.json", "w"), indent=2)
