"""Exercise schema introspection examples without contacting an Infrahub server."""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REFERENCES = (
    "skills/infrahub-common/netbox-vs-infrahub.md",
    "skills/infrahub-importing-data/rules/workflow-introspect-first.md",
)


@pytest.mark.parametrize("reference", REFERENCES)
@pytest.mark.parametrize(("curl_status", "jq_status"), [(0, 0), (22, 0), (0, 4)])
def test_schema_fetch_preserves_project_files(
    reference: str, curl_status: int, jq_status: int, tmp_path: Path
) -> None:
    """Keep project files intact and clean responses even when fetch or parsing fails."""
    blocks = re.findall(r"```bash\n(.*?)```", (ROOT / reference).read_text(), re.S)
    block = next(block for block in blocks if "/api/schema?" in block)
    schema = tmp_path / "schema.json"
    schema.write_text("existing project schema\n")
    temporary_files = tmp_path / "temporary"
    temporary_files.mkdir()
    commands = r'''
        infrahubctl() { return 0; }
        curl() {
            while [ "$#" -gt 0 ]; do
                case "$1" in
                    -o) printf '{"nodes": []}\n' > "$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            return "$CURL_STATUS"
        }
        jq() { cat "$2"; return "$JQ_STATUS"; }
    '''
    result = subprocess.run(
        ["bash", "-c", textwrap.dedent(commands) + "\n" + textwrap.dedent(block)],
        cwd=tmp_path,
        env={
            **os.environ,
            "TMPDIR": str(temporary_files),
            "INFRAHUB_ADDRESS": "http://unused.invalid",
            "CURL_STATUS": str(curl_status),
            "JQ_STATUS": str(jq_status),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (curl_status or jq_status), result.stderr
    assert schema.read_text() == "existing project schema\n"
    assert list(temporary_files.iterdir()) == []
    if curl_status:
        assert result.stdout == "", "Do not filter a failed fetch's partial response"
    else:
        assert result.stdout == '{"nodes": []}\n'
