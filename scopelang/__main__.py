"""Run a scopelang program: python -m scopelang FILE [--tree] [--strict]"""

import argparse
import sys

from . import LexError, ParseError, run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scopelang", description=__doc__)
    ap.add_argument("file", help="a .jur program, or - for stdin")
    ap.add_argument("--tree", action="store_true", help="print the jurisdiction tree at the end")
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything was struck down")
    args = ap.parse_args(argv)

    source = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    try:
        result = run(source)
    except (LexError, ParseError) as err:
        print(f"syntax error: {err}", file=sys.stderr)
        return 2

    print(result.text(tree=args.tree))
    return 1 if args.strict and result.diagnostics else 0


if __name__ == "__main__":
    sys.exit(main())
