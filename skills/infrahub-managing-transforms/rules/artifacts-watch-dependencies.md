---
title: Declare a Transform's Dependencies with watch
impact: HIGH
tags: artifacts, watch, dependencies, regeneration, fingerprint, infrahub-yml
---

## Declare a Transform's Dependencies with `watch`

**Impact:** HIGH

Infrahub computes a **dependency closure** for every
Transformation when the repository is imported, and stores it
on the Transformation. In a proposed change, a changed file
re-renders that Transformation's artifacts only if the file
is inside its closure. `watch.files` in `.infrahub.yml` is
how you declare the dependencies detection does not supply.

Requires Infrahub 1.10 or later.

### Why it matters

Detection differs sharply between the two transform types,
and for Python it is far weaker than it looks:

| Type | Rely on being detected |
| ---- | ---------------------- |
| `python_transforms` | **Only the entry file at `file_path`.** Imports are never followed. Some versions also add every tracked file in the entry point's directory, but that directory listing is being withdrawn ([opsmill/infrahub#9644](https://github.com/opsmill/infrahub/issues/9644)) — never write a `watch` list that leans on it. |
| `jinja2_transforms` | The template plus every template reachable through a **literal** `{% include %}` / `{% import %}` / `{% extends %}`, transitively. |

For a Python transform, treat **every first-party module the
entry point imports as undeclared until you list it** — a
sibling module in the same directory included. Sharing a
directory is not a dependency relationship, and a transform
whose `watch` list relies on it breaks the moment the
directory listing is withdrawn.

Because those imports were never scanned, Infrahub does not
trust the result: for a Python transform with no `watch` key
it folds the commit id into the transform's fingerprint, so
the fingerprint moves on every commit and the artifacts
re-render on every unrelated change in the repository.
Declaring `watch` is what asserts the dependency list is
complete and switches precise regeneration on.

A **Jinja2** closure comes from parsing the template and
following every reference it declares; a reference that could
not be followed already marks the closure incomplete. A
complete Jinja2 closure is trusted by itself, so `watch`
there is only for genuinely undetectable dependencies.

The trade runs both ways, which is why the list has to be
derived from the code rather than guessed:

- **No `watch` on a Python transform** → re-renders on every
  commit. Safe, wasteful, and it buries the useful signal in
  the proposed-change task log.
- **An incomplete `watch`** → silent staleness. The artifact
  keeps its old content, no error is raised anywhere, and the
  pipeline just goes quiet. Worse than the noisy default.
- **An entry matching no Git-tracked file** (typo, gitignored
  path, symlink) → cannot extend the closure but still counts
  as a declaration. The only trace is a warning in the
  repository import log.

Python transforms also back computed attributes, whose
recompute trigger keys purely on the fingerprint with no
file-level backstop — so an under-declared closure there
means the attribute silently keeps a stale value.

### Deriving the list from the code

1. **Start from the entry point** — `file_path` for a Python
   transform, `template_path` for Jinja2 — and read it.
2. **Resolve every import to a repository path** and classify
   it:
   - **Relative** (`from .cabling_plan_query import ...`) →
     a first-party module. **Declare it**; the sibling
     directory does not cover it.
   - **Absolute, resolving to an in-repo package**
     (`from my_package.protocols import ...` where the
     package lives at `src/my_package/`) → **declare it**.
   - **Third-party or stdlib** (`infrahub_sdk`, `yaml`,
     `ipaddress`) → installed dependencies, not tracked
     repository files. Never declare these. A **generated**
     `protocols.py` committed in the repo is first-party and
     does count.
3. **Follow the imports transitively.** A module you declare
   that imports a third one makes that third module a
   dependency of the transform as well.
4. **Grep the code for runtime file access** — `open(...)`,
   `Path(...).read_text()`, `yaml.safe_load(...)`,
   `json.load(...)`, `FileSystemLoader(...)`,
   `importlib.resources`. A path that exists only as a string
   is invisible to detection, and a `.yml` / `.csv` data file
   is as much a dependency as code.
5. **For Jinja2, find non-literal references** —
   `{% include partial_name %}`, `{% extends layout_var %}`.
   Prefer rewriting these as literals so detection handles
   them; where the reference must stay dynamic, declare the
   directory the candidates live in.
6. **Prefer specific paths over directories.** Name the
   modules and data files the transform actually uses. A
   directory entry is legitimate for a package consumed as a
   unit (`src/my_package/`, `templates/partials/`), but every
   edit beneath it re-renders the artifacts — the broader the
   entry, the closer you are back to regenerating on
   everything.
7. **`files: []` only for a genuinely self-contained entry
   point**: no first-party imports, no runtime file reads. It
   is not a placeholder — it asserts there is nothing to
   declare.

### Correct pattern

```yaml
python_transforms:
  # Imports a sibling query model and the shared src/ package.
  # Both are listed: the sibling too, since sharing ./transforms
  # is not something to depend on.
  - name: cabling_plan
    class_name: CablingPlan
    file_path: transforms/cabling_plan.py
    watch:
      files:
        - transforms/cabling_plan_query.py
        - src/my_package/

  # Single-file transform: no first-party imports, nothing read
  # at runtime. The empty list asserts exactly that, and stops
  # the fingerprint folding in the commit id.
  - name: interface_names
    class_name: InterfaceNames
    file_path: transforms/interface_names.py
    watch:
      files: []

  # Renders vendor defaults it loads at runtime, so the data
  # file is a dependency even though no import mentions it.
  - name: vendor_defaults
    class_name: VendorDefaults
    file_path: transforms/vendor_defaults.py
    watch:
      files:
        - transforms/vendor_defaults_query.py
        - data/vendors.yml

jinja2_transforms:
  # Every include is a literal path, so detection follows them
  # all — no watch needed.
  - name: arista_startup_config
    query: device_startup_config
    template_path: templates/startup_config_arista.j2

  # Picks its partial through a variable, which the parser
  # cannot resolve; the directory covers every candidate.
  - name: cisco_startup_config
    query: device_startup_config
    template_path: templates/startup_config_cisco.j2
    watch:
      files:
        - templates/partials/
```

### Anti-patterns

```yaml
python_transforms:
  # WRONG — imports from src/, and no watch at all. Re-renders
  # on every commit; and once the fingerprint is the only
  # regeneration signal, a change under src/ is missed entirely.
  - name: cilium_manifest
    class_name: CiliumManifest
    file_path: transforms/cilium_manifest.py

  # WRONG — bare list. watch is an object whose only key is
  # `files`; this is rejected when the repository is imported.
  - name: cabling_plan
    file_path: transforms/cabling_plan.py
    watch:
      - src/my_package/

  # WRONG — the transform imports `.device_config_query` and
  # `my_package.formatting`, but declares neither. Declaring
  # anything switches off the safe fallback, so this reads as a
  # complete list while missing both real dependencies.
  - name: device_config
    file_path: transforms/device_config.py
    watch:
      files:
        - data/vendors.yml

  # AVOID — a whole-directory entry that happens to contain the
  # dependency. It works, but every unrelated edit under
  # transforms/ re-renders this artifact. Name the modules.
  - name: device_config
    file_path: transforms/device_config.py
    watch:
      files:
        - transforms/
```

### Reviewing an existing `watch`

Existing entries are as worth auditing as missing ones — a
wrong list is trusted exactly as much as a right one. For
each Transformation:

1. **Is `watch` present at all** on every `python_transforms`
   entry? A missing key means re-render-on-every-commit.
2. **Is it the object form**, `watch: {files: [...]}`? A bare
   list or an unknown key under `watch` fails the import
   outright.
3. **Does every entry resolve** to a Git-tracked file or
   directory? Check for typos, gitignored paths, and symlinks
   — these silently contribute nothing.
4. **Is the list complete?** Re-run the derivation above
   against the current code and compare. Two gaps recur:
   imports added after the `watch` block was written, and
   sibling modules left out because they were once covered by
   the directory listing.
5. **Is any entry broader than it needs to be** — a whole
   directory where two named modules would do? Not an error,
   but it costs precision on every commit.
6. **Is `watch` only on the sections that accept it?** On
   `check_definitions` or `artifact_definitions` it fails the
   repository import.

Reference:
[../infrahub-common/infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
