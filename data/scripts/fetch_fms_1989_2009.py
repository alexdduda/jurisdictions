"""Fetch provincial-plus-local spending by function, 1989-2009, from the
Statistics Canada Web Data Service (table 10-10-0039, Financial Management
System, archived). Writes data/historical/fms_1989_2009.csv.

The FMS classification is older than the CCOFOG one used for 2008-2024
(table 10-10-0005), so the two are bridged on their overlap years in
validation/backtest.py rather than spliced.

    python3 data/scripts/fetch_fms_1989_2009.py
"""

import csv
import json
import urllib.request
from pathlib import Path

API = "https://www150.statcan.gc.ca/t1/wds/rest/"
PRODUCT = 10100039
PROVINCES = ["Newfoundland and Labrador", "Prince Edward Island", "Nova Scotia", "New Brunswick",
             "Quebec", "Ontario", "Manitoba", "Saskatchewan", "Alberta", "British Columbia"]
# Member ids in dimension 3 ("Revenue and expenditure"); sector 3 is
# "Local and provincial and territorial governments".
ITEMS = {34: "Total expenditures", 51: "Elementary and secondary education", 56: "Environment",
         37: "Transportation and communication", 43: "Social services", 44: "Social assistance"}
OUT = Path(__file__).resolve().parent.parent / "historical" / "fms_1989_2009.csv"


def post(endpoint: str, body: list) -> list:
    req = urllib.request.Request(API + endpoint, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def main() -> None:
    coords = [(g, i) for g in range(2, 12) for i in ITEMS]
    info = post("getSeriesInfoFromCubePidCoord",
                [{"productId": PRODUCT, "coordinate": f"{g}.3.{i}.0.0.0.0.0.0.0"} for g, i in coords])
    # Responses don't come back in request order: key each on its own coordinate.
    def parse(coord: str) -> tuple[int, int]:
        g, _, i = coord.split(".")[:3]
        return int(g), int(i)
    vectors = {x["object"]["vectorId"]: parse(x["object"]["coordinate"]) for x in info}
    titles = {x["object"]["vectorId"]: x["object"]["SeriesTitleEn"] for x in info}
    data = post("getDataFromVectorsAndLatestNPeriods", [{"vectorId": v, "latestN": 25} for v in vectors])
    rows = []
    for x in data:
        o = x["object"]
        g, i = vectors[o["vectorId"]]
        assert titles[o["vectorId"]].startswith(PROVINCES[g - 2]) and titles[o["vectorId"]].endswith(ITEMS[i])
        for p in o["vectorDataPoint"]:
            rows.append({"province": PROVINCES[g - 2], "fiscal_year_end": p["refPerRaw"][:10], "item": ITEMS[i],
                         "dollars_millions": p["value"], "vector": f"v{o['vectorId']}"})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
