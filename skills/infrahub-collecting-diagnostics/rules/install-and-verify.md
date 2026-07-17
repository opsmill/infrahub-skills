---
title: Verify the binary before assuming it's installed
impact: HIGH
tags: install, verify, binary
---

## Verify the binary before assuming it's installed

Impact: HIGH

Always check whether `infrahub-collect` is already
on the user's `PATH` before walking them through an
install. Only install if the check fails.

### Why it matters

Users who already have the tool installed (e.g.
provided by their platform team) don't need to
re-download it, and re-running the install steps
unprompted wastes their time and can overwrite a
pinned version. Checking first also surfaces the
installed version up front, which is useful context
for the expert reviewing the bundle later.

### What to do

Run the version check first:

```bash
infrahub-collect version
```

If the command is not found, install it for the
user's OS/architecture:

```bash
curl https://infrahub.opsmill.io/ops/$(uname -s)/$(uname -m)/infrahub-collect -o infrahub-collect
chmod +x infrahub-collect
sudo mv infrahub-collect /usr/local/bin/   # optional, if the user wants it on PATH
```

The URL path segments are `$(uname -s)` /
`$(uname -m)`, which resolve to one of
`Linux/x86_64`, `Linux/aarch64`, `Darwin/x86_64`, or
`Darwin/arm64`. If the user is on an unsupported
platform, building from source needs Go 1.25+.

Confirm the install succeeded:

```bash
infrahub-collect version
```

or `infrahub-collect --help` if `version` isn't
available in an older build.

**Airgapped environments.** The `curl` step needs
outbound network access to `infrahub.opsmill.io`. If
the user's network blocks this, they need to obtain
the binary through their own channel (internal
mirror, artifact repository, manual transfer) before
continuing — don't fall back to hand-rolling the
collection with `docker`/`kubectl` commands instead.

### Compliant

```text
$ infrahub-collect version
infrahub-collect version 0.3.1
```

or, when missing:

```text
$ infrahub-collect version
command not found: infrahub-collect
$ curl https://infrahub.opsmill.io/ops/Darwin/arm64/infrahub-collect -o infrahub-collect
$ chmod +x infrahub-collect
$ sudo mv infrahub-collect /usr/local/bin/
$ infrahub-collect version
infrahub-collect version 0.3.1
```

### Non-compliant

```text
$ curl https://infrahub.opsmill.io/ops/Darwin/arm64/infrahub-collect -o infrahub-collect
```

Installing without first checking whether the binary
is already present and on `PATH`.

### Common mistakes

- Assuming the binary exists (or assuming it's
  missing) without running `infrahub-collect
  version` first.
- Guessing the OS/arch URL segment instead of using
  `$(uname -s)`/`$(uname -m)` — a typo silently
  404s.
- Treating a blocked `curl` as a dead end and
  hand-rolling `docker`/`kubectl` collection instead
  of asking the user to fetch the binary through
  their own channel.

Reference: [Install infrahub-collect](https://docs.infrahub.app/backup/guides/install-collect)
