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
until the expected count materialises, with a hard timeout that
surfaces a warning instead of silently shipping zero artifacts.

### Required shape of a programmatic regen helper

Every function that triggers regen MUST contain all three:

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
   to check whether regen has produced the expected count yet.

If any of the three is missing, you have written the bug. Refer
to "Correct pattern" below.

### Anti-pattern

```python
async def regenerate(client, def_id, branch):
    # WRONG — fire-and-forget; "success" doesn't mean anything finished
    await client.post(f"/api/artifact/generate/{def_id}?branch={branch}")
    return "regenerated"
```

### Correct pattern

```python
import asyncio

POLL_INTERVAL_SECONDS = 2
TIMEOUT_SECONDS = 60


async def regenerate_and_wait(client, def_id, expected_count, branch):
    """Trigger regen, poll until artifact count matches, or warn on timeout."""
    await client.post(f"/api/artifact/generate/{def_id}?branch={branch}")

    deadline = asyncio.get_event_loop().time() + TIMEOUT_SECONDS
    reposted = False
    while asyncio.get_event_loop().time() < deadline:
        artifacts = await client.filters(
            kind="CoreArtifact",
            definition__ids=[def_id],
            branch=branch,
        )
        if len(artifacts) >= expected_count:
            return artifacts
        if not reposted:
            # Re-POST once: covers the read-replica visibility gap
            await client.post(f"/api/artifact/generate/{def_id}?branch={branch}")
            reposted = True
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Artifact regen for {def_id} did not converge "
        f"to {expected_count} within {TIMEOUT_SECONDS}s"
    )
```

### When this matters

- **Catalog/UI pages** that trigger regen on user action — the
  user clicks "deploy" and walks away; silent failure is the
  worst outcome.
- **CI jobs** that gate a deploy on regen success.
- **Orchestrators** that chain generator → regen → assertion.

Manual regen in the Infrahub UI doesn't need this — the UI
polls on its own.

Reference:
[Infrahub artifacts docs](https://docs.infrahub.app)
