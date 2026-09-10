"""Subprocess tests for the teaching-concepts task graders.

Three things the unit tests over lib.py cannot show:

1. every grader emits well-formed skillgrade JSON and scores an empty
   workspace 0.0;
2. a compliant workspace scores 1.0, so a wrapper wired to a key that
   never passes cannot hide behind an all-zero suite;
3. each wrapper's CHECK_NAMES match the assertion names eval.yaml
   declares for the task that runs it, so a renamed check cannot leave
   the eval reporting an assertion nobody grades.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRADER_DIR = REPO_ROOT / "graders" / "teaching-concepts"
EVAL_YAML = REPO_ROOT / "eval.yaml"

SCRIPTS = [
    "check_probe_first.py",
    "check_structured_lesson.py",
    "check_record_progress.py",
    "check_sandbox_branch.py",
    "check_verified_solution.py",
    "check_learner_authors.py",
    "check_hint_ladder.py",
    "check_own_artifacts.py",
    "check_cite_docs.py",
    "check_graduation.py",
    "check_off_map.py",
    "check_competitor.py",
]


def run_grader(script: str, workspace: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(GRADER_DIR / script), str(workspace)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


# One workspace that satisfies every check at once. Building it is itself
# the point: if two checks ever contradict each other, no lesson session
# can score 1.0 and this fixture stops being constructible.

SCHEMA = """version: "1.0"
nodes:
  - name: Sensor
    namespace: Testbed
    attributes:
      - name: name
        kind: Text
        unique: true
  - name: Zone
    namespace: Testbed
    attributes:
      - name: name
        kind: Text
"""

SCHEMA_LESSON = """# Lesson: schema relationships

## Probe
1. What does a relationship connect?
2. Have you used foreign keys in a database before?

## Explain
A relationship connects two schema nodes. Your `TestbedSensor` points at
`TestbedZone`, and cardinality controls how many peers one object holds.
See https://docs.infrahub.app/schema/overview for the full model.

## Exercise
**Your task:** Add a relationship from `TestbedSensor` to a new
`TestbedRack` node and pick the cardinality you think fits.

## Check
1. What happens if you omit cardinality?

Next step when you are ready: the infrahub-managing-schemas skill does
this work on real projects.
"""

SCHEMA_SOLUTION = """# Solution: schema relationships

## Solution
```yaml
relationships:
  - name: rack
    peer: TestbedRack
    cardinality: one
    kind: Attribute
```

## Verification
Ran `infrahubctl schema check schemas/testbed.yml`: loads cleanly and
the relationship resolves.
"""

SCHEMA_HINTS = """## Hint 1
Look again at what `peer` expects. Is the value you gave it one of your
own node kinds?
"""

# Off-map slug: no row on the concept map, taught through the docs
# fallback, so check_off_map has something to find.
WEBHOOKS_LESSON = """# Lesson: webhooks (off-map)

## Probe
1. Have you wired an outbound webhook before?
2. What would you want Infrahub to notify you about?

## Explain
A webhook posts an event to a URL you own. Your `TestbedSensor` changes
are the kind of event worth sending. This topic is not on my curriculum,
so I looked it up: https://docs.infrahub.app/webhooks/overview.

## Exercise
**Your task:** Sketch the payload you would want when a
`TestbedSensor` changes, and say which field you would key on.

## Check
1. Why is a webhook a poor fit for a synchronous check?

Next step when you are ready: the infrahub-managing-checks skill covers
the synchronous half of this.
"""

WEBHOOKS_SOLUTION = """# Solution: webhooks

## Solution
```json
{"event": "node.updated", "kind": "TestbedSensor", "id": "..."}
```

## Verification
Derived from https://docs.infrahub.app/webhooks/overview, which lists the
event payload fields.
"""

# Comparison lesson: exercises the competitor-mapping check's sourced
# branch.
TRANSFORMS_LESSON = """# Lesson: transforms

## Probe
1. Have you templated a device config before?
2. What format do you need out the other end?

## Explain
In NetBox, config contexts attach JSON data to devices by scope.
**Comparison source:** https://docs.netbox.dev/en/stable/features/context-data/
In Infrahub the same need is met by a transform over your own data, so
your `TestbedSensor` rows render straight into the output.
See https://docs.infrahub.app/transformations/overview for the model.

## Exercise
**Your task:** Describe the output you want for one `TestbedZone` and
which attributes feed it.

## Check
1. Why does the transform read the schema rather than a fixed template?

Next step when you are ready: the infrahub-managing-transforms skill
builds these for real.
"""

TRANSFORMS_SOLUTION = """# Solution: transforms

## Solution
```python
def transform(data):
    return {"zone": data["TestbedZone"]["name"]}
```

## Verification
Ran `infrahubctl transform zone_export` against the sample data in the
repo: rendered without error.
"""

PROGRESS = """| concept | status | last-seen | notes |
|---|---|---|---|
| schema | introduced | 2026-09-10 | first attempt failed, hint 1 given |
| webhooks | introduced | 2026-09-10 | off-map, taught from the docs |
| transforms | introduced | 2026-09-10 | comparison lesson |
"""


@pytest.fixture
def compliant_ws(tmp_path):
    root = tmp_path / ".infrahub-learning"
    for sub in ("lessons", "solutions", "hints"):
        (root / sub).mkdir(parents=True)
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "testbed.yml").write_text(SCHEMA)
    (root / "lessons" / "schema.md").write_text(SCHEMA_LESSON)
    (root / "solutions" / "schema.md").write_text(SCHEMA_SOLUTION)
    (root / "hints" / "schema.md").write_text(SCHEMA_HINTS)
    (root / "lessons" / "webhooks.md").write_text(WEBHOOKS_LESSON)
    (root / "solutions" / "webhooks.md").write_text(WEBHOOKS_SOLUTION)
    (root / "lessons" / "transforms.md").write_text(TRANSFORMS_LESSON)
    (root / "solutions" / "transforms.md").write_text(TRANSFORMS_SOLUTION)
    (root / "progress.md").write_text(PROGRESS)
    return tmp_path


@pytest.mark.parametrize("script", SCRIPTS)
def test_empty_workspace_scores_zero(tmp_path, script):
    result = run_grader(script, tmp_path)
    assert result["score"] == 0.0
    assert result["checks"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_compliant_workspace_scores_one(compliant_ws, script):
    result = run_grader(script, compliant_ws)
    assert result["score"] == 1.0, result["details"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_output_shape(tmp_path, script):
    result = run_grader(script, tmp_path)
    assert set(result) == {"score", "details", "checks"}
    for check in result["checks"]:
        assert set(check) == {"name", "passed", "message"}


def _check_names(script: str) -> list[str]:
    """Read CHECK_NAMES out of the wrapper without importing it."""
    tree = ast.parse((GRADER_DIR / script).read_text())
    for node in tree.body:
        targets = getattr(node, "targets", [])
        if any(getattr(t, "id", None) == "CHECK_NAMES" for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{script} declares no CHECK_NAMES")


def _tasks_running(script: str) -> list[dict]:
    tasks = yaml.safe_load(EVAL_YAML.read_text())["tasks"]
    return [
        task for task in tasks
        if any(script in (g.get("run") or "") for g in task.get("graders", []))
    ]


@pytest.mark.parametrize("script", SCRIPTS)
def test_check_names_match_the_eval_assertions(script):
    """A renamed check must not leave eval.yaml naming an ungraded one."""
    tasks = _tasks_running(script)
    assert tasks, f"no eval.yaml task runs {script}"
    expected = set(_check_names(script))
    for task in tasks:
        declared = {a["name"] for a in task["assertions"]}
        assert declared == expected, (
            f"{task['name']} declares {sorted(declared)}, "
            f"{script} grades {sorted(expected)}"
        )
