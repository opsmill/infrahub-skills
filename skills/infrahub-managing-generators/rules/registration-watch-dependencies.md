---
title: Declare a Generator's Dependencies with watch
impact: HIGH
tags: registration, watch, dependencies, regeneration, fingerprint, infrahub-yml
---

## Declare a Generator's Dependencies with `watch`

**Impact:** HIGH

Infrahub computes a **dependency closure** for every Generator
when the repository is imported and stores it on the Generator
definition. In a proposed change, a changed file re-runs that
Generator's instances only if the file is inside its closure.
`watch.files` on the `generator_definitions` entry is how you
declare the dependencies detection does not supply.

Requires Infrahub 1.11 or later. A Generator imported before
precise triggering shipped has no stored closure and falls
back to re-running on any file change; it adopts precise
behavior on the next import, with no error either way.

### Why it matters

Generators are Python-only, and for Python the only thing to
rely on being detected is **the entry file at `file_path`**.
Imports are never followed. Some versions also add every
tracked file sitting in the entry point's directory, but that
directory listing is being withdrawn
([opsmill/infrahub#9644](https://github.com/opsmill/infrahub/issues/9644))
— never write a `watch` list that leans on it.

So treat **every first-party module the Generator imports as
undeclared until you list it**, including a relative import of
a sibling module such as its own query model. Sharing a
directory is not a dependency relationship.

Because those imports were never scanned, Infrahub does not
trust the result: with no `watch` key it folds the commit id
into the Generator definition's fingerprint, so the
fingerprint moves on **every commit** and the Generator
re-runs on every unrelated change in the repository.
Declaring `watch` asserts the dependency list is complete and
switches precise triggering on.

Almost every non-trivial Generator imports shared helpers — a
`GeneratorMixin`, a generated `protocols.py`, allocation
utilities — plus its own sibling query model, so a Generator
with nothing declared is the common case rather than the
exception:

- **No `watch`** → re-runs on every commit. Safe, wasteful,
  and slow: unlike an artifact re-render, a Generator run
  writes objects, so every proposed change pays for a full
  create/upsert pass and its tracking cleanup.
- **An incomplete `watch`** → silent staleness. A change to
  the shared helper does not re-run the Generator, the objects
  it should have created or updated never appear, and no error
  is raised. The drift surfaces later as missing data.
- **An entry matching no Git-tracked file** (typo, gitignored
  path, symlink) → cannot extend the closure but still counts
  as a declaration. The only trace is a warning in the
  repository import log.

### Deriving the list from the code

1. **Start from `file_path`** and read the Generator.
2. **Resolve every import to a repository path** and classify
   it:
   - **Relative** (`from .fabric_generator_query import ...`)
     → a first-party module. **Declare it**; being a sibling
     does not cover it.
   - **Absolute, resolving to an in-repo package**
     (`from my_package.generator import GeneratorMixin` where
     the package lives at `src/my_package/`) → **declare it**.
   - **Third-party or stdlib** (`infrahub_sdk`, `logging`,
     `ipaddress`) → installed dependencies, never declared.
     This includes `infrahub_sdk.protocols`; a **generated**
     `protocols.py` committed inside the repo is first-party
     and does count.
3. **Follow the imports transitively.** A module you declare
   that imports a third one makes that third module a
   dependency of the Generator as well.
4. **Grep for runtime file access** — `open(...)`,
   `Path(...).read_text()`, `yaml.safe_load(...)`,
   `json.load(...)`. A path that exists only as a string is
   invisible to detection, and a `.yml` / `.csv` data file is
   as much a dependency as code.
5. **Prefer specific paths over directories.** Name the
   modules the Generator actually uses. A directory entry is
   legitimate for a package consumed as a unit
   (`src/my_package/`), but every edit beneath it re-runs the
   Generator — the broader the entry, the closer you are back
   to running on everything.
6. **`files: []` only for a genuinely self-contained
   Generator**: no first-party imports, no runtime file reads.
   It is not a placeholder — it asserts there is nothing to
   declare.

### Correct pattern

```yaml
generator_definitions:
  # Imports GeneratorMixin and protocols from the shared src/
  # package, plus its own sibling query model. All are listed:
  # the sibling too, since sharing ./generators is not something
  # to depend on.
  - name: generate_fabric
    file_path: generators/generate_fabric.py
    query: generate_fabric
    targets: fabrics
    class_name: FabricGenerator
    parameters:
      fabric_name: name__value
    watch:
      files:
        - generators/fabric_generator_query.py
        - src/my_package/

  # Self-contained: no first-party imports, nothing read at
  # runtime. The empty list asserts exactly that, and stops the
  # fingerprint folding in the commit id.
  - name: generate_rack
    file_path: generators/generate_rack.py
    query: generate_rack
    targets: racks
    class_name: RackGenerator
    parameters:
      rack_name: name__value
    watch:
      files: []
```

### Anti-patterns

```yaml
generator_definitions:
  # WRONG — imports from src/, no watch. Re-runs on every commit
  # now; and once the fingerprint is the only trigger, a change
  # under src/ stops re-running it at all.
  - name: generate_pod
    file_path: generators/generate_pod.py
    query: generate_pod
    targets: pods
    class_name: PodGenerator

  # WRONG — bare list. watch is an object whose only key is
  # `files`; this is rejected when the repository is imported.
  - name: generate_tenant
    file_path: generators/generate_tenant.py
    query: generate_tenant
    targets: tenants
    watch:
      - src/my_package/

  # WRONG — declares the shared package but not the sibling
  # query model the Generator imports. Declaring anything
  # switches off the safe fallback, so this reads as complete
  # while a change to that query model is missed.
  - name: generate_server
    file_path: generators/generate_server.py
    query: generate_server
    targets: server_services
    watch:
      files:
        - src/my_package/

  # AVOID — a whole-directory entry that happens to contain the
  # dependency. It works, but every unrelated edit under
  # generators/ re-runs this Generator. Name the modules.
  - name: generate_server
    file_path: generators/generate_server.py
    query: generate_server
    targets: server_services
    watch:
      files:
        - generators/
```

### Reviewing an existing `watch`

A wrong list is trusted exactly as much as a right one, so
audit the entries that exist, not just the ones that are
missing. For each `generator_definitions` entry:

1. **Is `watch` present at all?** A missing key means
   re-run-on-every-commit.
2. **Is it the object form**, `watch: {files: [...]}`? A bare
   list or an unknown key under `watch` fails the import.
3. **Does every entry resolve** to a Git-tracked file or
   directory? Typos, gitignored paths, and symlinks contribute
   nothing while still counting as a declaration.
4. **Is the list complete?** Re-derive it from the current
   imports and compare. Two gaps recur: an import added after
   the `watch` block was written, and the Generator's own
   sibling query model, left out because it was once covered
   by the directory listing.
5. **Is any entry broader than it needs to be** — a whole
   directory where two named modules would do? Not an error,
   but it costs precision on every commit.
6. **Is `watch` only where it is accepted?** It is valid on
   `generator_definitions`, `python_transforms`, and
   `jinja2_transforms`; on `check_definitions` or
   `artifact_definitions` it fails the repository import.

Reference:
[../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md),
[../infrahub-managing-transforms/rules/artifacts-watch-dependencies.md](../../infrahub-managing-transforms/rules/artifacts-watch-dependencies.md)
