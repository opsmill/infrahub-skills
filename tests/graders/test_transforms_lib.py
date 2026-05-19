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
