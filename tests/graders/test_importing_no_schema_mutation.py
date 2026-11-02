"""Subprocess tests for the csv-import-no-schema-mutation task grader.

The task feeds a CSV with a column the schema does not declare, so the
fail-closed rule requires an output dir with no object rows and no schema
document. The grader used to bundle ``envelope``, which fails an empty
output dir, so the correct answer scored 0.0 on every trial.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GRADER = (
    Path(__file__).resolve().parent.parent.parent
    / "graders" / "importing-data" / "check_no_schema_mutation.py"
)

OBJECT_ROWS = """---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: spine-01
      role: spine
      status: active
"""

SCHEMA_DOC = """---
version: "1.0"
nodes:
  - name: Device
    namespace: Dcim
    attributes:
      - name: gpu_count
        kind: Number
"""

REPORT = "gpu_count has no schema home on DcimDevice. Checked: DcimDevice.\n"


def _score(tmp_path: Path, files: dict[str, str]) -> float:
    out = tmp_path / "output_dir"
    out.mkdir()
    for rel, content in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(content)
    proc = subprocess.run(
        [sys.executable, str(GRADER), str(out)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)["score"]


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        # Compliant, the way the rule shows it: a report and nothing else.
        ({"report.txt": REPORT}, 1.0),
        # Compliant, refactored: an Object document that carries no rows.
        ({"01_dcim_devices.yml": OBJECT_ROWS.replace(
            "  data:\n    - name: spine-01\n      role: spine\n      status: active\n",
            "  data: []\n",
        )}, 1.0),
    ],
    ids=["report-only", "object-without-rows"],
)
def test_fail_closed_answer_passes(tmp_path: Path, files: dict, expected: float) -> None:
    assert _score(tmp_path, files) == expected


@pytest.mark.parametrize(
    "files",
    [
        # Violating: the schema change the user did not approve.
        {"report.txt": REPORT, "schemas/dcim.yml": SCHEMA_DOC},
        # Near-miss: no schema document anywhere, so no-schema-mutation is
        # satisfied, but the partial write the rule forbids is there.
        {"01_dcim_devices.yml": OBJECT_ROWS, "report.txt": REPORT},
    ],
    ids=["schema-document", "partial-object-write"],
)
def test_schema_change_or_partial_write_fails(tmp_path: Path, files: dict) -> None:
    assert _score(tmp_path, files) < 1.0
