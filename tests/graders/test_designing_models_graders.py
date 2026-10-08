"""Four-fixture tests for the infrahub-designing-models task graders.

Each task grader is run as a subprocess, the way skillgrade runs it, against
four hand-written workspaces: compliant, a compliant variant shaped the way
the check's parsing is vulnerable to, violating, and a violating near miss
that keeps the right vocabulary while breaking the rule. Expected scores are
1.0, 1.0, below 1.0, below 1.0.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRADER_DIR = REPO_ROOT / "graders" / "designing-models"
EVAL_YAML = REPO_ROOT / "eval.yaml"


def run_grader(script: str, workspace: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(GRADER_DIR / script), str(workspace)],
        capture_output=True, text=True, check=True, cwd=workspace,
    )
    return json.loads(proc.stdout)


def write(ws: Path, rel: str, text: str) -> None:
    path = ws / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


SKETCH_HEADER = (
    "| Feature | Node kind | Identified by | Key attributes (value class) "
    "| Peers (cardinality) | Source of truth | Owner | Evidence |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
)

DECISIONS = """\
| # | Decision | Tag | Basis |
| --- | --- | --- | --- |
| 1 | Sites are imported from the facilities sheet | stated | |
| 2 | VLAN IDs come from a number pool | recommended | Pool avoids clashes; you allocate by hand today (strong) |
"""


def brief(
    *,
    inputs: str = "none\n",
    sketch_rows: str,
    features: str | None = None,
    decisions: str | None = DECISIONS,
    open_items: str = "none\n",
) -> str:
    parts = [
        "# Design brief: test\n",
        "## Summary\n\nWhat the team needs and what is not decided.\n",
        f"## Inputs\n\n{inputs}",
        "## Business\n\nWho uses the data and why.\n",
        "## Service\n\nWhat is ordered.\n",
    ]
    if features is not None:
        parts.append(f"## Features\n\n{features}")
    parts.append(f"## Data model sketch\n\n{SKETCH_HEADER}{sketch_rows}")
    parts.append("## Mechanisms\n\nNo generator: nothing creates objects.\n")
    if decisions is not None:
        parts.append(f"## Decision log\n\n{decisions}")
    parts.append(f"## Open items\n\n{open_items}")
    return "\n".join(parts)


BRIEF = "docs/designs/test/design-brief.md"
SPEC_KIT_BRIEF = "specs/test-design/design-brief.md"


# --------------------------------------------------------------------------
# interview-one-question-recommended
# --------------------------------------------------------------------------

Q_COMPLIANT = """\
**Q1 (business):** Which decision or report fails today because cabinet or power data is wrong?

- A. Capacity planning: we sell power we do not have
- B. Billing: cross-connects are invoiced late or not at all  **(Recommended)**
- C. Field work: technicians patch the wrong cabinet

**Basis:** you named cross-connects first, and billing errors are the usual reason this data gets modelled (weak basis).
"""

Q_VARIANT = """\
Before I sketch anything, one question about why this data matters (background: https://docs.infrahub.app/topics/schema?tab=design).

**Q1 (business):** Who stops work today when cabinet data is wrong?

* A. Sales, because quotes promise space that is taken
* B. Facilities, because power budgets are exceeded
* C. Field engineers, because cross-connect records are stale
* D. Billing, because cross-connects are not invoiced **(Recommended)**

**Basis:** your request lists three things you sell, and
cross-connects are the only one billed per item (medium).
"""

Q_VIOLATING = """\
Here is a first draft:

```yaml
version: "1.0"
nodes:
  - name: Cabinet
    namespace: Colo
```

Does this look right?
"""

Q_NEAR_SECOND_QUESTION = Q_COMPLIANT + "\nAlso, which system owns cabinet records today?\n"
Q_NEAR_TWO_RECOMMENDED = Q_COMPLIANT.replace(
    "- A. Capacity planning: we sell power we do not have",
    "- A. Capacity planning: we sell power we do not have  **(Recommended)**",
)
Q_NEAR_EMPTY_BASIS = Q_COMPLIANT.split("**Basis:**")[0] + "**Basis:**\n"


@pytest.mark.parametrize(
    ("answer", "should_pass"),
    [
        pytest.param(Q_COMPLIANT, True, id="compliant"),
        pytest.param(Q_VARIANT, True, id="compliant-variant"),
        pytest.param(Q_VIOLATING, False, id="violating-yaml"),
        pytest.param(Q_NEAR_SECOND_QUESTION, False, id="near-miss-second-question"),
        pytest.param(Q_NEAR_TWO_RECOMMENDED, False, id="near-miss-two-recommended"),
        pytest.param(Q_NEAR_EMPTY_BASIS, False, id="near-miss-empty-basis"),
    ],
)
def test_one_question_recommended(tmp_path: Path, answer: str, should_pass: bool) -> None:
    write(tmp_path, "output_dir/answer.md", answer)
    result = run_grader("check_one_question_recommended.py", tmp_path)
    assert (result["score"] == 1.0) is should_pass, result["details"]


# --------------------------------------------------------------------------
# interview-inputs-digested
# --------------------------------------------------------------------------

INPUTS_TABLE = """\
| File | Taken from it |
| --- | --- |
| pops.csv | pop_code identifies each PoP; region becomes the parent |
| backbone.txt | PoP routers and the links between PoPs |
"""

INPUT_ROWS = """\
| F1 | LocationRegion | region | name (imported) | PoP (many) | Facilities sheet | Facilities | pops.csv:region |
| F1 | LocationPop | pop_code | name, city (imported) | Region (one) | Facilities sheet | Facilities | pops.csv:pop_code |
| F1 | NetworkBackboneLink | endpoints a and b | capacity (stated) | Router (two) | Infrahub | Backbone team | backbone.txt:links |
"""

INPUTS_VARIANT_TABLE = """\
Two files came with the request.

| Taken from it | File |
|:--|:--|
| routers per PoP and inter-PoP links | `backbone.txt` |
| region hierarchy and the PoP code | `inputs/pops.csv` |
"""

INPUT_VARIANT_ROWS = """\
| F1 | NetworkBackboneLink | endpoints a and b | capacity (stated) | Router (two) | Infrahub | Backbone team | `backbone.txt` (link lines) |
| F1 | LocationPop | `pop_code` | name, city (imported) | Region (one) | Facilities sheet | Facilities | pops.csv (pop_code column) |
| F1 | LocationRegion | `region` | name (imported) | PoP (many) | Facilities sheet | Facilities | pops.csv (region column) |
"""


@pytest.mark.parametrize(
    ("rel", "text", "should_pass"),
    [
        pytest.param(BRIEF, brief(inputs=INPUTS_TABLE, sketch_rows=INPUT_ROWS), True, id="compliant"),
        pytest.param(
            SPEC_KIT_BRIEF,
            brief(inputs=INPUTS_VARIANT_TABLE, sketch_rows=INPUT_VARIANT_ROWS),
            True, id="compliant-variant",
        ),
        pytest.param(BRIEF, brief(inputs="none\n", sketch_rows=INPUT_ROWS), False, id="violating-no-inputs"),
        pytest.param(
            BRIEF,
            brief(
                inputs=INPUTS_TABLE.replace("| backbone.txt | PoP routers and the links between PoPs |\n", ""),
                sketch_rows=INPUT_ROWS,
            ),
            False, id="near-miss-file-missing",
        ),
        pytest.param(
            BRIEF,
            brief(inputs=INPUTS_TABLE, sketch_rows=INPUT_ROWS.replace("pops.csv:pop_code", "user")),
            False, id="near-miss-evidence-user",
        ),
    ],
)
def test_inputs_digested(tmp_path: Path, rel: str, text: str, should_pass: bool) -> None:
    write(tmp_path, rel, text)
    result = run_grader("check_inputs_digested.py", tmp_path)
    assert (result["score"] == 1.0) is should_pass, result["details"]


# --------------------------------------------------------------------------
# scope-split-before-data-layer
# --------------------------------------------------------------------------

FEATURES = """\
| ID | Feature | Intent | Scope boundary | Artifacts | Depends on | Status | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | DC fabric | Know what is racked where | Site, Rack, Device, Interface | schema, objects | - | planned | |
| F2 | IPAM | Allocate prefixes without clashes | Prefix, IP pool | schema | F1 | planned | |
| F3 | Firewall policy | Rules follow zones | Zone, Rule | schema, check, transform | F1, F2 | planned | |
| F4 | Customer peering | Sessions per customer | Peer, Session | schema, generator | F2 | planned | |

F1 prompt: `/speckit.specify DC fabric: sites, racks, devices and interfaces.`
"""

FEATURES_VARIANT = """\
The estate splits into four features, built in this order.

| Depends on | ID | Feature | Intent | Scope boundary | Status | Spec | Artifacts |
|---|---|---|---|---|---|---|---|
| none | `F1` | DC fabric | Know what is racked where | Site, Rack, Device | planned | | `schema` |
| after F1 | `F2` | IPAM | Prefixes without clashes | Prefix, IP pool | planned | | Schema; Objects |
| after F1 and F2 | `F3` | Firewall policy | Rules follow zones | Zone, Rule | planned | | check and transform |
| F2 | `F4` | Customer peering | Sessions per customer | Peer, Session | planned | | schema -> generator |

Ready-to-paste prompts:

```text
| F2 | IPAM | /speckit.specify IPAM: prefixes and pools for the fabric |
| F3 | Firewall | /speckit.specify Firewall policy on top of F1 and F2 |
```
"""

F1_ROWS = """\
| F1 | LocationSite | site_code | name (stated) | Rack (many) | Infrahub | DC team | answer Q4 |
| F1 | DcimDevice | hostname | role (stated) | Interface (many) | Infrahub | DC team | answer Q6 |
"""

F1_VARIANT_ROWS = """\
| `F1` | LocationSite | site_code | name (stated) | Rack (many) | Infrahub | DC team | answer Q4 |
| F1 (fabric) | DcimDevice | hostname | role (stated) | Interface (many) | Infrahub | DC team | answer Q6 |
"""

ALL_ROWS = F1_ROWS + """\
| F1 | IpamPrefix | prefix | status (stated) | VRF (one) | Infrahub | Network team | answer Q8 |
| F1 | SecurityRule | name | action (stated) | Zone (two) | Infrahub | Security | answer Q9 |
"""


@pytest.mark.parametrize(
    ("text", "should_pass"),
    [
        pytest.param(brief(features=FEATURES, sketch_rows=F1_ROWS), True, id="compliant"),
        pytest.param(brief(features=FEATURES_VARIANT, sketch_rows=F1_VARIANT_ROWS), True, id="compliant-variant"),
        pytest.param(brief(features=None, sketch_rows=ALL_ROWS), False, id="violating-no-split"),
        pytest.param(
            brief(
                features=FEATURES,
                sketch_rows=F1_ROWS + "| F2 | IpamPrefix | prefix | status (stated) | VRF (one) | Infrahub | Network team | answer Q8 |\n",
            ),
            False, id="near-miss-f2-sketched",
        ),
        pytest.param(
            brief(features=FEATURES.replace("| F1, F2 | planned |", "| | planned |"), sketch_rows=F1_ROWS),
            False, id="near-miss-empty-depends-on",
        ),
        pytest.param(
            brief(features=FEATURES.replace("| schema, generator |", "| generator, schema |"), sketch_rows=F1_ROWS),
            False, id="near-miss-generator-before-schema",
        ),
        pytest.param(
            brief(features=FEATURES.replace("| schema, check, transform |", "| schema, python |"), sketch_rows=F1_ROWS),
            False, id="near-miss-unroutable-artifact",
        ),
    ],
)
def test_scope_split(tmp_path: Path, text: str, should_pass: bool) -> None:
    write(tmp_path, BRIEF, text)
    result = run_grader("check_scope_split.py", tmp_path)
    assert (result["score"] == 1.0) is should_pass, result["details"]


# --------------------------------------------------------------------------
# brief-sketch-rows-complete
# --------------------------------------------------------------------------

WIFI_ROWS = """\
| F1 | WirelessAccessPoint | serial number | model (imported) | Controller (one) | Controller export | Campus network | answer Q3 |
| F1 | WirelessSsid | name | vlan (pool) | AccessPoint (many) | Infrahub | open: O1 | answer Q5 |
"""

WIFI_OPEN = "- O1: Who owns SSID definitions? (owner: unknown)\n"

WIFI_VARIANT_ROWS = """\
| F1 | WirelessController | hostname | version (imported) | AccessPoint (many) | open: O1 | Campus network | answer Q2 |
| F1 | WirelessSsid | name | vlan (pool) | AccessPoint (many) | Infrahub | `open: O2` | answer Q5 |
"""

WIFI_VARIANT_OPEN = """\
1. **O1**: Is the controller or Infrahub authoritative for firmware versions? (owner: campus team)
2. **O2**: Who owns SSID definitions? (owner: unknown)
"""


@pytest.mark.parametrize(
    ("text", "should_pass"),
    [
        pytest.param(brief(sketch_rows=WIFI_ROWS, open_items=WIFI_OPEN), True, id="compliant"),
        pytest.param(brief(sketch_rows=WIFI_VARIANT_ROWS, open_items=WIFI_VARIANT_OPEN), True, id="compliant-variant"),
        pytest.param(
            brief(sketch_rows=WIFI_ROWS.replace("open: O1", "NetOps"), open_items="none\n"),
            False, id="violating-invented-owner",
        ),
        pytest.param(
            brief(sketch_rows=WIFI_ROWS.replace("open: O1", "TBD"), open_items=WIFI_OPEN),
            False, id="near-miss-tbd",
        ),
        pytest.param(
            brief(sketch_rows=WIFI_ROWS.replace("open: O1", "open: O3"), open_items=WIFI_OPEN),
            False, id="near-miss-dangling-reference",
        ),
    ],
)
def test_sketch_rows_complete(tmp_path: Path, text: str, should_pass: bool) -> None:
    write(tmp_path, BRIEF, text)
    result = run_grader("check_sketch_rows_complete.py", tmp_path)
    assert (result["score"] == 1.0) is should_pass, result["details"]


# --------------------------------------------------------------------------
# brief-decision-provenance
# --------------------------------------------------------------------------

CIRCUIT_ROWS = """\
| F1 | CircuitCircuit | carrier circuit ID | bandwidth (stated) | Provider (one) | Carrier portal | Transport team | answer Q2 |
"""

CIRCUIT_DECISIONS = """\
| # | Decision | Tag | Basis |
| --- | --- | --- | --- |
| 1 | Circuits are identified by the carrier's circuit ID | stated | |
| 2 | Providers are a separate node kind | stated | |
| 3 | Bandwidth is entered by the requester | stated | |
| 4 | Circuit endpoints use a generic for sites and PoPs | recommended | Both endpoint kinds share address and code (medium) |
| 5 | Contract end dates are imported, not typed | recommended | Your carrier export has the dates (strong) |
"""

CIRCUIT_DECISIONS_VARIANT = """\
| # | Decision | Tag | Basis |
|---|---|---|---|
| 5 | Contract end dates are imported | `recommended` | [carriers.xlsx](carriers.xlsx) has an end_date column (strong) |
| 1 | Circuits are identified by the carrier's circuit ID | Stated | |
| 6 | Who approves new carriers | open | |
| 4 | Endpoints use a generic | recommended | Sites and PoPs share address and code (medium) |
"""


@pytest.mark.parametrize(
    ("text", "should_pass"),
    [
        pytest.param(brief(sketch_rows=CIRCUIT_ROWS, decisions=CIRCUIT_DECISIONS), True, id="compliant"),
        pytest.param(brief(sketch_rows=CIRCUIT_ROWS, decisions=CIRCUIT_DECISIONS_VARIANT), True, id="compliant-variant"),
        pytest.param(brief(sketch_rows=CIRCUIT_ROWS, decisions=None), False, id="violating-no-log"),
        pytest.param(
            brief(sketch_rows=CIRCUIT_ROWS, decisions=CIRCUIT_DECISIONS.replace("| recommended |", "| stated |")),
            False, id="violating-all-stated",
        ),
        pytest.param(
            brief(
                sketch_rows=CIRCUIT_ROWS,
                decisions=CIRCUIT_DECISIONS.replace("Your carrier export has the dates (strong)", ""),
            ),
            False, id="near-miss-empty-basis",
        ),
        pytest.param(
            brief(sketch_rows=CIRCUIT_ROWS, decisions=CIRCUIT_DECISIONS.replace("| 3 | Bandwidth is entered by the requester | stated |", "| 3 | Bandwidth is entered by the requester | agreed |")),
            False, id="near-miss-invented-tag",
        ),
    ],
)
def test_decision_provenance(tmp_path: Path, text: str, should_pass: bool) -> None:
    write(tmp_path, BRIEF, text)
    result = run_grader("check_decision_provenance.py", tmp_path)
    assert (result["score"] == 1.0) is should_pass, result["details"]


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------


def test_two_briefs_fail(tmp_path: Path) -> None:
    """A session writes one brief; two leave the hook unable to choose."""
    text = brief(sketch_rows=WIFI_ROWS, open_items=WIFI_OPEN)
    write(tmp_path, BRIEF, text)
    write(tmp_path, SPEC_KIT_BRIEF, text)
    result = run_grader("check_sketch_rows_complete.py", tmp_path)
    assert result["score"] == 0.0, result["details"]


@pytest.mark.parametrize("script", sorted(p.name for p in GRADER_DIR.glob("check_*.py")))
def test_empty_workspace_scores_zero(tmp_path: Path, script: str) -> None:
    assert run_grader(script, tmp_path)["score"] == 0.0


def test_every_grader_has_a_task() -> None:
    """A task grader with no eval.yaml task is dead coverage (#147)."""
    tasks = yaml.safe_load(EVAL_YAML.read_text())["tasks"]
    runs = " ".join(g.get("run", "") for t in tasks for g in t.get("graders", []))
    for script in GRADER_DIR.glob("check_*.py"):
        assert f"graders/designing-models/{script.name}" in runs, script.name


SINGLE_FEATURE = """\
| ID | Feature | Intent | Scope boundary | Artifacts | Depends on | Status | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Campus wireless | Guests stay off staff VLANs | AccessPoint, Controller, Ssid | schema | - | planned | |
"""


@pytest.mark.parametrize(
    ("features", "should_pass"),
    [
        pytest.param(SINGLE_FEATURE, True, id="single-feature-table"),
        pytest.param(None, False, id="no-features-section"),
    ],
)
def test_features_table_always_present(tmp_path: Path, features: str | None, should_pass: bool) -> None:
    """A brief with one feature still carries the table the hook reads."""
    sys.path.insert(0, str(GRADER_DIR))
    from lib import check_features_artifacts  # noqa: PLC0415

    write(tmp_path, BRIEF, brief(features=features, sketch_rows=WIFI_ROWS, open_items=WIFI_OPEN))
    passed, message = check_features_artifacts(tmp_path)
    assert passed is should_pass, message
