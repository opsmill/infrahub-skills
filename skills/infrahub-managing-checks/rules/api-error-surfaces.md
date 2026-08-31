---
title: How Rejections Surface to Check Code
impact: HIGH
tags: api, errors, graphql, status-code, fail-open
---

## How Rejections Surface to Check Code

Impact: HIGH

A schema-level rejection comes back as **HTTP 200 with
a populated GraphQL `errors` array**, not as an HTTP
error status. Use the SDK's `execute_graphql` and catch
`GraphQLError`; do not branch on a status code.

### Why it matters

This is the worst shape of failure a check can have.
The check is the thing meant to catch the problem, and
it reports green. A check that branches on
`response.status_code` treats a rejection as a success,
so it **fails open**: it passes on exactly the case it
exists to catch, and nothing distinguishes it from a
check that is working.

The server hard-codes `status_code=200` on every
response where the GraphQL document actually executed.
Errors go in the body. A non-200 means the request never
reached execution at all.

| Status | What it means |
| ------ | ------------- |
| **200** | The query ran. **May still carry `errors`.** Attribute-bound violations, constraint violations, unknown fields, permission denials |
| 400 | Malformed request, or batching attempted |
| 404 | Unknown branch |
| 405 | Wrong HTTP method |

### The correct shape: let the SDK raise

`self.client.execute_graphql` already does the right
thing. All of its variants end with:

```python
if "errors" in response:
    raise GraphQLError(errors=response["errors"], query=query, variables=variables)
```

So a check making a follow-up call gets an **exception**,
not a silent pass:

```python
from infrahub_sdk.exceptions import GraphQLError


class VlanBoundsCheck(InfrahubCheck):
    query = "vlan_bounds"

    async def validate(self, data: dict) -> None:
        for edge in data["NetVlan"]["edges"]:
            vlan = edge["node"]
            try:
                await self.client.execute_graphql(
                    query=PROBE_MUTATION,
                    variables={"id": vlan["id"], "vlan_id": vlan["vlan_id"]["value"]},
                    branch_name=self.branch_name,
                )
            except GraphQLError as exc:
                # A rejection. exc.errors is the errors array from the body.
                self.log_error(
                    message=f"{vlan['name']['value']} rejected: {_first(exc.errors)}",
                    object_id=vlan["id"],
                    object_type=vlan["__typename"],
                )


def _first(errors: list) -> str:
    """GraphQL errors are dicts with a `message`; be tolerant of plain strings."""
    if not errors:
        return "no error detail returned"
    first = errors[0]
    return first.get("message", str(first)) if isinstance(first, dict) else str(first)
```

Note that the data passed to `validate()` never has this
problem: `collect_data()` runs the query and unpacks it
before your method is called, so a failing primary query
fails the check before `validate` runs. **The exposure is
follow-up calls the check makes itself.**

### The wrong shape

```python
# WRONG. Fails open: a rejected value takes the success branch.
import httpx

resp = httpx.post(f"{url}/graphql/{branch}", json={"query": q})
if resp.status_code == 200:
    self.log_info(message="value accepted")   # runs even when rejected
else:
    self.log_error(message="value rejected")  # never runs
```

If you must use raw HTTP, the status code tells you
nothing about validity. Read the body:

```python
payload = resp.json()
if payload.get("errors"):
    self.log_error(message=f"rejected: {payload['errors']}")
```

Prefer `self.client`. It carries the branch, the token
and the timeout, and it raises.

### Distinguishing a rejection from a wrong value

A check that has to tell "the server refused this" apart
from "this value is present and wrong" needs both paths,
because only the first raises:

```python
if not _in_bounds(value):
    self.log_error(message=f"{name}: {value} outside the allowed range")
    continue          # a wrong value, locally detectable

try:
    await self.client.execute_graphql(...)
except GraphQLError as exc:
    self.log_error(message=f"{name}: server refused: {_first(exc.errors)}")
```

### Test that the check fails on a known-bad value

A check that fails open cannot be told apart from a
passing check by observation, so a test asserting the
green path is not evidence of anything. Assert the
**red** path:

```yaml
# tests/test_checks.yml
infrahub_tests:
  - resource: Check
    resource_name: vlan_bounds
    tests:
      - name: rejects_a_vlan_id_above_the_bound
        expect: FAIL          # the assertion that matters
        spec:
          kind: check-unit-process
          directory: tests/fixtures/vlan_bounds_bad
```

See
[testing-resource-framework.md](testing-resource-framework.md).

### Common mistakes

- Branching on `status_code` to detect a rejection.
- Catching `Exception` around `execute_graphql` and
  logging it as info, which reintroduces fail-open.
- Assuming a 200 with `"data": null` is success.
- Only testing the passing case.

Reference:
[api-reference.md](api-reference.md),
[../../infrahub-common/graphql-queries.md](../../infrahub-common/graphql-queries.md)
