---
title: Sharing One Module Across Checks, Generators and Transforms
impact: HIGH
tags: patterns, shared-module, packaging, docker, uv, imports
---

## Sharing One Module Across Checks, Generators and Transforms

Impact: HIGH

A relative import works only inside one artifact
directory. A module used by more than one artifact type
has to be **installed**, not imported relatively, which
means a package plus a custom worker image.

### Why it matters

[patterns-common.md](patterns-common.md) shows
`from .common import get_data` — correct, and it only
works within `checks/`. Nothing in these skills covers
one piece of domain logic called from a check, a
generator and a transform, which is the case where
keeping the three from drifting actually matters.

The relative-import pattern does not span directories,
so it does not address the case at all. Discovering that
is cheap; discovering what to do instead is not. The
answer needs a package layout, a build backend, a
Dockerfile, and three flags whose absence each produces
a differently confusing failure. It is worth carrying as
a documented pattern because every downstream artifact
depends on the answer, so nothing else can be built
until it is settled.

### The pattern

A `src/` layout package in the repository, installed
into the worker image that executes the artifacts, and
imported **absolutely** from every artifact directory.

```text
project/
  pyproject.toml              # builds the package below
  src/
    mydomain/
      __init__.py
      allocation.py           # the shared logic
  checks/
    check_allocation.py       # from mydomain.allocation import plan
  generators/
    build_services.py         # from mydomain.allocation import plan
  transforms/
    render_service.py         # from mydomain.allocation import plan
  Dockerfile                  # derived from the Infrahub image
```

```python
# checks/check_allocation.py
from infrahub_sdk.checks import InfrahubCheck

from mydomain.allocation import plan   # absolute, not relative
```

### The image

```dockerfile
FROM registry.opsmill.io/opsmill/infrahub:1.11.0

# Install into the virtualenv the base image already has.
# Creating a new one leaves the workers running the old interpreter.
ENV UV_PROJECT_ENVIRONMENT=/.venv

WORKDIR /source
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN uv sync --inexact --no-dev --frozen
```

Three flags, and each one matters:

| Flag | Why |
| ---- | --- |
| `UV_PROJECT_ENVIRONMENT=/.venv` | The base image's virtualenv lives at `/.venv` and is already on `PATH`. Without this, `uv` creates its own and nothing you install is visible to the workers |
| `--inexact` | *"Do not remove extraneous packages present in the environment."* Without it, `uv sync` **removes everything not in your lockfile**, which is the entire Infrahub install. The image builds and is destroyed |
| `--no-dev` | Development dependencies pull a second copy of `infrahub-sdk`, which conflicts with the one the base image ships editable |

`uv` and `uvx` are present in the runtime image
deliberately, so a downstream image can install into
`/.venv` without adding a toolchain.

### Two constraints on the package itself

**The base image's Python version bounds yours.** The
image ships a newer interpreter than a project might
otherwise target, so `requires-python` has to admit it or
the build fails on resolution. Check the image rather
than assuming:

```bash
docker run --rm registry.opsmill.io/opsmill/infrahub:1.11.0 python --version
```

**There is no compiler in the runtime image.** The
Dockerfile strips the toolchain after the build stage, so
a shared package with C extensions, or a dependency
without a wheel for that platform, will not build. Keep
the shared module pure Python, or add the toolchain
yourself and accept the image size.

### Guard against losing the package

If the image is rebuilt without the package, the failure
is an `ImportError` deep inside whichever artifact ran
first, which reads as a bug in that artifact. Add a
trivial check that imports one constant, so the failure
names the real cause:

```python
# checks/check_shared_module.py
from infrahub_sdk.checks import InfrahubCheck


class SharedModuleCheck(InfrahubCheck):
    """Fails loudly when the shared package is missing from the worker image."""

    query = "any_cheap_query"

    def validate(self, data: dict) -> None:
        try:
            from mydomain import __version__
        except ImportError as exc:
            self.log_error(
                message=(
                    "The `mydomain` shared package is not installed in the worker "
                    f"image. Rebuild it from the repository Dockerfile. ({exc})"
                )
            )
            return
        self.log_info(message=f"mydomain {__version__} present")
```

Register it globally (no `targets:`) so it runs on every
proposed change.

### Declare the shared package as a dependency

An installed package is invisible to Infrahub's
dependency detection, so a transform or generator that
imports it will not regenerate when it changes. Declare
it under `watch:` on every `python_transforms` and
`generator_definitions` entry that imports it. See
[../../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md).

Note that `check_definitions` accepts no such field, so a
check's dependency on the shared package cannot be
declared today.

### When not to do this

The image is real overhead: a build, a registry, and a
version to keep in step with the Infrahub release. Skip
it when only one artifact type needs the logic — then a
relative import inside that directory is correct and
sufficient. Reach for the package on the *second*
consumer, not in anticipation of one.

### Common mistakes

- Trying to reach across directories with `..` or
  `sys.path` edits. It works locally and fails in the
  worker, which has a different working directory.
- Omitting `--inexact` and destroying the base
  environment.
- Creating a fresh virtualenv instead of targeting
  `/.venv`.
- Shipping dev dependencies and resolving a second SDK.
- Assuming an unchanged shared module means unchanged
  artifacts, without a `watch:` declaration.

Cross-referenced from the generators and transforms
skills, which share this problem exactly.

Reference:
[patterns-common.md](patterns-common.md),
[connectivity-python-environment.md](../../infrahub-common/rules/connectivity-python-environment.md)
