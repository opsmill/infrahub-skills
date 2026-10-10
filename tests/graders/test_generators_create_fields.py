"""Tests for check_create_fields_exist_on_kind in graders/managing-generators/lib.py.

``client.create()`` keeps only the keys that name an attribute or relationship
of the kind and drops the rest without an error (issue #193). The check reads
every create() call, resolves its kind and its fields, and compares them with
graders/managing-generators/fixtures/create_fields_interfaces_schema.yml.

These tests guard the check, not the skill's prose. No eval task runs the
check: every task that gives the model the schema also hands it the answer,
so the rule took the carve-out in dev/guidelines/rule-equals-test.md
§ "When no task can score the rule". The check and these fixtures are what a
future task would wire.

The four fixtures under fixtures/managing-generators/create-fields-match-kind/
are the compliant, compliant variant, violating, and violating near-miss
cases. They are `.txt` so ruff does not lint them as part of this package.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "managing-generators"
_FIXTURES = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "managing-generators"
    / "create-fields-match-kind"
)

# Load lib.py by path under a unique name, so it does not collide with every
# other grader's lib.py in sys.modules.
_spec = importlib.util.spec_from_file_location(
    "managing_generators_create_fields_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check = _mod.check_create_fields_exist_on_kind
load_output_py = _mod.load_output_py
CHECKS = _mod.CHECKS


def _run(src: str) -> tuple[bool, str]:
    return check(ast.parse(src))


def _run_file(path: Path) -> tuple[bool, str]:
    tree, _raw = load_output_py(path)
    return check(tree)


def test_check_is_registered():
    assert CHECKS["create-fields-exist-on-kind"] is check


# ---------------------------------------------------------------------------
# The four fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["pass", "pass-variant"])
def test_compliant_fixture_passes(case):
    ok, msg = _run_file(_FIXTURES / f"{case}.txt")
    assert ok, msg


@pytest.mark.parametrize("case", ["fail", "fail-nearmiss"])
def test_violating_fixture_fails_on_the_unknown_field(case):
    ok, msg = _run_file(_FIXTURES / f"{case}.txt")
    assert not ok
    assert "create(DcimVirtualInterface) passes lag" in msg, msg


# ---------------------------------------------------------------------------
# Fails closed
# ---------------------------------------------------------------------------


def test_missing_output_fails(tmp_path):
    ok, _msg = _run_file(tmp_path / "output.py")
    assert not ok


def test_unparseable_output_fails(tmp_path):
    out = tmp_path / "output.py"
    out.write_text(
        "def generate(:\n    self.client.create(kind='DcimVirtualInterface', lag=x)\n"
    )
    ok, _msg = _run_file(out)
    assert not ok


def test_no_create_call_fails():
    ok, msg = _run("async def generate(self):\n    pass\n")
    assert not ok
    assert "no create() call targets DcimPhysicalInterface, DcimVirtualInterface" in msg


def test_skipping_one_kind_fails():
    """An answer that drops the loopback cannot pass by omission."""
    ok, msg = _run(
        "async def generate(self, device, lag):\n"
        "    await self.client.create(kind='DcimPhysicalInterface', name='eth1', device=device, lag=lag)\n"
    )
    assert not ok
    assert "no create() call targets DcimVirtualInterface" in msg


@pytest.mark.parametrize(
    "src, expected",
    [
        pytest.param(
            "async def make(self, kind, device):\n"
            "    await self.client.create(kind=kind, name='lo0', device=device, lag=None)\n",
            "cannot read the kind",
            id="kind-from-parameter",
        ),
        pytest.param(
            "async def generate(self, device):\n"
            "    await self.client.create(kind='DcimVirtualInterface', data=build(device))\n",
            "cannot read the DcimVirtualInterface fields",
            id="data-from-call",
        ),
        pytest.param(
            "async def generate(self, device, extra):\n"
            "    await self.client.create(kind='DcimVirtualInterface', name='lo0', device=device, **extra)\n",
            "cannot read the DcimVirtualInterface fields",
            id="kwargs-splat-from-parameter",
        ),
        pytest.param(
            "async def generate(self, device, key):\n"
            "    payload = {'name': 'lo0', 'device': device}\n"
            "    payload[key] = 1\n"
            "    await self.client.create(kind='DcimVirtualInterface', data=payload)\n",
            "cannot read the DcimVirtualInterface fields",
            id="non-literal-subscript-key",
        ),
    ],
)
def test_unreadable_create_call_fails(src, expected):
    ok, msg = _run(src)
    assert not ok
    assert expected in msg, msg


# ---------------------------------------------------------------------------
# Laundering: the same unknown field reached another way
# ---------------------------------------------------------------------------

_PHYSICAL = "    await self.client.create(kind='DcimPhysicalInterface', name='eth1', device=device, lag=lag)\n"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            "    await self.client.create('DcimVirtualInterface', {'name': 'lo0', 'lag': lag})\n",
            id="positional-data",
        ),
        pytest.param(
            "    base = {'name': 'lo0', 'device': device}\n"
            "    await self.client.create(kind='DcimVirtualInterface', data={**base, 'lag': lag})\n",
            id="dict-unpacking",
        ),
        pytest.param(
            "    payload = dict(name='lo0', device=device)\n"
            "    payload.update(lag=lag)\n"
            "    await self.client.create(kind='DcimVirtualInterface', data=payload)\n",
            id="update-keyword",
        ),
        pytest.param(
            "    payload = {'name': 'lo0'}\n"
            "    payload.setdefault('lag', lag)\n"
            "    await self.client.create(kind='DcimVirtualInterface', data=payload)\n",
            id="setdefault",
        ),
        pytest.param(
            "    extra = {'lag': lag}\n"
            "    await self.client.create(kind='DcimVirtualInterface', name='lo0', **extra)\n",
            id="kwargs-splat",
        ),
        pytest.param(
            "    sdk = self.client\n"
            "    await sdk.create(kind='DcimVirtualInterface', name='lo0', lag=lag)\n",
            id="aliased-client",
        ),
        pytest.param(
            "    kind = 'DcimVirtualInterface'\n"
            "    await self.client.create(kind=kind, name='lo0', lag=lag)\n",
            id="kind-from-local-string",
        ),
        pytest.param(
            "    await self.client.create(protocols.DcimVirtualInterface, name='lo0', lag=lag)\n",
            id="kind-from-module-attribute",
        ),
        pytest.param(
            "    await self.client.create(kind='DcimVirtualInterface', name='lo0', nmae='lo0')\n",
            id="misspelled-attribute",
        ),
    ],
)
def test_unknown_field_reached_another_way_fails(body):
    ok, msg = _run("async def generate(self, device, lag):\n" + _PHYSICAL + body)
    assert not ok
    assert "create(DcimVirtualInterface) passes" in msg, msg


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------


def test_payload_in_another_function_does_not_leak():
    """A ``payload`` that gets ``lag`` in one function is not the one in another."""
    ok, msg = _run(
        "async def physical(self, device, lag):\n"
        "    payload = {'name': 'eth1', 'device': device}\n"
        "    payload['lag'] = lag\n"
        "    await self.client.create(kind='DcimPhysicalInterface', data=payload)\n"
        "\n"
        "async def virtual(self, device):\n"
        "    payload = {'name': 'lo0', 'device': device}\n"
        "    await self.client.create(kind='DcimVirtualInterface', data=payload)\n"
    )
    assert ok, msg


def test_payload_change_after_the_call_does_not_count():
    """A key added to a reused payload after create() is not in that call."""
    ok, msg = _run(
        "async def generate(self, device, lag):\n"
        "    payload = {'name': 'lo0', 'device': device}\n"
        "    await self.client.create(kind='DcimVirtualInterface', data=payload)\n"
        "    payload['lag'] = lag\n"
        "    await self.client.create(kind='DcimPhysicalInterface', data=payload)\n"
        "    payload = {'name': 'eth2', 'device': device, 'lag': lag}\n"
        "    await self.client.create(kind='DcimPhysicalInterface', data=payload)\n"
    )
    assert ok, msg


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            "    payload = {'name': 'lo0', 'device': device}\n"
            "    for _ in range(2):\n"
            "        await self.client.create(kind='DcimVirtualInterface', data=payload)\n"
            "        payload['lag'] = lag\n",
            id="loop-carried-key",
        ),
        pytest.param(
            "    payload = {'name': 'lo0', 'device': device}\n"
            "    while True:\n"
            "        await self.client.create(kind='DcimVirtualInterface', data=payload)\n"
            "        payload = {'name': 'lo1', 'lag': lag}\n",
            id="loop-carried-rebinding",
        ),
        pytest.param(
            "    payload = {'name': 'lo0', 'device': device}\n"
            "    await self.client.create(kind='DcimVirtualInterface', data=payload)\n"
            "    def add_lag():\n"
            "        payload['lag'] = lag\n",
            id="nested-function-key",
        ),
    ],
)
def test_payload_change_that_can_reach_the_call_counts(body):
    """Later lines still count when a loop or a nested function can run them first."""
    ok, msg = _run("async def generate(self, device, lag):\n" + _PHYSICAL + body)
    assert not ok
    assert "create(DcimVirtualInterface) passes lag" in msg, msg


def test_create_params_are_not_fields():
    ok, msg = _run(
        "async def generate(self, device, lag):\n"
        "    await self.client.create(kind='DcimPhysicalInterface', name='eth1', lag=lag, branch='main', timeout=10)\n"
        "    await self.client.create(kind='DcimVirtualInterface', data=None, name='lo0', branch='main')\n"
    )
    assert ok, msg


def test_create_for_a_kind_outside_the_schema_is_ignored():
    ok, msg = _run(
        "async def generate(self, device, lag):\n"
        + _PHYSICAL
        + "    await self.client.create(kind='DcimVirtualInterface', name='lo0', device=device)\n"
        "    await self.client.create(kind='DcimLagInterface', name='po1', device=device, members=[])\n"
    )
    assert ok, msg
