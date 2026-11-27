"""Tests for .agents/skills/harvesting-release-notes/scripts/list_releases.py.

The script expands a release spec into the tags to read, one per line as
`<owner/repo> <tag>`, in ascending version order:

    list_releases.py "<spec>" [--releases-json PATH] [--include-prereleases]

A spec is a single release or a `from..to` range, inclusive at both ends.
The repository is inferred from the spec: a bare version or an
`infrahub-v` tag means opsmill/infrahub, an `sdk` prefix means
opsmill/infrahub-sdk-python, an `mcp` prefix means opsmill/infrahub-mcp-server.
`--releases-json` reads `gh release list --json tagName,isPrerelease,publishedAt`
output from a file instead of calling gh, which keeps these tests offline.

The near miss these tests guard is string ordering, which puts 1.10.0 before
1.9.0, and date ordering, which puts infrahub-v1.11.12 after infrahub-v1.12.0b1.
"""

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / ".agents" / "skills" / "harvesting-release-notes" / "scripts" / "list_releases.py"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "list_releases"


def _run(spec: str, data: str, *extra: str) -> subprocess.CompletedProcess:
    if not _SCRIPT.exists():
        pytest.fail(f"{_SCRIPT.relative_to(_REPO_ROOT)} does not exist yet")
    return subprocess.run(
        [sys.executable, "-I", str(_SCRIPT), spec, "--releases-json", str(_FIXTURES / data), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def _lines(spec: str, data: str, *extra: str) -> list[str]:
    result = _run(spec, data, *extra)
    assert result.returncode == 0, result.stderr
    return result.stdout.split("\n")[:-1] if result.stdout.endswith("\n") else result.stdout.splitlines()


def test_orders_by_version_not_by_string():
    assert _lines("1.9.0..1.10.2", "infrahub.json") == [
        "opsmill/infrahub infrahub-v1.9.0",
        "opsmill/infrahub infrahub-v1.9.4",
        "opsmill/infrahub infrahub-v1.10.0",
        "opsmill/infrahub infrahub-v1.10.2",
    ]


def test_orders_by_version_not_by_publish_date():
    # 1.11.12 was published after 1.12.0b1, and still comes before 1.12.0.
    assert _lines("1.11.11..1.12.0", "infrahub.json") == [
        "opsmill/infrahub infrahub-v1.11.11",
        "opsmill/infrahub infrahub-v1.11.12",
        "opsmill/infrahub infrahub-v1.12.0",
    ]


def test_excludes_prereleases_by_default():
    out = _lines("1.11.12..1.12.1", "infrahub.json")
    assert "opsmill/infrahub infrahub-v1.12.0b1" not in out


def test_includes_prereleases_on_request():
    out = _lines("1.11.12..1.12.1", "infrahub.json", "--include-prereleases")
    assert out == [
        "opsmill/infrahub infrahub-v1.11.12",
        "opsmill/infrahub infrahub-v1.12.0b1",
        "opsmill/infrahub infrahub-v1.12.0",
        "opsmill/infrahub infrahub-v1.12.1",
    ]


def test_single_release_returns_that_tag():
    assert _lines("1.12.1", "infrahub.json") == ["opsmill/infrahub infrahub-v1.12.1"]


def test_infrahub_tag_form_in_the_spec():
    assert _lines("infrahub-v1.12.0..infrahub-v1.12.1", "infrahub.json") == [
        "opsmill/infrahub infrahub-v1.12.0",
        "opsmill/infrahub infrahub-v1.12.1",
    ]


def test_sdk_prefix_reads_v_tags():
    assert _lines("sdk 1.23.0..1.24.0", "sdk.json") == [
        "opsmill/infrahub-sdk-python v1.23.0",
        "opsmill/infrahub-sdk-python v1.23.2",
        "opsmill/infrahub-sdk-python v1.24.0",
    ]


def test_mcp_prefix_names_the_mcp_server_repository():
    # The tag shapes match the SDK's, so the SDK fixture stands in.
    out = _lines("mcp 1.22.2..1.22.2", "sdk.json")
    assert out == ["opsmill/infrahub-mcp-server v1.22.2"]


def test_unknown_release_fails_loudly():
    result = _run("1.8.0", "infrahub.json")
    assert result.returncode != 0
    assert "1.8.0" in result.stderr


def test_unparseable_spec_fails_loudly():
    result = _run("latest-ish", "infrahub.json")
    assert result.returncode != 0
    assert result.stderr.strip()


@pytest.mark.parametrize("spec", ["1.12.1..1.11.0", "sdk 1.24.0..1.23.0"])
def test_reversed_range_fails_loudly(spec):
    result = _run(spec, "sdk.json" if spec.startswith("sdk") else "infrahub.json")
    assert result.returncode != 0
    assert "before" in result.stderr


@pytest.mark.parametrize("spec", ["1.11.0..", "..1.12.1"])
def test_range_with_an_empty_end_fails_loudly(spec):
    result = _run(spec, "infrahub.json")
    assert result.returncode != 0
    assert result.stderr.strip()
