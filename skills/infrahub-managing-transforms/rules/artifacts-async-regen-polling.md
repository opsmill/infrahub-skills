---
title: Programmatic Artifact Regeneration Is Fire-and-Forget
impact: HIGH
tags: artifacts, regenerate, async, polling, CoreArtifact
---

## Programmatic Artifact Regeneration Is Fire-and-Forget

**Impact:** HIGH

``POST /api/artifact/generate/<def-id>?branch=<branch>`` returns
HTTP 200 as soon as the regen request is **queued**, not when
regen is **finished**. The async server-side regen can run
seconds later, and on a busy system can even run before a
recent generator's group-membership write is visible on the
read replica — at which point the regen sees the wrong target
set and silently produces nothing.

Any caller that triggers regen programmatically (catalog page,
CI job, generator orchestration) **must poll** ``CoreArtifact``
until every expected artifact is **body-ready**, with a hard
timeout that surfaces a warning instead of silently shipping
zero artifacts.

Counting nodes is not enough. Infrahub creates the
``CoreArtifact`` node with ``status`` ``Pending`` and no
``storage_id``, then fills both in only once the transform has
rendered and the content is in the object store. A poll that
stops at the count therefore returns artifacts whose content
fetch still 404s.

### Required shape of a programmatic regen helper

Every function that triggers regen MUST contain all four:

1. **A POST** to ``/api/artifact/generate/<def-id>?branch=<branch>``.
   Use whichever HTTP entry point fits — public methods like
   ``client.post(...)``, ``httpx.post(...)``, ``requests.post(...)``,
   ``aiohttp.ClientSession().post(...)``, or the infrahub_sdk's own
   private helper ``client._post(url=..., payload={}, params=...)``.
   The URL must contain the literal string
   ``/api/artifact/generate``.
2. **A loop** (``while``, ``for``, or ``async for``) that waits
   for completion. A function that POSTs and returns is the bug.
3. **A read** of ``CoreArtifact`` inside the loop —
   ``client.filters(kind="CoreArtifact", ...)`` or equivalent —
   to see what regen has produced so far.
4. **An acceptance predicate that requires a body**, not merely
   a node: ``status`` equal to ``"Ready"``, or a present
   ``storage_id``. Push it into the query
   (``status__value="Ready"``) or apply it to the fetched
   artifacts before counting them — either is fine, so long as
   a bodyless artifact cannot satisfy the count.

If any of the four is missing, you have written the bug. Refer
to "Correct pattern" below.

### Anti-pattern

```python
async def regenerate(client, def_id, branch):
    # WRONG — fire-and-forget; "success" doesn't mean anything finished
    await client._post(
        url=f"/api/artifact/generate/{def_id}", payload={}, params={"branch": branch}
    )
    return "regenerated"
```

The second wrong shape does poll, but accepts a bare node:

```python
async def regenerate_and_wait(client, def_id, expected_count, branch):
    await client._post(
        url=f"/api/artifact/generate/{def_id}", payload={}, params={"branch": branch}
    )

    deadline = asyncio.get_event_loop().time() + 60
    while asyncio.get_event_loop().time() < deadline:
        artifacts = await client.filters(
            kind="CoreArtifact", definition__ids=[def_id], branch=branch
        )
        # WRONG — the node exists before its body does, so these
        # artifacts can still 404 on a content fetch
        if len(artifacts) >= expected_count:
            return artifacts
        await asyncio.sleep(2)

    raise TimeoutError(f"Artifact regen for {def_id} timed out")
```

### Correct pattern

```python
import asyncio

POLL_INTERVAL_SECONDS = 2
TIMEOUT_SECONDS = 60


async def regenerate_and_wait(client, def_id, expected_count, branch):
    """Trigger regen, poll until every artifact body is retrievable."""
    await client._post(
        url=f"/api/artifact/generate/{def_id}", payload={}, params={"branch": branch}
    )

    deadline = asyncio.get_event_loop().time() + TIMEOUT_SECONDS
    reposted = False
    while asyncio.get_event_loop().time() < deadline:
        artifacts = await client.filters(
            kind="CoreArtifact",
            definition__ids=[def_id],
            branch=branch,
            # Only artifacts whose rendered body is in storage.
            # Without this the count converges on Pending nodes.
            status__value="Ready",
        )
        if len(artifacts) >= expected_count:
            return artifacts
        if not reposted:
            # Re-POST once: covers the read-replica visibility gap
            await client._post(
                url=f"/api/artifact/generate/{def_id}",
                payload={},
                params={"branch": branch},
            )
            reposted = True
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Artifact regen for {def_id} did not converge to {expected_count} "
        f"retrievable artifacts within {TIMEOUT_SECONDS}s"
    )
```

Filtering in the query is one option. Narrowing the fetched
list works the same way, and suits a caller that wants to log
how many are still pending:

```python
ready = [a for a in artifacts if a.storage_id.value]
if len(ready) >= expected_count:
    return ready
```

### When this matters

- **Catalog/UI pages** that trigger regen on user action — the
  user clicks "deploy" and walks away; silent failure is the
  worst outcome.
- **CI jobs** that gate a deploy on regen success.
- **Orchestrators** that chain generator → regen → assertion.

Manual regen in the Infrahub UI doesn't need this — the UI
polls on its own.

Two separate visibility gaps sit behind the pattern, and each
element covers one. The single re-POST covers the read-replica
gap: a recent group-membership write may not be visible when
regen runs, so the first regen sees the wrong target set. The
readiness predicate covers the other: the ``CoreArtifact`` node
materialises before its rendered body does. Neither fixes the
other.

**Scope.** Readiness catches an artifact that has no body yet.
It does not catch a *stale* body on re-generation: an artifact
that already existed keeps ``status`` ``Ready`` and its previous
``storage_id`` for the whole re-render window. A caller that
must see changed content compares ``checksum`` or ``storage_id``
against the value it read before the POST.

Reference:
[Infrahub artifacts docs](https://docs.infrahub.app)
