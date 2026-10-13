"""tiebout: find the best split of power between a nation and its regions.

    python -m tiebout study [--seeds N] [--quick] [--out DIR]
    python -m tiebout uncertainty [--draws N] [--seeds N] [--ranges wide|canada]
    python -m tiebout evaluate FILE.jur [--seeds N]
"""

import argparse
import sys
from pathlib import Path

from .bridge import jur_to_arrangement
from .config import DEFAULT_WORLD
from .optimize import Evaluator, make_pool


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tiebout", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("study", help="optimise, map the trade-offs, write a report")
    st.add_argument("--seeds", type=int, default=6)
    st.add_argument("--workers", type=int, default=None)
    st.add_argument("--quick", action="store_true", help="small world, coarse maps (for smoke tests)")
    st.add_argument("--out", default="results")

    un = sub.add_parser("uncertainty", help="sample parameter ranges and find robust policies")
    un.add_argument("--draws", type=int, default=200)
    un.add_argument("--seeds", type=int, default=3)
    un.add_argument("--check-worlds", type=int, default=8)
    un.add_argument("--out", default="results")
    un.add_argument("--ranges", choices=("wide", "canada"), default="wide",
                    help="wide: guessed ranges; canada: calibrated to Statistics Canada data where possible")
    un.add_argument("--only", nargs="+", metavar="AREA",
                    help="re-run only these policy areas (and the cross-check), keeping the rest")

    ev = sub.add_parser("evaluate", help="score the arrangement declared by a scopelang program")
    ev.add_argument("file")
    ev.add_argument("--seeds", type=int, default=6)
    ev.add_argument("--scope", default="nation", help="scope whose laws define the arrangement")

    args = ap.parse_args(argv)
    # Long runs usually write to a log file; flush each line so progress is visible.
    sys.stdout.reconfigure(line_buffering=True)

    if args.cmd == "study":
        from .experiments import run_study

        out = Path(args.out)
        run_study(list(range(args.seeds)), out, workers=args.workers, quick=args.quick)
        print(f"\nwrote {out / 'REPORT.md'}, {out / 'best_arrangement.jur'}, {out / 'results.json'}")
        return 0

    if args.cmd == "uncertainty":
        from .uncertainty import run_uncertainty

        run_uncertainty(Path(args.out), args.draws, args.seeds, args.check_worlds, ranges=args.ranges, only=args.only)
        return 0

    source = Path(args.file).read_text(encoding="utf-8")
    arrangement, warnings = jur_to_arrangement(source, DEFAULT_WORLD, args.scope)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    with make_pool() as pool:
        score = Evaluator(DEFAULT_WORLD, list(range(args.seeds)), pool).score([arrangement])[0]
    for name, policy in arrangement.items():
        print(f"  {name:<16} {policy.label()}")
    print(f"welfare {score.welfare:.4f} ± {score.se:.4f} ({args.seeds} seeds)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
