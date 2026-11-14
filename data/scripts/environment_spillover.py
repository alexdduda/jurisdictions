"""How much of provincial environmental spending benefits other provinces.

The model's environment area is provincial and local spending on environmental
protection (COFOG 705). Its spillover range used to be a guess, 30% to 80%,
which suits air pollution. But most of this spending is waste and wastewater,
whose benefits mostly stay home. This splits 705 into its parts (Statistics
Canada table 10-10-0005, consolidated provincial-territorial and local, 2015-2024)
and gives each part a spillover range. The shares are measured; the per-part
ranges are assumptions, stated here so they can be argued with:

  waste management [7051]          0.00-0.05  landfills and collection are local
  waste water management [7052]    0.10-0.30  some effluent reaches rivers that cross
                                              provincial lines (Ottawa, St. Lawrence,
                                              the Saskatchewan rivers)
  pollution abatement [7053]       0.30-0.70  air and water pollution travel
  biodiversity and landscape [7054] 0.10-0.40 migratory species, shared watersheds
  not elsewhere classified [7055-6] 0.10-0.50 unknown mix

The area's spillover range is the spending-weighted sum of the lower and upper
ends.

    python3 data/scripts/environment_spillover.py   # writes data/environment_spillover.json
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
YEARS = {str(y) for y in range(2015, 2025)}
PARTS = {
    "Waste management [7051]": (0.00, 0.05),
    "Waste water management [7052]": (0.10, 0.30),
    "Pollution abatement [7053]": (0.30, 0.70),
    "Protection of biodiversity and landscape [7054]": (0.10, 0.40),
    "Environmental protection not elsewhere classified [7055, 7056]": (0.10, 0.50),
}


def main() -> dict:
    tot = {k: 0.0 for k in PARTS}
    with (ROOT / "data" / "raw" / "10100005.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            k = r["Canadian Classification of Functions of Government (CCOFOG)"]
            if (k in tot and r["GEO"] == "Canada" and r["REF_DATE"] in YEARS
                    and r["Public sector components"] == "Consolidated provincial-territorial and local governments"
                    and r["VALUE"]):
                tot[k] += float(r["VALUE"])
    s = sum(tot.values())
    shares = {k: round(v / s, 4) for k, v in tot.items()}
    lo = sum(shares[k] * PARTS[k][0] for k in PARTS)
    hi = sum(shares[k] * PARTS[k][1] for k in PARTS)
    out = {"source": "Statistics Canada 10-10-0005, Canada, consolidated provincial-territorial and local, 2015-2024",
           "shares": shares, "part_ranges": PARTS, "spillover_range": [round(lo, 3), round(hi, 3)]}
    (ROOT / "data" / "environment_spillover.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
