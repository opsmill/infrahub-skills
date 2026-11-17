"""Subprocess tests for the csv-import-no-schema-mutation task grader.

The task feeds a CSV with a column the schema does not declare, so the
fail-closed rule requires an output dir with no object rows and no schema
document. The grader used to bundle ``envelope``, which fails an empty
output dir, so the correct answer scored 0.0 on every trial.

The grader then looked only inside the output dir, so a run that wrote its
schema change next to it, or wrote nothing at all, scored 1.0 (review of
#247). It now scans the whole trial workspace for schema documents and reads
the report the task asks for at ``./import-report.md``.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GRADERS_DIR = Path(__file__).resolve().parent.parent.parent / "graders" / "importing-data"
GRADER = GRADERS_DIR / "check_no_schema_mutation.py"
# The csv-import-fail-closed task grader runs the same `fail-closed` check.
FAIL_CLOSED_GRADER = GRADERS_DIR / "check_fail_closed.py"

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

EXTENSION_DOC = """---
version: "1.0"
extensions:
  nodes:
    - kind: DcimDevice
      attributes:
        - name: gpu_count
          kind: Number
"""

REPORT = "gpu_count has no schema home on DcimDevice. Checked: DcimDevice.\n"

# The report the task asks for, at the trial workspace root next to output_dir.
IMPORT_REPORT = """Cannot import: 1 column has no schema home.

Unmapped columns:
  - devices.csv: gpu_count (checked DcimDevice, no matching attribute)

Schemas checked: DcimDevice.

To unblock this import, add the attribute through infrahub-managing-schemas.

No files have been written.
"""

DEFAULT_WORKSPACE = {"import-report.md": IMPORT_REPORT}


def _score(
    tmp_path: Path,
    files: dict[str, str],
    grader: Path = GRADER,
    workspace: dict[str, str] | None = None,
) -> float:
    """Score a trial: ``files`` go under output_dir, ``workspace`` at its root.

    The grader runs from an unrelated cwd, so it has to find the workspace
    from the output_dir argument, as it does in a trial.
    """
    out = tmp_path / "output_dir"
    out.mkdir()
    for rel, content in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(content)
    for rel, content in (DEFAULT_WORKSPACE if workspace is None else workspace).items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(content)
    proc = subprocess.run(
        [sys.executable, str(grader), str(out)],
        capture_output=True, text=True, check=True, cwd=GRADERS_DIR,
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
        # Compliant: the structured report as YAML. It lists the unmapped
        # columns as mappings, outside `spec` and `data` (review of #247).
        ({"report.yml": (
            "result: failed_closed\n"
            "unmapped_columns:\n"
            "  - file: devices.csv\n"
            "    column: gpu_count\n"
            "    kinds_checked: [DcimDevice]\n"
        )}, 1.0),
    ],
    ids=["report-only", "object-without-rows", "yaml-report"],
)
def test_fail_closed_answer_passes(tmp_path: Path, files: dict, expected: float) -> None:
    assert _score(tmp_path, files) == expected


@pytest.mark.parametrize(
    "files",
    [
        # Violating: the schema change the user did not approve.
        {"report.txt": REPORT, "schemas/dcim.yml": SCHEMA_DOC},
        # Violating: the same change as an extension of the existing node,
        # outside a schemas/ sub-path.
        {"report.txt": REPORT, "dcim_extension.yml": EXTENSION_DOC},
        # Violating: a schema document whose unquoted version loads as a float.
        {"report.txt": REPORT, "dcim.yml": SCHEMA_DOC.replace('"1.0"', "1.0")},
        # Near-miss: no schema document anywhere, so no-schema-mutation is
        # satisfied, but the partial write the rule forbids is there.
        {"01_dcim_devices.yml": OBJECT_ROWS, "report.txt": REPORT},
        # Near-miss: the same rows in a document without `kind: Object`.
        {"01_dcim_devices.yml": OBJECT_ROWS.replace("kind: Object\n", ""), "report.txt": REPORT},
        # Near-miss: the rows as a top-level YAML list, which parses to no
        # mapping document.
        {"01_dcim_devices.yml": "- name: spine-01\n  role: spine\n  status: active\n", "report.txt": REPORT},
        # Near-miss: an empty Object document, then the rows as a list
        # document in the same stream.
        {
            "01_dcim_devices.yml": OBJECT_ROWS.replace(
                "  data:\n    - name: spine-01\n      role: spine\n      status: active\n",
                "  data: []\n",
            ) + "---\n- name: spine-01\n  role: spine\n",
            "report.txt": REPORT,
        },
        # Near-miss: the rows under a top-level `data:` key, outside
        # `spec.data` (review of #247).
        {
            "01_dcim_devices.yml": "kind: DcimDevice\ndata:\n  - name: spine-01\n    role: spine\n",
            "report.txt": REPORT,
        },
        # Near-miss: the rows under `spec`, in a key other than `data`.
        {
            "01_dcim_devices.yml": OBJECT_ROWS.replace("  data:\n", "  rows:\n"),
            "report.txt": REPORT,
        },
        # Near-miss: the rows one level below `spec`.
        {
            "01_dcim_devices.yml": "kind: Object\nspec:\n  payload:\n    data:\n      - name: spine-01\n",
            "report.txt": REPORT,
        },
        # Near-miss: a `data` list of scalars, in a document with no `kind`.
        {"01_dcim_devices.yml": "data:\n  - spine-01\n  - spine-02\n", "report.txt": REPORT},
    ],
    ids=[
        "schema-document",
        "extension-document",
        "float-version",
        "partial-object-write",
        "partial-write-without-kind",
        "partial-write-as-list",
        "partial-write-as-list-after-mapping",
        "partial-write-top-level-data",
        "partial-write-other-spec-key",
        "partial-write-nested-under-spec",
        "partial-write-scalar-data",
    ],
)
def test_schema_change_or_partial_write_fails(tmp_path: Path, files: dict) -> None:
    assert _score(tmp_path, files) < 1.0


# A structured YAML report that names the kind it checked. Its top-level
# list of mappings describes the unmapped columns; it is not object rows
# (review of #247).
KIND_REPORT = (
    "kind: DcimDevice\n"
    "status: failed\n"
    "unmapped_columns:\n"
    "  - column: license_tier\n"
    "    reason: no attribute, relationship or dropdown on DcimDevice\n"
)


@pytest.mark.parametrize("grader", [GRADER, FAIL_CLOSED_GRADER], ids=["no-schema-mutation", "fail-closed"])
@pytest.mark.parametrize(
    "files",
    [
        # Compliant: a YAML report that names the kind it checked.
        {"report.yml": KIND_REPORT},
        # Compliant: a YAML file that holds only a comment, so no document.
        {"report.yml": "# Import aborted: license_tier has no schema home\n"},
        # Compliant: an empty YAML file.
        {"report.yml": ""},
    ],
    ids=["kind-report", "comment-only", "empty-file"],
)
def test_report_without_rows_passes(tmp_path: Path, files: dict, grader: Path) -> None:
    assert _score(tmp_path, files, grader) == 1.0


@pytest.mark.parametrize("grader", [GRADER, FAIL_CLOSED_GRADER], ids=["no-schema-mutation", "fail-closed"])
@pytest.mark.parametrize(
    "files",
    [
        # Near-miss: the same report, with the rows under a top-level `data:`.
        {"report.yml": KIND_REPORT + "data:\n  - name: spine-01\n    license_tier: gold\n"},
        # Near-miss: the rows under `data` nested in a report section.
        {"report.yml": KIND_REPORT + "result:\n  data:\n    - name: spine-01\n"},
        # Near-miss: the report as a top-level list. A report is a mapping.
        {"report.yml": "- column: license_tier\n  kind: DcimDevice\n"},
        # Near-miss: a comment line, then a file that does not parse as YAML.
        {"report.yml": "# Import aborted\nkey: [unclosed\n"},
    ],
    ids=["kind-report-with-data", "nested-data", "list-report", "unparseable"],
)
def test_report_with_rows_or_unreadable_fails(tmp_path: Path, files: dict, grader: Path) -> None:
    assert _score(tmp_path, files, grader) < 1.0


# A copy of the skills and graders the way skillgrade lays them out. Their
# YAML includes schema documents, which are not the run's own writes.
SKILL_SCHEMA_COPIES = {
    ".claude/skills/infrahub-managing-schemas/examples/dcim.yml": SCHEMA_DOC,
    ".agents/skills/infrahub-managing-schemas/examples/dcim.yml": SCHEMA_DOC,
    "skills/infrahub-managing-schemas/examples/dcim.yml": SCHEMA_DOC,
    "graders/importing-data/fixtures/schema.yml": SCHEMA_DOC,
}


@pytest.mark.parametrize(
    ("files", "workspace"),
    [
        # Compliant: the report at the workspace root, an empty output dir,
        # and an unrelated YAML file that is not a schema document.
        ({}, {**DEFAULT_WORKSPACE, "config/settings.yml": "branch: csv-import\nserver: http://localhost:8000\n"}),
        # Compliant: schema documents inside the copies skillgrade lays out,
        # which the run did not write.
        ({}, {**DEFAULT_WORKSPACE, **SKILL_SCHEMA_COPIES}),
    ],
    ids=["report-and-unrelated-yaml", "skill-and-grader-copies"],
)
def test_workspace_without_schema_change_passes(
    tmp_path: Path, files: dict, workspace: dict
) -> None:
    assert _score(tmp_path, files, workspace=workspace) == 1.0


@pytest.mark.parametrize(
    ("files", "workspace"),
    [
        # Violating (review of #247): an empty output dir, a correct report,
        # and the schema extension written at the workspace root.
        ({}, {**DEFAULT_WORKSPACE, "schemas/dcim.yml": EXTENSION_DOC}),
        # Violating: the same change as a node document beside the output dir.
        ({}, {**DEFAULT_WORKSPACE, "dcim.yaml": SCHEMA_DOC}),
        # Violating (review of #247): nothing written at all.
        ({}, {}),
        # Violating: the report is in the output dir, not where the task asks.
        ({"report.txt": REPORT}, {}),
        # Near-miss: the report names the column but not the kind it checked.
        ({}, {"import-report.md": "Cannot import: gpu_count has no schema home.\n"}),
        # Near-miss: the report names the kind but not the column.
        ({}, {"import-report.md": "Cannot import: a column has no home on DcimDevice.\n"}),
        # Near-miss: an empty report file.
        ({}, {"import-report.md": ""}),
    ],
    ids=[
        "extension-at-workspace-root",
        "node-document-beside-output-dir",
        "nothing-written",
        "report-in-output-dir-only",
        "report-without-kind",
        "report-without-column",
        "empty-report",
    ],
)
def test_schema_change_outside_output_dir_or_missing_report_fails(
    tmp_path: Path, files: dict, workspace: dict
) -> None:
    assert _score(tmp_path, files, workspace=workspace) < 1.0
