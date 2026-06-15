"""Tests for graders/managing-transforms/lib.py helpers."""

import ast
import importlib.util
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "managing-transforms" / "lib.py"
_spec = importlib.util.spec_from_file_location(
    "managing_transforms_graders_lib", _LIB_PATH
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


find_inline_fragments = _mod.find_inline_fragments
block_for_relationship = _mod.block_for_relationship
field_appears_directly_under_union = _mod.field_appears_directly_under_union
has_post_to_artifact_generate = _mod.has_post_to_artifact_generate
has_loop_construct = _mod.has_loop_construct
references_core_artifact_in_call = _mod.references_core_artifact_in_call


# -- find_inline_fragments -------------------------------------------------


def test_find_inline_fragments_basic():
    gql = """
query {
  DcimDevice {
    edges {
      node {
        location {
          node {
            ... on LocationSite { name { value } }
            ... on LocationBuilding { name { value } }
          }
        }
      }
    }
  }
}
"""
    fragments = find_inline_fragments(gql)
    assert "LocationSite" in fragments
    assert "LocationBuilding" in fragments


def test_find_inline_fragments_empty():
    assert find_inline_fragments("") == []
    assert find_inline_fragments("query { foo { bar } }") == []


# -- block_for_relationship -----------------------------------------------


def test_block_for_relationship_extracts_braced_block():
    gql = """
query {
  DcimDevice {
    edges {
      node {
        location { node { name { value } } }
      }
    }
  }
}
"""
    block = block_for_relationship(gql, "location")
    assert block is not None
    assert "node" in block
    assert "name" in block


def test_block_for_relationship_missing_returns_none():
    gql = "query { DcimDevice { edges { node { name { value } } } } }"
    assert block_for_relationship(gql, "location") is None


# -- field_appears_directly_under_union -----------------------------------


def test_field_directly_under_union_detects_bug():
    bug_gql = """
query {
  DcimDevice {
    edges {
      node {
        location { node { name { value } shortname { value } } }
      }
    }
  }
}
"""
    assert field_appears_directly_under_union(bug_gql, "location", "name") is True
    assert field_appears_directly_under_union(bug_gql, "location", "shortname") is True


def test_field_directly_under_union_passes_with_fragments():
    good_gql = """
query {
  DcimDevice {
    edges {
      node {
        location {
          node {
            ... on LocationSite { name { value } shortname { value } }
            ... on LocationBuilding { name { value } }
          }
        }
      }
    }
  }
}
"""
    # name is inside a fragment, not directly under location > node
    assert field_appears_directly_under_union(good_gql, "location", "name") is False


def test_field_directly_under_union_missing_relationship():
    gql = "query { DcimDevice { edges { node { name { value } } } } }"
    assert field_appears_directly_under_union(gql, "location", "name") is False


# -- has_post_to_artifact_generate ----------------------------------------


def test_has_post_to_artifact_generate_httpx():
    tree = ast.parse(
        "import httpx\n"
        "r = httpx.post('https://infrahub/api/artifact/generate/abc?branch=main')\n"
    )
    assert has_post_to_artifact_generate(tree) is True


def test_has_post_to_artifact_generate_requests():
    tree = ast.parse(
        "import requests\n"
        "r = requests.post(f'/api/artifact/generate/{def_id}?branch={br}')\n"
    )
    assert has_post_to_artifact_generate(tree) is True


def test_has_post_to_artifact_generate_self_client():
    tree = ast.parse(
        "async def f(self):\n"
        "    await self.client.post('/api/artifact/generate/xyz?branch=dev')\n"
    )
    assert has_post_to_artifact_generate(tree) is True


def test_has_post_to_artifact_generate_no_match():
    tree = ast.parse("import httpx\nr = httpx.post('/api/other')\n")
    assert has_post_to_artifact_generate(tree) is False


def test_has_post_to_artifact_generate_url_in_variable():
    """Fallback path: URL stored in a variable + a .post() call elsewhere.

    The strict AST helper can't reassemble the path through a Name node,
    but the fallback (py_raw text + any .post call) accepts it. This is
    a realistic pattern produced by capable LLMs.
    """
    src = (
        "async def regenerate(client, def_id, branch):\n"
        "    endpoint = f'/api/artifact/generate/{def_id}?branch={branch}'\n"
        "    await client.post(endpoint)\n"
    )
    tree = ast.parse(src)
    # Without py_raw fallback, this fails (URL is a Name, not a Constant)
    assert has_post_to_artifact_generate(tree) is False
    # With py_raw, the fallback fires
    assert has_post_to_artifact_generate(tree, src) is True


def test_has_post_to_artifact_generate_fallback_rejects_without_post():
    """The fallback requires SOME .post() call — text alone isn't enough."""
    src = (
        "URL_TEMPLATE = '/api/artifact/generate/{}'\n"
        "# never actually POSTs\n"
    )
    tree = ast.parse(src)
    assert has_post_to_artifact_generate(tree, src) is False


def test_has_post_to_artifact_generate_sdk_private_post():
    """infrahub_sdk's private ``client._post(...)`` helper is matched."""
    src = (
        "async def regen(client, def_id, branch):\n"
        "    url = f'{client.address}/api/artifact/generate/{def_id}'\n"
        "    await client._post(url=url, payload={}, params={'branch': branch})\n"
    )
    tree = ast.parse(src)
    # Via fallback (url is a Name, not literal in the post call)
    assert has_post_to_artifact_generate(tree, src) is True


def test_has_post_to_artifact_generate_sdk_private_post_literal_url():
    """``client._post(url="/api/artifact/generate/...")`` direct AST match."""
    src = (
        "async def regen(client):\n"
        "    await client._post(url='/api/artifact/generate/abc?branch=main')\n"
    )
    tree = ast.parse(src)
    assert has_post_to_artifact_generate(tree) is True


# -- has_loop_construct ---------------------------------------------------


def test_has_loop_construct_while():
    tree = ast.parse("while True:\n    pass\n")
    assert has_loop_construct(tree) is True


def test_has_loop_construct_for():
    tree = ast.parse("for i in range(10):\n    pass\n")
    assert has_loop_construct(tree) is True


def test_has_loop_construct_async_for():
    tree = ast.parse(
        "async def f():\n"
        "    async for x in stream():\n"
        "        pass\n"
    )
    assert has_loop_construct(tree) is True


def test_has_loop_construct_none():
    tree = ast.parse("x = 1\ny = 2\n")
    assert has_loop_construct(tree) is False


# -- references_core_artifact_in_call -------------------------------------


def test_references_core_artifact_filters_call():
    tree = ast.parse(
        "x = client.filters(kind='CoreArtifact', definition__ids=[def_id])\n"
    )
    assert references_core_artifact_in_call(tree) is True


def test_references_core_artifact_get_call():
    tree = ast.parse("x = client.get(kind='CoreArtifact', id=art_id)\n")
    assert references_core_artifact_in_call(tree) is True


def test_references_core_artifact_no_match():
    tree = ast.parse("x = client.filters(kind='CoreNode')\n")
    assert references_core_artifact_in_call(tree) is False


# -- Task 3: union-fragment checks ----------------------------------------


SRC_BUG_QUERY = """
query {
  DcimDevice {
    edges {
      node {
        location { node { name { value } shortname { value } } }
      }
    }
  }
}
"""

SRC_GOOD_QUERY = """
query {
  DcimDevice {
    edges {
      node {
        location {
          node {
            ... on LocationSite { name { value } shortname { value } }
            ... on LocationBuilding { name { value } }
          }
        }
      }
    }
  }
}
"""


def test_query_uses_inline_fragments_for_location_passes_on_good():
    ok, msg = _mod.CHECKS["query-uses-inline-fragments-for-location"](
        gql_text=SRC_GOOD_QUERY, tree=None, py_raw=""
    )
    assert ok, msg


def test_query_uses_inline_fragments_for_location_fails_on_bug():
    ok, msg = _mod.CHECKS["query-uses-inline-fragments-for-location"](
        gql_text=SRC_BUG_QUERY, tree=None, py_raw=""
    )
    assert not ok


def test_query_no_direct_field_on_union_location_passes_on_good():
    ok, msg = _mod.CHECKS["query-no-direct-field-on-union-location"](
        gql_text=SRC_GOOD_QUERY, tree=None, py_raw=""
    )
    assert ok, msg


def test_query_no_direct_field_on_union_location_fails_on_bug():
    ok, msg = _mod.CHECKS["query-no-direct-field-on-union-location"](
        gql_text=SRC_BUG_QUERY, tree=None, py_raw=""
    )
    assert not ok
    assert "name" in msg or "shortname" in msg


# -- Task 4: artifact regen polling checks --------------------------------


SRC_GOOD_POLLING = """
import asyncio


async def regen_and_wait(client, def_id, expected_count, branch):
    await client.post(f"/api/artifact/generate/{def_id}?branch={branch}")
    deadline = asyncio.get_event_loop().time() + 60
    while asyncio.get_event_loop().time() < deadline:
        artifacts = await client.filters(
            kind="CoreArtifact", definition__ids=[def_id], branch=branch,
        )
        if len(artifacts) >= expected_count:
            return artifacts
        await asyncio.sleep(2)
    raise TimeoutError("regen did not converge")
"""

SRC_BAD_FIRE_AND_FORGET = """
async def regenerate(client, def_id, branch):
    await client.post(f"/api/artifact/generate/{def_id}?branch={branch}")
    return "regenerated"
"""

SRC_BAD_NO_POST = """
async def maybe_regen(client, def_id):
    artifacts = await client.filters(kind="CoreArtifact", definition__ids=[def_id])
    return artifacts
"""


def test_posts_artifact_generate_passes_on_good():
    tree = ast.parse(SRC_GOOD_POLLING)
    ok, msg = _mod.CHECKS["posts-artifact-generate-endpoint"](
        gql_text="", tree=tree, py_raw=SRC_GOOD_POLLING
    )
    assert ok, msg


def test_posts_artifact_generate_fails_when_missing():
    tree = ast.parse(SRC_BAD_NO_POST)
    ok, msg = _mod.CHECKS["posts-artifact-generate-endpoint"](
        gql_text="", tree=tree, py_raw=SRC_BAD_NO_POST
    )
    assert not ok


def test_has_polling_loop_passes_on_good():
    tree = ast.parse(SRC_GOOD_POLLING)
    ok, msg = _mod.CHECKS["has-polling-loop"](
        gql_text="", tree=tree, py_raw=SRC_GOOD_POLLING
    )
    assert ok, msg


def test_has_polling_loop_fails_on_fire_and_forget():
    tree = ast.parse(SRC_BAD_FIRE_AND_FORGET)
    ok, msg = _mod.CHECKS["has-polling-loop"](
        gql_text="", tree=tree, py_raw=SRC_BAD_FIRE_AND_FORGET
    )
    assert not ok


def test_polls_coreartifact_passes_on_good():
    tree = ast.parse(SRC_GOOD_POLLING)
    ok, msg = _mod.CHECKS["polls-coreartifact-after-post"](
        gql_text="", tree=tree, py_raw=SRC_GOOD_POLLING
    )
    assert ok, msg


def test_polls_coreartifact_fails_on_fire_and_forget():
    tree = ast.parse(SRC_BAD_FIRE_AND_FORGET)
    ok, msg = _mod.CHECKS["polls-coreartifact-after-post"](
        gql_text="", tree=tree, py_raw=SRC_BAD_FIRE_AND_FORGET
    )
    assert not ok


# -- Task 5: pre-merge GraphQL dry-run checks -----------------------------


PLAN_GOOD_DRY_RUN = """
Before opening the PR, dry-run the changed query against a live schema:

```bash
infrahubctl render device_config --branch ci-check
```

`infrahubctl schema check` and YAML validation pass but don't execute the
query, so a field / union-fragment mismatch only surfaces when CoreRepository
runs it during schema-sync. Render it before merge to catch that.
"""

PLAN_NO_DRY_RUN = """
Run `infrahubctl schema check schemas/` and make sure the YAML is valid,
then open the PR. CI will validate the rest.
"""

PLAN_RENDER_NO_TIMING = """
You can run `infrahubctl render device_config --branch dev` to see the
output whenever you want to inspect it.
"""


def test_dry_run_executes_query_passes_on_render():
    ok, msg = _mod.CHECKS["dry-run-executes-query"](md_text=PLAN_GOOD_DRY_RUN)
    assert ok, msg


def test_dry_run_executes_query_fails_without_live_command():
    ok, _ = _mod.CHECKS["dry-run-executes-query"](md_text=PLAN_NO_DRY_RUN)
    assert not ok


def test_dry_run_executes_query_accepts_check_run():
    ok, _ = _mod.CHECKS["dry-run-executes-query"](
        md_text="Run `infrahubctl check run rack_collision` before merging."
    )
    assert ok


def test_dry_run_before_merge_passes_on_good():
    ok, msg = _mod.CHECKS["dry-run-before-merge"](md_text=PLAN_GOOD_DRY_RUN)
    assert ok, msg


def test_dry_run_before_merge_fails_without_timing():
    ok, _ = _mod.CHECKS["dry-run-before-merge"](md_text=PLAN_RENDER_NO_TIMING)
    assert not ok


def test_dry_run_checks_empty_input_fails():
    assert _mod.CHECKS["dry-run-executes-query"](md_text="")[0] is False
    assert _mod.CHECKS["dry-run-before-merge"](md_text="")[0] is False
