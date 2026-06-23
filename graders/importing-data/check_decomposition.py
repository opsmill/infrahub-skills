#!/usr/bin/env python3
"""Grader for the csv-import-decomposition eval task.

Asserts that ONE denormalized CSV (a single sheet conflating several kinds,
with parent columns repeated per child row) is split into the right kinds:

- Every conflated kind appears, each produced by exactly one NN-prefixed file
  (the sheet was split, not dumped into a single kind).
- Repeated parent values are deduped (no duplicate HFID ``name`` within a
  referent kind).
- Referent kinds load before the referring kind, so ``object load`` resolves
  each reference target before the row that points at it.
- Device references to the referent kinds are scalar HFIDs (target HFID
  length 1).

Usage::

    python check_decomposition.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ["envelope", "load-order-numbering", "hfid-reference-shape", "decomposition"]


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
