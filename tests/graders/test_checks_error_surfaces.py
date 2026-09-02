"""Tests for the error-surface and shared-module checks in managing-checks.

Two shapes drove these: the eval prompt's own antipattern scoring the task's
most distinctive assertion, and a three-artifact stub scoring 4/4 because
nothing tied the three artifacts to the same package.
"""

import ast
import importlib.util
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "managing_checks_lib", _REPO_ROOT / "graders" / "managing-checks" / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ERROR_SURFACE_CHECKS = (
    ("uses-sdk-execute-graphql", _mod.check_uses_sdk_execute_graphql),
    ("no-status-code-branch", _mod.check_no_status_code_branch),
    ("catches-graphql-error", _mod.check_catches_graphql_error),
    ("separate-local-bounds-branch", _mod.check_separate_local_bounds_branch),
)


def _score(src: str) -> float:
    tree = ast.parse(src)
    passed = sum(
        bool(fn(None, tree=tree, py_raw=src)[0]) for _name, fn in ERROR_SURFACE_CHECKS
    )
    return passed / len(ERROR_SURFACE_CHECKS)


PROMPT_ANTIPATTERN = '''
import httpx

class C:
    async def validate(self, data):
        resp = httpx.post(self.url, json={"query": q})
        if resp.status_code == 200:
            pass
        else:
            self.log_error(message="rejected")
'''

COMPLIANT_SDK = '''
import json
from infrahub_sdk.exceptions import GraphQLError

class C:
    async def validate(self, data):
        try:
            payload = json.loads(self.raw)
        except Exception:
            payload = {}
        vlan = payload.get("vlan", 0)
        if not 1 <= vlan <= 4094:
            self.log_error(message=f"vlan {vlan} out of range")
        try:
            await self.client.execute_graphql(query=q)
        except GraphQLError as exc:
            self.log_error(message=f"rejected: {exc}")
'''

SANCTIONED_RAW_HTTP = '''
import httpx

class C:
    async def validate(self, data):
        vlan = data["vlan"]
        if not 1 <= vlan <= 4094:
            self.log_error(message="out of range")
        payload = httpx.post(self.url, json={"query": q}).json()
        if payload.get("errors"):
            self.log_error(message=str(payload["errors"]))
'''

URLLIB_FOR_A_URL = '''
import urllib.parse
from infrahub_sdk.exceptions import GraphQLError

class C:
    async def validate(self, data):
        url = urllib.parse.urljoin(self.base, "/graphql")
        vlan = data["vlan"]
        if not 1 <= vlan <= 4094:
            self.log_error(message="out of range")
        try:
            await self.client.execute_graphql(query=q, url=url)
        except GraphQLError as exc:
            self.log_error(message=str(exc))
'''


def test_the_prompts_own_antipattern_scores_zero():
    assert _score(PROMPT_ANTIPATTERN) == 0.0


def test_a_bare_log_error_is_not_a_local_bounds_branch():
    ok, _ = _mod.check_separate_local_bounds_branch(
        None,
        tree=ast.parse("class C:\n    def validate(self, data):\n        self.log_error(message='x')\n"),
        py_raw="x",
    )
    assert not ok


CORRECT = [
    pytest.param(COMPLIANT_SDK, id="sdk-plus-an-unrelated-except-Exception"),
    pytest.param(URLLIB_FOR_A_URL, id="urllib-parse-to-build-a-url"),
    pytest.param(SANCTIONED_RAW_HTTP, id="the-rules-own-raw-http-fallback"),
]


@pytest.mark.parametrize("src", CORRECT)
def test_correct_answers_score_full(src):
    """The grader must not forbid what api-error-surfaces.md allows."""
    assert _score(src) == 1.0


# --- shared module -------------------------------------------------------

SHARED_CHECKS = (
    ("shared-module-absolute-import", _mod.check_shared_module_absolute_import),
    ("dockerfile-targets-base-venv", _mod.check_dockerfile_targets_base_venv),
    ("dockerfile-uv-sync-inexact", _mod.check_dockerfile_uv_sync_inexact),
    ("watch-declares-shared-package", _mod.check_watch_declares_shared_package),
)

STUB_DOCKERFILE = """FROM python:3.12
# ENV UV_PROJECT_ENVIRONMENT=/.venv ; uv sync --inexact
RUN pip install .
"""

GOOD_DOCKERFILE = """FROM registry/infrahub-base:1.2
ENV UV_PROJECT_ENVIRONMENT=/.venv
# WRONG: `uv sync` alone wipes the base environment
RUN uv sync --inexact --no-dev --frozen
"""

STUB_CONFIG = yaml.safe_load("""
generator_definitions:
  - name: a
    watch: {files: []}
python_transforms:
  - name: b
    watch: {files: []}
""")

GOOD_CONFIG = yaml.safe_load("""
generator_definitions:
  - name: plan_vlans
    watch:
      files:
        - src/mydomain
""")


def _shared_score(py: str, dockerfile: str, config: dict) -> float:
    tree = ast.parse(py) if py else None
    passed = sum(
        bool(fn(config, tree=tree, py_raw=py, dockerfile_raw=dockerfile)[0])
        for _name, fn in SHARED_CHECKS
    )
    return passed / len(SHARED_CHECKS)


@pytest.mark.parametrize("py", ["import json\n", "import os\n"])
def test_a_stub_implementing_none_of_the_rule_scores_low(py):
    assert _shared_score(py, STUB_DOCKERFILE, STUB_CONFIG) <= 0.25


def test_the_compliant_set_scores_full():
    """The `# WRONG:` comment the rule teaches must not fail the answer."""
    assert _shared_score(
        "from mydomain.allocation import plan\n", GOOD_DOCKERFILE, GOOD_CONFIG
    ) == 1.0


def test_the_import_has_to_name_the_package_the_layout_declares():
    ok, msg = _mod.check_shared_module_absolute_import(
        GOOD_CONFIG,
        tree=ast.parse("import otherpkg\n"),
        py_raw="import otherpkg\n",
        dockerfile_raw=GOOD_DOCKERFILE,
    )
    assert not ok and "mydomain" in msg


def test_a_dockerfile_comment_is_not_an_instruction():
    ok, _ = _mod.check_dockerfile_targets_base_venv(None, dockerfile_raw=STUB_DOCKERFILE)
    assert not ok
    ok, _ = _mod.check_dockerfile_uv_sync_inexact(None, dockerfile_raw=STUB_DOCKERFILE)
    assert not ok
