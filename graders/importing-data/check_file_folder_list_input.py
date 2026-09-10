#!/usr/bin/env python3
"""Grader for the csv-import-file-folder-list-input eval task.

Asserts all three input shapes are described, with .tsv and non-CSV disposition.

Usage::

    python check_file_folder_list_input.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import run_checks  # noqa: E402

CHECKS = ['input-shapes-normalized']


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output_dir")
    print(json.dumps(run_checks(CHECKS, output_dir)))


if __name__ == "__main__":
    main()
